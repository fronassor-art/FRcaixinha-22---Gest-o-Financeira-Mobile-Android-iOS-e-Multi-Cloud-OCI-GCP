#!/usr/bin/env python3
"""M40910: SQL113 read-only replacement gateway in disposable PG18 ONLY.

M40900 revokes app-role SQL113 SELECT, column INSERT and old GUC function
EXECUTE; this fixture then tests a token-bound, NOLOGIN-owner read broker.
Not a live schema migration, HTTP integration, credential rollout or GO.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from hashlib import sha256
import os
import secrets
import sys
from urllib.parse import urlsplit
from uuid import uuid4

DB="fr_m39067_disposable_ci"
PORT=55433
FUNC="m40910.read_new_admin_offers(text,uuid)"
TABLE="public.platform_saas_promotion_revisions"
APP="frcaixinha_app_role"
OWNER="m40910_broker_owner"


def require_disposable() -> None:
    values={
        "GITHUB_ACTIONS":"true",
        "CI_M40910_DISPOSABLE":"1",
        "CI_M40900_DISPOSABLE":"1",
        "CI_M40560_DISPOSABLE":"1",
        "FRCAIXINHA_CI_ISOLATED":"1",
        "PIX_REAL":"OFF",
        "PAGAMENTOS_REAIS":"OFF",
        "ATIVACAO_REAL":"OFF",
    }
    if any(os.environ.get(k)!=v for k,v in values.items()):
        raise RuntimeError("M40910_GITHUB_DISPOSABLE_ONLY")
    try:
        parsed=urlsplit(os.environ.get("CI_PROMOTIONS_DATABASE_URL",""))
        if (parsed.scheme!="postgresql" or parsed.hostname!="127.0.0.1"
                or parsed.port!=PORT or parsed.path!="/"+DB
                or parsed.username!="postgres" or not parsed.password
                or parsed.query or parsed.fragment):
            raise ValueError("bad disposable target")
    except (ValueError, TypeError, AttributeError):
        raise RuntimeError("M40910_DISPOSABLE_DB_IDENTITY_DENIED") from None


def create_broker(conn) -> None:
    """All DDL is restricted to the GitHub disposable PostgreSQL container."""
    conn.execute("CREATE ROLE m40910_broker_owner NOLOGIN NOINHERIT NOBYPASSRLS")
    conn.execute(
        "CREATE ROLE m40910_ci_login LOGIN NOINHERIT NOBYPASSRLS "
        "PASSWORD 'synthetic-m40910-only-no-real-secret'"
    )
    conn.execute("GRANT frcaixinha_app_role TO m40910_ci_login")
    conn.execute("CREATE SCHEMA m40910 AUTHORIZATION m40910_broker_owner")
    conn.execute("REVOKE ALL ON SCHEMA m40910 FROM PUBLIC")
    conn.execute("GRANT USAGE ON SCHEMA m40910 TO frcaixinha_app_role")
    conn.execute("""
      CREATE TABLE m40910.sessions(
        token_digest text PRIMARY KEY,
        user_id uuid NOT NULL,
        active_role text NOT NULL,
        tenant_id uuid NOT NULL,
        expires_at timestamptz NOT NULL,
        revoked_at timestamptz
      )
    """)
    conn.execute("ALTER TABLE m40910.sessions OWNER TO m40910_broker_owner")
    conn.execute("REVOKE ALL ON m40910.sessions FROM PUBLIC,frcaixinha_app_role")
    # FORCE RLS on SQL113 requires explicit broker SELECT policy.
    # The broker itself is NOLOGIN with no membership granted to app.
    conn.execute(
        "GRANT SELECT ON public.platform_saas_promotion_revisions "
        "TO m40910_broker_owner"
    )
    conn.execute(
        "CREATE POLICY m40910_broker_read "
        "ON public.platform_saas_promotion_revisions "
        "FOR SELECT TO m40910_broker_owner USING (true)"
    )
    conn.execute(
        "GRANT SELECT ON public.tenants, public.saas_subscription_preparations, "
        "public.saas_license_entitlements TO m40910_broker_owner"
    )
    conn.execute("""
      CREATE FUNCTION m40910.read_new_admin_offers(p_token text, p_tenant uuid)
      RETURNS TABLE(campaign_id uuid, promotional_price numeric)
      LANGUAGE plpgsql SECURITY DEFINER
      SET search_path=pg_catalog,pg_temp
      AS $body$
      DECLARE actor uuid;
      BEGIN
        IF p_token IS NULL OR pg_catalog.length(p_token)<32 OR p_tenant IS NULL
           OR pg_catalog.length(p_token)>256 THEN
          RETURN;
        END IF;
        -- No app.current_* GUC is an authorization input.
        SELECT s.user_id INTO actor
        FROM m40910.sessions AS s
        JOIN public.tenants AS t
          ON t.id=s.tenant_id
         AND t.admin_user_id=s.user_id
         AND t.status='ATIVO'
        WHERE s.token_digest=pg_catalog.encode(
             pg_catalog.sha256(pg_catalog.convert_to(p_token,'UTF8')),'hex')
          AND s.active_role='TENANT_ADMIN'
          AND s.tenant_id=p_tenant
          AND s.expires_at>pg_catalog.clock_timestamp()
          AND s.revoked_at IS NULL
          AND NOT EXISTS (
             SELECT 1 FROM public.saas_subscription_preparations p
              WHERE p.admin_user_id=s.user_id
          )
          AND NOT EXISTS (
             SELECT 1 FROM public.saas_license_entitlements l
              WHERE l.tenant_id=s.tenant_id
          );
        IF NOT FOUND THEN RETURN; END IF;
        RETURN QUERY
          SELECT latest.campaign_id,latest.promotional_price
          FROM (
             SELECT DISTINCT ON (p.campaign_id)
                    p.campaign_id,p.promotional_price,p.state,
                    p.starts_at,p.ends_at
             FROM public.platform_saas_promotion_revisions AS p
             ORDER BY p.campaign_id,p.revision DESC
          ) AS latest
          WHERE latest.state='PUBLISHED'
            AND latest.starts_at<=pg_catalog.clock_timestamp()
            AND latest.ends_at>pg_catalog.clock_timestamp()
          ORDER BY latest.campaign_id;
      END;
      $body$
    """)
    conn.execute(
        "ALTER FUNCTION m40910.read_new_admin_offers(text,uuid) "
        "OWNER TO m40910_broker_owner"
    )
    conn.execute(f"REVOKE ALL ON FUNCTION {FUNC} FROM PUBLIC")
    conn.execute(f"GRANT EXECUTE ON FUNCTION {FUNC} TO {APP}")


def proof(conn) -> None:
    from m40900_sql113_acl_fence_disposable import run as m40900_fence
    m40900_fence(conn)
    create_broker(conn)
    tenant_a,admin_a=conn.execute(
        "SELECT id,admin_user_id FROM public.tenants "
        "ORDER BY id LIMIT 1"
    ).fetchone()
    tenant_b,admin_b=conn.execute(
        "SELECT id,admin_user_id FROM public.tenants "
        "WHERE id<>%s",(tenant_a,)
    ).fetchone()
    campaign,price=conn.execute(
        "SELECT campaign_id,promotional_price "
        "FROM public.platform_saas_promotion_revisions "
        "WHERE state='PUBLISHED' ORDER BY revision DESC LIMIT 1"
    ).fetchone()
    assert price==Decimal("490.33")
    now=datetime.now(timezone.utc)

    tokens={}
    def issue(name,user,role,tenant,until=None,revoked=None):
        token=secrets.token_urlsafe(40)
        tokens[name]=token
        conn.execute(
          "INSERT INTO m40910.sessions "
          "(token_digest,user_id,active_role,tenant_id,expires_at,revoked_at) "
          "VALUES (%s,%s,%s,%s,%s,%s)",
          (sha256(token.encode()).hexdigest(),user,role,tenant,
           until or now+timedelta(minutes=30),revoked),
        )

    issue("admin",admin_a,"TENANT_ADMIN",tenant_a)
    issue("other",admin_b,"TENANT_ADMIN",tenant_b)
    issue("member",admin_a,"TENANT_MEMBER",tenant_a)
    issue("wrong_tenant",admin_a,"TENANT_ADMIN",tenant_b)
    issue("expired",admin_a,"TENANT_ADMIN",tenant_a,now-timedelta(seconds=1))
    issue("revoked",admin_a,"TENANT_ADMIN",tenant_a,revoked=now)

    import psycopg
    from psycopg.conninfo import make_conninfo
    db_url=make_conninfo(
        os.environ["CI_PROMOTIONS_DATABASE_URL"],
        user="m40910_ci_login",
        password="synthetic-m40910-only-no-real-secret",
    )
    with psycopg.connect(db_url,autocommit=True) as app:
        app.execute("SET ROLE frcaixinha_app_role")
        assert app.execute("SELECT session_user").fetchone()[0]=="m40910_ci_login"
        assert app.execute("SELECT current_user").fetchone()[0]==APP
        assert not app.execute(
           "SELECT pg_catalog.pg_has_role('m40910_ci_login',"
           "'m40910_broker_owner','MEMBER')"
        ).fetchone()[0]

        def deny(statement,label):
            try:
                with app.transaction():
                    app.execute(statement)
            except psycopg.Error as exc:
                if exc.sqlstate!="42501":
                    raise AssertionError("M40910_UNEXPECTED_SQLSTATE_"+label) from exc
                print("M40910_"+label+"=DENIED_42501")
            else:
                raise AssertionError("M40910_UNAUTHORIZED_ACCESS_"+label)

        deny(f"SELECT * FROM {TABLE}","DIRECT_PROMOTION_TABLE")
        deny("SELECT * FROM m40910.sessions","DIRECT_TOKEN_DIGESTS")
        deny(
            "SELECT * FROM public.frfinance_saas_new_admin_published_promotions()",
            "LEGACY_GUC_DEFINER",
        )
        deny("SET ROLE m40910_broker_owner","BROKER_ROLE_ESCALATION")
        assert not app.execute(
            "SELECT has_table_privilege('frcaixinha_app_role',%s,'SELECT')",
            (TABLE,),
        ).fetchone()[0]
        assert not app.execute(
            "SELECT has_table_privilege('frcaixinha_app_role',"
            "'m40910.sessions','SELECT')"
        ).fetchone()[0]

        def visible(token,tenant):
            return app.execute(
              "SELECT campaign_id,promotional_price FROM "
              "m40910.read_new_admin_offers(%s,%s)",
              (token,tenant),
            ).fetchall()

        # Valid tenant admins retain read-only SaaS offer after ACL fence.
        assert visible(tokens["admin"],tenant_a)==[(campaign,price)]
        assert visible(tokens["other"],tenant_b)==[(campaign,price)]
        print("M40910_ADMIN_LEGITIMATE_OFFER=RESTORED_VIA_TOKEN_ONLY")
        assert visible(tokens["member"],tenant_a)==[]
        assert visible(tokens["wrong_tenant"],tenant_b)==[]
        assert visible(tokens["expired"],tenant_a)==[]
        assert visible(tokens["revoked"],tenant_a)==[]
        assert visible(tokens["admin"],tenant_b)==[]
        assert visible(secrets.token_urlsafe(40),tenant_a)==[]
        print("M40910_EXPIRED_REVOKED_MEMBER_CROSS_TENANT=DENIED")

        # Arbitrary app GUCs cannot substitute for a valid independent token.
        for key,value in (
            ("app.current_role","TENANT_ADMIN"),
            ("app.current_user_id",str(admin_a)),
            ("app.current_tenant_id",str(tenant_a)),
        ):
            app.execute("SELECT set_config(%s,%s,false)",(key,value))
        assert visible(tokens["member"],tenant_a)==[]
        assert visible(secrets.token_urlsafe(40),tenant_a)==[]
        assert visible(tokens["admin"],tenant_a)==[(campaign,price)]
        deny(f"SELECT count(*) FROM {TABLE}","GUC_FORGED_TABLE_READ")
        print("M40910_SQL_GUC_SPOOF_CANNOT_WIDEN_BROKER=PASS")

        # Prepared admin already enrolled may not read new-admin promos.
        conn.execute(
            "INSERT INTO public.saas_subscription_preparations "
            "(admin_user_id) VALUES (%s)",(admin_a,)
        )
        assert visible(tokens["admin"],tenant_a)==[]
        conn.execute("DELETE FROM public.saas_subscription_preparations")
        assert visible(tokens["admin"],tenant_a)==[(campaign,price)]
        print("M40910_EXISTING_ADMIN_ELIGIBILITY=ENFORCED")

        # Immediate session revocation is checked within each SQL call.
        conn.execute(
            "UPDATE m40910.sessions SET revoked_at=%s "
            "WHERE token_digest=%s",
            (datetime.now(timezone.utc),sha256(tokens["admin"].encode()).hexdigest()),
        )
        assert visible(tokens["admin"],tenant_a)==[]
        print("M40910_LIVE_REVOCATION=ENFORCED")

        # Traded-off risk: bearer theft is still a complete read capability.
        assert visible(tokens["other"],tenant_b)==[(campaign,price)]
        print("M40910_STOLEN_VALID_BEARER=NOT_MITIGATED_NO_GO")
        print("M40910_HTTP_RUNTIME_INTEGRATION=NOT_IMPLEMENTED")
        print("M40910_LEGACY_MASTER_WRITES=STILL_DISABLED")
        print("M40910_REAL_SQL113_SCHEMA=NOT_CHANGED")


def main() -> int:
    try:
        require_disposable()
        from m40900_sql113_acl_fence_disposable import (
            require_disposable as verify_fence,
        )
        verify_fence()
        from m39067_postgres18_disposable_runtime import restricted_connection
        with restricted_connection() as conn:
            proof(conn)
    except Exception as exc:
        import traceback
        frame=traceback.extract_tb(exc.__traceback__)[-1]
        print("M40910_FAILURE_SITE="+frame.name+":"+str(frame.lineno))
        print("M40910_STATUS=BLOCKED_"+type(exc).__name__)
        return 2
    finally:
        print("M40910_ORIGINAL_TERMUX_PG_5433=NOT_ACCESSED")
        print("M40910_FR_CAIXINHA_2_2=NOT_ACCESSED")
        print("M40910_LOCAL_MIGRATIONS=NONE")
        print("M40910_LOCAL_DB_WRITES=NONE")
        print("M40910_SERVICE_RESTARTS=NONE")
        print("M40910_PIX_REAL=OFF")
        print("M40910_PAGAMENTOS_REAIS=OFF")
        print("M40910_ATIVACAO_REAL=OFF")
        print("M40910_PRODUCTION=BLOCKED")
    print("M40910_STATUS=PASS_DISPOSABLE_TOKEN_ONLY_SAAS_READ")
    return 0

if __name__=="__main__":
    sys.exit(main())
