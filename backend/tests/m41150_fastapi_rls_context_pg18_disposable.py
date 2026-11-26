#!/usr/bin/env python3
"""M41150 FastAPI ledger-directory to capability/RLS proof; disposable PG18 only."""
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
        admin_id, member_id = uuid4(), uuid4()
        owner.execute(
            "INSERT INTO m40650.users(id,status,is_master) VALUES (%s,'ACTIVE',false)",
            (admin_id,),
        )
        owner.execute(
            "INSERT INTO m40650.users(id,status,is_master) VALUES (%s,'ACTIVE',false)",
            (member_id,),
        )
        for user_id, tenant_id, role in (
            (admin_id, tenant_a, "TENANT_ADMIN"),
            (member_id, tenant_a, "TENANT_MEMBER"),
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

        owner.execute("""
            CREATE TABLE public.ledger_accounts(
                id uuid PRIMARY KEY,
                tenant_id uuid NOT NULL,
                account_code text NOT NULL,
                account_name text NOT NULL,
                account_type text NOT NULL
            )
        """)
        owner.execute(
            "ALTER TABLE public.ledger_accounts OWNER TO m40650_owner"
        )
        owner.execute("""
            INSERT INTO public.ledger_accounts(
                id,tenant_id,account_code,account_name,account_type
            ) VALUES
              (%s,%s,'A-CASH','Caixa A','ASSET'),
              (%s,%s,'B-CASH','Caixa B','ASSET')
        """, (uuid4(), tenant_a, uuid4(), tenant_b))
        owner.execute(
            "ALTER TABLE public.ledger_accounts ENABLE ROW LEVEL SECURITY"
        )
        owner.execute(
            "ALTER TABLE public.ledger_accounts FORCE ROW LEVEL SECURITY"
        )
        owner.execute("""
            CREATE POLICY m41150_ledger_directory_read
            ON public.ledger_accounts
            FOR SELECT TO m40650_app
            USING (
              EXISTS (
                SELECT 1 FROM m41050.current_claims() AS claims
                 WHERE claims.scope_name='READ_ENTRIES'
                   AND claims.role_name='TENANT_ADMIN'
                   AND claims.tenant_id=ledger_accounts.tenant_id
              )
            )
        """)
        owner.execute(
            "GRANT SELECT ON public.ledger_accounts TO m40650_app"
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
                forged = await connection.fetch(
                    "SELECT id FROM public.ledger_accounts ORDER BY account_code"
                )
                if forged:
                    raise AssertionError("M41150_LEGACY_GUC_FORGED_CONTEXT_VISIBLE")
        print("M41150_FORGED_LEGACY_GUC_DENIED=PASS")

        now = datetime.now(timezone.utc)

        def make_session(user_id, role, tenant_id, *, verification_source=None):
            return AuthenticatedSession(
                user_id=str(user_id),
                role=role,
                tenant_id=str(tenant_id) if tenant_id is not None else None,
                email="ci@example.invalid",
                name="synthetic",
                is_master=(role == "MASTER"),
                verified_session_id=str(uuid4()),
                verified_session_at=now - timedelta(seconds=1),
                verified_session_expires_at=now + timedelta(minutes=10),
                verification_source=(
                    verification_source or "POSTGRES_TOKEN_HASH_REFRESH"
                ),
            )

        admin_session = make_session(admin_id, "TENANT_ADMIN", tenant_a)
        member_session = make_session(member_id, "TENANT_MEMBER", tenant_a)
        master_session = make_session(uuid4(), "MASTER", None)
        unverified_session = make_session(
            admin_id, "TENANT_ADMIN", tenant_a,
            verification_source="LEGACY_NO_SESSION_BINDING",
        )
        sessions = {
            "Bearer m41150-admin": admin_session,
            "Bearer m41150-member": member_session,
            "Bearer m41150-master": master_session,
            "Bearer m41150-unverified": unverified_session,
        }

        class FixtureCapabilityProvider:
            def __init__(self):
                self.session_digests = {
                    (str(admin_id), "TENANT_ADMIN", str(tenant_a)): admin_digest,
                    (str(member_id), "TENANT_MEMBER", str(tenant_a)): member_digest,
                }
                self.last_ticket = None
                self.last_capability = None
                self.reuse_next = False
                self.issue_calls = 0

            async def issue_ticket(self, session, *, scope):
                self.issue_calls += 1
                if scope != "READ_ENTRIES":
                    return None
                if self.reuse_next and self.last_ticket:
                    self.reuse_next = False
                    return self.last_ticket
                digest = self.session_digests.get(
                    (session.user_id, session.role, session.tenant_id)
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
                return capability

        provider = FixtureCapabilityProvider()
        app = FastAPI()
        app.include_router(ledger.router, prefix="/api/v1")

        async def synthetic_current_session(request: Request):
            raw = request.headers.get("authorization")
            session = sessions.get(raw)
            if session is None:
                raise HTTPException(status_code=401, detail="Unauthorized")
            return session

        app.dependency_overrides[get_current_session] = synthetic_current_session
        setattr(app.state, gateway.PROVIDER_STATE_ATTRIBUTE, provider)

        async def fixture_pool():
            return pool

        gateway.get_db_pool = fixture_pool

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://frfinance.test"
        ) as client:
            path_a = (
                f"/api/v1/tenants/{tenant_a}/ledger/accounts/directory"
            )
            response = await client.get(
                path_a, headers={"Authorization": "Bearer m41150-admin"}
            )
            if response.status_code != 200:
                raise AssertionError(
                    f"M41150_DIRECTORY_HTTP_{response.status_code}: {response.text}"
                )
            payload = response.json()
            if (len(payload.get("accounts", [])) != 1
                    or payload["accounts"][0]["account_code"] != "A-CASH"
                    or payload.get("balance_values_hidden") is not True
                    or payload.get("financial_closing_authorized") is not False):
                raise AssertionError("M41150_LEDGER_DIRECTORY_SCOPE_OR_SHAPE")
            print("M41150_FASTAPI_LEDGER_DIRECTORY=PASS")

            provider.reuse_next = True
            replay = await client.get(
                path_a, headers={"Authorization": "Bearer m41150-admin"}
            )
            if replay.status_code != 401:
                raise AssertionError("M41150_REPLAYED_TICKET_ACCEPTED")
            print("M41150_TICKET_REPLAY_DENIED=PASS")

            member_response = await client.get(
                path_a,
                headers={
                    "Authorization": "Bearer m41150-member",
                    "X-Role": "TENANT_ADMIN",
                    "X-Tenant": str(tenant_a),
                },
            )
            if member_response.status_code != 403:
                raise AssertionError("M41150_FORGED_ROLE_HEADER_ACCEPTED")

            cross_tenant = await client.get(
                f"/api/v1/tenants/{tenant_b}/ledger/accounts/directory",
                headers={"Authorization": "Bearer m41150-admin"},
            )
            if cross_tenant.status_code != 403:
                raise AssertionError("M41150_CROSS_TENANT_DIRECTORY_ACCEPTED")

            master_response = await client.get(
                path_a, headers={"Authorization": "Bearer m41150-master"}
            )
            if master_response.status_code != 403:
                raise AssertionError("M41150_MASTER_DIRECTORY_ACCEPTED")

            issue_count = provider.issue_calls
            unverified = await client.get(
                path_a, headers={"Authorization": "Bearer m41150-unverified"}
            )
            if unverified.status_code != 401 or provider.issue_calls != issue_count:
                raise AssertionError("M41150_UNVERIFIED_SESSION_REACHED_ISSUER")
            no_session = await client.get(path_a)
            if no_session.status_code != 401:
                raise AssertionError("M41150_MISSING_SESSION_ACCEPTED")
            print("M41150_NEGATIVE_ROUTE_AUTH=PASS")

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
