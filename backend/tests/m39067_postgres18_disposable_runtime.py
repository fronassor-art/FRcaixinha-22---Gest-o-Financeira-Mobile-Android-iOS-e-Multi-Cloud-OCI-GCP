#!/usr/bin/env python3
"""M39067: PG18 descartável CI — exercita DDL da SQL112+113 e campanhas.

JAMAIS conecta ao Termux. Banco efêmero EXCLUSIVO do GitHub Actions em 55433.
Os DO de identidade Termux são substituídos em memória apenas para este teste
controlado; os SQLs versionados não são alterados. Verifica comportamento
real de generated->ordinary column, trigger e função de divulgação interna.
"""
from __future__ import annotations

from decimal import Decimal
import os
from pathlib import Path
import re
import sys
from uuid import UUID, uuid4

import psycopg
from psycopg.conninfo import conninfo_to_dict

ROOT = Path(__file__).resolve().parents[2]
DATABASE_NAME = "fr_m39067_disposable_ci"
PORT = 55433


def restricted_connection():
    if os.environ.get("FRCAIXINHA_CI_ISOLATED") != "1":
        raise RuntimeError("CI_ONLY_FLAG_REQUIRED")
    dsn = os.environ.get("CI_PROMOTIONS_DATABASE_URL", "")
    parsed = conninfo_to_dict(dsn)
    if (parsed.get("host") != "127.0.0.1"
            or int(parsed.get("port", "0")) != PORT
            or parsed.get("dbname") != DATABASE_NAME
            or parsed.get("user") != "postgres"):
        raise RuntimeError("NEVER_CONNECT_NON_DISPOSABLE_POSTGRES")
    return psycopg.connect(dsn,autocommit=True)


def isolate_only_identity_do(source: str, tag: str) -> str:
    pattern = rf"DO \$({tag})\$.*?END\s*\$\1\$;"
    clean, count = re.subn(pattern, "", source, count=1, flags=re.DOTALL)
    if count != 1:
        raise RuntimeError("CI_IDENTITY_DO_NOT_UNIQUE")
    return clean


def bootstrap(conn) -> None:
    conn.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    conn.execute("CREATE ROLE frcaixinha_app_role NOLOGIN")
    conn.execute("CREATE ROLE frcaixinha_auth_role NOLOGIN")
    conn.execute("""
      CREATE TABLE public.users(id uuid PRIMARY KEY);
      CREATE TABLE public.tenants(id uuid PRIMARY KEY,admin_user_id uuid NOT NULL,status text NOT NULL);
      CREATE TABLE public.platform_license_plans(
        tier varchar(20) PRIMARY KEY,
        status varchar(40) NOT NULL
      );
      CREATE TABLE public.platform_license_price_versions(
        id uuid PRIMARY KEY,
        plan_tier varchar(20) NOT NULL REFERENCES public.platform_license_plans(tier),
        monthly_price numeric(12,2) NOT NULL,
        annual_price numeric(12,2) GENERATED ALWAYS AS (monthly_price*10) STORED,
        changed_by uuid REFERENCES public.users(id),
        reason text NOT NULL,
        created_at timestamptz NOT NULL DEFAULT now()
      );
      CREATE TABLE public.saas_subscription_preparations(
        admin_user_id uuid NOT NULL
      );
      CREATE TABLE public.saas_license_entitlements(tenant_id uuid NOT NULL);
      CREATE FUNCTION public.rls_is_master(id uuid) RETURNS boolean
      LANGUAGE sql STABLE AS $fn$ SELECT id IS NOT NULL $fn$;
      CREATE FUNCTION public.rls_is_tenant_admin(actor uuid,tenant uuid)
      RETURNS boolean LANGUAGE sql STABLE AS $fn$
      SELECT EXISTS(SELECT 1 FROM public.tenants
        WHERE id=tenant AND admin_user_id=actor AND status='ATIVO') $fn$;
    """)


def expect_pg_exception(conn, statement: str, args: tuple, name: str) -> None:
    try:
        with conn.transaction():
            conn.execute(statement,args)
    except psycopg.Error:
        print("M39067_DISPOSABLE_DENY_" + name + "=PASS")
    else:
        raise AssertionError("M39067_DID_NOT_BLOCK_" + name)


def run(conn) -> None:
    bootstrap(conn)
    admin = uuid4()
    tenant = uuid4()
    version = uuid4()
    campaign = uuid4()
    conn.execute("INSERT INTO public.users VALUES (%s)",(admin,))
    conn.execute("INSERT INTO public.tenants VALUES (%s,%s,'ATIVO')",(tenant,admin))
    conn.execute("INSERT INTO public.platform_license_plans VALUES "
                 "('ESSENCIAL','ACTIVE'),('INTERMEDIARIO','ACTIVE')")
    conn.execute("INSERT INTO public.platform_license_price_versions "
                 "(id,plan_tier,monthly_price,reason) "
                 "VALUES (%s,'ESSENCIAL',89.90,'Homologacao de dados sinteticos')",
                 (version,))
    old_annual = conn.execute(
        "SELECT annual_price FROM public.platform_license_price_versions "
        "WHERE id=%s",(version,)
    ).fetchone()[0]
    assert old_annual == Decimal("899.00")

    sql112=(ROOT/"backend/migrations/112_frfinance_master_independent_saas_prices.sql").read_text()
    sql113=(ROOT/"backend/migrations/113_frfinance_saas_new_admin_promotions.sql").read_text()
    d112=isolate_only_identity_do(sql112,"fr_m39066")
    d113=isolate_only_identity_do(sql113,"m39067")
    with conn.transaction():
        conn.execute(d112)
        conn.execute(d113)
    assert conn.execute(
        "SELECT annual_price FROM public.platform_license_price_versions WHERE id=%s",
        (version,)
    ).fetchone()[0] == old_annual
    print("M39067_DISPOSABLE_EXISTING_ANNUAL_PRICE_PRESERVED=PASS")

    newer=uuid4()
    conn.execute(
        "INSERT INTO public.platform_license_price_versions "
        "(id,plan_tier,monthly_price,annual_price,reason) "
        "VALUES (%s,'ESSENCIAL',120.23,550.11,'Nova versao sintetica independente')",
        (newer,)
    )
    assert conn.execute(
        "SELECT annual_price FROM public.platform_license_price_versions WHERE id=%s",
        (newer,)
    ).fetchone()[0] == Decimal("550.11")
    print("M39067_DISPOSABLE_INDEPENDENT_MONTHLY_ANNUAL=PASS")

    draft_sql=(
        "INSERT INTO public.platform_saas_promotion_revisions "
        "(campaign_id,revision,plan_tier,billing_period,base_price_version_id,"
        "promotional_price,audience,title,benefit_description,starts_at,ends_at,"
        "state,reason,created_by) "
        "VALUES (%s,%s,%s,%s,%s,%s,'NEW_ADMIN_ONLY',"
        "'Oferta de entrada','Desconto de homologacao para novos admins',"
        "now()-interval '1 day',now()+interval '20 days',%s,"
        "'Aprovacao comercial com motivo suficiente',%s)"
    )
    def args(cam,rev,tier="ESSENCIAL",period="ANNUAL",ver=newer,price="480.33",state="DRAFT"):
        return (cam,rev,tier,period,ver,price,state,admin)
    conn.execute(draft_sql,args(campaign,1))
    expect_pg_exception(conn,draft_sql,args(uuid4(),1,state="PUBLISHED"),"DIRECT_PUBLISH")
    expect_pg_exception(conn,draft_sql,args(uuid4(),1,tier="INTERMEDIARIO"),"TIER_VERSION_MISMATCH")
    expect_pg_exception(conn,draft_sql,args(campaign,3,state="PUBLISHED"),"SKIPPED_REVISION")

    conn.execute(draft_sql,args(campaign,2,state="PUBLISHED"))
    conn.execute("SELECT set_config('app.current_role','TENANT_ADMIN',false)")
    conn.execute("SELECT set_config('app.current_user_id',%s,false)",(str(admin),))
    conn.execute("SELECT set_config('app.current_tenant_id',%s,false)",(str(tenant),))
    visible=conn.execute(
        "SELECT campaign_id,promotional_price FROM "
        "public.frfinance_saas_new_admin_published_promotions()"
    ).fetchall()
    assert visible==[(campaign,Decimal("480.33"))]
    print("M39067_DISPOSABLE_NEW_ADMIN_VISIBLE=PASS")

    other=uuid4()
    conn.execute(draft_sql,args(other,1))
    expect_pg_exception(conn,draft_sql,args(other,2,state="PUBLISHED"),"OVERLAPPING_CAMPAIGN")

    conn.execute("INSERT INTO public.saas_subscription_preparations "
                 "(admin_user_id) VALUES (%s)",(admin,))
    assert not conn.execute(
        "SELECT * FROM public.frfinance_saas_new_admin_published_promotions()"
    ).fetchall()
    print("M39067_DISPOSABLE_EXISTING_ADMIN_HIDDEN=PASS")

    conn.execute("DELETE FROM public.saas_subscription_preparations")
    conn.execute(draft_sql,args(campaign,3,state="CANCELED"))
    assert not conn.execute(
        "SELECT * FROM public.frfinance_saas_new_admin_published_promotions()"
    ).fetchall()
    print("M39067_DISPOSABLE_CANCELED_HIDDEN=PASS")

    verify=conn.execute(
      "SELECT relrowsecurity,relforcerowsecurity FROM pg_class "
      "WHERE oid='public.platform_saas_promotion_revisions'::regclass"
    ).fetchone()
    assert verify==(True,True)
    assert not conn.execute(
      "SELECT has_function_privilege('frcaixinha_auth_role',"
      "'public.frfinance_saas_new_admin_published_promotions()','EXECUTE')"
    ).fetchone()[0]
    print("M39067_DISPOSABLE_RLS_AND_NO_AUTH_EXECUTE=PASS")


def main() -> int:
    try:
        with restricted_connection() as conn:
            run(conn)
    except Exception as error:
        print("M39067_DISPOSABLE_STATUS=BLOCKED_" + type(error).__name__)
        return 2
    print("M39067_DISPOSABLE_STATUS=PASS")
    print("M39067_TERMUX_ORIGINAL_DB=NEVER_CONNECTED")
    print("M39067_REAL_PIX=OFF")
    return 0


if __name__=="__main__":
    sys.exit(main())
