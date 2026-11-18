#!/usr/bin/env python3
"""FR Finance M40560: role-level SQL112/113 RLS on DISPOSABLE PG18 CI only.

No original Termux, production database, network provider, credential, or payment.
DDL/data modifications happen EXCLUSIVELY in the synthetic CI database :55433.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import os
from pathlib import Path
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
DB_NAME = "fr_m39067_disposable_ci"
DB_PORT = 55433


def require_disposable() -> None:
    if (os.environ.get("GITHUB_ACTIONS") != "true"
            or os.environ.get("CI_M40560_DISPOSABLE") != "1"
            or os.environ.get("FRCAIXINHA_CI_ISOLATED") != "1"
            or os.environ.get("PIX_REAL") != "OFF"
            or os.environ.get("PAGAMENTOS_REAIS") != "OFF"
            or os.environ.get("ATIVACAO_REAL") != "OFF"):
        raise RuntimeError("M40560_NOT_DISPOSABLE_GITHUB_CI")
    from psycopg.conninfo import conninfo_to_dict
    parsed = conninfo_to_dict(os.environ.get("CI_PROMOTIONS_DATABASE_URL", ""))
    if (parsed.get("host") != "127.0.0.1"
            or int(parsed.get("port", "0")) != DB_PORT
            or parsed.get("dbname") != DB_NAME
            or parsed.get("user") != "postgres"):
        raise RuntimeError("M40560_WRONG_DATABASE_TARGET")


def set_identity(conn, actor_role: str, actor_id: str, tenant_id: str = "") -> None:
    """Context is synthetic: independent app-role sessions, NOT real authentication."""
    conn.execute("RESET ROLE")
    conn.execute("SELECT set_config('app.current_role',%s,false)", (actor_role,))
    conn.execute("SELECT set_config('app.current_user_id',%s,false)", (actor_id,))
    conn.execute("SELECT set_config('app.current_tenant_id',%s,false)", (tenant_id,))
    conn.execute("SET ROLE frcaixinha_app_role")


def expect_denied(conn, statement: str, params: tuple, label: str) -> None:
    import psycopg
    try:
        with conn.transaction():
            conn.execute(statement, params)
    except psycopg.Error as exc:
        if exc.sqlstate != "42501":
            raise AssertionError(
                "M40560_DENIAL_WRONG_SQLSTATE_" + label + "_" + str(exc.sqlstate)
            ) from exc
        print("M40560_DENIED_" + label + "=PASS")
    else:
        raise AssertionError("M40560_UNAUTHORIZED_ALLOWED_" + label)


def run(conn) -> None:
    from m39067_postgres18_disposable_runtime import bootstrap, isolate_only_identity_do
    # All objects, roles, and rows are synthetic and are created only in CI.
    bootstrap(conn)
    master = uuid4()
    stranger = uuid4()
    tenant = uuid4()
    other_tenant = uuid4()
    price = uuid4()
    campaign = uuid4()
    t1 = datetime.now(timezone.utc) - timedelta(days=1)
    t2 = t1 + timedelta(days=20)

    conn.execute("CREATE TABLE public.m40560_ci_master_allowlist(user_id uuid PRIMARY KEY)")
    conn.execute("INSERT INTO public.m40560_ci_master_allowlist VALUES (%s)", (master,))
    conn.execute(
        "CREATE OR REPLACE FUNCTION public.rls_is_master(id uuid) RETURNS boolean "
        "LANGUAGE sql STABLE AS $f$ "
        "SELECT EXISTS(SELECT 1 FROM public.m40560_ci_master_allowlist "
        "WHERE user_id=id) $f$"
    )
    conn.execute(
        "GRANT SELECT ON public.m40560_ci_master_allowlist, "
        "public.platform_license_price_versions TO frcaixinha_app_role"
    )
    conn.execute("GRANT USAGE ON SCHEMA public TO frcaixinha_app_role,frcaixinha_auth_role")
    conn.execute("INSERT INTO public.users(id) VALUES (%s),(%s)",(master,stranger))
    conn.execute(
        "INSERT INTO public.tenants(id,admin_user_id,status) "
        "VALUES (%s,%s,'ATIVO'),(%s,%s,'ATIVO')",
        (tenant,master,other_tenant,stranger),
    )
    conn.execute(
        "INSERT INTO public.platform_license_plans(tier,status) "
        "VALUES ('ESSENCIAL','ACTIVE')"
    )
    conn.execute(
        "INSERT INTO public.platform_license_price_versions("
        "id,plan_tier,monthly_price,reason) "
        "VALUES (%s,'ESSENCIAL',89.90,'synthetic legacy')",
        (price,),
    )

    mig112=(ROOT/"backend/migrations/112_frfinance_master_independent_saas_prices.sql").read_text()
    mig113=(ROOT/"backend/migrations/113_frfinance_saas_new_admin_promotions.sql").read_text()
    # ONLY the immutable Termux identity DO is stripped in-memory for CI.
    # SQL files on disk and original database are never modified.
    ddl112=isolate_only_identity_do(mig112,"fr_m39066")
    ddl113=isolate_only_identity_do(mig113,"m39067")
    with conn.transaction():
        conn.execute(ddl112)
        conn.execute(ddl113)
    assert conn.execute(
        "SELECT annual_price FROM public.platform_license_price_versions "
        "WHERE id=%s",(price,)
    ).fetchone()[0] == Decimal("899.00")
    print("M40560_SQL112_LEGACY_ANNUAL_PRESERVED=PASS")

    insert_promo = (
        "INSERT INTO public.platform_saas_promotion_revisions "
        "(campaign_id,revision,plan_tier,billing_period,base_price_version_id,"
        "promotional_price,audience,title,benefit_description,starts_at,ends_at,"
        "state,reason,created_by) "
        "VALUES (%s,%s,'ESSENCIAL','ANNUAL',%s,490.33,'NEW_ADMIN_ONLY',"
        "'Oferta sintética','Campanha sintética para testes CI de RLS',"
        "%s,%s,%s,'Aprovacao ficticia apenas no runner descartavel',%s)"
    )
    def args(revision: int, state: str, actor=master):
        return (campaign, revision, price, t1, t2, state, actor)

    set_identity(conn,"TENANT_MEMBER",str(master),str(tenant))
    assert conn.execute(
        "SELECT count(*) FROM public.platform_saas_promotion_revisions"
    ).fetchone()[0] == 0
    expect_denied(conn, insert_promo, args(1,"DRAFT"), "MEMBER_INSERT")
    print("M40560_MEMBER_RLS_EMPTY=PASS")

    set_identity(conn,"MASTER",str(stranger))
    assert conn.execute(
        "SELECT count(*) FROM public.platform_saas_promotion_revisions"
    ).fetchone()[0] == 0
    expect_denied(conn, insert_promo, args(1,"DRAFT",stranger), "FAKE_MASTER_INSERT")
    print("M40560_UNVERIFIED_MASTER_RLS_EMPTY=PASS")

    set_identity(conn,"MASTER",str(master))
    conn.execute(insert_promo,args(1,"DRAFT"))
    assert conn.execute(
        "SELECT count(*) FROM public.platform_saas_promotion_revisions"
    ).fetchone()[0] == 1
    print("M40560_VERIFIED_MASTER_DRAFT_INSERT_AND_SELECT=PASS")

    expect_denied(
        conn, "UPDATE public.platform_saas_promotion_revisions "
              "SET state='CANCELED' WHERE campaign_id=%s",
        (campaign,), "APP_PROMO_UPDATE"
    )
    expect_denied(
        conn, "DELETE FROM public.platform_saas_promotion_revisions "
              "WHERE campaign_id=%s", (campaign,), "APP_PROMO_DELETE"
    )
    expect_denied(
        conn, "UPDATE public.platform_license_price_versions "
              "SET annual_price=1 WHERE id=%s", (price,), "APP_PRICE_UPDATE"
    )
    expect_denied(
        conn, "DELETE FROM public.platform_license_price_versions "
              "WHERE id=%s", (price,), "APP_PRICE_DELETE"
    )
    expect_denied(
        conn, "SELECT public.frfinance_guard_saas_promotion_append()",
        (), "APP_GUARD_EXECUTE"
    )

    conn.execute("RESET ROLE")
    conn.execute(insert_promo,args(2,"PUBLISHED"))
    print("M40560_PUBLISH_VIA_SYNTHETIC_OWNER=PASS")

    set_identity(conn,"TENANT_ADMIN",str(master),str(tenant))
    visible=conn.execute(
        "SELECT campaign_id,promotional_price "
        "FROM public.frfinance_saas_new_admin_published_promotions()"
    ).fetchall()
    assert visible==[(campaign,Decimal("490.33"))], visible
    print("M40560_ADMIN_OWN_TENANT_PUBLISHED_OFFER=PASS")

    set_identity(conn,"TENANT_ADMIN",str(master),str(other_tenant))
    assert conn.execute(
        "SELECT * FROM public.frfinance_saas_new_admin_published_promotions()"
    ).fetchall()==[]
    print("M40560_ADMIN_CROSS_TENANT_OFFER_DENIED=PASS")

    set_identity(conn,"TENANT_ADMIN",str(stranger),str(other_tenant))
    # Stranger can be a genuine other-tenant admin. Published offer is public
    # to new administrators, but should not leak drafts/member/owner details.
    other_visible=conn.execute(
        "SELECT campaign_id FROM public.frfinance_saas_new_admin_published_promotions()"
    ).fetchall()
    assert other_visible==[(campaign,)]
    print("M40560_OTHER_NEW_ADMIN_CAN_VIEW_PUBLIC_OFFER=PASS")

    set_identity(conn,"TENANT_MEMBER",str(master),str(tenant))
    assert conn.execute(
        "SELECT * FROM public.frfinance_saas_new_admin_published_promotions()"
    ).fetchall()==[]
    print("M40560_MEMBER_CANNOT_VIEW_ADMIN_OFFERS=PASS")

    conn.execute("RESET ROLE")
    conn.execute("SET ROLE frcaixinha_auth_role")
    expect_denied(
        conn,
        "SELECT * FROM public.frfinance_saas_new_admin_published_promotions()",
        (), "AUTH_ROLE_OFFER_READER"
    )
    expect_denied(
        conn, "SELECT campaign_id FROM public.platform_saas_promotion_revisions",
        (), "AUTH_ROLE_PROMO_TABLE"
    )
    conn.execute("RESET ROLE")
    print("M40560_ROLE_DATA_PLANE=PASS_DISPOSABLE_ONLY_NOT_PRODUCTION")


def main() -> int:
    try:
        require_disposable()
        from m39067_postgres18_disposable_runtime import restricted_connection
        with restricted_connection() as conn:
            run(conn)
    except Exception as exc:
        print("M40560_STATUS=BLOCKED_" + type(exc).__name__)
        return 2
    finally:
        print("M40560_ORIGINAL_TERMUX_PG_5433=NOT_ACCESSED")
        print("M40560_FR_CAIXINHA_2_2=NOT_ACCESSED")
        print("M40560_REAL_SESSIONS=NONE")
        print("M40560_LOCAL_DB_WRITES=NONE")
        print("M40560_LOCAL_MIGRATIONS=NONE")
        print("M40560_SERVICE_RESTARTS=NONE")
        print("M40560_PIX_REAL=OFF")
        print("M40560_PAGAMENTOS_REAIS=OFF")
        print("M40560_ATIVACAO_REAL=OFF")
        print("M40560_PRODUCTION=BLOCKED")
    print("M40560_STATUS=PASS_DISPOSABLE_ROLE_RLS_ONLY")
    return 0


if __name__=="__main__":
    sys.exit(main())
