#!/usr/bin/env python3
"""FR Finance M40670: synthetic ASGI Bearer -> SQL gateway proof in PG18 CI only.

NOT deployed, NOT a real API route, NOT production. The raw bearer is passed to
a synthetic SQL function ONLY as a parameter; token logging risk remains a
production design blocker. No migrations or local database connections.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import os
import re
import secrets
from urllib.parse import urlsplit
from uuid import UUID, uuid4

DB = "fr_m40670_disposable_ci"
PORT = 55436
TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_-]{40,128}\Z")


def require_disposable() -> None:
    expected = {
        "GITHUB_ACTIONS": "true",
        "CI_M40670_DISPOSABLE": "1",
        "FRCAIXINHA_CI_ISOLATED": "1",
        "PIX_REAL": "OFF",
        "PAGAMENTOS_REAIS": "OFF",
        "ATIVACAO_REAL": "OFF",
    }
    if any(os.environ.get(key) != value for key, value in expected.items()):
        raise RuntimeError("M40670_DISPOSABLE_ONLY")
    try:
        target = urlsplit(os.environ.get("CI_M40670_DATABASE_URL", ""))
        if (target.scheme != "postgresql" or target.hostname != "127.0.0.1"
                or target.port != PORT or target.path != "/" + DB
                or target.username != "postgres" or not target.password
                or target.query or target.fragment):
            raise RuntimeError("M40670_WRONG_DATABASE_IDENTITY")
    except (ValueError, AttributeError) as exc:
        raise RuntimeError("M40670_WRONG_DATABASE_IDENTITY") from exc


def create_http_function(owner) -> None:
    # The fixture's NOLOGIN owner, unprivileged caller and tables are synthetic.
    from m40650_token_bound_gateway_disposable import schema
    schema(owner)
    owner.execute("""
        CREATE FUNCTION m40650.http_read_entries(p_token text, p_tenant uuid)
        RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER
        SET search_path = pg_catalog, pg_temp
        AS $body$
        DECLARE
          v_user uuid;
          v_role text;
          v_entries jsonb;
        BEGIN
          IF p_token IS NULL OR length(p_token) < 40
                  OR p_tenant IS NULL THEN
            RETURN pg_catalog.jsonb_build_object('authorized',false);
          END IF;

          SELECT s.user_id, s.active_role INTO v_user, v_role
          FROM m40650.sessions AS s
          JOIN m40650.users AS u ON u.id=s.user_id AND u.status='ACTIVE'
          JOIN m40650.memberships AS m
            ON m.user_id=s.user_id AND m.tenant_id=s.active_tenant_id
           AND m.role=s.active_role AND m.status='ATIVA'
          WHERE s.token_digest=pg_catalog.encode(
            pg_catalog.sha256(pg_catalog.convert_to(p_token,'UTF8')), 'hex')
            AND s.expires_at > pg_catalog.clock_timestamp()
            AND s.revoked_at IS NULL
            AND s.active_role IN ('TENANT_MEMBER','TENANT_ADMIN')
            AND s.active_tenant_id=p_tenant;
          IF NOT FOUND THEN
            RETURN pg_catalog.jsonb_build_object('authorized',false);
          END IF;

          SELECT COALESCE(
            pg_catalog.jsonb_agg(
              pg_catalog.jsonb_build_object('id',e.id,'amount',e.amount)
              ORDER BY e.id
            ), '[]'::jsonb
          ) INTO v_entries
          FROM m40650.entries AS e
          WHERE e.tenant_id=p_tenant
            AND (v_role='TENANT_ADMIN' OR e.user_id=v_user);
          RETURN pg_catalog.jsonb_build_object(
            'authorized',true,'entries',v_entries);
        END
        $body$
    """)
    owner.execute(
        "ALTER FUNCTION m40650.http_read_entries(text,uuid) OWNER TO m40650_owner"
    )
    owner.execute(
        "REVOKE ALL ON FUNCTION m40650.http_read_entries(text,uuid) FROM PUBLIC"
    )
    owner.execute(
        "GRANT EXECUTE ON FUNCTION m40650.http_read_entries(text,uuid) TO m40650_app"
    )


def make_app(app_dsn: str):
    # Imported only after the strict CI gate, not by the production FastAPI.
    import psycopg
    from fastapi import FastAPI, Header
    from fastapi.responses import JSONResponse

    app = FastAPI(title="M40670 disposable-only test ASGI app")

    @app.get("/m40670/tenants/{tenant_id}/entries")
    def entries(tenant_id: str, authorization: str | None = Header(default=None)):
        denied = JSONResponse(status_code=401, content={"detail": "Unauthorized"},
                              headers={"Cache-Control": "no-store"})
        if not isinstance(authorization, str) or not authorization.startswith("Bearer "):
            return denied
        token = authorization[7:]
        if not TOKEN_PATTERN.fullmatch(token):
            return denied
        try:
            target = UUID(tenant_id)
            if str(target) != tenant_id or target.int == 0:
                return denied
        except (ValueError, AttributeError, TypeError):
            return denied

        # Fixed SQL. Headers such as X-Role and X-Tenant are deliberately ignored.
        # No application GUC may supply tenant, role or principal authority.
        # WARNING: a raw bearer reaches a synthetic SQL parameter here.
        # Query logging / token exposure MUST be solved before real integration.
        try:
            with psycopg.connect(app_dsn, autocommit=True) as conn:
                conn.execute("SET ROLE m40650_app")
                payload = conn.execute(
                    "SELECT m40650.http_read_entries(%s,%s)",
                    (token, target),
                ).fetchone()[0]
        except psycopg.Error:
            return JSONResponse(status_code=503, content={"detail": "Unavailable"},
                                headers={"Cache-Control": "no-store"})
        if not payload.get("authorized"):
            return denied
        return JSONResponse(status_code=200, content={"entries": payload["entries"]},
                            headers={"Cache-Control": "no-store"})

    return app


async def proof(owner) -> None:
    import psycopg
    from psycopg.conninfo import make_conninfo
    from httpx import ASGITransport, AsyncClient

    create_http_function(owner)
    tenant_a, tenant_b = uuid4(), uuid4()
    member, other, admin, master = [uuid4() for _ in range(4)]
    entry_member, entry_other, entry_b = [uuid4() for _ in range(3)]
    for uid, is_master in ((member, False), (other, False), (admin, False),
                           (master, True)):
        owner.execute(
            "INSERT INTO m40650.users(id,status,is_master) VALUES (%s,'ACTIVE',%s)",
            (uid, is_master),
        )
    for uid, tenant, role in (
        (member, tenant_a, "TENANT_MEMBER"),
        (member, tenant_b, "TENANT_MEMBER"),
        (other, tenant_a, "TENANT_MEMBER"),
        (admin, tenant_a, "TENANT_ADMIN"),
        (master, tenant_a, "TENANT_MEMBER"),
    ):
        owner.execute(
            "INSERT INTO m40650.memberships VALUES (%s,%s,%s,'ATIVA')",
            (uid, tenant, role),
        )
    for eid, tenant, uid, amount in (
        (entry_member, tenant_a, member, 150),
        (entry_other, tenant_a, other, 250),
        (entry_b, tenant_b, member, 350),
    ):
        owner.execute(
            "INSERT INTO m40650.entries VALUES (%s,%s,%s,%s)",
            (eid, tenant, uid, amount),
        )

    tokens: dict[str, str] = {}
    now = datetime.now(timezone.utc)
    for name, uid, role, tenant, expiry, revoked in (
        ("member", member, "TENANT_MEMBER", tenant_a, now+timedelta(hours=1), None),
        ("other", other, "TENANT_MEMBER", tenant_a, now+timedelta(hours=1), None),
        ("admin", admin, "TENANT_ADMIN", tenant_a, now+timedelta(hours=1), None),
        ("master", master, "MASTER", None, now+timedelta(hours=1), None),
        ("master_member", master, "TENANT_MEMBER", tenant_a, now+timedelta(hours=1), None),
        ("expired", member, "TENANT_MEMBER", tenant_a, now-timedelta(seconds=5), None),
        ("revoked", member, "TENANT_MEMBER", tenant_a, now+timedelta(hours=1), now),
    ):
        raw = secrets.token_urlsafe(40)
        tokens[name] = raw
        owner.execute(
            "INSERT INTO m40650.sessions VALUES (%s,%s,%s,%s,%s,%s)",
            (sha256(raw.encode("utf-8")).hexdigest(), uid, role, tenant, expiry, revoked),
        )

    app_dsn = make_conninfo(
        os.environ["CI_M40670_DATABASE_URL"],
        user="m40650_ci_login",
        password="synthetic-only-m40650-ci-not-a-real-credential",
    )
    app = make_app(app_dsn)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        async def get(token: str | None, tenant=tenant_a, **headers):
            auth = {"Authorization": "Bearer " + token} if token is not None else {}
            auth.update(headers)
            return await c.get(f"/m40670/tenants/{tenant}/entries", headers=auth)

        async def ids(token, tenant=tenant_a, **headers):
            response = await get(token, tenant, **headers)
            assert response.status_code == 200
            assert response.headers["cache-control"] == "no-store"
            # Never echo bearer tokens or hashed tokens to the response.
            assert token not in response.text
            return {x["id"] for x in response.json()["entries"]}

        assert await ids(tokens["member"]) == {str(entry_member)}
        assert await ids(tokens["other"]) == {str(entry_other)}
        assert await ids(tokens["admin"]) == {str(entry_member), str(entry_other)}
        assert await ids(tokens["master_member"]) == set()
        assert await ids(tokens["member"], X_Role="TENANT_ADMIN", X_Tenant=str(tenant_b)) == {str(entry_member)}
        assert (await get(tokens["member"], tenant_b)).status_code == 401
        assert (await get(tokens["admin"], tenant_b)).status_code == 401
        assert (await get(tokens["master"])).status_code == 401
        assert (await get(tokens["expired"])).status_code == 401
        assert (await get(tokens["revoked"])).status_code == 401
        assert (await get(None)).status_code == 401
        assert (await get(secrets.token_urlsafe(40))).status_code == 401
        assert (await get("short")).status_code == 401
        assert (await get(tokens["member"], "not-a-uuid")).status_code == 401
        print("M40670_HTTP_BEARER_TENANT_ROLE_SEPARATION=PASS")

        # The SQL application role must not have direct table access.
        with psycopg.connect(app_dsn, autocommit=True) as conn:
            conn.execute("SET ROLE m40650_app")
            for table in ("users", "sessions", "memberships", "entries"):
                assert not conn.execute(
                    "SELECT pg_catalog.has_table_privilege(%s,%s,'SELECT')",
                    ("m40650_app", "m40650." + table),
                ).fetchone()[0]
        print("M40670_SQL_APP_DIRECT_READ_DENIED=PASS")

        owner.execute("UPDATE m40650.users SET status='SUSPENDED' WHERE id=%s", (member,))
        assert (await get(tokens["member"])).status_code == 401
        owner.execute("UPDATE m40650.users SET status='ACTIVE' WHERE id=%s", (member,))
        assert await ids(tokens["member"]) == {str(entry_member)}
        owner.execute(
            "UPDATE m40650.memberships SET status='DESLIGADA' "
            "WHERE user_id=%s AND tenant_id=%s", (member, tenant_a)
        )
        assert (await get(tokens["member"])).status_code == 401
        print("M40670_HTTP_REVOCATION_ACCOUNT_MEMBERSHIP=PASS")

    print("M40670_SYNTHETIC_HTTP_ONLY=YES")
    print("M40670_REAL_FASTAPI_ROUTES=NOT_MODIFIED")
    print("M40670_BEARER_SQL_LOG_RISK=UNRESOLVED")
    print("M40670_EXISTING_GUC_RISK=NOT_REMEDIATED")


def main() -> int:
    print("=== FR FINANCE M40670 — HTTP BEARER PG18 SYNTHETIC ===")
    try:
        require_disposable()
        # No DB driver imported or connection attempted until exact gate.
        import asyncio
        import psycopg
        with psycopg.connect(os.environ["CI_M40670_DATABASE_URL"], autocommit=True) as owner:
            asyncio.run(proof(owner))
    except Exception as exc:
        import traceback
        frames = traceback.extract_tb(exc.__traceback__)
        if frames:
            last = frames[-1]
            print("M40670_FAILURE_SITE=" + last.name + ":" + str(last.lineno))
        print("M40670_STATUS=BLOCKED_" + type(exc).__name__)
        return 2
    finally:
        print("M40670_ORIGINAL_PG_5433=NOT_ACCESSED")
        print("M40670_MIGRATIONS=NONE")
        print("M40670_LOCAL_DB_WRITES=NONE")
        print("M40670_SERVICE_RESTARTS=NONE")
        print("M40670_PIX_REAL=OFF")
        print("M40670_PAGAMENTOS_REAIS=OFF")
        print("M40670_ATIVACAO_REAL=OFF")
        print("M40670_PRODUCTION=BLOCKED")
    print("M40670_STATUS=PASS_DISPOSABLE_HTTP_PROTOTYPE_ONLY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
