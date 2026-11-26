"""FR Finance M40070 — real FastAPI GET through disposable PostgreSQL 18.

Unlike M40060 dependency-overrides, the server's actual get_current_session,
auth_refresh_session, get_rls_db_connection and tenant RLS are exercised.
This test must never run on Termux, production, FR Finance 5433 or FR 2.2.
Fixture functions are CI simulations and do not prove real contract policy.
"""
from __future__ import annotations

import os
from urllib.parse import urlsplit

AUTH_DSN = (
    "postgresql://fr_m40070_auth:m40070-auth-ci-only"
    "@127.0.0.1:5432/frcaixinha_ci"
)
APP_DSN = (
    "postgresql://fr_m40070_app:m40070-app-ci-only"
    "@127.0.0.1:5432/frcaixinha_ci"
)
EXPECTED = {
    "GITHUB_ACTIONS": "true",
    "CI_M40070_DISPOSABLE": "1",
    "PGHOST": "127.0.0.1",
    "PGPORT": "5432",
    "PGUSER": "postgres",
    "PGDATABASE": "frcaixinha_ci",
    "PGPASSWORD": "postgres",
    "FRCAIXINHA_TEST_AUTH": "1",
    "ENVIRONMENT": "development",
    "AUTH_DATABASE_URL": AUTH_DSN,
    "DATABASE_URL": APP_DSN,
    "PIX_REAL": "OFF",
    "PAGAMENTOS_REAIS": "OFF",
    "ATIVACAO_REAL": "OFF",
    "FR_FINANCE_PIX_REAL": "OFF",
    "FR_FINANCE_REAL_PAYMENTS": "OFF",
    "FR_FINANCE_REAL_USER_ACTIVATION": "OFF",
}


def require_disposable_ci(environ=None) -> None:
    e = os.environ if environ is None else environ
    if any(e.get(k) != v for k, v in EXPECTED.items()):
        raise RuntimeError("M40070_BLOCKED_UNSAFE_ENVIRONMENT")
    if "frfinance.m40070_ci=DISPOSABLE_ONLY" not in e.get("PGOPTIONS", ""):
        raise RuntimeError("M40070_BLOCKED_MISSING_DISPOSABLE_GUC")
    for name in ("AUTH_DATABASE_URL", "DATABASE_URL"):
        u = urlsplit(e[name])
        if u.scheme != "postgresql" or u.hostname != "127.0.0.1" or (
            u.port != 5432 or u.path != "/frcaixinha_ci"
        ):
            raise RuntimeError("M40070_BLOCKED_UNEXPECTED_DSN")
    if e.get("CI_M40070_NO_NETWORK") == "1":
        raise RuntimeError("M40070_BLOCKED_NO_NETWORK_MODE")


def main() -> None:
    require_disposable_ci()  # Must precede importing app and all connections.
    from uuid import UUID
    import psycopg
    from fastapi.testclient import TestClient
    from app.main import app
    from app.database import get_rls_db_connection
    from app.dependencies import get_current_session, require_master

    # This in-process marker is set only after require_disposable_ci() validates
    # the isolated PG18 test database, roles, DSNs, flags and environment.
    app.state.frfinance_m40070_disposable_read_test = True

    # These are synthetic test-only secrets; no real tokens are ever used.
    TOKENS = {
        "master": "m40070-ci-master-never-real",
        "a": "m40070-ci-admin-a-never-real",
        "b": "m40070-ci-admin-b-never-real",
        "member": "m40070-ci-member-a-never-real",
        "nonowner": "m40070-ci-notowner-a-never-real",
        "expired": "m40070-ci-expired-a-never-real",
        "revoked": "m40070-ci-revoked-a-never-real",
        "invalid": "m40070-ci-random-unknown-never-real",
    }
    A = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
    B = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
    MASTER = "/api/v1/master/exclusive-cashbox/review-policy-gaps"
    admin = lambda tenant: (
        f"/api/v1/tenants/{tenant}/admin-exclusive-cashbox/review-policy-gaps"
    )
    assert not app.dependency_overrides
    assert callable(get_current_session) and callable(require_master)
    assert callable(get_rls_db_connection)
    routes = {route.path: route.methods for route in app.routes if hasattr(route,"methods")}
    assert routes[MASTER] == {"GET"}
    assert routes["/api/v1/tenants/{tenant_id}/admin-exclusive-cashbox/review-policy-gaps"] == {"GET"}

    def header(actor):
        return {"Authorization": "Bearer " + TOKENS[actor]}

    def blocked(response, expected_scope, tenant=None):
        assert response.status_code == 200, (response.status_code, response.text)
        assert response.headers.get("cache-control") == "no-store"
        assert response.headers.get("pragma") == "no-cache"
        assert response.headers.get("vary") == "Authorization"
        data = response.json()
        assert data["state"] == "POLICY_AND_MANDATE_UNRATIFIED"
        assert data["scope"] == expected_scope
        assert data["tenant_id"] == (str(tenant) if tenant else None)
        assert data["owner_verified_for_view"] is (tenant is not None)
        assert data["session_bound_for_view"] is True
        assert data["available_balance_cents"] is None
        for key in (
            "policy_ratified", "reviewer_grants_verified",
            "two_person_approval_verified", "effective_revocation_verified",
            "real_review_approved", "bank_reconciled", "journal_posted",
            "payout_enabled", "payment_enabled", "pix_enabled",
            "production_authorized",
        ):
            assert data[key] is False, key
        output = str(data)
        for secret in TOKENS.values():
            assert secret not in output
        for private in ("master@ci.invalid", "owner-a@ci.invalid",
                        "owner-b@ci.invalid", "m40070-auth-ci-only",
                        "m40070-app-ci-only"):
            assert private not in output
        return data

    # CI-only diagnostic: independently confirm RLS behavior with the same
    # exact app role and transaction-local settings as get_rls_db_connection.
    # Never print identities, token contents or DSNs.
    import asyncio
    import asyncpg

    async def _verify_fixture_rls():
        c = await asyncpg.connect(APP_DSN, timeout=3)
        try:
            async with c.transaction():
                await c.execute("SELECT set_config('app.current_user_id',$1,true)",
                                "22222222-2222-4222-8222-222222222222")
                await c.execute("SELECT set_config('app.current_role',$1,true)",
                                "TENANT_ADMIN")
                await c.execute("SELECT set_config('app.current_tenant_id',$1,true)",
                                str(A))
                value = await c.fetchval(
                    "SELECT admin_user_id FROM public.tenants "
                    "WHERE id=$1 AND status='ATIVO'", A)
                print("M40070_CI_DIRECT_RLS_OWNER_VISIBLE=" +
                      ("TRUE" if value == UUID("22222222-2222-4222-8222-222222222222")
                       else "FALSE"), flush=True)
        finally:
            await c.close()

    asyncio.run(_verify_fixture_rls())

    with psycopg.connect(
        host="127.0.0.1", port=5432, dbname="frcaixinha_ci",
        user="postgres", password="postgres", connect_timeout=3,
        autocommit=True,
    ) as admin_conn:
        identity = admin_conn.execute(
            "SELECT current_database(), session_user, "
            "current_setting('frfinance.m40070_ci',true), "
            "current_setting('server_version_num')::int"
        ).fetchone()
        assert identity[0:3] == (
            "frcaixinha_ci", "postgres", "DISPOSABLE_ONLY"
        )
        assert identity[3] >= 180000, "M40070_POSTGRESQL_18_REQUIRED"
        before = admin_conn.execute(
            "SELECT id,admin_user_id,status FROM public.tenants ORDER BY id"
        ).fetchall()
        assert len(before) == 2
        assert admin_conn.execute(
            "SELECT count(*) FROM public.sessions"
        ).fetchone()[0] == 7

        # The API uses all REAL dependency wiring, without overrides.
        # TestClient runs one ASGI portal to keep the asyncpg pool on one loop.
        with TestClient(app) as client:
            blocked(client.get(MASTER,headers=header("master")),
                    "PLATFORM_MASTER")
            assert client.get(MASTER,headers=header("a")).status_code == 403
            assert client.get(MASTER,headers=header("b")).status_code == 403
            print("M40070_REAL_BEARER_HASH_MASTER_SAAS=PASS", flush=True)

            blocked(client.get(admin(A),headers=header("a")),
                    "TENANT_ADMIN_OWN", A)
            blocked(client.get(admin(B),headers=header("b")),
                    "TENANT_ADMIN_OWN", B)
            assert client.get(admin(B),headers=header("a")).status_code == 403
            assert client.get(admin(A),headers=header("b")).status_code == 403
            assert client.get(admin(A),headers=header("master")).status_code == 403
            assert client.get(admin(A),headers=header("member")).status_code == 403
            assert client.get(admin(A),headers=header("nonowner")).status_code == 403
            print("M40070_RLS_TENANT_AND_OWNER_BARRIERS=PASS", flush=True)

            for actor in ("expired", "revoked", "invalid"):
                assert client.get(admin(A),headers=header(actor)).status_code == 401
            assert client.get(MASTER).status_code == 401
            assert client.get(admin(A)).status_code == 401
            print("M40070_EXPIRED_REVOKED_UNKNOWN_ANONYMOUS=DENIED",flush=True)

            blocked(client.get(admin(A)+"?policy_ratified=true&pix_enabled=true",
                               headers=header("a")), "TENANT_ADMIN_OWN",A)
            assert client.post(admin(A),headers=header("a"),
                               json={"decision":"APPROVED"}).status_code == 405
            assert client.post(MASTER,headers=header("master"),
                               json={"policy_ratified":True}).status_code == 405
            print("M40070_QUERY_TAMPERING_AND_POST_APPROVAL=DENIED",flush=True)

        after = admin_conn.execute(
            "SELECT id,admin_user_id,status FROM public.tenants ORDER BY id"
        ).fetchall()
        assert before == after, "M40070_TENANT_RECORDS_MUTATED"
        assert admin_conn.execute(
            "SELECT count(*) FROM public.sessions"
        ).fetchone()[0] == 7
        assert admin_conn.execute(
            "SELECT count(*) FROM public.sessions WHERE revoked_at IS NOT NULL"
        ).fetchone()[0] == 1
        # Session expiry refreshes are expected legitimate writes
        # INSIDE THIS CI database, not financial authorization.
        print("M40070_CI_AUTH_REFRESH_ONLY_EXPECTED=TRUE",flush=True)
        print("M40070_ORIGINAL_DATABASE_ACCESS=NONE",flush=True)
        print("M40070_APPROVALS=FALSE",flush=True)
        print("M40070_REAL_PIX=OFF",flush=True)
        print("M40070_PRODUCTION=BLOCKED",flush=True)


if __name__ == "__main__":
    main()
