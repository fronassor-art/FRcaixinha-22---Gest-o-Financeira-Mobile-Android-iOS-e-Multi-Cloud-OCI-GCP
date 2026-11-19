#!/usr/bin/env python3
"""M40680: isolated digest->one-use ticket->SQL read experiment, PG18 CI ONLY.

No original PostgreSQL, no deployment. The bearer never enters SQL parameters.
Both the digest (auth-side) and single-use ticket (financial-side) remain
sensitive credentials; this fixture does NOT solve production security.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import os
import re
import secrets
import sys
from urllib.parse import urlsplit
from uuid import UUID, uuid4

DB = "fr_m40680_disposable_ci"
PORT = 55437
TOKEN = re.compile(r"[A-Za-z0-9_-]{40,128}\Z")


def gate() -> None:
    for k, v in {
        "GITHUB_ACTIONS": "true",
        "CI_M40680_DISPOSABLE": "1",
        "FRCAIXINHA_CI_ISOLATED": "1",
        "PIX_REAL": "OFF",
        "PAGAMENTOS_REAIS": "OFF",
        "ATIVACAO_REAL": "OFF",
    }.items():
        if os.environ.get(k) != v:
            raise RuntimeError("M40680_DISPOSABLE_ONLY")
    try:
        p = urlsplit(os.environ.get("CI_M40680_DATABASE_URL", ""))
        if (p.scheme != "postgresql" or p.hostname != "127.0.0.1"
                or p.port != PORT or p.path != "/" + DB
                or p.username != "postgres" or not p.password
                or p.query or p.fragment):
            raise RuntimeError("M40680_WRONG_DATABASE_IDENTITY")
    except (ValueError, AttributeError) as exc:
        raise RuntimeError("M40680_WRONG_DATABASE_IDENTITY") from exc


def bootstrap(conn) -> None:
    from m40650_token_bound_gateway_disposable import schema
    schema(conn)
    conn.execute("CREATE ROLE m40680_auth NOLOGIN NOINHERIT NOBYPASSRLS")
    conn.execute(
        "CREATE ROLE m40680_auth_login LOGIN NOINHERIT NOBYPASSRLS "
        "PASSWORD 'm40680-fixture-auth-only-not-real'"
    )
    conn.execute("GRANT m40680_auth TO m40680_auth_login")
    conn.execute("GRANT USAGE ON SCHEMA m40650 TO m40680_auth")
    # The old bearer-reading function is intentionally not callable by app.
    conn.execute("REVOKE EXECUTE ON FUNCTION m40650.read_entries(text,uuid) "
                 "FROM PUBLIC, m40650_app")
    conn.execute("""
        CREATE TABLE m40650.m40680_tickets(
            digest text PRIMARY KEY,
            session_digest text NOT NULL,
            tenant_id uuid NOT NULL,
            expires_at timestamptz NOT NULL,
            used_at timestamptz
        )
    """)
    conn.execute("ALTER TABLE m40650.m40680_tickets OWNER TO m40650_owner")
    conn.execute("REVOKE ALL ON m40650.m40680_tickets "
                 "FROM PUBLIC, m40650_app, m40680_auth")
    conn.execute("""
        CREATE FUNCTION m40650.m40680_issue(p_digest text, p_tenant uuid)
        RETURNS text LANGUAGE plpgsql SECURITY DEFINER
        SET search_path=pg_catalog,pg_temp
        AS $body$
        DECLARE v_ticket text;
        BEGIN
          IF p_digest IS NULL OR length(p_digest)<>64 OR p_tenant IS NULL
            OR p_digest !~ '^[0-9a-f]{64}$' THEN RETURN NULL; END IF;
          PERFORM 1 FROM m40650.sessions AS s
            JOIN m40650.users AS u ON u.id=s.user_id AND u.status='ACTIVE'
            JOIN m40650.memberships AS m
              ON m.user_id=s.user_id AND m.tenant_id=s.active_tenant_id
             AND m.role=s.active_role AND m.status='ATIVA'
          WHERE s.token_digest=p_digest AND s.revoked_at IS NULL
            AND s.expires_at>pg_catalog.clock_timestamp()
            AND s.active_role IN ('TENANT_MEMBER','TENANT_ADMIN')
            AND s.active_tenant_id=p_tenant;
          IF NOT FOUND THEN RETURN NULL; END IF;
          v_ticket=pg_catalog.encode(pg_catalog.gen_random_bytes(32),'hex');
          INSERT INTO m40650.m40680_tickets
            (digest,session_digest,tenant_id,expires_at)
          VALUES (
            pg_catalog.encode(
              pg_catalog.sha256(pg_catalog.convert_to(v_ticket,'UTF8')),'hex'),
            p_digest,p_tenant,pg_catalog.clock_timestamp()+interval '30 seconds'
          );
          RETURN v_ticket;
        END
        $body$
    """)
    conn.execute("ALTER FUNCTION m40650.m40680_issue(text,uuid) "
                 "OWNER TO m40650_owner")
    conn.execute("REVOKE ALL ON FUNCTION m40650.m40680_issue(text,uuid) "
                 "FROM PUBLIC, m40650_app")
    conn.execute("GRANT EXECUTE ON FUNCTION m40650.m40680_issue(text,uuid) "
                 "TO m40680_auth")
    conn.execute("""
        CREATE FUNCTION m40650.m40680_consume(p_ticket text,p_tenant uuid)
        RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER
        SET search_path=pg_catalog,pg_temp
        AS $body$
        DECLARE v_digest text;
                v_user uuid;
                v_role text;
                v_entries jsonb;
        BEGIN
          IF p_ticket IS NULL OR length(p_ticket)<>64 OR p_tenant IS NULL
             OR p_ticket !~ '^[0-9a-f]{64}$' THEN
            RETURN pg_catalog.jsonb_build_object('authorized',false);
          END IF;
          -- UPDATE takes a row lock; exactly one invocation can consume.
          UPDATE m40650.m40680_tickets AS t
             SET used_at=pg_catalog.clock_timestamp()
          WHERE t.digest=pg_catalog.encode(
               pg_catalog.sha256(pg_catalog.convert_to(p_ticket,'UTF8')),'hex')
            AND t.tenant_id=p_tenant AND t.used_at IS NULL
            AND t.expires_at>pg_catalog.clock_timestamp()
          RETURNING t.session_digest INTO v_digest;
          IF NOT FOUND THEN
            RETURN pg_catalog.jsonb_build_object('authorized',false);
          END IF;
          -- Re-check revocation, account and membership AFTER consumption.
          SELECT s.user_id,s.active_role INTO v_user,v_role
          FROM m40650.sessions AS s
            JOIN m40650.users AS u ON u.id=s.user_id AND u.status='ACTIVE'
            JOIN m40650.memberships AS m
              ON m.user_id=s.user_id AND m.tenant_id=s.active_tenant_id
             AND m.role=s.active_role AND m.status='ATIVA'
          WHERE s.token_digest=v_digest AND s.revoked_at IS NULL
            AND s.expires_at>pg_catalog.clock_timestamp()
            AND s.active_role IN ('TENANT_MEMBER','TENANT_ADMIN')
            AND s.active_tenant_id=p_tenant;
          IF NOT FOUND THEN
            RETURN pg_catalog.jsonb_build_object('authorized',false);
          END IF;
          SELECT COALESCE(pg_catalog.jsonb_agg(
            pg_catalog.jsonb_build_object('id',e.id,'amount',e.amount)
            ORDER BY e.id),'[]'::jsonb) INTO v_entries
          FROM m40650.entries AS e WHERE e.tenant_id=p_tenant
            AND (v_role='TENANT_ADMIN' OR e.user_id=v_user);
          RETURN pg_catalog.jsonb_build_object(
            'authorized',true,'entries',v_entries);
        END
        $body$
    """)
    conn.execute("ALTER FUNCTION m40650.m40680_consume(text,uuid) "
                 "OWNER TO m40650_owner")
    conn.execute("REVOKE ALL ON FUNCTION m40650.m40680_consume(text,uuid) "
                 "FROM PUBLIC, m40680_auth")
    conn.execute("GRANT EXECUTE ON FUNCTION m40650.m40680_consume(text,uuid) "
                 "TO m40650_app")


def connections():
    from psycopg.conninfo import make_conninfo
    dsn = os.environ["CI_M40680_DATABASE_URL"]
    return (
        make_conninfo(dsn,user="m40680_auth_login",
                      password="m40680-fixture-auth-only-not-real"),
        make_conninfo(dsn,user="m40650_ci_login",
                      password="synthetic-only-m40650-ci-not-a-real-credential"),
    )


def make_app(auth_dsn: str, app_dsn: str):
    import psycopg
    from fastapi import FastAPI, Header
    from fastapi.responses import JSONResponse

    app = FastAPI(title="M40680 independent synthetic HTTP")
    @app.get("/m40680/tenants/{tenant_id}/entries")
    def read(tenant_id: str, authorization: str | None = Header(default=None)):
        denied = JSONResponse(status_code=401,content={"detail":"Unauthorized"},
                              headers={"Cache-Control":"no-store"})
        if not authorization or not authorization.startswith("Bearer "):
            return denied
        raw = authorization[7:]
        if not TOKEN.fullmatch(raw):
            return denied
        try:
            tenant = UUID(tenant_id)
            if not tenant.int or str(tenant) != tenant_id:
                return denied
        except (TypeError, ValueError, AttributeError):
            return denied

        # Raw bearer is hashed in Python. No SQL statement receives 'raw'.
        digest = sha256(raw.encode("utf-8")).hexdigest()
        try:
            with psycopg.connect(auth_dsn,autocommit=True) as auth:
                auth.execute("SET ROLE m40680_auth")
                ticket = auth.execute(
                    "SELECT m40650.m40680_issue(%s,%s)",(digest,tenant)
                ).fetchone()[0]
            if not ticket:
                return denied
            with psycopg.connect(app_dsn,autocommit=True) as financial:
                financial.execute("SET ROLE m40650_app")
                payload = financial.execute(
                    "SELECT m40650.m40680_consume(%s,%s)",(ticket,tenant)
                ).fetchone()[0]
        except psycopg.Error:
            return JSONResponse(status_code=503,content={"detail":"Unavailable"},
                                headers={"Cache-Control":"no-store"})
        if not payload.get("authorized"):
            return denied
        return JSONResponse(status_code=200,content={"entries":payload["entries"]},
                            headers={"Cache-Control":"no-store"})
    return app


def denied(conn, query, args=()):
    import psycopg
    try:
        with conn.transaction():
            conn.execute(query,args)
    except psycopg.Error as exc:
        assert exc.sqlstate == "42501", "M40680_UNEXPECTED_SQLSTATE"
    else:
        raise AssertionError("M40680_UNEXPECTED_PRIVILEGE")


async def proof(owner):
    import psycopg
    from httpx import ASGITransport,AsyncClient
    bootstrap(owner)
    ta,tb=uuid4(),uuid4()
    member,other,admin,master=[uuid4() for _ in range(4)]
    e1,e2,e3=[uuid4() for _ in range(3)]
    for u,master_flag in ((member,False),(other,False),(admin,False),(master,True)):
        owner.execute("INSERT INTO m40650.users VALUES (%s,'ACTIVE',%s)",(u,master_flag))
    for u,t,r in (
        (member,ta,"TENANT_MEMBER"),(member,tb,"TENANT_MEMBER"),
        (other,ta,"TENANT_MEMBER"),(admin,ta,"TENANT_ADMIN"),
        (master,ta,"TENANT_MEMBER"),
    ):
        owner.execute("INSERT INTO m40650.memberships VALUES (%s,%s,%s,'ATIVA')",(u,t,r))
    for entry,t,u,n in ((e1,ta,member,120),(e2,ta,other,240),(e3,tb,member,360)):
        owner.execute("INSERT INTO m40650.entries VALUES (%s,%s,%s,%s)",(entry,t,u,n))
    now=datetime.now(timezone.utc)
    tokens={}
    for name,u,role,t,expire,revoked in (
        ("member",member,"TENANT_MEMBER",ta,now+timedelta(hours=1),None),
        ("other",other,"TENANT_MEMBER",ta,now+timedelta(hours=1),None),
        ("admin",admin,"TENANT_ADMIN",ta,now+timedelta(hours=1),None),
        ("master",master,"MASTER",None,now+timedelta(hours=1),None),
        ("master_member",master,"TENANT_MEMBER",ta,now+timedelta(hours=1),None),
        ("expired",member,"TENANT_MEMBER",ta,now-timedelta(hours=1),None),
        ("revoked",member,"TENANT_MEMBER",ta,now+timedelta(hours=1),now),
    ):
        token=secrets.token_urlsafe(40)
        tokens[name]=token
        owner.execute(
            "INSERT INTO m40650.sessions VALUES (%s,%s,%s,%s,%s,%s)",
            (sha256(token.encode()).hexdigest(),u,role,t,expire,revoked)
        )
    auth_dsn,app_dsn=connections()
    app=make_app(auth_dsn,app_dsn)
    async with AsyncClient(transport=ASGITransport(app=app),base_url="http://ci") as client:
        async def get(name,tenant=ta,**headers):
            h={"Authorization":"Bearer "+tokens[name]} if name else {}
            h.update(headers)
            return await client.get(
                f"/m40680/tenants/{tenant}/entries",headers=h
            )
        async def visible(name,tenant=ta,**headers):
            r=await get(name,tenant,**headers)
            assert r.status_code==200
            assert r.headers["cache-control"]=="no-store"
            assert tokens[name] not in r.text
            return {x["id"] for x in r.json()["entries"]}

        assert await visible("member")=={str(e1)}
        assert await visible("other")=={str(e2)}
        assert await visible("admin")=={str(e1),str(e2)}
        assert await visible("master_member")==set()
        assert await visible("member",X_Role="TENANT_ADMIN",X_Tenant=str(tb))=={str(e1)}
        for who,tenant in (("member",tb),("admin",tb),("master",ta),
                           ("expired",ta),("revoked",ta),(None,ta)):
            assert (await get(who,tenant)).status_code==401
        print("M40680_HTTP_DIGEST_AUTH_AND_TENANT_ISOLATION=PASS")

        # Independent connections and privileges, not SET ROLE from postgres.
        with psycopg.connect(auth_dsn,autocommit=True) as auth:
            auth.execute("SET ROLE m40680_auth")
            assert auth.execute("SELECT session_user").fetchone()[0]=="m40680_auth_login"
            denied(auth,"SELECT * FROM m40650.entries")
            denied(auth,"SELECT m40650.m40680_consume(%s,%s)",("0"*64,ta))
            ticket=auth.execute(
                "SELECT m40650.m40680_issue(%s,%s)",
                (sha256(tokens["member"].encode()).hexdigest(),ta)
            ).fetchone()[0]
            assert ticket and len(ticket)==64
        with psycopg.connect(app_dsn,autocommit=True) as financial:
            financial.execute("SET ROLE m40650_app")
            assert financial.execute("SELECT session_user").fetchone()[0]=="m40650_ci_login"
            for table in ("users","sessions","memberships","entries","m40680_tickets"):
                denied(financial,f"SELECT * FROM m40650.{table}")
            denied(financial,"SELECT m40650.m40680_issue(%s,%s)",("0"*64,ta))
            denied(financial,"SET ROLE m40650_owner")
            denied(financial,"SELECT m40650.read_entries(%s,%s)",("x"*64,ta))
            financial.execute("SELECT pg_catalog.set_config('app.current_role','MASTER',false)")
            first=financial.execute(
                "SELECT m40650.m40680_consume(%s,%s)",(ticket,ta)
            ).fetchone()[0]
            assert first["authorized"] is True
            assert {x["id"] for x in first["entries"]}=={str(e1)}
            again=financial.execute(
                "SELECT m40650.m40680_consume(%s,%s)",(ticket,ta)
            ).fetchone()[0]
            assert again["authorized"] is False
            wrong=financial.execute(
                "SELECT m40650.m40680_consume(%s,%s)",(ticket,tb)
            ).fetchone()[0]
            assert wrong["authorized"] is False
        print("M40680_SPLIT_SQL_ROLES_AND_ONE_TIME_REPLAY_DENIED=PASS")

        # An issued ticket is rejected after session revocation.
        with psycopg.connect(auth_dsn,autocommit=True) as auth:
            auth.execute("SET ROLE m40680_auth")
            ticket2=auth.execute("SELECT m40650.m40680_issue(%s,%s)",(
                sha256(tokens["member"].encode()).hexdigest(),ta
            )).fetchone()[0]
            ticket3=auth.execute("SELECT m40650.m40680_issue(%s,%s)",(
                sha256(tokens["other"].encode()).hexdigest(),ta
            )).fetchone()[0]
        owner.execute("UPDATE m40650.sessions SET revoked_at=pg_catalog.clock_timestamp() "
                      "WHERE token_digest=%s",
                      (sha256(tokens["member"].encode()).hexdigest(),))
        with psycopg.connect(app_dsn,autocommit=True) as f:
            f.execute("SET ROLE m40650_app")
            assert f.execute(
                "SELECT m40650.m40680_consume(%s,%s)",(ticket2,ta)
            ).fetchone()[0]["authorized"] is False
        owner.execute("UPDATE m40650.m40680_tickets "
                      "SET expires_at=pg_catalog.clock_timestamp()-interval '1 second' "
                      "WHERE digest=%s",
                      (sha256(ticket3.encode()).hexdigest(),))
        with psycopg.connect(app_dsn,autocommit=True) as f:
            f.execute("SET ROLE m40650_app")
            assert f.execute(
                "SELECT m40650.m40680_consume(%s,%s)",(ticket3,ta)
            ).fetchone()[0]["authorized"] is False
        assert (await get("member")).status_code==401
        print("M40680_REVOKED_SESSION_AND_EXPIRED_TICKET_DENIED=PASS")

    print("M40680_RAW_BEARER_SQL_PARAMETERS=NONE")
    print("M40680_DIGEST_AND_TICKET_LOG_RISK=NOT_REMEDIATED")
    print("M40680_REAL_FASTAPI_ROUTES=NOT_MODIFIED")
    print("M40680_EXISTING_GUC_SQL_RISK=NOT_REMEDIATED")


def main():
    print("=== FR FINANCE M40680 — DIGEST AND ONE-TIME SQL TICKET (CI) ===")
    try:
        gate()
        # Imports and any connection only AFTER disposable CI identity gate.
        import asyncio
        import psycopg
        with psycopg.connect(os.environ["CI_M40680_DATABASE_URL"],
                             autocommit=True) as owner:
            asyncio.run(proof(owner))
    except Exception as exc:
        import traceback
        stack=traceback.extract_tb(exc.__traceback__)
        if stack:
            print("M40680_FAILURE_SITE="+stack[-1].name+":"+str(stack[-1].lineno))
        print("M40680_STATUS=BLOCKED_"+type(exc).__name__)
        return 2
    finally:
        print("M40680_ORIGINAL_PG_5433=NOT_ACCESSED")
        print("M40680_LOCAL_DB_WRITES=NONE")
        print("M40680_LOCAL_MIGRATIONS=NONE")
        print("M40680_LOCAL_SERVICE_RESTARTS=NONE")
        print("M40680_PIX_REAL=OFF")
        print("M40680_PAGAMENTOS_REAIS=OFF")
        print("M40680_ATIVACAO_REAL=OFF")
        print("M40680_PRODUCTION=BLOCKED")
    print("M40680_STATUS=PASS_SYNTHETIC_ONLY_NOT_PRODUCTION")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
