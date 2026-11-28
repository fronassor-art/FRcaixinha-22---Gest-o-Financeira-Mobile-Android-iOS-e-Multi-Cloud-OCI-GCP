#!/usr/bin/env python3
"""M40921: SQL113 token-broker read/write role split in disposable PG18 only.

Maintains M40910's reader while replacing M40920's shared function owner
with a distinct NOLOGIN writer. NOT an API migration or production authorization.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from hashlib import sha256
import os
import secrets
import sys

READ_OWNER = "m40910_broker_owner"
WRITE_OWNER = "m40921_writer_owner"
APP = "frcaixinha_app_role"
TABLE = "public.platform_saas_promotion_revisions"
COLUMNS = (
    "campaign_id", "revision", "plan_tier", "billing_period",
    "base_price_version_id", "promotional_price", "audience",
    "title", "benefit_description", "starts_at", "ends_at",
    "state", "reason", "created_by",
)
DRAFT_FUNC = (
    "m40920.create_draft(text,character varying,character varying,uuid,"
    "numeric,text,text,timestamp with time zone,timestamp with time zone,text)"
)
TRANSITION_FUNC = "m40920.transition(text,uuid,integer,text,text)"


def require_disposable() -> None:
    from m40920_master_token_writes_disposable import require_disposable as prior
    prior()
    if os.environ.get("CI_M40921_DISPOSABLE") != "1":
        raise RuntimeError("M40921_GITHUB_DISPOSABLE_ONLY")


def split_broker_roles(conn) -> None:
    """Called only after inherited exact GitHub/PG18 identity guards."""
    conn.execute(
        "CREATE ROLE m40921_writer_owner NOLOGIN NOINHERIT NOBYPASSRLS"
    )
    conn.execute(
        "GRANT USAGE ON SCHEMA public,m40910,m40920 TO m40921_writer_owner"
    )
    conn.execute(
        "GRANT SELECT ON m40910.sessions,"
        "public.m40560_ci_master_allowlist,"
        "public.platform_license_plans,"
        "public.platform_license_price_versions "
        "TO m40921_writer_owner"
    )
    conn.execute(
        "GRANT SELECT ON public.platform_saas_promotion_revisions "
        "TO m40921_writer_owner"
    )
    conn.execute(
        "GRANT INSERT ("+",".join(COLUMNS)+") ON "
        +TABLE+" TO m40921_writer_owner"
    )
    conn.execute(
        "CREATE POLICY m40921_writer_read ON "+TABLE
        +" FOR SELECT TO m40921_writer_owner USING (true)"
    )
    conn.execute(
        "CREATE POLICY m40921_writer_append ON "+TABLE
        +" FOR INSERT TO m40921_writer_owner WITH CHECK (true)"
    )
    # Give the new writer independent ownership of its private audit trail.
    conn.execute("ALTER TABLE m40920.audit OWNER TO m40921_writer_owner")
    for fn in (DRAFT_FUNC,TRANSITION_FUNC):
        conn.execute("ALTER FUNCTION "+fn+" OWNER TO m40921_writer_owner")
        conn.execute("REVOKE ALL ON FUNCTION "+fn+" FROM PUBLIC")
        conn.execute("GRANT EXECUTE ON FUNCTION "+fn+" TO frcaixinha_app_role")

    # Original M40910 read broker must NOT keep M40920's accidental writes.
    conn.execute("REVOKE INSERT ("+",".join(COLUMNS)+") ON "
                 +TABLE+" FROM m40910_broker_owner")
    conn.execute("DROP POLICY m40920_broker_append ON "+TABLE)

    for column in COLUMNS:
        if conn.execute(
            "SELECT has_column_privilege(%s,%s,%s,'INSERT')",
            (READ_OWNER,TABLE,column),
        ).fetchone()[0]:
            raise AssertionError("M40921_READER_WRITE_GRANT_"+column)
        if not conn.execute(
            "SELECT has_column_privilege(%s,%s,%s,'INSERT')",
            (WRITE_OWNER,TABLE,column),
        ).fetchone()[0]:
            raise AssertionError("M40921_WRITER_GRANT_MISSING_"+column)
    if conn.execute(
        "SELECT has_table_privilege(%s,'m40920.audit','INSERT')",
        (READ_OWNER,),
    ).fetchone()[0]:
        raise AssertionError("M40921_READER_AUDIT_WRITE")
    if conn.execute(
        "SELECT has_function_privilege(%s,%s,'EXECUTE')",
        (READ_OWNER,DRAFT_FUNC),
    ).fetchone()[0]:
        raise AssertionError("M40921_READER_DRAFT_EXECUTE")
    if not conn.execute(
        "SELECT has_table_privilege(%s,'m40910.sessions','SELECT')",
        (WRITE_OWNER,),
    ).fetchone()[0]:
        raise AssertionError("M40921_WRITER_SESSION_READ_MISSING")
    if conn.execute(
        "SELECT pg_catalog.pg_has_role(%s,%s,'MEMBER')",
        (APP,WRITE_OWNER),
    ).fetchone()[0]:
        raise AssertionError("M40921_APP_MEMBERSHIP")
    print("M40921_READ_OWNER_WRITE_PRIVILEGES=REVOKED")
    print("M40921_WRITE_OWNER=ISOLATED_NOLOGIN_NOBYPASSRLS")


def proof(conn) -> None:
    from m40900_sql113_acl_fence_disposable import run as fence
    from m40920_master_token_writes_disposable import install_broker
    fence(conn)
    install_broker(conn)
    split_broker_roles(conn)

    master = conn.execute(
        "SELECT user_id FROM public.m40560_ci_master_allowlist"
    ).fetchone()[0]
    outsider = conn.execute(
        "SELECT id FROM public.users WHERE id<>%s LIMIT 1",(master,)
    ).fetchone()[0]
    tenant = conn.execute(
        "SELECT id FROM public.tenants WHERE admin_user_id=%s LIMIT 1",(master,)
    ).fetchone()[0]
    version = conn.execute(
        "SELECT id FROM public.platform_license_price_versions "
        "WHERE plan_tier='ESSENCIAL' ORDER BY created_at DESC,id DESC LIMIT 1"
    ).fetchone()[0]
    legacy_offer = conn.execute(
        "SELECT campaign_id,promotional_price "
        "FROM public.platform_saas_promotion_revisions "
        "WHERE state='PUBLISHED' ORDER BY revision DESC LIMIT 1"
    ).fetchone()
    now = datetime.now(timezone.utc)
    tokens = {}
    def issue(name,user,role,expired=False,revoked=False):
        token = secrets.token_urlsafe(40)
        tokens[name] = token
        conn.execute(
            "INSERT INTO m40910.sessions "
            "(token_digest,user_id,active_role,tenant_id,expires_at,revoked_at) "
            "VALUES (%s,%s,%s,%s,%s,%s)",
            (sha256(token.encode()).hexdigest(),user,role,tenant,
             now-timedelta(minutes=1) if expired else now+timedelta(minutes=30),
             now if revoked else None),
        )
    issue("admin",master,"TENANT_ADMIN")
    issue("master",master,"MASTER")
    issue("member",master,"TENANT_MEMBER")
    issue("outsider",outsider,"MASTER")
    issue("expired",master,"MASTER",expired=True)
    issue("revoked",master,"MASTER",revoked=True)

    import psycopg
    from psycopg.conninfo import make_conninfo
    dsn=make_conninfo(
        os.environ["CI_PROMOTIONS_DATABASE_URL"],
        user="m40910_ci_login",
        password="synthetic-m40910-only-no-real-secret",
    )
    with psycopg.connect(dsn,autocommit=True) as app:
        app.execute("SET ROLE frcaixinha_app_role")
        def deny(action,label,sqlstate="42501"):
            try:
                with app.transaction():
                    action()
            except psycopg.Error as exc:
                assert exc.sqlstate==sqlstate, (label,exc.sqlstate)
            else:
                raise AssertionError("M40921_UNAUTHORIZED_"+label)

        deny(lambda:app.execute("SET ROLE m40921_writer_owner"),
             "ASSUME_WRITER")
        deny(lambda:app.execute("SELECT * FROM m40910.sessions"),
             "READ_TOKENS")
        deny(lambda:app.execute("SELECT * FROM m40920.audit"),
             "READ_AUDIT")
        deny(lambda:app.execute("SELECT * FROM "+TABLE),
             "READ_PROMOTIONS")
        deny(lambda:app.execute("INSERT INTO "+TABLE+" DEFAULT VALUES"),
             "DIRECT_INSERT")
        read=app.execute(
            "SELECT campaign_id,promotional_price "
            "FROM m40910.read_new_admin_offers(%s,%s)",
            (tokens["admin"],tenant),
        ).fetchall()
        assert read==[legacy_offer],read
        print("M40921_READ_GATEWAY_SURVIVES_ROLE_SPLIT=PASS")

        draft_sql=(
            "SELECT * FROM m40920.create_draft("
            "%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"
        )
        def draft(token):
            return app.execute(draft_sql,(
                token,"ESSENCIAL","MONTHLY",version,Decimal("59.21"),
                "Oferta de ensaio","Beneficio sintetico de verificacao",
                now-timedelta(hours=1),now+timedelta(days=6),
                "Justificativa comercial em ambiente descartavel",
            )).fetchone()

        for label in ("member","outsider","expired","revoked"):
            deny(lambda x=label:draft(tokens[x]),"DRAFT_"+label)
        app.execute("SELECT set_config('app.current_role','MASTER',false)")
        app.execute(
            "SELECT set_config('app.current_user_id',%s,false)",(str(master),)
        )
        deny(lambda:draft(tokens["member"]),"FORGED_GUC")
        assert app.execute(
            "SELECT * FROM m40910.read_new_admin_offers(%s,%s)",
            (tokens["admin"],tenant),
        ).fetchall()==[legacy_offer]

        campaign,revision,state=draft(tokens["master"])
        assert (revision,state)==(1,"DRAFT")
        transition_sql="SELECT * FROM m40920.transition(%s,%s,%s,%s,%s)"
        def transition(token,expected,action):
            return app.execute(transition_sql,(
                token,campaign,expected,action,
                "Mudanca sintetica auditada e autorizada",
            )).fetchone()
        deny(lambda:transition(tokens["member"],1,"PUBLISH"),"MEMBER_PUBLISH")
        deny(lambda:transition(tokens["master"],4,"PUBLISH"),
             "STALE_REVISION","P0001")
        assert transition(tokens["master"],1,"PUBLISH")==(
            campaign,2,"PUBLISHED"
        )
        deny(lambda:transition(tokens["master"],1,"CANCEL"),
             "REVISION_REPLAY","P0001")
        assert transition(tokens["master"],2,"CANCEL")==(
            campaign,3,"CANCELED"
        )
        deny(lambda:transition(tokens["master"],3,"CANCEL"),
             "CANCEL_REPLAY","P0001")
        conn.execute(
            "UPDATE m40910.sessions SET revoked_at=pg_catalog.clock_timestamp() "
            "WHERE token_digest=%s",
            (sha256(tokens["master"].encode()).hexdigest(),),
        )
        deny(lambda:draft(tokens["master"]),"LIVE_REVOKED")
        assert conn.execute(
            "SELECT action,revision,actor_id FROM m40920.audit "
            "WHERE campaign_id=%s ORDER BY revision",(campaign,),
        ).fetchall()==[
            ("DRAFT",1,master),("PUBLISHED",2,master),("CANCELED",3,master)
        ]
        assert conn.execute(
            "SELECT state FROM public.platform_saas_promotion_revisions "
            "WHERE campaign_id=%s ORDER BY revision",(campaign,)
        ).fetchall()==[("DRAFT",),("PUBLISHED",),("CANCELED",)]
        print("M40921_MASTER_WRITES_AND_ATOMIC_AUDIT=PASS")
        print("M40921_REVOKED_AND_FORGED_MASTER=DENIED")
        print("M40921_STOLEN_VALID_MASTER_TOKEN=UNMITIGATED_NO_GO")
        print("M40921_REAL_SQL_ISSUER_AND_HTTP=NOT_INTEGRATED")


def main() -> int:
    try:
        require_disposable()
        from m39067_postgres18_disposable_runtime import restricted_connection
        with restricted_connection() as conn:
            proof(conn)
    except Exception as exc:
        import traceback
        frame=traceback.extract_tb(exc.__traceback__)[-1]
        print("M40921_FAILURE_SITE="+frame.name+":"+str(frame.lineno))
        print("M40921_STATUS=BLOCKED_"+type(exc).__name__)
        return 2
    finally:
        print("M40921_ORIGINAL_TERMUX_PG_5433=NOT_ACCESSED")
        print("M40921_ORIGINAL_ACL_CHANGES=NONE")
        print("M40921_LOCAL_MIGRATIONS=NONE")
        print("M40921_LOCAL_DB_WRITES=NONE")
        print("M40921_SERVICE_RESTARTS=NONE")
        print("M40921_PIX_REAL=OFF")
        print("M40921_PAGAMENTOS_REAIS=OFF")
        print("M40921_ATIVACAO_REAL=OFF")
        print("M40921_PRODUCTION=BLOCKED")
    print("M40921_STATUS=PASS_DISPOSABLE_ROLE_SPLIT_ONLY")
    return 0

if __name__=="__main__":
    sys.exit(main())
