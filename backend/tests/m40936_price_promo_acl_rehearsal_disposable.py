#!/usr/bin/env python3
"""M40936: REAL PostgreSQL 18 disposable-only price + promotion ACL rehearsal.

Reproduces the historical 011 + 112 price INSERT grants and the historical
113 promotion grants on synthetic tables, proves GUC-spoofed app SQL writes
before SQL ACL revocation and permission-denied after. NEVER run in Termux
or against the original PostgreSQL. This is NOT a migration or full SQL
trust-boundary repair, and is not connected to production FastAPI.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4
import os
import sys

PRICE = "public.platform_license_price_versions"
PROMOTION = "public.platform_saas_promotion_revisions"
APP_ROLE = "frcaixinha_app_role"
PRICE_INSERT_COLUMNS = (
    "plan_tier", "monthly_price", "changed_by", "reason", "annual_price",
)


def require_disposable() -> None:
    if os.environ.get("CI_M40936_DISPOSABLE") != "1":
        raise RuntimeError("M40936_GITHUB_DISPOSABLE_ONLY")
    # The older gate checks *all* CI identity, host, port, DB, account and
    # financial-off variables BEFORE any driver connection.
    from m40900_sql113_acl_fence_disposable import require_disposable as prior
    prior()


def price_insert_sql() -> str:
    return (
        "INSERT INTO " + PRICE +
        " (plan_tier,monthly_price,annual_price,changed_by,reason) "
        "VALUES ('ESSENCIAL',99.90,770.11,%s,"
        "'Homologacao sintetica M40936 sem cobranca') "
        "RETURNING id"
    )


def promo_insert_sql() -> str:
    return (
        "INSERT INTO " + PROMOTION +
        " (campaign_id,revision,plan_tier,billing_period,base_price_version_id,"
        "promotional_price,audience,title,benefit_description,starts_at,ends_at,"
        "state,reason,created_by) "
        "VALUES (%s,1,'ESSENCIAL','ANNUAL',%s,550.11,'NEW_ADMIN_ONLY',"
        "'Campanha M40936','Oferta sintetica sem provedor e sem repasse',"
        "%s,%s,'DRAFT','Motivo documentado de laboratorio CI',%s)"
    )


def apply_price_acl_fence(conn) -> None:
    """Synthetic owner only. NOT an installation SQL or live migration."""
    columns = ",".join(PRICE_INSERT_COLUMNS)
    conn.execute("REVOKE INSERT ON " + PRICE + " FROM " + APP_ROLE)
    conn.execute(
        "REVOKE INSERT (" + columns + ") ON " + PRICE + " FROM " + APP_ROLE
    )


def install_synthetic_011_price_context(conn) -> None:
    """M40560 runs 112/113, but its tiny fixture omits RLS and 011 grants."""
    conn.execute("RESET ROLE")
    # M40560 trimmed the SQL011 synthetic fixture: restore the documented
    # UUID default so a column-scoped app INSERT can omit the id column.
    conn.execute("ALTER TABLE " + PRICE + " ALTER COLUMN id SET DEFAULT uuid_generate_v4()")
    conn.execute("ALTER TABLE " + PRICE + " ENABLE ROW LEVEL SECURITY")
    conn.execute("ALTER TABLE " + PRICE + " FORCE ROW LEVEL SECURITY")
    conn.execute("""
        CREATE POLICY m40936_ci_price_master_select
        ON public.platform_license_price_versions
        FOR SELECT TO frcaixinha_app_role
        USING (
            current_setting('app.current_role',true)='MASTER'
            AND public.rls_is_master(
                NULLIF(current_setting('app.current_user_id',true),'')::uuid)
        )
    """)
    conn.execute("""
        CREATE POLICY m40936_ci_price_master_insert
        ON public.platform_license_price_versions
        FOR INSERT TO frcaixinha_app_role
        WITH CHECK (
            current_setting('app.current_role',true)='MASTER'
            AND public.rls_is_master(
                NULLIF(current_setting('app.current_user_id',true),'')::uuid)
            AND changed_by=NULLIF(
                current_setting('app.current_user_id',true),'')::uuid
        )
    """)
    # SQL011 historical column INSERT grant on price, SQL112 already added
    # annual_price via synthetic setup. Reproducing both is essential.
    conn.execute(
        "GRANT INSERT(plan_tier,monthly_price,changed_by,reason) "
        "ON " + PRICE + " TO " + APP_ROLE
    )


def deny_permission(conn, statement: str, params: tuple, label: str) -> None:
    import psycopg
    try:
        with conn.transaction():
            conn.execute(statement, params)
    except psycopg.Error as exc:
        if exc.sqlstate != "42501":
            raise AssertionError(
                "M40936_UNEXPECTED_SQLSTATE_" + label + "_" + str(exc.sqlstate)
            ) from exc
        print("M40936_" + label + "=DENIED_42501")
    else:
        raise AssertionError("M40936_UNAUTHORIZED_WRITE_ALLOWED_" + label)


def prove(conn) -> None:
    from m40560_saas_role_dataplane_disposable import (
        run as synthetic_setup, set_identity,
    )
    from m40900_sql113_acl_fence_disposable import fence_sql

    synthetic_setup(conn)
    install_synthetic_011_price_context(conn)

    master = conn.execute(
        "SELECT user_id FROM public.m40560_ci_master_allowlist"
    ).fetchone()[0]
    old_price = conn.execute("SELECT count(*) FROM " + PRICE).fetchone()[0]
    old_promo = conn.execute("SELECT count(*) FROM " + PROMOTION).fetchone()[0]
    version = conn.execute(
        "SELECT id FROM " + PRICE + " WHERE plan_tier='ESSENCIAL' "
        "ORDER BY created_at DESC,id DESC LIMIT 1"
    ).fetchone()[0]

    # An existing member with SQL access should NOT have Master authority.
    set_identity(conn, "TENANT_MEMBER", str(master))
    deny_permission(conn, price_insert_sql(), (master,), "MEMBER_PRICE_INSERT")
    # Forge the two user-settable PostgreSQL GUCs despite previous member.
    conn.execute("SELECT set_config('app.current_role','MASTER',false)")
    conn.execute(
        "SELECT set_config('app.current_user_id',%s,false)", (str(master),)
    )

    inserted = conn.execute(price_insert_sql(), (master,)).fetchone()[0]
    start = datetime.now(timezone.utc) + timedelta(days=1)
    end = start + timedelta(days=12)
    campaign = uuid4()
    conn.execute(promo_insert_sql(), (
        campaign, version, start, end, master,
    ))
    print("M40936_BEFORE_ACL_MEMBER_SQL_GUC_MASTER_SPOOF=CONFIRMED")
    print("M40936_BEFORE_ACL_PRICE_AND_PROMO_WRITES=CONFIRMED")

    # READ ONLY SELECT of prices is deliberately preserved: remove direct
    # INSERT to prices; remove table SELECT, INSERT and definer EXECUTE for
    # promotions, as previously proved in the M40900 disposable experiment.
    conn.execute("RESET ROLE")
    apply_price_acl_fence(conn)
    for sql in fence_sql():
        conn.execute(sql)

    if not conn.execute(
        "SELECT has_table_privilege(%s,%s,'SELECT')",
        (APP_ROLE, PRICE),
    ).fetchone()[0]:
        raise AssertionError("M40936_PRICE_SELECT_REGRESSION")
    if conn.execute(
        "SELECT has_table_privilege(%s,%s,'INSERT')",
        (APP_ROLE, PRICE),
    ).fetchone()[0]:
        raise AssertionError("M40936_PRICE_TABLE_INSERT_REMAINS")
    for column in PRICE_INSERT_COLUMNS:
        if conn.execute(
            "SELECT has_column_privilege(%s,%s,%s,'INSERT')",
            (APP_ROLE, PRICE, column),
        ).fetchone()[0]:
            raise AssertionError("M40936_PRICE_COLUMN_INSERT_REMAINS_" + column)
    if conn.execute(
        "SELECT has_table_privilege(%s,%s,'INSERT')",
        (APP_ROLE, PROMOTION),
    ).fetchone()[0]:
        raise AssertionError("M40936_PROMOTION_TABLE_INSERT_REMAINS")
    for column in (
        "campaign_id", "revision", "plan_tier", "billing_period",
        "base_price_version_id", "promotional_price", "audience",
        "title", "benefit_description", "starts_at", "ends_at",
        "state", "reason", "created_by",
    ):
        if conn.execute(
            "SELECT has_column_privilege(%s,%s,%s,'INSERT')",
            (APP_ROLE, PROMOTION, column),
        ).fetchone()[0]:
            raise AssertionError("M40936_PROMO_COLUMN_INSERT_REMAINS_" + column)
    print("M40936_PRICE_INSERT_COLUMNS_ALL_REVOKED=PASS")
    print("M40936_PROMOTION_INSERT_COLUMNS_ALL_REVOKED=PASS")
    print("M40936_LEGACY_PRICE_SELECT_PRESERVED=PASS")

    # A stolen app SQL role still can set MASTER GUCs, but loses the direct
    # ability to write both SaaS tables. This proves ACL containment only.
    set_identity(conn, "TENANT_MEMBER", str(master))
    conn.execute("SELECT set_config('app.current_role','MASTER',false)")
    conn.execute(
        "SELECT set_config('app.current_user_id',%s,false)", (str(master),)
    )
    deny_permission(conn, price_insert_sql(), (master,), "FORGED_MASTER_PRICE_WRITE")
    deny_permission(conn, promo_insert_sql(), (
        uuid4(), version, start, end, master,
    ), "FORGED_MASTER_PROMOTION_WRITE")
    # This SELECT is still allowed with forged GUCs. The identity weakness
    # remains until independent custody and SQL policies are implemented.
    visible = conn.execute(
        "SELECT count(*) FROM " + PRICE
    ).fetchone()[0]
    if visible != old_price + 1:
        raise AssertionError("M40936_PRICE_READ_AFTER_REVOKE_REGRESSION")
    print("M40936_GUC_FORGED_PRICE_SELECT=STILL_EXPOSED_NO_GO")
    conn.execute("RESET ROLE")
    assert conn.execute(
        "SELECT count(*) FROM " + PRICE
    ).fetchone()[0] == old_price + 1
    assert conn.execute(
        "SELECT count(*) FROM " + PROMOTION
    ).fetchone()[0] == old_promo + 1
    assert conn.execute(
        "SELECT id FROM " + PRICE + " WHERE id=%s", (inserted,)
    ).fetchone() is not None
    print("M40936_EXISTING_SYNTHETIC_ROWS_PRESERVED=PASS")
    print("M40936_ORIGINAL_DB_PRIVILEGES=NOT_ATTESTED")
    print("M40936_MASTER_SQL_RELEASE=NO_GO")


def main() -> int:
    try:
        require_disposable()
        from m39067_postgres18_disposable_runtime import restricted_connection
        with restricted_connection() as conn:
            prove(conn)
    except Exception as exc:
        print("M40936_STATUS=BLOCKED_" + type(exc).__name__)
        return 2
    finally:
        print("M40936_ORIGINAL_TERMUX_PG_5433=NOT_ACCESSED")
        print("M40936_FR_CAIXINHA_2_2=NOT_ACCESSED")
        print("M40936_MIGRATIONS=NONE")
        print("M40936_SERVICE_RESTARTS=NONE")
        print("M40936_PIX_REAL=OFF")
        print("M40936_PAGAMENTOS_REAIS=OFF")
        print("M40936_ATIVACAO_REAL=OFF")
        print("M40936_PRODUCTION=BLOCKED")
    print("M40936_STATUS=PASS_DISPOSABLE_ONLY_NO_GO")
    return 0


if __name__ == "__main__":
    sys.exit(main())
