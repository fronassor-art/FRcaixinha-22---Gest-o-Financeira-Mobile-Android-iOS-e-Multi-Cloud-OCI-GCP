#!/usr/bin/env python3
"""M40922: isolate token-session ownership from both SaaS broker roles.

Disposable GitHub PostgreSQL 18 ONLY. No real issuer or production migration.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from hashlib import sha256
import os
import secrets
import sys

SESSION_OWNER = "m40922_session_owner"
READER = "m40910_broker_owner"
WRITER = "m40921_writer_owner"
APP = "frcaixinha_app_role"

def require_disposable() -> None:
    from m40921_saas_broker_role_split_disposable import require_disposable as prior
    prior()
    if os.environ.get("CI_M40922_DISPOSABLE") != "1":
        raise RuntimeError("M40922_DISPOSABLE_ONLY")

def separate_session_custody(conn) -> None:
    """Synthetic DDL after all inherited CI identity guards."""
    conn.execute(
        "CREATE ROLE m40922_session_owner NOLOGIN NOINHERIT NOBYPASSRLS"
    )
    conn.execute("ALTER TABLE m40910.sessions OWNER TO m40922_session_owner")
    conn.execute("ALTER SCHEMA m40910 OWNER TO m40922_session_owner")
    conn.execute(
        "REVOKE ALL ON m40910.sessions FROM PUBLIC,frcaixinha_app_role,"
        "m40910_broker_owner,m40921_writer_owner"
    )
    conn.execute(
        "GRANT USAGE ON SCHEMA m40910 TO m40910_broker_owner,"
        "m40921_writer_owner,frcaixinha_app_role"
    )
    conn.execute(
        "GRANT SELECT ON m40910.sessions "
        "TO m40910_broker_owner,m40921_writer_owner"
    )
    owner=conn.execute(
        "SELECT pg_catalog.pg_get_userbyid(relowner) "
        "FROM pg_catalog.pg_class "
        "WHERE oid='m40910.sessions'::pg_catalog.regclass"
    ).fetchone()[0]
    schema_owner=conn.execute(
        "SELECT pg_catalog.pg_get_userbyid(nspowner) "
        "FROM pg_catalog.pg_namespace WHERE nspname='m40910'"
    ).fetchone()[0]
    assert owner==SESSION_OWNER and schema_owner==SESSION_OWNER
    for role in (READER,WRITER,APP):
        for privilege in ("INSERT","UPDATE","DELETE","TRUNCATE","REFERENCES","TRIGGER"):
            if conn.execute(
                "SELECT has_table_privilege(%s,'m40910.sessions',%s)",
                (role,privilege),
            ).fetchone()[0]:
                raise AssertionError("M40922_FORBIDDEN_"+role+"_"+privilege)
        if conn.execute(
            "SELECT pg_catalog.pg_has_role(%s,%s,'MEMBER')",
            (role,SESSION_OWNER),
        ).fetchone()[0]:
            raise AssertionError("M40922_CUSTODIAN_ROLE_MEMBERSHIP")
    for role in (READER,WRITER):
        assert conn.execute(
            "SELECT has_table_privilege(%s,'m40910.sessions','SELECT')",
            (role,),
        ).fetchone()[0]
    assert not conn.execute(
        "SELECT has_table_privilege(%s,'m40910.sessions','SELECT')",
        (APP,),
    ).fetchone()[0]
    print("M40922_SESSION_TABLE_AND_SCHEMA_OWNER=DETACHED")
    print("M40922_READER_WRITER_SESSION_DML=DENIED_CATALOG")

def proof(conn) -> None:
    from m40900_sql113_acl_fence_disposable import run as fence
    from m40920_master_token_writes_disposable import install_broker
    from m40921_saas_broker_role_split_disposable import split_broker_roles
    fence(conn)
    install_broker(conn)
    split_broker_roles(conn)
    separate_session_custody(conn)

    # Test actual PostgreSQL permissions under both NOLOGIN roles.
    import psycopg
    def deny_as_role(role,statement,label):
        conn.execute("SET ROLE "+role)
        try:
            try:
                with conn.transaction():
                    conn.execute(statement)
            except psycopg.Error as exc:
                assert exc.sqlstate=="42501",(label,exc.sqlstate)
            else:
                raise AssertionError("M40922_WRITE_ALLOWED_"+label)
        finally:
            conn.execute("RESET ROLE")
    for role in (READER,WRITER):
        for cmd in (
            "INSERT INTO m40910.sessions DEFAULT VALUES",
            "UPDATE m40910.sessions SET revoked_at=now()",
            "DELETE FROM m40910.sessions",
            "TRUNCATE m40910.sessions",
        ):
            deny_as_role(role,cmd,role+"_"+cmd.split()[0])
    print("M40922_READER_WRITER_SESSION_DML=DENIED_SQLSTATE_42501")

    # Synthetic issuer is the isolated PostgreSQL CI superuser, not app.
    master=conn.execute(
        "SELECT user_id FROM public.m40560_ci_master_allowlist"
    ).fetchone()[0]
    tenant=conn.execute(
        "SELECT id FROM public.tenants WHERE admin_user_id=%s LIMIT 1",
        (master,),
    ).fetchone()[0]
    version=conn.execute(
        "SELECT id FROM public.platform_license_price_versions "
        "WHERE plan_tier='ESSENCIAL' ORDER BY created_at DESC,id DESC LIMIT 1"
    ).fetchone()[0]
    campaign_read=conn.execute(
        "SELECT campaign_id,promotional_price "
        "FROM public.platform_saas_promotion_revisions "
        "WHERE state='PUBLISHED' ORDER BY revision DESC LIMIT 1"
    ).fetchone()
    now=datetime.now(timezone.utc)
    tokens={}
    def issue(label,role):
        token=secrets.token_urlsafe(40)
        tokens[label]=token
        conn.execute(
            "INSERT INTO m40910.sessions "
            "(token_digest,user_id,active_role,tenant_id,expires_at,revoked_at)"
            " VALUES (%s,%s,%s,%s,%s,NULL)",
            (sha256(token.encode()).hexdigest(),master,role,tenant,
             now+timedelta(minutes=30)),
        )
    issue("admin","TENANT_ADMIN")
    issue("master","MASTER")
    issue("member","TENANT_MEMBER")
    from psycopg.conninfo import make_conninfo
    dsn=make_conninfo(
        os.environ["CI_PROMOTIONS_DATABASE_URL"],
        user="m40910_ci_login",
        password="synthetic-m40910-only-no-real-secret",
    )
    with psycopg.connect(dsn,autocommit=True) as app:
        app.execute("SET ROLE frcaixinha_app_role")
        def deny(action,label):
            try:
                with app.transaction():
                    action()
            except psycopg.Error as exc:
                assert exc.sqlstate=="42501",(label,exc.sqlstate)
            else:
                raise AssertionError("M40922_UNAUTHORIZED_"+label)
        deny(lambda:app.execute(
            "INSERT INTO m40910.sessions DEFAULT VALUES"
        ),"APP_TOKEN_ISSUE")
        deny(lambda:app.execute("SET ROLE m40922_session_owner"),
             "APP_CUSTODIAN_ESCALATION")
        offers=app.execute(
            "SELECT campaign_id,promotional_price "
            "FROM m40910.read_new_admin_offers(%s,%s)",
            (tokens["admin"],tenant),
        ).fetchall()
        assert offers==[campaign_read],offers
        print("M40922_READER_WITHOUT_SESSION_OWNERSHIP=PASS")
        draft_sql="SELECT * FROM m40920.create_draft(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"
        def draft(token):
            return app.execute(draft_sql,(
                token,"ESSENCIAL","MONTHLY",version,Decimal("54.32"),
                "Oferta validada","Beneficio sintetico sem nenhuma cobranca",
                now-timedelta(minutes=1),now+timedelta(days=5),
                "Justificativa isolada com custodia de sessoes",
            )).fetchone()
        deny(lambda:draft(tokens["member"]),"MEMBER_CANNOT_MINT_MASTER")
        campaign,revision,state=draft(tokens["master"])
        assert (revision,state)==(1,"DRAFT")
        trans="SELECT * FROM m40920.transition(%s,%s,%s,%s,%s)"
        def transition(expected,action):
            return app.execute(trans,(
                tokens["master"],campaign,expected,action,
                "Mudanca autorizada em prova descartavel"
            )).fetchone()
        assert transition(1,"PUBLISH")==(
            campaign,2,"PUBLISHED"
        )
        assert transition(2,"CANCEL")==(
            campaign,3,"CANCELED"
        )
        conn.execute(
            "UPDATE m40910.sessions SET revoked_at=pg_catalog.clock_timestamp() "
            "WHERE token_digest=%s",
            (sha256(tokens["master"].encode()).hexdigest(),)
        )
        deny(lambda:draft(tokens["master"]),"REVOKED_TOKEN_REPLAY")
        assert conn.execute(
            "SELECT action,revision FROM m40920.audit "
            "WHERE campaign_id=%s ORDER BY revision",(campaign,),
        ).fetchall()==[("DRAFT",1),("PUBLISHED",2),("CANCELED",3)]
        print("M40922_WRITER_WITHOUT_SESSION_OWNERSHIP=PASS")
        print("M40922_SESSION_REVOCATION=ENFORCED")
        print("M40922_SQL_ISSUER_COMPROMISE=STILL_NO_GO")
        print("M40922_STOLEN_VALID_TOKEN=STILL_NO_GO")
        print("M40922_REAL_API_SESSION_ISSUER=NOT_INTEGRATED")

def main() -> int:
    try:
        require_disposable()
        from m39067_postgres18_disposable_runtime import restricted_connection
        with restricted_connection() as conn:
            proof(conn)
    except Exception as exc:
        import traceback
        frame=traceback.extract_tb(exc.__traceback__)[-1]
        print("M40922_FAILURE_SITE="+frame.name+":"+str(frame.lineno))
        print("M40922_STATUS=BLOCKED_"+type(exc).__name__)
        return 2
    finally:
        print("M40922_ORIGINAL_TERMUX_PG_5433=NOT_ACCESSED")
        print("M40922_ORIGINAL_ACL_CHANGES=NONE")
        print("M40922_MIGRATIONS=NONE")
        print("M40922_LOCAL_DB_WRITES=NONE")
        print("M40922_SERVICE_RESTARTS=NONE")
        print("M40922_PIX_REAL=OFF")
        print("M40922_PAGAMENTOS_REAIS=OFF")
        print("M40922_ATIVACAO_REAL=OFF")
        print("M40922_PRODUCTION=BLOCKED")
    print("M40922_STATUS=PASS_DISPOSABLE_SESSION_CUSTODY_ONLY")
    return 0

if __name__=="__main__":
    sys.exit(main())
