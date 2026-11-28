#!/usr/bin/env python3
"""M41150/M41160/M41170 FastAPI ledger read proof; disposable PG18 only."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import sys
from urllib.parse import urlsplit
from uuid import UUID, uuid4

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend" / "tests"))

DATABASE = "fr_m40700_disposable_ci"
PORT = 55439
DATABASE_PASSWORD = "only_m41050_disposable_ci"


def require_disposable() -> str:
    expected = {
        "GITHUB_ACTIONS": "true",
        "FRCAIXINHA_CI_ISOLATED": "1",
        "CI_M41050_DISPOSABLE": "1",
        "CI_M41150_DISPOSABLE": "1",
        "CI_M41160_DISPOSABLE": "1",
        "CI_M41170_DISPOSABLE": "1",
        "PIX_REAL": "OFF",
        "PAGAMENTOS_REAIS": "OFF",
        "ATIVACAO_REAL": "OFF",
    }
    if any(os.environ.get(key) != value for key, value in expected.items()):
        raise RuntimeError("M41150_DISPOSABLE_ONLY")
    if any(os.environ.get(key) for key in (
        "DATABASE_URL", "AUTH_DATABASE_URL", "AUTH_VERIFIER_DATABASE_URL",
    )):
        raise RuntimeError("M41150_UNEXPECTED_DATABASE_DSN_PRESENT")

    dsn = os.environ.get("CI_M41150_DATABASE_URL", "")
    try:
        parsed = urlsplit(dsn)
        valid = (
            parsed.scheme == "postgresql"
            and parsed.hostname == "127.0.0.1"
            and parsed.port == PORT
            and parsed.path == "/" + DATABASE
            and parsed.username == "postgres"
            and parsed.password == DATABASE_PASSWORD
            and not parsed.query
            and not parsed.fragment
            and os.environ.get("CI_M41050_DATABASE_URL") == dsn
            and os.environ.get("CI_M40700_DATABASE_URL") == dsn
            and os.environ.get("CI_M41080_DATABASE_URL") == dsn
            and os.environ.get("CI_M41090_DATABASE_URL") == dsn
            and os.environ.get("CI_M41100_DATABASE_URL") == dsn
            and os.environ.get("CI_M41140_DATABASE_URL") == dsn
            and os.environ.get("CI_M41160_DATABASE_URL") == dsn
        )
    except (ValueError, AttributeError, TypeError):
        valid = False
    if not valid:
        raise RuntimeError("M41150_DISPOSABLE_DATABASE_IDENTITY_DENIED")
    return dsn


async def exercise(dsn: str) -> None:
    import asyncpg
    import psycopg
    from fastapi import FastAPI, HTTPException, Request
    from httpx import ASGITransport, AsyncClient

    import m41050_sql_sealed_context_pg18_disposable as fixture
    from m41240_target_signer_disposable import TargetSigner, TargetProofDenied
    from backend.app.dependencies import AuthenticatedSession, get_current_session
    from backend.app.routers import ledger
    import backend.app.m41150_fastapi_rls_context as gateway

    auth_dsn, app_dsn = fixture.connection_dsns(dsn)
    owner = fixture.connect(dsn, autocommit=True)
    signer = None
    identity_authority = None
    try:
        key = owner.execute(
            "SELECT key FROM m40700.verifier_secret WHERE singleton=true"
        ).fetchone()[0]
        if not key:
            raise AssertionError("M41150_FIXTURE_SIGNER_KEY_MISSING")

        challenge_key = bytes(owner.execute(
            "SELECT key FROM m41050.target_challenge_secret WHERE singleton=true"
        ).fetchone()[0])
        signer = TargetSigner(challenge_key=challenge_key)
        del challenge_key
        target_key = signer.take_bootstrap_key()
        assert target_key != key
        owner.execute(
            "INSERT INTO m41050.target_verifier_secret(singleton,key) VALUES(true,%s)",
            (target_key,),
        )
        del target_key
        for dsn_, role in ((auth_dsn, "m40680_auth"), (app_dsn, "m40650_app")):
            with psycopg.connect(dsn_, autocommit=True) as denied:
                denied.execute("SET ROLE " + role)
                try:
                    denied.execute("SELECT key FROM m41050.target_verifier_secret")
                except psycopg.errors.InsufficientPrivilege:
                    pass
                else:
                    raise AssertionError("M41240_TARGET_KEY_VISIBLE")
        print("M41240_DISTINCT_TARGET_KEY_AND_SQL_ACL=PASS")
        # The integrated provider must use the process-credential channel,
        # not the historical pipe or an in-process HMAC fallback.
        import socket
        assert signer._channel.getsockopt(socket.SOL_SOCKET, socket.SO_PASSCRED) == 1
        assert signer._channel.getsockopt(socket.SOL_SOCKET, socket.SO_TYPE) == socket.SOCK_SEQPACKET
        print("M41250_LEDGER_SIGNER_CREDENTIAL_CHANNEL=PASS")
        for dsn_, role in ((auth_dsn, "m40680_auth"), (app_dsn, "m40650_app")):
            with psycopg.connect(dsn_, autocommit=True) as denied:
                denied.execute("SET ROLE " + role)
                try:
                    denied.execute("SELECT key FROM m41050.target_challenge_secret")
                except psycopg.errors.InsufficientPrivilege:
                    pass
                else:
                    raise AssertionError("M41260_CHALLENGE_KEY_VISIBLE")
                if role == "m40650_app":
                    assert denied.execute(
                        "SELECT m41050.read_target_challenge(%s,%s)",
                        ("a"*64, uuid4()),
                    ).fetchone()[0] is None
                else:
                    try:
                        denied.execute("SELECT m41050.read_target_challenge(%s,%s)", ("a"*64, uuid4()))
                    except psycopg.errors.InsufficientPrivilege:
                        pass
                    else:
                        raise AssertionError("M41260_AUTH_CAN_MINT_CHALLENGE")
        print("M41260_SQL_CHALLENGE_ACL_AND_READONLY=PASS")
        for dsn_, role in ((auth_dsn, "m40680_auth"), (app_dsn, "m40650_app")):
            with psycopg.connect(dsn_, autocommit=True) as denied:
                denied.execute("SET ROLE " + role)
                for sql in ("SELECT * FROM m41050.read_target_reservations",
                            "DELETE FROM m41050.read_target_reservations"):
                    try:
                        denied.execute(sql)
                    except psycopg.errors.InsufficientPrivilege:
                        pass
                    else:
                        raise AssertionError("M41290_RESERVATION_TABLE_EXPOSED")
                if role == "m40650_app":
                    try:
                        denied.execute("SELECT m40700.reserve_read_target(%s,%s,%s,%s,%s,%s)",
                                       ("a"*64, uuid4(), 1, "1/2", datetime.now(timezone.utc), "b"*64))
                    except psycopg.errors.InsufficientPrivilege:
                        pass
                    else:
                        raise AssertionError("M41290_APP_CAN_RESERVE")
        print("M41290_RESERVATION_ACL=PASS")

        tenant_a, tenant_b = uuid4(), uuid4()
        admin_id, member_id, admin_b_id = uuid4(), uuid4(), uuid4()
        owner.execute(
            "INSERT INTO m40650.users(id,status,is_master) VALUES (%s,'ACTIVE',false)",
            (admin_id,),
        )
        owner.execute(
            "INSERT INTO m40650.users(id,status,is_master) VALUES (%s,'ACTIVE',false)",
            (member_id,),
        )
        owner.execute(
            "INSERT INTO m40650.users(id,status,is_master) VALUES (%s,'ACTIVE',false)",
            (admin_b_id,),
        )
        for user_id, tenant_id, role in (
            (admin_id, tenant_a, "TENANT_ADMIN"),
            (member_id, tenant_a, "TENANT_MEMBER"),
            (admin_b_id, tenant_b, "TENANT_ADMIN"),
        ):
            owner.execute(
                "INSERT INTO m40650.memberships(user_id,tenant_id,role,status) "
                "VALUES (%s,%s,%s,'ATIVA')",
                (user_id, tenant_id, role),
            )

        _, admin_digest = fixture.create_session(
            owner, admin_id, "TENANT_ADMIN", tenant_a
        )
        _, member_digest = fixture.create_session(
            owner, member_id, "TENANT_MEMBER", tenant_a
        )

        _, admin_b_digest = fixture.create_session(
            owner, admin_b_id, "TENANT_ADMIN", tenant_b
        )

        _, admin_second_digest = fixture.create_session(
            owner, admin_id, "TENANT_ADMIN", tenant_a
        )

        def session_id_for(digest):
            return owner.execute(
                "SELECT id FROM m40650.sessions WHERE token_digest=%s", (digest,)
            ).fetchone()[0]

        admin_session_id = session_id_for(admin_digest)
        admin_second_session_id = session_id_for(admin_second_digest)
        member_session_id = session_id_for(member_digest)
        assert admin_session_id != admin_second_session_id

        account_a_id, account_offset_id = uuid4(), uuid4()
        account_b_id, account_b_offset_id = uuid4(), uuid4()
        owner.execute("""
            CREATE TABLE public.ledger_accounts(
                id uuid PRIMARY KEY,
                tenant_id uuid NOT NULL,
                account_code text NOT NULL,
                account_name text NOT NULL,
                account_type text NOT NULL,
                balance_cents bigint NOT NULL
            )
        """)
        owner.execute(
            "ALTER TABLE public.ledger_accounts OWNER TO m40650_owner"
        )
        owner.execute("""
            INSERT INTO public.ledger_accounts(
                id,tenant_id,account_code,account_name,account_type,balance_cents
            ) VALUES
              (%s,%s,'A-CASH','Caixa A','ASSET',1250),
              (%s,%s,'A-OFFSET','Conta de contrapartida','LIABILITY',1250),
              (%s,%s,'B-CASH','Caixa B','ASSET',9900),
              (%s,%s,'B-OFFSET','Conta de contrapartida B','LIABILITY',9900)
        """, (
            account_a_id, tenant_a, account_offset_id, tenant_a,
            account_b_id, tenant_b, account_b_offset_id, tenant_b,
        ))
        owner.execute("""
            CREATE TABLE public.ledger_transactions(
                id uuid PRIMARY KEY,
                tenant_id uuid NOT NULL,
                transaction_date timestamptz NOT NULL,
                description text NOT NULL,
                reference_id text NOT NULL
            )
        """)
        owner.execute(
            "ALTER TABLE public.ledger_transactions OWNER TO m40650_owner"
        )
        owner.execute("""
            CREATE TABLE public.ledger_entries(
                id uuid PRIMARY KEY,
                tenant_id uuid NOT NULL,
                transaction_id uuid NOT NULL,
                account_id uuid NOT NULL,
                entry_type text NOT NULL,
                amount_cents bigint NOT NULL
            )
        """)
        owner.execute(
            "ALTER TABLE public.ledger_entries OWNER TO m40650_owner"
        )
        for table_name in (
            "ledger_accounts", "ledger_transactions", "ledger_entries",
        ):
            owner.execute(
                f"ALTER TABLE public.{table_name} ENABLE ROW LEVEL SECURITY"
            )
            owner.execute(
                f"ALTER TABLE public.{table_name} FORCE ROW LEVEL SECURITY"
            )
            owner.execute(f"""
                CREATE POLICY m41160_{table_name}_read
                ON public.{table_name}
                FOR SELECT TO m40650_app
                USING (
                  EXISTS (
                    SELECT 1 FROM m41050.current_claims_v4() AS claims
                     WHERE claims.scope_name='READ_ENTRIES'
                       AND claims.role_name='TENANT_ADMIN'
                       AND claims.tenant_id={table_name}.tenant_id
                  )
                )
            """)
            owner.execute(
                f"GRANT SELECT ON public.{table_name} TO m40650_app"
            )
        owner.execute(
            "GRANT EXECUTE ON FUNCTION m41050.current_claims() TO m40650_app"
        )

        def reserve_read(ticket, tenant, pid, vxid, started, challenge):
            with psycopg.connect(auth_dsn, autocommit=True) as auth:
                auth.execute("SET ROLE m40680_auth")
                return auth.execute(
                    "SELECT m40700.reserve_read_target(%s,%s,%s,%s,%s,%s)",
                    (ticket, tenant, pid, vxid, started, challenge),
                ).fetchone()[0] is True

        def bind_read(ticket, tenant, pid, vxid, started, *, challenge, proof=None):
            if proof is None:
                if not reserve_read(ticket, tenant, pid, vxid, started, challenge):
                    return None
                try:
                    proof = signer.sign(ticket, tenant, pid, vxid, started, challenge=challenge)
                except TargetProofDenied:
                    return None
            with psycopg.connect(app_dsn, autocommit=True) as app:
                app.execute("SET ROLE m40650_app")
                return app.execute(
                    "SELECT m41050.bind_read_transaction(%s,%s,%s,%s,%s,%s,%s)",
                    (ticket, tenant, pid, vxid, started, proof, challenge),
                ).fetchone()[0]

        async def set_app_role(connection):
            await connection.execute("SET ROLE m40650_app")

        # connection_dsns() returns a libpq keyword DSN for psycopg;
        # asyncpg needs discrete connection parameters.
        pool = await asyncpg.create_pool(
            host="127.0.0.1",
            port=PORT,
            database=DATABASE,
            user="m40650_ci_login",
            password=fixture.APP_PASSWORD,
            min_size=1,
            max_size=2,
            init=set_app_role,
            command_timeout=5,
        )
        async with pool.acquire() as probe_connection:
            pg_version = int(await probe_connection.fetchval("SHOW server_version_num"))
        if not 180000 <= pg_version < 190000:
            raise RuntimeError("M41150_EXPECTED_POSTGRES18")
        os.environ.setdefault("ENVIRONMENT", "development")

        now = datetime.now(timezone.utc)
        transaction_id, transaction_b_id = uuid4(), uuid4()
        owner.execute(
            "INSERT INTO public.ledger_transactions("
            "id,tenant_id,transaction_date,description,reference_id"
            ") VALUES (%s,%s,%s,%s,%s),(%s,%s,%s,%s,%s)",
            (
                transaction_id, tenant_a, now, "Lancamento teste M41160 A",
                "M41160-TEST-A",
                transaction_b_id, tenant_b, now, "Lancamento teste M41160 B",
                "M41160-TEST-B",
            ),
        )
        owner.execute(
            "INSERT INTO public.ledger_entries("
            "id,tenant_id,transaction_id,account_id,entry_type,amount_cents"
            ") VALUES "
            "(%s,%s,%s,%s,'DR',1250),(%s,%s,%s,%s,'CR',1250),"
            "(%s,%s,%s,%s,'DR',9900),(%s,%s,%s,%s,'CR',9900)",
            (
                uuid4(), tenant_a, transaction_id, account_a_id,
                uuid4(), tenant_a, transaction_id, account_offset_id,
                uuid4(), tenant_b, transaction_b_id, account_b_id,
                uuid4(), tenant_b, transaction_b_id, account_b_offset_id,
            ),
        )

        async with pool.acquire() as connection:
            async with connection.transaction():
                await connection.execute(
                    "SELECT pg_catalog.set_config('app.current_tenant_id',$1,true)",
                    str(tenant_a),
                )
                await connection.execute(
                    "SELECT pg_catalog.set_config('app.current_role',$1,true)",
                    "TENANT_ADMIN",
                )
                await connection.execute(
                    "SELECT pg_catalog.set_config('app.current_user_id',$1,true)",
                    str(admin_id),
                )
                for table_name in (
                    "ledger_accounts", "ledger_transactions", "ledger_entries",
                ):
                    forged = await connection.fetch(
                        f"SELECT id FROM public.{table_name} ORDER BY id"
                    )
                    if forged:
                        raise AssertionError(
                            f"M41160_LEGACY_GUC_FORGED_CONTEXT_VISIBLE_{table_name}"
                        )
        print("M41150_FORGED_LEGACY_GUC_DENIED=PASS")
        print("M41160_FORGED_LEGACY_GUC_DENIED=PASS")

        def make_session(user_id, role, tenant_id, *, session_id=None, verification_source=None):
            return AuthenticatedSession(
                user_id=str(user_id),
                role=role,
                tenant_id=str(tenant_id) if tenant_id is not None else None,
                email="ci@example.invalid",
                name="synthetic",
                is_master=(role == "MASTER"),
                verified_session_id=str(session_id or uuid4()),
                verified_session_at=now - timedelta(seconds=1),
                verified_session_expires_at=now + timedelta(minutes=10),
                verification_source=(
                    verification_source or "POSTGRES_TOKEN_HASH_REFRESH"
                ),
            )

        admin_session = make_session(
            admin_id, "TENANT_ADMIN", tenant_a, session_id=admin_session_id
        )
        admin_second_session = make_session(
            admin_id, "TENANT_ADMIN", tenant_a, session_id=admin_second_session_id
        )
        member_session = make_session(
            member_id, "TENANT_MEMBER", tenant_a, session_id=member_session_id
        )
        master_session = make_session(uuid4(), "MASTER", None)
        unverified_session = make_session(
            admin_id, "TENANT_ADMIN", tenant_a,
            verification_source="LEGACY_NO_SESSION_BINDING",
        )
        sessions = {
            "Bearer m41150-admin": admin_session,
            "Bearer m41200-admin-second": admin_second_session,
            "Bearer m41150-member": member_session,
            "Bearer m41150-master": master_session,
            "Bearer m41150-unverified": unverified_session,
        }

        class FixtureCapabilityProvider:
            def __init__(self):
                self.session_digests = {
                    (str(admin_session_id), str(admin_id), "TENANT_ADMIN", str(tenant_a)): admin_digest,
                    (str(admin_second_session_id), str(admin_id), "TENANT_ADMIN", str(tenant_a)): admin_second_digest,
                    (str(member_session_id), str(member_id), "TENANT_MEMBER", str(tenant_a)): member_digest,
                }
                self.last_ticket = None
                self.last_capability = None
                self.reuse_next = False
                self.override_capability = None
                self.replay_capability = None
                self.override_digest = None
                self.expire_next = False
                self.issue_calls = 0

            async def issue_ticket(self, session, *, scope, request_nonce):
                self.issue_calls += 1
                if scope != "READ_ENTRIES":
                    return None
                if self.reuse_next and self.last_ticket:
                    self.reuse_next = False
                    return self.last_ticket
                digest = self.session_digests.get(
                    (session.verified_session_id, session.user_id, session.role, session.tenant_id)
                )
                if self.override_digest is not None:
                    digest = self.override_digest
                    self.override_digest = None
                if digest is None:
                    return None
                ticket = fixture.issue_ticket(
                    owner, auth_dsn, key, digest, UUID(session.tenant_id),
                    scope=scope, nonce=request_nonce,
                )
                if ticket:
                    self.last_ticket = ticket
                return ticket

            async def bind_ticket(self, ticket, *, tenant_id, backend_pid,
                                  virtual_xid, transaction_started_at, target_challenge):
                capability = bind_read(ticket, tenant_id, backend_pid,
                                       virtual_xid, transaction_started_at, challenge=target_challenge)
                if capability:
                    self.last_capability = capability
                if self.expire_next and capability:
                    self.expire_next = False
                    updated = owner.execute(
                        "UPDATE m41050.session_caps SET expires_at=pg_catalog.clock_timestamp() "
                        "WHERE token_hash=pg_catalog.sha256(pg_catalog.convert_to(%s,'UTF8'))",
                        (capability,),
                    )
                    assert updated.rowcount == 1
                if self.replay_capability is not None:
                    return self.replay_capability
                if self.override_capability is not None:
                    override = self.override_capability
                    self.override_capability = None
                    return override
                return capability

        provider = FixtureCapabilityProvider()
        app = FastAPI()
        app.include_router(ledger.router, prefix="/api/v1")

        async def synthetic_current_session(request):
            raw = request.headers.get("authorization")
            session = sessions.get(raw)
            if session is None:
                raise HTTPException(status_code=401, detail="Unauthorized")
            return session

        # Request is imported locally after preflight; bind its runtime type
        # because postponed annotations cannot resolve exercise-local names.
        synthetic_current_session.__annotations__["request"] = Request

        app.dependency_overrides[get_current_session] = synthetic_current_session
        setattr(app.state, gateway.PROVIDER_STATE_ATTRIBUTE, provider)

        async def fixture_pool():
            return pool

        gateway.get_db_pool = fixture_pool

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://frfinance.test"
        ) as client:
            path_a = f"/api/v1/tenants/{tenant_a}/ledger/accounts/directory"
            accounts_path = f"/api/v1/tenants/{tenant_a}/ledger/accounts"
            transactions_path = f"/api/v1/tenants/{tenant_a}/ledger/transactions"
            integrity_path = f"/api/v1/tenants/{tenant_a}/ledger/integrity-preview"
            entries_path = (
                f"/api/v1/tenants/{tenant_a}/ledger/accounts/"
                f"{account_a_id}/entries"
            )
            keyset_path = entries_path + "/keyset"
            read_paths = [
                path_a, integrity_path, accounts_path, transactions_path,
                entries_path, keyset_path,
            ]

            # With no approved provider, all ledger reads must stop before a pool
            # borrow; a guarded pool makes any legacy GUC fallback fail this test.
            import backend.app.database as database_module

            no_provider_app = FastAPI()
            no_provider_app.include_router(ledger.router, prefix="/api/v1")
            no_provider_app.dependency_overrides[get_current_session] = (
                synthetic_current_session
            )
            database_get_pool = database_module.get_db_pool
            gateway_get_pool = gateway.get_db_pool
            pool_calls = 0

            async def forbidden_pool():
                nonlocal pool_calls
                pool_calls += 1
                raise AssertionError("M41170_DATABASE_POOL_OPENED_WITHOUT_PROVIDER")

            database_module.get_db_pool = forbidden_pool
            gateway.get_db_pool = forbidden_pool
            try:
                async with AsyncClient(
                    transport=ASGITransport(app=no_provider_app),
                    base_url="http://frfinance.test",
                ) as no_provider_client:
                    no_provider_responses = await asyncio.gather(*(
                        no_provider_client.get(
                            path, headers={"Authorization": "Bearer m41150-admin"}
                        )
                        for path in read_paths
                    ))
                if any(response.status_code != 503
                       for response in no_provider_responses):
                    raise AssertionError(
                        "M41170_PROVIDER_ABSENT_ROUTE_STATUS_"
                        + str([r.status_code for r in no_provider_responses])
                    )
            finally:
                database_module.get_db_pool = database_get_pool
                gateway.get_db_pool = gateway_get_pool
            if pool_calls != 0:
                raise AssertionError("M41170_DATABASE_POOL_CALLS_WITHOUT_PROVIDER")
            print("M41170_PROVIDER_ABSENT_FAIL_CLOSED=PASS")
            print("M41170_DATABASE_POOL_CALLS_WITHOUT_PROVIDER=0")

            admin_headers = {"Authorization": "Bearer m41150-admin"}
            responses = await asyncio.gather(*(
                client.get(path, headers=admin_headers) for path in read_paths
            ))
            if any(response.status_code != 200 for response in responses):
                codes = [response.status_code for response in responses]
                raise AssertionError(f"M41160_READ_ROUTE_HTTP_STATUS_{codes}")

            directory_payload = responses[0].json()
            if (len(directory_payload.get("accounts", [])) != 2
                    or [item["account_code"] for item in directory_payload["accounts"]]
                    != ["A-CASH", "A-OFFSET"]
                    or directory_payload.get("balance_values_hidden") is not True
                    or directory_payload.get("financial_closing_authorized") is not False):
                raise AssertionError("M41160_LEDGER_DIRECTORY_SCOPE_OR_SHAPE")
            if len(responses[2].json()) != 2:
                raise AssertionError("M41160_LEDGER_ACCOUNTS_SHAPE")
            tx_payload = responses[3].json()
            if len(tx_payload) != 1 or len(tx_payload[0].get("entries", [])) != 2:
                raise AssertionError("M41160_LEDGER_TRANSACTIONS_SHAPE")
            if len(responses[4].json().get("entries", [])) != 1:
                raise AssertionError("M41160_LEDGER_JOURNAL_PAGE_SHAPE")
            if len(responses[5].json().get("entries", [])) != 1:
                raise AssertionError("M41160_LEDGER_KEYSET_PAGE_SHAPE")
            active_capability = provider.last_capability
            if not active_capability:
                raise AssertionError("M41160_FIXTURE_CAPABILITY_MISSING")
            expected_tenant_rows = {
                "ledger_accounts": 2,
                "ledger_transactions": 1,
                "ledger_entries": 2,
            }
            async with pool.acquire() as connection:
                async with connection.transaction(readonly=True):
                    pid, vxid, started = await gateway._read_transaction_identity(connection)
                    ticket = fixture.issue_ticket(owner, auth_dsn, key, admin_digest, tenant_a)
                    assert ticket
                    challenge = await gateway._read_target_challenge(connection, ticket, tenant_a)
                    direct_cap = bind_read(ticket, tenant_a, pid, vxid, started, challenge=challenge)
                    assert direct_cap
                    await gateway.install_session_capability(connection, direct_cap)
                    for table_name, expected_count in expected_tenant_rows.items():
                        rows = await connection.fetch(
                            f"SELECT tenant_id FROM public.{table_name}"
                        )
                        if (len(rows) != expected_count
                                or any(row["tenant_id"] != tenant_a for row in rows)):
                            raise AssertionError(
                                f"M41160_RLS_TENANT_ISOLATION_{table_name}"
                            )
            # A valid bound capability must die at transaction end, even on
            # the same pooled physical connection or a different connection.
            async with pool.acquire() as first, pool.acquire() as second:
                async with first.transaction(readonly=True):
                    pid, vxid, started = await gateway._read_transaction_identity(first)
                    ticket = fixture.issue_ticket(owner, auth_dsn, key, admin_digest, tenant_a)
                    assert ticket
                    challenge = await gateway._read_target_challenge(first, ticket, tenant_a)
                    assert bind_read(ticket, tenant_a, pid, "0/0", started, challenge=challenge) is None
                    proof = signer.sign(ticket, tenant_a, pid, vxid, started, challenge=challenge)
                    assert bind_read(ticket, tenant_a, pid, vxid, started, challenge=challenge, proof=proof) is None
                    assert reserve_read(ticket, tenant_a, pid, vxid, started, challenge)
                    assert reserve_read(ticket, tenant_a, pid, vxid, started, challenge)
                    print("M41290_UNRESERVED_PROOF_DENIED=PASS")
                    issuer_proof = fixture.sign_read_transaction(key, ticket, tenant_a, pid, vxid, started, challenge=challenge)
                    # Disposable owner constructs a negative legacy-domain proof only.
                    legacy_key = owner.execute('SELECT key FROM m41050.target_verifier_secret WHERE singleton=true').fetchone()[0]
                    legacy_proof = fixture.sign_read_transaction(legacy_key, ticket, tenant_a, pid, vxid, started)
                    assert bind_read(ticket, tenant_a, pid, vxid, started, challenge=challenge, proof=legacy_proof) is None
                    wrong_challenge = '0' * 64 if challenge != '0' * 64 else '1' * 64
                    try:
                        signer.sign(ticket, tenant_a, pid, vxid, started, challenge=wrong_challenge)
                    except TargetProofDenied:
                        pass
                    else:
                        raise AssertionError("M41280_INVALID_CHALLENGE_SIGNED")
                    # Keep the SQL negative test independent of the worker denial.
                    wrong_proof = fixture.sign_read_transaction(legacy_key, ticket, tenant_a, pid, vxid, started, challenge=wrong_challenge)
                    del legacy_key
                    print("M41280_WORKER_AUTHENTICATES_SQL_CHALLENGE=PASS")
                    assert bind_read(ticket, tenant_a, pid, vxid, started, challenge=challenge, proof=wrong_proof) is None
                    assert bind_read(ticket, tenant_a, pid, vxid, started, challenge=wrong_challenge, proof=wrong_proof) is None
                    print('M41270_LEGACY_AND_MIXED_PROOFS_DENIED=PASS')
                    assert bind_read(ticket, tenant_a, pid, vxid, started, challenge=challenge, proof=issuer_proof) is None
                    print("M41240_ISSUER_KEY_CANNOT_BIND_TARGET=PASS")
                    for invalid_challenge in (None, "", "0" * 64, proof):
                        assert bind_read(ticket, tenant_a, pid, vxid, started,
                                         challenge=invalid_challenge, proof=proof) is None
                    # Even the authorized signer cannot invent a different SQL
                    # transaction timestamp without a matching SQL challenge.
                    changed = started + timedelta(microseconds=1)
                    assert bind_read(ticket, tenant_a, pid, vxid, changed,
                                     challenge=challenge) is None
                    assert bind_read(ticket, tenant_b, pid, vxid, started,
                                     challenge=challenge) is None
                    assert await first.fetchval(
                        "SELECT m41050.read_target_challenge($1,$2)", ticket, tenant_a
                    ) == challenge
                    assert bind_read(ticket, tenant_a, pid, vxid, started, challenge=challenge, proof="0" * 64) is None
                    assert bind_read(ticket, tenant_a, pid, vxid, started, challenge=challenge, proof="") is None
                    assert bind_read(ticket, tenant_a, pid, vxid,
                                     started + timedelta(microseconds=1), challenge=challenge, proof=proof) is None
                    other_ticket = fixture.issue_ticket(owner, auth_dsn, key, admin_digest, tenant_a)
                    assert other_ticket
                    assert bind_read(other_ticket, tenant_a, pid, vxid, started, challenge=challenge, proof=proof) is None
                    assert bind_read(ticket, tenant_b, pid, vxid, started, challenge=challenge, proof=proof) is None
                    async with second.transaction(readonly=True):
                        other_pid, other_vxid, other_started = await gateway._read_transaction_identity(second)
                        assert bind_read(ticket, tenant_a, other_pid, other_vxid,
                                         other_started, challenge=challenge, proof=proof) is None
                        # Correct signature for another live target is not enough.
                        assert bind_read(ticket, tenant_a, other_pid, other_vxid,
                                         other_started, challenge=challenge) is None
                        other_challenge = await gateway._read_target_challenge(second, ticket, tenant_a)
                        assert other_challenge != challenge
                        assert bind_read(ticket, tenant_a, other_pid, other_vxid,
                                         other_started, challenge=other_challenge) is None
                        # A valid proof from an independent verifier-key holder
                        # cannot bypass the committed authority reservation.
                        independent_key = owner.execute(
                            "SELECT key FROM m41050.target_verifier_secret WHERE singleton=true"
                        ).fetchone()[0]
                        alternate_proof = fixture.sign_read_transaction(
                            independent_key, ticket, tenant_a, other_pid, other_vxid,
                            other_started, challenge=other_challenge,
                        )
                        del independent_key
                        assert not reserve_read(ticket, tenant_a, other_pid, other_vxid,
                                                other_started, other_challenge)
                        assert bind_read(ticket, tenant_a, other_pid, other_vxid,
                                         other_started, challenge=other_challenge, proof=alternate_proof) is None
                        assert not await second.fetch("SELECT id FROM public.ledger_accounts")
                        print("M41290_ALTERNATE_VALID_PROOF_DENIED=PASS")
                        print("M41280_SECOND_AUTHENTIC_TARGET_DENIED=PASS")
                    print("M41260_SQL_CHALLENGE_TARGET_SUBSTITUTION_DENIED=PASS")
                    print("M41230_TICKET_ONLY_AND_TARGET_SUBSTITUTION_DENIED=PASS")
                    cap = bind_read(ticket, tenant_a, pid, vxid, started, challenge=challenge)
                    assert cap
                    await gateway.install_session_capability(first, cap)
                    assert len(await first.fetch("SELECT id FROM public.ledger_accounts")) == 2
                    async with second.transaction(readonly=True):
                        await gateway.install_session_capability(second, cap)
                        assert not await second.fetch("SELECT id FROM public.ledger_accounts")
                        assert not await second.fetch("SELECT * FROM m41050.current_claims_v4()")
                    assert len(await first.fetch("SELECT id FROM public.ledger_accounts")) == 2
                async with first.transaction(readonly=True):
                    assert await first.fetchval("SELECT pg_catalog.pg_backend_pid()") == pid
                    await gateway.install_session_capability(first, cap)
                    assert not await first.fetch("SELECT id FROM public.ledger_accounts")
                    assert not await first.fetch("SELECT * FROM m41050.current_claims_v3()")
                # Rollback does not restore the externally consumed ticket.
                tx = first.transaction(readonly=True)
                await tx.start()
                try:
                    pid, vxid, started = await gateway._read_transaction_identity(first)
                    ticket = fixture.issue_ticket(owner, auth_dsn, key, admin_digest, tenant_a)
                    assert ticket
                    challenge = await gateway._read_target_challenge(first, ticket, tenant_a)
                    rolled_cap = bind_read(ticket, tenant_a, pid, vxid, started, challenge=challenge)
                    assert rolled_cap
                    await gateway.install_session_capability(first, rolled_cap)
                    assert len(await first.fetch("SELECT id FROM public.ledger_accounts")) == 2
                finally:
                    await tx.rollback()
                async with first.transaction(readonly=True):
                    pid, vxid, started = await gateway._read_transaction_identity(first)
                    challenge = await gateway._read_target_challenge(first, ticket, tenant_a)
                    assert bind_read(ticket, tenant_a, pid, vxid, started, challenge=challenge) is None
                    await gateway.install_session_capability(first, rolled_cap)
                    assert not await first.fetch("SELECT id FROM public.ledger_accounts")
                # Old unbound issuance cannot access any ledger table.
                ticket = fixture.issue_ticket(owner, auth_dsn, key, admin_digest, tenant_a)
                assert ticket
                unbound = fixture.bind_ticket(app_dsn, ticket, tenant_a)
                assert unbound
                async with first.transaction(readonly=True):
                    await gateway.install_session_capability(first, unbound)
                    for name in expected_tenant_rows:
                        assert not await first.fetch(f"SELECT id FROM public.{name}")
            # Race two independently authenticated issuer connections for a
            # single ticket while both read transactions are live.
            async with pool.acquire() as first, pool.acquire() as second:
                async with first.transaction(readonly=True), second.transaction(readonly=True):
                    ticket = fixture.issue_ticket(owner, auth_dsn, key, admin_digest, tenant_a)
                    assert ticket
                    targets = [await gateway._read_transaction_identity(c) for c in (first, second)]
                    challenges = [await gateway._read_target_challenge(c, ticket, tenant_a)
                                  for c in (first, second)]
                    results = await asyncio.gather(*(
                        asyncio.to_thread(reserve_read, ticket, tenant_a, *target, challenge)
                        for target, challenge in zip(targets, challenges)
                    ))
                    assert sorted(results) == [False, True]
                    winner = results.index(True)
                    assert reserve_read(ticket, tenant_a, *targets[winner], challenges[winner])
                    assert not reserve_read(ticket, tenant_a, *targets[1-winner], challenges[1-winner])
                    cap = bind_read(ticket, tenant_a, *targets[winner], challenge=challenges[winner])
                    assert cap
                    assert not reserve_read(ticket, tenant_a, *targets[winner], challenges[winner])
                    connections = (first, second)
                    await gateway.install_session_capability(connections[winner], cap)
                    assert len(await connections[winner].fetch("SELECT id FROM public.ledger_accounts")) == 2
                    await gateway.install_session_capability(connections[1-winner], cap)
                    assert not await connections[1-winner].fetch("SELECT id FROM public.ledger_accounts")
            print("M41290_CONCURRENT_RESERVATIONS_ONE_WINNER=PASS")
            print("M41220_CROSS_BACKEND_AND_SAME_BACKEND_REPLAY_DENIED=PASS")
            print("M41220_ROLLBACK_AND_UNBOUND_LEDGER_REPLAY_DENIED=PASS")
            print("M41160_RLS_TENANT_ISOLATION=PASS")
            print("M41150_FASTAPI_LEDGER_DIRECTORY=PASS")
            print("M41160_FASTAPI_LEDGER_READ_ROUTES=6_OF_6_PASS")
            print("M41160_CONCURRENT_READS=PASS")

            # A valid opaque capability for another identity or tenant
            # must not turn into an empty successful read.
            for digest, tenant in ((member_digest, tenant_a),
                                   (admin_b_digest, tenant_b)):
                wrong_ticket = fixture.issue_ticket(
                    owner, auth_dsn, key, digest, tenant, scope="READ_ENTRIES",
                )
                assert wrong_ticket
                wrong_capability = fixture.bind_ticket(app_dsn, wrong_ticket, tenant)
                assert wrong_capability
                provider.override_capability = wrong_capability
                denied = await client.get(path_a, headers=admin_headers)
                assert denied.status_code == 401, denied.status_code
            provider.override_capability = "0" * 64
            unknown = await client.get(path_a, headers=admin_headers)
            assert unknown.status_code == 401, unknown.status_code
            async with pool.acquire() as first, pool.acquire() as second:
                for connection in (first, second):
                    assert not connection.is_in_transaction()
                    assert not await connection.fetch(
                        "SELECT user_id FROM m41050.current_claims()"
                    )
            recovered = await client.get(path_a, headers=admin_headers)
            assert recovered.status_code == 200
            assert len(recovered.json()["accounts"]) == 2
            print("M41190_WRONG_SQL_CLAIMS_AND_UNKNOWN_CAPABILITY_DENIED=PASS")
            print("M41190_POOL_RECOVERY_AFTER_DENIAL=PASS")

            # Same account, role and tenant, different database session UUID.
            second_headers = {"Authorization": "Bearer m41200-admin-second"}
            both = await asyncio.gather(*(
                client.get(path, headers=headers)
                for path in read_paths for headers in (admin_headers, second_headers)
            ))
            assert all(response.status_code == 200 for response in both)
            # Second direction first, so last_capability remains bound to admin A
            # before the existing replay and revocation checks.
            for digest, headers in ((admin_digest, second_headers),
                                    (admin_second_digest, admin_headers)):
                wrong_ticket = fixture.issue_ticket(
                    owner, auth_dsn, key, digest, tenant_a, scope="READ_ENTRIES",
                )
                assert wrong_ticket
                wrong_capability = fixture.bind_ticket(app_dsn, wrong_ticket, tenant_a)
                assert wrong_capability
                provider.override_capability = wrong_capability
                denied = await client.get(path_a, headers=headers)
                assert denied.status_code == 401, denied.status_code
            print("M41200_SAME_ACCOUNT_CROSS_SESSION_DENIED=PASS")
            print("M41200_TWO_SESSION_CONCURRENT_READS=PASS")

            # Preserve the M41200 isolation test with an otherwise correct nonce.
            for digest, headers in ((admin_second_digest, admin_headers),
                                    (admin_digest, second_headers)):
                provider.override_digest = digest
                denied = await client.get(path_a, headers=headers)
                assert denied.status_code == 401, denied.status_code
            print("M41210_CORRECT_NONCE_WRONG_SESSION_DENIED=PASS")

            fresh = await client.get(path_a, headers=admin_headers)
            assert fresh.status_code == 200
            used_capability = provider.last_capability
            assert used_capability
            # The same capability is now invalid in another SQL transaction.
            async with pool.acquire() as connection:
                async with connection.transaction(readonly=True):
                    await gateway.install_session_capability(connection, used_capability)
                    claims = await connection.fetch(
                        "SELECT session_id,request_nonce FROM m41050.current_claims_v3()"
                    )
                    assert not claims
                    assert not await connection.fetch("SELECT id FROM public.ledger_accounts")
            provider.replay_capability = used_capability
            try:
                denied = await client.get(path_a, headers=admin_headers)
                assert denied.status_code == 401
                replays = await asyncio.gather(*(
                    client.get(path, headers=admin_headers) for path in read_paths
                ))
                assert all(response.status_code == 401 for response in replays)
            finally:
                provider.replay_capability = None
            print("M41210_SAME_SESSION_SEQUENTIAL_AND_CONCURRENT_REPLAY_DENIED=PASS")

            provider.expire_next = True
            expired = await client.get(path_a, headers=admin_headers)
            assert expired.status_code == 401
            assert not provider.expire_next
            print("M41210_MATCHING_NONCE_EXPIRED_CAPABILITY_DENIED=PASS")

            recovered = await client.get(path_a, headers=admin_headers)
            assert recovered.status_code == 200
            assert len(recovered.json()["accounts"]) == 2
            print("M41210_FRESH_REQUEST_RECOVERY=PASS")

            provider.reuse_next = True
            replay = await client.get(path_a, headers=admin_headers)
            if replay.status_code != 401:
                raise AssertionError("M41150_REPLAYED_TICKET_ACCEPTED")
            print("M41150_TICKET_REPLAY_DENIED=PASS")

            for path in read_paths:
                member_response = await client.get(
                    path,
                    headers={
                        "Authorization": "Bearer m41150-member",
                        "X-Role": "TENANT_ADMIN",
                        "X-Tenant": str(tenant_a),
                    },
                )
                if member_response.status_code != 403:
                    raise AssertionError(
                        f"M41160_MEMBER_ROUTE_AUTH_{member_response.status_code}"
                    )
                cross_tenant = await client.get(
                    path.replace(str(tenant_a), str(tenant_b), 1),
                    headers=admin_headers,
                )
                if cross_tenant.status_code != 403:
                    raise AssertionError(
                        f"M41160_CROSS_TENANT_ROUTE_{cross_tenant.status_code}"
                    )
                master_response = await client.get(
                    path,
                    headers={"Authorization": "Bearer m41150-master"},
                )
                if master_response.status_code != 403:
                    raise AssertionError(
                        f"M41160_MASTER_ROUTE_AUTH_{master_response.status_code}"
                    )
                unverified = await client.get(
                    path,
                    headers={"Authorization": "Bearer m41150-unverified"},
                )
                if unverified.status_code != 401:
                    raise AssertionError(
                        f"M41160_UNVERIFIED_ROUTE_AUTH_{unverified.status_code}"
                    )
                no_session = await client.get(path)
                if no_session.status_code != 401:
                    raise AssertionError(
                        f"M41160_MISSING_SESSION_ROUTE_AUTH_{no_session.status_code}"
                    )
            print("M41160_TENANT_ROLE_NEGATIVE=PASS")

            issue_count = provider.issue_calls
            unverified = await client.get(
                path_a, headers={"Authorization": "Bearer m41150-unverified"}
            )
            if unverified.status_code != 401 or provider.issue_calls != issue_count:
                raise AssertionError("M41150_UNVERIFIED_SESSION_REACHED_ISSUER")
            stale_capability = provider.last_capability
            if not stale_capability:
                raise AssertionError("M41150_FIXTURE_CAPABILITY_MISSING")
            revoked = owner.execute(
                "UPDATE m40650.sessions SET revoked_at=pg_catalog.clock_timestamp() "
                "WHERE token_digest=%s",
                (admin_digest,),
            )
            if revoked.rowcount != 1:
                raise AssertionError("M41150_FIXTURE_SESSION_REVOCATION_MISSING")

            async with pool.acquire() as connection:
                async with connection.transaction(readonly=True):
                    await connection.execute(
                        "SELECT pg_catalog.set_config('app.session_capability',$1,true)",
                        stale_capability,
                    )
                    stale_rows = await connection.fetch(
                        "SELECT id FROM public.ledger_accounts "
                        "WHERE tenant_id=$1 ORDER BY account_code",
                        tenant_a,
                    )
            if stale_rows:
                raise AssertionError("M41150_REVOKED_CAPABILITY_RETAINED_RLS_ACCESS")

            denied_after_revoke = await client.get(
                path_a, headers={"Authorization": "Bearer m41150-admin"}
            )
            if denied_after_revoke.status_code != 401:
                raise AssertionError("M41150_REVOKED_SESSION_TICKET_ACCEPTED")
            print("M41150_REVOKED_CAPABILITY_DENIED=PASS")
            unaffected = await client.get(path_a, headers=second_headers)
            assert unaffected.status_code == 200
            async with pool.acquire() as connection:
                async with connection.transaction(readonly=True):
                    await gateway.install_session_capability(connection, stale_capability)
                    assert not await connection.fetch(
                        "SELECT session_id FROM m41050.current_claims_v2()"
                    )
            print("M41200_INDEPENDENT_SESSION_REVOCATION=PASS")
            from m41610_identity_authorization_disposable import exercise_dual_identity
            issue_authorized = await exercise_dual_identity(
                owner=owner, auth_dsn=auth_dsn, app_dsn=app_dsn, key=key, fixture=fixture,
                provider=provider, client=client, read_paths=read_paths, path_a=path_a,
                admin_headers=admin_headers, second_headers=second_headers,
                admin_id=admin_id, admin_digest=admin_digest, admin_session_id=admin_session_id,
                second_digest=admin_second_digest, second_session_id=admin_second_session_id,
                tenant_a=tenant_a, tenant_b=tenant_b,
            )
            from m41620_identity_commitment_disposable import exercise_commitment
            identity_authority, issue_authorized = await exercise_commitment(
                owner=owner, auth_dsn=auth_dsn, app_dsn=app_dsn, key=key, fixture=fixture,
                provider=provider, client=client, read_paths=read_paths, path_a=path_a,
                admin_headers=admin_headers, second_headers=second_headers,
                admin_id=admin_id, second_digest=admin_second_digest,
                second_session_id=admin_second_session_id, tenant_a=tenant_a, tenant_b=tenant_b,
            )
            # Remove only the disposable verifier, prove no fallback to issuer.
            async with pool.acquire() as connection:
                async with connection.transaction(readonly=True):
                    pid, vxid, started = await gateway._read_transaction_identity(connection)
                    ticket = issue_authorized(admin_second_digest,tenant_a,uuid4(),"READ_ENTRIES")
                    assert ticket
                    challenge = await gateway._read_target_challenge(connection, ticket, tenant_a)
                    proof = signer.sign(ticket, tenant_a, pid, vxid, started, challenge=challenge)
                    assert reserve_read(ticket, tenant_a, pid, vxid, started, challenge)
                    owner.execute("DELETE FROM m41050.target_verifier_secret")
                    assert bind_read(ticket, tenant_a, pid, vxid, started, challenge=challenge, proof=proof) is None
                    assert not await connection.fetch("SELECT id FROM public.ledger_accounts")
            print("M41240_MISSING_TARGET_KEY_FAILS_CLOSED=PASS")
            signer.close()
            unavailable = await client.get(path_a, headers=second_headers)
            assert unavailable.status_code == 503, unavailable.status_code
            assert "M41240" not in unavailable.text
            async with pool.acquire() as connection:
                assert not connection.is_in_transaction()
                assert not await connection.fetch("SELECT * FROM m41050.current_claims_v4()")
            print("M41240_SIGNER_UNAVAILABLE_HTTP503_POOL_CLEAN=PASS")
            identity_authority.close()
            count = owner.execute("SELECT count(*) FROM m40700.identity_commitments").fetchone()[0]
            unavailable = await client.get(path_a, headers=second_headers)
            assert unavailable.status_code == 503
            assert owner.execute("SELECT count(*) FROM m40700.identity_commitments").fetchone()[0] == count
            print("M41620_AUTHORITY_LOSS_NO_NEW_COMMITMENT=PASS")
            await exercise_m41630_target_commitment(
                owner=owner, auth_dsn=auth_dsn, pool=pool, fixture=fixture, gateway=gateway,
                bind_read=bind_read, key=key, second_digest=admin_second_digest,
                second_session_id=admin_second_session_id, admin_id=admin_id,
                tenant_a=tenant_a, tenant_b=tenant_b,
            )
        await pool.close()
    finally:
        if identity_authority is not None:
            identity_authority.close()
        if signer is not None:
            signer.close()
        owner.close()



async def exercise_m41630_target_commitment(*, owner, auth_dsn, pool, fixture, gateway,
                                            bind_read, key, second_digest, second_session_id,
                                            admin_id, tenant_a, tenant_b):
    """CP26-0061/CTM-07, CP26-0062/CTM-08, CP26-0257/TENANT_RLS; TEC-09/12.
    Disposable proof only: pre-ticket SQL challenge, authority commitment bound
    to target, and ticket reservation in one issuer transaction.
    The fixture owner still controls enrollment and can observe the released token.
    The real provider protocol is unchanged (issue before pool acquisition);
    staging custody, same-target theft/DoS and external acceptance remain NO-GO.
    Matrix 330/2310 unchanged. No original database, migrations or runtime reload.
    """
    import hashlib
    import hmac
    import time
    import psycopg
    from m41240_target_signer_disposable import allowed, TargetSigner
    from m41620_identity_commitment_disposable import Authority, V4, commitment
    if (not allowed() or owner.info.dbname != DATABASE or owner.info.port != PORT
            or owner.info.host != "127.0.0.1"):
        raise RuntimeError("M41630_DISPOSABLE_ONLY")
    reservation = "m40700.reserve_read_target(text,uuid,integer,text,timestamptz,text)"
    v5 = "m40700.issue_bound_v5(text,uuid,uuid,bigint,text,uuid,text,bigint,text,uuid,text,integer,text,timestamptz,text)"
    owner.execute("REVOKE EXECUTE ON FUNCTION " + V4 + " FROM m40680_auth")
    owner.execute("REVOKE EXECUTE ON FUNCTION " + reservation + " FROM m40680_auth")
    owner.execute("""
        CREATE FUNCTION m40700.issue_bound_v5(
          p_digest text,p_tenant uuid,p_nonce uuid,p_expiry bigint,p_scope text,
          p_user uuid,p_role text,p_generation bigint,p_proof text,p_session uuid,p_token text,
          p_pid integer,p_vxid text,p_started timestamptz,p_challenge text
        ) RETURNS text LANGUAGE plpgsql SECURITY DEFINER
        SET search_path=pg_catalog,pg_temp AS $body$
        DECLARE v_key bytea; v_target text; v_hash text; v_ticket text;
                v_seed text; v_payload text; v_ticket_challenge text;
        BEGIN
          IF session_user <> 'm40680_auth_login'
             OR p_digest IS NULL OR p_digest !~ '^[0-9a-f]{64}
    try:
        dsn = require_disposable()
    except RuntimeError as exc:
        print("M41150_STATUS=BLOCKED_" + type(exc).__name__)
        print("M41150_DATABASE_CONNECTIONS=NONE")
        print("M41150_ORIGINAL_DATABASE=NOT_ACCESSED")
        return 2

    print("M41150_TARGET=POSTGRES18_DISPOSABLE_ONLY")
    asyncio.run(exercise(dsn))
    print("M41150_STATUS=PASS_FASTAPI_RLS_READ_ONLY_DISPOSABLE_ONLY")
    print("M41160_STATUS=PASS_READ_ONLY_DISPOSABLE_ONLY")
    print("M41170_STATUS=PASS_FAIL_CLOSED_DISPOSABLE_ONLY")
    print("M41170_LEGACY_GUC_FALLBACK=REMOVED")
    print("M41170_DATABASE_CONNECTIONS_WITHOUT_PROVIDER=NONE")
    print("M41160_AUTHENTICATION=OVERRIDDEN_SYNTHETIC")
    print("M41160_PROVIDER=CUSTODY_NOT_CONFIGURED")
    print("M41160_ORIGINAL_DATABASE=NOT_ACCESSED")
    print("M41160_MIGRATIONS=NONE")
    print("M41160_SERVICE_RESTARTS=NONE")
    print("M41160_RUNTIME=NOT_RELOADED_OR_ATTESTED")
    print("M41160_PIX_REAL=OFF")
    print("M41160_PAGAMENTOS_REAIS=OFF")
    print("M41160_ATIVACAO_REAL=OFF")
    print("M41160_PRODUCTION=BLOCKED")
    print("M41150_AUTHENTICATION=OVERRIDDEN_SYNTHETIC")
    print("M41150_PROVIDER=CUSTODY_NOT_CONFIGURED")
    print("M41150_ORIGINAL_DATABASE=NOT_ACCESSED")
    print("M41150_MIGRATIONS=NONE")
    print("M41150_SERVICE_RESTARTS=NONE")
    print("M41150_RUNTIME=NOT_RELOADED_OR_ATTESTED")
    print("M41150_PIX_REAL=OFF")
    print("M41150_PAGAMENTOS_REAIS=OFF")
    print("M41150_ATIVACAO_REAL=OFF")
    print("M41150_PRODUCTION=BLOCKED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

             OR p_token IS NULL OR p_token !~ '^[0-9a-f]{64}
    try:
        dsn = require_disposable()
    except RuntimeError as exc:
        print("M41150_STATUS=BLOCKED_" + type(exc).__name__)
        print("M41150_DATABASE_CONNECTIONS=NONE")
        print("M41150_ORIGINAL_DATABASE=NOT_ACCESSED")
        return 2

    print("M41150_TARGET=POSTGRES18_DISPOSABLE_ONLY")
    asyncio.run(exercise(dsn))
    print("M41150_STATUS=PASS_FASTAPI_RLS_READ_ONLY_DISPOSABLE_ONLY")
    print("M41160_STATUS=PASS_READ_ONLY_DISPOSABLE_ONLY")
    print("M41170_STATUS=PASS_FAIL_CLOSED_DISPOSABLE_ONLY")
    print("M41170_LEGACY_GUC_FALLBACK=REMOVED")
    print("M41170_DATABASE_CONNECTIONS_WITHOUT_PROVIDER=NONE")
    print("M41160_AUTHENTICATION=OVERRIDDEN_SYNTHETIC")
    print("M41160_PROVIDER=CUSTODY_NOT_CONFIGURED")
    print("M41160_ORIGINAL_DATABASE=NOT_ACCESSED")
    print("M41160_MIGRATIONS=NONE")
    print("M41160_SERVICE_RESTARTS=NONE")
    print("M41160_RUNTIME=NOT_RELOADED_OR_ATTESTED")
    print("M41160_PIX_REAL=OFF")
    print("M41160_PAGAMENTOS_REAIS=OFF")
    print("M41160_ATIVACAO_REAL=OFF")
    print("M41160_PRODUCTION=BLOCKED")
    print("M41150_AUTHENTICATION=OVERRIDDEN_SYNTHETIC")
    print("M41150_PROVIDER=CUSTODY_NOT_CONFIGURED")
    print("M41150_ORIGINAL_DATABASE=NOT_ACCESSED")
    print("M41150_MIGRATIONS=NONE")
    print("M41150_SERVICE_RESTARTS=NONE")
    print("M41150_RUNTIME=NOT_RELOADED_OR_ATTESTED")
    print("M41150_PIX_REAL=OFF")
    print("M41150_PAGAMENTOS_REAIS=OFF")
    print("M41150_ATIVACAO_REAL=OFF")
    print("M41150_PRODUCTION=BLOCKED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

             OR p_tenant IS NULL OR p_nonce IS NULL OR p_session IS NULL OR p_user IS NULL
             OR p_role IS DISTINCT FROM 'TENANT_ADMIN'
             OR p_scope IS DISTINCT FROM 'READ_ENTRIES'
             OR p_generation IS NULL OR p_generation<0
             OR p_expiry IS NULL
             OR p_expiry<=pg_catalog.floor(pg_catalog.date_part('epoch',pg_catalog.clock_timestamp()))::bigint
             OR p_expiry>pg_catalog.floor(pg_catalog.date_part('epoch',pg_catalog.clock_timestamp()))::bigint+30
             OR p_pid IS NULL OR p_pid<=0 OR p_pid=pg_catalog.pg_backend_pid()
             OR p_vxid IS NULL OR p_vxid !~ '^[0-9]+/[0-9]+
    try:
        dsn = require_disposable()
    except RuntimeError as exc:
        print("M41150_STATUS=BLOCKED_" + type(exc).__name__)
        print("M41150_DATABASE_CONNECTIONS=NONE")
        print("M41150_ORIGINAL_DATABASE=NOT_ACCESSED")
        return 2

    print("M41150_TARGET=POSTGRES18_DISPOSABLE_ONLY")
    asyncio.run(exercise(dsn))
    print("M41150_STATUS=PASS_FASTAPI_RLS_READ_ONLY_DISPOSABLE_ONLY")
    print("M41160_STATUS=PASS_READ_ONLY_DISPOSABLE_ONLY")
    print("M41170_STATUS=PASS_FAIL_CLOSED_DISPOSABLE_ONLY")
    print("M41170_LEGACY_GUC_FALLBACK=REMOVED")
    print("M41170_DATABASE_CONNECTIONS_WITHOUT_PROVIDER=NONE")
    print("M41160_AUTHENTICATION=OVERRIDDEN_SYNTHETIC")
    print("M41160_PROVIDER=CUSTODY_NOT_CONFIGURED")
    print("M41160_ORIGINAL_DATABASE=NOT_ACCESSED")
    print("M41160_MIGRATIONS=NONE")
    print("M41160_SERVICE_RESTARTS=NONE")
    print("M41160_RUNTIME=NOT_RELOADED_OR_ATTESTED")
    print("M41160_PIX_REAL=OFF")
    print("M41160_PAGAMENTOS_REAIS=OFF")
    print("M41160_ATIVACAO_REAL=OFF")
    print("M41160_PRODUCTION=BLOCKED")
    print("M41150_AUTHENTICATION=OVERRIDDEN_SYNTHETIC")
    print("M41150_PROVIDER=CUSTODY_NOT_CONFIGURED")
    print("M41150_ORIGINAL_DATABASE=NOT_ACCESSED")
    print("M41150_MIGRATIONS=NONE")
    print("M41150_SERVICE_RESTARTS=NONE")
    print("M41150_RUNTIME=NOT_RELOADED_OR_ATTESTED")
    print("M41150_PIX_REAL=OFF")
    print("M41150_PAGAMENTOS_REAIS=OFF")
    print("M41150_ATIVACAO_REAL=OFF")
    print("M41150_PRODUCTION=BLOCKED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

             OR p_started IS NULL OR p_started>pg_catalog.clock_timestamp()
             OR p_started<pg_catalog.clock_timestamp()-interval '30 seconds'
             OR p_challenge IS NULL OR p_challenge !~ '^[0-9a-f]{64}
    try:
        dsn = require_disposable()
    except RuntimeError as exc:
        print("M41150_STATUS=BLOCKED_" + type(exc).__name__)
        print("M41150_DATABASE_CONNECTIONS=NONE")
        print("M41150_ORIGINAL_DATABASE=NOT_ACCESSED")
        return 2

    print("M41150_TARGET=POSTGRES18_DISPOSABLE_ONLY")
    asyncio.run(exercise(dsn))
    print("M41150_STATUS=PASS_FASTAPI_RLS_READ_ONLY_DISPOSABLE_ONLY")
    print("M41160_STATUS=PASS_READ_ONLY_DISPOSABLE_ONLY")
    print("M41170_STATUS=PASS_FAIL_CLOSED_DISPOSABLE_ONLY")
    print("M41170_LEGACY_GUC_FALLBACK=REMOVED")
    print("M41170_DATABASE_CONNECTIONS_WITHOUT_PROVIDER=NONE")
    print("M41160_AUTHENTICATION=OVERRIDDEN_SYNTHETIC")
    print("M41160_PROVIDER=CUSTODY_NOT_CONFIGURED")
    print("M41160_ORIGINAL_DATABASE=NOT_ACCESSED")
    print("M41160_MIGRATIONS=NONE")
    print("M41160_SERVICE_RESTARTS=NONE")
    print("M41160_RUNTIME=NOT_RELOADED_OR_ATTESTED")
    print("M41160_PIX_REAL=OFF")
    print("M41160_PAGAMENTOS_REAIS=OFF")
    print("M41160_ATIVACAO_REAL=OFF")
    print("M41160_PRODUCTION=BLOCKED")
    print("M41150_AUTHENTICATION=OVERRIDDEN_SYNTHETIC")
    print("M41150_PROVIDER=CUSTODY_NOT_CONFIGURED")
    print("M41150_ORIGINAL_DATABASE=NOT_ACCESSED")
    print("M41150_MIGRATIONS=NONE")
    print("M41150_SERVICE_RESTARTS=NONE")
    print("M41150_RUNTIME=NOT_RELOADED_OR_ATTESTED")
    print("M41150_PIX_REAL=OFF")
    print("M41150_PAGAMENTOS_REAIS=OFF")
    print("M41150_ATIVACAO_REAL=OFF")
    print("M41150_PRODUCTION=BLOCKED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

             OR NOT EXISTS (SELECT 1 FROM pg_catalog.pg_locks AS l
                 WHERE l.pid=p_pid AND l.locktype='virtualxid' AND l.virtualxid=p_vxid
                   AND l.virtualtransaction=p_vxid AND l.mode='ExclusiveLock' AND l.granted)
          THEN RETURN NULL; END IF;
          SELECT key INTO v_key FROM m41050.target_challenge_secret WHERE singleton=true;
          IF NOT FOUND THEN RETURN NULL; END IF;
          -- Reuse the read-only SQL challenge with a domain-separated, pre-ticket seed.
          v_seed:=pg_catalog.encode(pg_catalog.sha256(pg_catalog.convert_to(
               'FRF-M41630-SEED|v1|'||p_nonce::text,'UTF8')),'hex');
          v_payload:='|'||p_tenant::text||'|'||p_pid::text||'|'||p_vxid||'|'||
              (EXTRACT(EPOCH FROM p_started)*1000000)::bigint::text;
          IF p_challenge<>pg_catalog.encode(m40700.hmac(pg_catalog.convert_to(
              'FRF-M41260|v1|'||pg_catalog.encode(pg_catalog.sha256(
              pg_catalog.convert_to(v_seed,'UTF8')),'hex')||v_payload,'UTF8'),v_key,'sha256'),'hex')
          THEN RETURN NULL; END IF;
          v_target:=pg_catalog.encode(pg_catalog.sha256(pg_catalog.convert_to(
              'FRF-M41630|v1|'||p_digest||'|'||p_challenge,'UTF8')),'hex');
          v_hash:=pg_catalog.encode(pg_catalog.sha256(pg_catalog.convert_to(
              'FRF-M41620|v1|'||v_target||'|'||p_session::text||'|'||p_tenant::text||'|'||
              p_nonce::text||'|'||p_expiry::text||'|'||p_scope||'|'||p_user::text||'|'||
              p_role||'|'||p_generation::text||'|'||p_token,'UTF8')),'hex');
          PERFORM 1 FROM m40700.identity_commitments WHERE nonce=p_nonce
              AND commitment=v_hash AND expiry=p_expiry AND consumed_at IS NULL FOR UPDATE;
          IF NOT FOUND OR p_expiry<=pg_catalog.floor(pg_catalog.date_part('epoch',pg_catalog.clock_timestamp()))::bigint
          THEN RETURN NULL; END IF;
          PERFORM 1 FROM m40650.sessions AS s WHERE s.id=p_session AND s.token_digest=p_digest
              AND s.user_id=p_user AND s.active_role=p_role AND s.active_tenant_id=p_tenant
              AND s.context_generation=p_generation AND s.revoked_at IS NULL
              AND s.expires_at>pg_catalog.clock_timestamp() FOR SHARE OF s;
          IF NOT FOUND THEN RETURN NULL; END IF;
          v_ticket:=m40700.issue_bound_v2(p_digest,p_tenant,p_nonce,p_expiry,p_scope,
                                         p_user,p_role,p_generation,p_proof);
          IF v_ticket IS NULL THEN RETURN NULL; END IF;
          v_ticket_challenge:=pg_catalog.encode(m40700.hmac(pg_catalog.convert_to(
              'FRF-M41260|v1|'||pg_catalog.encode(pg_catalog.sha256(
              pg_catalog.convert_to(v_ticket,'UTF8')),'hex')||v_payload,'UTF8'),v_key,'sha256'),'hex');
          -- No unreserved ticket may escape, including on target termination.
          IF NOT m40700.reserve_read_target(v_ticket,p_tenant,p_pid,p_vxid,p_started,v_ticket_challenge)
          THEN RAISE EXCEPTION 'M41630_TARGET_RESERVATION_FAILED'; END IF;
          UPDATE m40700.identity_commitments SET consumed_at=pg_catalog.clock_timestamp()
             WHERE nonce=p_nonce;
          RETURN v_ticket;
        END
        $body$
    """)
    owner.execute("ALTER FUNCTION " + v5 + " OWNER TO m40650_owner")
    owner.execute("REVOKE ALL ON FUNCTION " + v5 + " FROM PUBLIC,m40650_app")
    owner.execute("GRANT EXECUTE ON FUNCTION " + v5 + " TO m40680_auth")
    ctx = fixture.fixture_context(owner, second_digest)
    assert ctx[:2] == (admin_id, "TENANT_ADMIN")
    def submit(p, token, target, challenge, *, proof=None, rollback=False):
        signed = fixture.sign_context(key, second_digest, UUID(p["tenant"]), UUID(p["nonce"]),
                                    p["expiry"], p["scope"], (admin_id, p["role"], p["generation"]))
        with psycopg.connect(auth_dsn, autocommit=True) as c:
            c.execute("SET ROLE m40680_auth")
            if rollback:
                c.execute("BEGIN")
            result = c.execute(
                "SELECT m40700.issue_bound_v5(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (second_digest, UUID(p["tenant"]), UUID(p["nonce"]), p["expiry"], p["scope"],
                 admin_id, p["role"], p["generation"], signed if proof is None else proof,
                 second_session_id, token, *target, challenge)).fetchone()[0]
            if rollback:
                c.execute("ROLLBACK")
            return result
    with psycopg.connect(auth_dsn, autocommit=True) as c:
        c.execute("SET ROLE m40680_auth")
        for sig, permitted in ((V4, False), (reservation, False), (v5, True)):
            assert c.execute("SELECT has_function_privilege(current_user,%s,'EXECUTE')",
                             (sig,)).fetchone()[0] == permitted
    challenge_key = bytes(owner.execute(
        "SELECT key FROM m41050.target_challenge_secret WHERE singleton=true").fetchone()[0])
    new_signer = TargetSigner(challenge_key=challenge_key)
    try:
        target_key = new_signer.take_bootstrap_key()
        owner.execute("INSERT INTO m41050.target_verifier_secret(singleton,key) VALUES(true,%s)",
                      (target_key,))
        async with pool.acquire() as dest, pool.acquire() as other:
            async with dest.transaction(readonly=True), other.transaction(readonly=True):
                target = await gateway._read_transaction_identity(dest)
                wrong = await gateway._read_transaction_identity(other)
                nonce = uuid4()
                seed = hashlib.sha256(("FRF-M41630-SEED|v1|" + str(nonce)).encode("ascii")).hexdigest()
                challenge = await gateway._read_target_challenge(dest, seed, tenant_a)
                wrong_challenge = await gateway._read_target_challenge(other, seed, tenant_a)
                assert challenge != wrong_challenge
                frozen = dict(digest=hashlib.sha256(
                    ("FRF-M41630|v1|" + second_digest + "|" + challenge).encode("ascii")).hexdigest(),
                    session=str(second_session_id), tenant=str(tenant_a), scope="READ_ENTRIES",
                    user=str(admin_id), role="TENANT_ADMIN", generation=ctx[2])
                authority = Authority(frozen)
                try:
                    p = dict(frozen, nonce=str(nonce), expiry=int(time.time())+25)
                    digest = authority.request("prepare", p)
                    assert digest
                    owner.execute("INSERT INTO m40700.identity_commitments(nonce,commitment,expiry) VALUES(%s,%s,%s)",
                                  (nonce, digest, p["expiry"]))
                    token = authority.request("release", p)
                    assert token and commitment(p, token) == digest
                    assert authority.request("release", p) is None
                    # Captured token and valid alternate SQL challenge cannot redirect.
                    assert submit(p, token, wrong, wrong_challenge) is None
                    assert submit(p, token, wrong, challenge) is None
                    assert submit(p, token, target, challenge, proof="0"*64) is None
                    assert submit(p, digest, target, challenge) is None
                    owner.execute("UPDATE m40700.identity_commitments SET expiry=0 WHERE nonce=%s", (nonce,))
                    assert submit(p, token, target, challenge) is None
                    owner.execute("UPDATE m40700.identity_commitments SET expiry=%s WHERE nonce=%s", (p["expiry"],nonce))
                    # Rollback must undo issuance, reservation and consumption as a unit.
                    rolled = submit(p, token, target, challenge, rollback=True)
                    assert rolled
                    assert owner.execute("SELECT consumed_at FROM m40700.identity_commitments WHERE nonce=%s",
                                         (nonce,)).fetchone()[0] is None
                    assert not owner.execute("SELECT 1 FROM m41050.read_target_reservations WHERE ticket_digest=%s",
                                             (hashlib.sha256(rolled.encode("ascii")).hexdigest(),)).fetchone()
                    results = await asyncio.gather(*(asyncio.to_thread(
                        submit, p, token, target, challenge) for _ in range(2)))
                    assert sum(t is not None for t in results) == 1
                    ticket = next(t for t in results if t is not None)
                    assert submit(p, token, target, challenge) is None
                    ticket_digest = hashlib.sha256(ticket.encode("ascii")).hexdigest()
                    assert owner.execute(
                        "SELECT backend_pid,virtual_xid,transaction_started_at FROM m41050.read_target_reservations WHERE ticket_digest=%s",
                        (ticket_digest,)).fetchone() == target
                    bad = await gateway._read_target_challenge(other, ticket, tenant_a)
                    # Authentic alternate-target proof using the fixture's bootstrap key;
                    # binder must deny even if the signer is compromised.
                    epoch = datetime(1970,1,1,tzinfo=timezone.utc)
                    delta = wrong[2]-epoch
                    micros = (delta.days*86400+delta.seconds)*1000000+delta.microseconds
                    payload = f"FRF-M41270|v1|{ticket_digest}|{tenant_a}|{wrong[0]}|{wrong[1]}|{micros}|{bad}"
                    bad_proof = hmac.new(target_key,payload.encode("ascii"),hashlib.sha256).hexdigest()
                    assert bind_read(ticket,tenant_a,*wrong,challenge=bad,proof=bad_proof) is None
                    good = await gateway._read_target_challenge(dest,ticket,tenant_a)
                    proof = new_signer.sign(ticket,tenant_a,*target,challenge=good)
                    cap = bind_read(ticket,tenant_a,*target,challenge=good,proof=proof)
                    assert cap
                    await gateway.install_session_capability(other,cap)
                    assert not await other.fetch("SELECT id FROM public.ledger_accounts")
                    await gateway.install_session_capability(dest,cap)
                    rows = await dest.fetch("SELECT tenant_id FROM public.ledger_accounts")
                    assert rows and all(row["tenant_id"] == tenant_a for row in rows)
                    assert not await dest.fetch("SELECT id FROM public.ledger_accounts WHERE tenant_id=$1",tenant_b)
                    print("M41630_TARGET_COMMITMENT_CAPTURE_ROLLBACK_RACE_RLS=PASS_DISPOSABLE_ONLY")
                finally:
                    authority.close()
            async with dest.transaction(readonly=True):
                await gateway.install_session_capability(dest,cap)
                assert not await dest.fetch("SELECT id FROM public.ledger_accounts")
        print("M41630_TRANSACTION_END_REPLAY_DENIED=PASS")
    finally:
        new_signer.close()
        owner.execute("DELETE FROM m41050.target_verifier_secret")
    print("M41630_REAL_PROVIDER=NOT_INTEGRATED")
    print("M41630_PRODUCTION=BLOCKED")


def main() -> int:
    try:
        dsn = require_disposable()
    except RuntimeError as exc:
        print("M41150_STATUS=BLOCKED_" + type(exc).__name__)
        print("M41150_DATABASE_CONNECTIONS=NONE")
        print("M41150_ORIGINAL_DATABASE=NOT_ACCESSED")
        return 2

    print("M41150_TARGET=POSTGRES18_DISPOSABLE_ONLY")
    asyncio.run(exercise(dsn))
    print("M41150_STATUS=PASS_FASTAPI_RLS_READ_ONLY_DISPOSABLE_ONLY")
    print("M41160_STATUS=PASS_READ_ONLY_DISPOSABLE_ONLY")
    print("M41170_STATUS=PASS_FAIL_CLOSED_DISPOSABLE_ONLY")
    print("M41170_LEGACY_GUC_FALLBACK=REMOVED")
    print("M41170_DATABASE_CONNECTIONS_WITHOUT_PROVIDER=NONE")
    print("M41160_AUTHENTICATION=OVERRIDDEN_SYNTHETIC")
    print("M41160_PROVIDER=CUSTODY_NOT_CONFIGURED")
    print("M41160_ORIGINAL_DATABASE=NOT_ACCESSED")
    print("M41160_MIGRATIONS=NONE")
    print("M41160_SERVICE_RESTARTS=NONE")
    print("M41160_RUNTIME=NOT_RELOADED_OR_ATTESTED")
    print("M41160_PIX_REAL=OFF")
    print("M41160_PAGAMENTOS_REAIS=OFF")
    print("M41160_ATIVACAO_REAL=OFF")
    print("M41160_PRODUCTION=BLOCKED")
    print("M41150_AUTHENTICATION=OVERRIDDEN_SYNTHETIC")
    print("M41150_PROVIDER=CUSTODY_NOT_CONFIGURED")
    print("M41150_ORIGINAL_DATABASE=NOT_ACCESSED")
    print("M41150_MIGRATIONS=NONE")
    print("M41150_SERVICE_RESTARTS=NONE")
    print("M41150_RUNTIME=NOT_RELOADED_OR_ATTESTED")
    print("M41150_PIX_REAL=OFF")
    print("M41150_PAGAMENTOS_REAIS=OFF")
    print("M41150_ATIVACAO_REAL=OFF")
    print("M41150_PRODUCTION=BLOCKED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
