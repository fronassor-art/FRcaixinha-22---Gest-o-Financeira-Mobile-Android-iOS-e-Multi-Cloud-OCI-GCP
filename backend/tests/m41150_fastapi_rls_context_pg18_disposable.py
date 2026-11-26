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
    from backend.app.dependencies import AuthenticatedSession, get_current_session
    from backend.app.routers import ledger
    import backend.app.m41150_fastapi_rls_context as gateway

    auth_dsn, app_dsn = fixture.connection_dsns(dsn)
    owner = fixture.connect(dsn, autocommit=True)
    try:
        key = owner.execute(
            "SELECT key FROM m40700.verifier_secret WHERE singleton=true"
        ).fetchone()[0]
        if not key:
            raise AssertionError("M41150_FIXTURE_SIGNER_KEY_MISSING")

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
                    SELECT 1 FROM m41050.current_claims() AS claims
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
                self.issue_calls = 0

            async def issue_ticket(self, session, *, scope):
                self.issue_calls += 1
                if scope != "READ_ENTRIES":
                    return None
                if self.reuse_next and self.last_ticket:
                    self.reuse_next = False
                    return self.last_ticket
                digest = self.session_digests.get(
                    (session.verified_session_id, session.user_id, session.role, session.tenant_id)
                )
                if digest is None:
                    return None
                ticket = fixture.issue_ticket(
                    owner, auth_dsn, key, digest, UUID(session.tenant_id),
                    scope=scope,
                )
                if ticket:
                    self.last_ticket = ticket
                return ticket

            async def bind_ticket(self, ticket, *, tenant_id):
                capability = fixture.bind_ticket(app_dsn, ticket, tenant_id)
                if capability:
                    self.last_capability = capability
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
                    await gateway.install_session_capability(
                        connection, active_capability
                    )
                    for table_name, expected_count in expected_tenant_rows.items():
                        rows = await connection.fetch(
                            f"SELECT tenant_id FROM public.{table_name}"
                        )
                        if (len(rows) != expected_count
                                or any(row["tenant_id"] != tenant_a for row in rows)):
                            raise AssertionError(
                                f"M41160_RLS_TENANT_ISOLATION_{table_name}"
                            )
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
        await pool.close()
    finally:
        owner.close()


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
