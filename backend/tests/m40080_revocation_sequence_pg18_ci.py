"""M40080 — session revocation and RLS owner transfer, disposable PG18 only.

Uses M40070's strictly guarded CI configuration and existing fixture.
Only synthetic sessions and tenant rows are changed by the CI superuser.
No originals, no production users, no policy ratification and no Pix.
"""
from __future__ import annotations

from m40070_pg18_policy_runtime_ci import require_disposable_ci

def main() -> None:
    require_disposable_ci()  # No imports of network/database clients before guard.
    from uuid import UUID
    from fastapi.testclient import TestClient
    import psycopg
    from app.main import app

    A = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
    B = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
    ACTOR_B = UUID("33333333-3333-4333-8333-333333333333")
    OTHER = UUID("55555555-5555-4555-8555-555555555555")
    PATH = lambda tid: (
        f"/api/v1/tenants/{tid}/admin-exclusive-cashbox/review-policy-gaps"
    )
    HEADERS = {
        "a": {"Authorization": "Bearer m40070-ci-admin-a-never-real"},
        "b": {"Authorization": "Bearer m40070-ci-admin-b-never-real"},
        "nonowner": {
            "Authorization": "Bearer m40070-ci-notowner-a-never-real"
        },
    }
    assert not app.dependency_overrides
    with psycopg.connect(
        host="127.0.0.1", port=5432, dbname="frcaixinha_ci",
        user="postgres", password="postgres", connect_timeout=3,
        autocommit=True,
    ) as db:
        info = db.execute(
            "SELECT current_database(),session_user,"
            "current_setting('frfinance.m40070_ci',true),"
            "current_setting('server_version_num')::int"
        ).fetchone()
        assert info[:3] == ("frcaixinha_ci","postgres","DISPOSABLE_ONLY")
        assert info[3] >= 180000
        assert db.execute("SELECT count(*) FROM public.sessions").fetchone()[0] == 7
        assert db.execute("SELECT admin_user_id FROM public.tenants WHERE id=%s",
                          (B,)).fetchone()[0] == ACTOR_B

        with TestClient(app) as client:
            assert client.get(PATH(A),headers=HEADERS["a"]).status_code == 200
            assert client.get(PATH(B),headers=HEADERS["b"]).status_code == 200
            assert client.get(PATH(B),headers=HEADERS["a"]).status_code == 403
            assert client.get(PATH(A),headers=HEADERS["b"]).status_code == 403
            print("M40080_ALTERNATING_SESSION_ISOLATION=PASS",flush=True)

            # Commit a synthetic token revocation in a separate PG18 session.
            changed = db.execute(
                "UPDATE public.sessions SET revoked_at=clock_timestamp() "
                "WHERE token_hash=encode(public.digest(%s,'sha256'),'hex') "
                "AND revoked_at IS NULL RETURNING id",
                ("m40070-ci-admin-a-never-real",),
            ).fetchall()
            assert len(changed) == 1, "M40080_REVOKE_MUST_CHANGE_ONE_CI_ROW"
            assert client.get(PATH(A),headers=HEADERS["a"]).status_code == 401
            assert client.get(PATH(B),headers=HEADERS["b"]).status_code == 200
            print("M40080_REVOKED_TOKEN_DENIED_AFTER_COMMIT=PASS",flush=True)

            # Reassign another tenant in the test fixture. Even a still valid
            # token for B loses RLS ownership immediately in the next request.
            changed = db.execute(
                "UPDATE public.tenants SET admin_user_id=%s "
                "WHERE id=%s AND admin_user_id=%s RETURNING id",
                (OTHER, B, ACTOR_B),
            ).fetchall()
            assert len(changed) == 1, "M40080_OWNER_SWAP_MUST_CHANGE_ONE_CI_ROW"
            assert client.get(PATH(B),headers=HEADERS["b"]).status_code == 403
            assert client.get(PATH(A),headers=HEADERS["nonowner"]).status_code == 403
            assert client.get(PATH(B),headers=HEADERS["a"]).status_code == 401
            print("M40080_OWNER_TRANSFER_RLS_NEXT_REQUEST_DENIED=PASS",flush=True)

            # No decision endpoint introduced; no finance or provider IO.
            assert client.post(PATH(B),headers=HEADERS["b"],
                               json={"approved":True}).status_code == 405

        assert db.execute(
            "SELECT count(*) FROM public.sessions WHERE revoked_at IS NOT NULL"
        ).fetchone()[0] == 2
        assert db.execute(
            "SELECT admin_user_id FROM public.tenants WHERE id=%s",(B,)
        ).fetchone()[0] == OTHER
        print("M40080_NO_SECOND_APPROVAL_OR_PAYMENT=PASS",flush=True)
        print("M40080_FIXTURE_WRITES=CI_DISPOSABLE_ONLY",flush=True)
        print("M40080_ORIGINAL_DATABASE_ACCESS=NONE",flush=True)
        print("M40080_LOCAL_MIGRATIONS=NONE",flush=True)
        print("M40080_REAL_REVOCATION=NOT_ATTESTED",flush=True)
        print("M40080_PIX_REAL=OFF",flush=True)
        print("M40080_PRODUCTION=BLOCKED",flush=True)

if __name__ == "__main__":
    main()
