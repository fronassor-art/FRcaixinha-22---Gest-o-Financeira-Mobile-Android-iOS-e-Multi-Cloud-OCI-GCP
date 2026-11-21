#!/usr/bin/env python3
"""M40900: disposable PG18 ACL revocation rehearsal, NEVER original DB.

Reproduces M40570's app-role GUC forgery on synthetic SQL112/SQL113, then
revokes table-level SELECT, column-level INSERT, and definer EXECUTE.
This fence breaks the old SaaS promotion endpoints; it is not a complete
identity migration or a production authorization.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
DISPOSABLE_DB="fr_m39067_disposable_ci"
DISPOSABLE_PORT=55433
COLUMNS=(
    "campaign_id", "revision", "plan_tier", "billing_period",
    "base_price_version_id", "promotional_price", "audience",
    "title", "benefit_description", "starts_at", "ends_at",
    "state", "reason", "created_by",
)
TABLE="public.platform_saas_promotion_revisions"
FUNCTION="public.frfinance_saas_new_admin_published_promotions()"

def require_disposable() -> None:
    flags=(
      ("GITHUB_ACTIONS","true"),("CI_M40900_DISPOSABLE","1"),
      ("CI_M40560_DISPOSABLE","1"),("FRCAIXINHA_CI_ISOLATED","1"),
      ("PIX_REAL","OFF"),("PAGAMENTOS_REAIS","OFF"),
      ("ATIVACAO_REAL","OFF"),
    )
    if any(os.environ.get(k)!=v for k,v in flags):
        raise RuntimeError("M40900_GITHUB_PG18_DISPOSABLE_ONLY")
    # No import of psycopg or network operation before exact target checks.
    from urllib.parse import urlsplit
    url=os.environ.get("CI_PROMOTIONS_DATABASE_URL","")
    try:
        parsed=urlsplit(url)
        if (parsed.scheme!="postgresql" or parsed.hostname!="127.0.0.1"
                or parsed.port!=DISPOSABLE_PORT
                or parsed.path!="/"+DISPOSABLE_DB or parsed.username!="postgres"
                or not parsed.password or parsed.query or parsed.fragment):
            raise ValueError("target")
    except (ValueError,TypeError,AttributeError) as exc:
        raise RuntimeError("M40900_INVALID_CI_TARGET") from None

def fence_sql() -> tuple[str,...]:
    """LABORATORY ONLY: NOT a SQL migration, never target native Termux."""
    return (
       f"REVOKE SELECT ON {TABLE} FROM frcaixinha_app_role",
       "REVOKE INSERT (" + ",".join(COLUMNS) + ") ON "
           + TABLE + " FROM frcaixinha_app_role",
       f"REVOKE EXECUTE ON FUNCTION {FUNCTION} FROM frcaixinha_app_role",
    )

def deny_pg(conn,statement: str,label: str) -> None:
    import psycopg
    try:
        with conn.transaction():
            conn.execute(statement)
    except psycopg.Error as exc:
        if exc.sqlstate!="42501":
            raise AssertionError("M40900_UNEXPECTED_SQLSTATE_"+label) from exc
        print("M40900_"+label+"=DENIED_42501")
    else:
        raise AssertionError("M40900_FENCE_FAILED_"+label)

def run(conn) -> None:
    from m40560_saas_role_dataplane_disposable import (
       run as synthetic_setup, set_identity,
    )
    synthetic_setup(conn)
    master=conn.execute(
        "SELECT user_id FROM public.m40560_ci_master_allowlist"
    ).fetchone()[0]
    # Prove exposure BEFORE revocation, not merely absence of synthetic rows.
    set_identity(conn,"TENANT_MEMBER",str(master))
    conn.execute("SELECT set_config('app.current_role','MASTER',false)")
    conn.execute("SELECT set_config('app.current_user_id',%s,false)",(str(master),))
    exposed=conn.execute(f"SELECT count(*) FROM {TABLE}").fetchone()[0]
    if exposed<1:
        raise AssertionError("M40900_BASELINE_GUC_EXPOSURE_NOT_CONFIRMED")
    print("M40900_BASELINE_SQL_GUC_SPOOF=EXPOSURE_CONFIRMED")

    # Owner context in disposable runner only; never operates on user DB.
    conn.execute("RESET ROLE")
    for statement in fence_sql():
        conn.execute(statement)
    print("M40900_DISPOSABLE_REVOKE_SELECT_INSERT_COLUMNS_EXECUTE=APPLIED")
    app_role="frcaixinha_app_role"
    if conn.execute(
        "SELECT has_table_privilege(%s,%s,'SELECT')",
        (app_role,TABLE),
    ).fetchone()[0]:
        raise AssertionError("M40900_TABLE_SELECT_GRANT_SURVIVED")
    for column in COLUMNS:
        can_insert=conn.execute(
            "SELECT has_column_privilege(%s,%s,%s,'INSERT')",
            (app_role,TABLE,column),
        ).fetchone()[0]
        if can_insert:
            raise AssertionError("M40900_COLUMN_INSERT_GRANT_SURVIVED_"+column)
    if conn.execute(
        "SELECT has_function_privilege(%s,%s,'EXECUTE')",
        (app_role,FUNCTION),
    ).fetchone()[0]:
        raise AssertionError("M40900_FUNCTION_EXECUTE_GRANT_SURVIVED")
    print("M40900_ACL_TABLE_COLUMN_FUNCTION=REVOKED_ALL_SYNTHETIC")

    # The very same spoofed identity is no longer SQL capability.
    set_identity(conn,"TENANT_MEMBER",str(master))
    conn.execute("SELECT set_config('app.current_role','MASTER',false)")
    conn.execute("SELECT set_config('app.current_user_id',%s,false)",(str(master),))
    deny_pg(conn,f"SELECT count(*) FROM {TABLE}","FORGED_MASTER_SELECT")
    deny_pg(conn,f"SELECT * FROM {FUNCTION}","FORGED_ADMIN_DEFINER")
    deny_pg(conn,f"INSERT INTO {TABLE} DEFAULT VALUES","FORGED_MASTER_INSERT")
    conn.execute("RESET ROLE")
    owner_visible=conn.execute(f"SELECT count(*) FROM {TABLE}").fetchone()[0]
    if owner_visible!=exposed:
        raise AssertionError("M40900_OWNER_DATA_CHANGED")
    print("M40900_SYNTHETIC_DATA_UNCHANGED=PASS")
    print("M40900_LEGACY_SAAS_ENDPOINTS=UNAVAILABLE_AFTER_FENCE")
    print("M40900_IDENTITY_REDESIGN=STILL_REQUIRED")
    print("M40900_REAL_POSTGRES_PRIVILEGES=NOT_ATTESTED")

def main() -> int:
    try:
        require_disposable()
        from m40560_saas_role_dataplane_disposable import require_disposable as check_local_pg
        check_local_pg()
        from m39067_postgres18_disposable_runtime import restricted_connection
        with restricted_connection() as conn:
            run(conn)
    except Exception as exc:
        print("M40900_STATUS=BLOCKED_"+type(exc).__name__)
        return 2
    finally:
        print("M40900_ORIGINAL_TERMUX_PG_5433=NOT_ACCESSED")
        print("M40900_FR_CAIXINHA_2_2=NOT_ACCESSED")
        print("M40900_LOCAL_DB_WRITES=NONE")
        print("M40900_LOCAL_MIGRATIONS=NONE")
        print("M40900_SERVICE_RESTARTS=NONE")
        print("M40900_PIX_REAL=OFF")
        print("M40900_PAGAMENTOS_REAIS=OFF")
        print("M40900_ATIVACAO_REAL=OFF")
        print("M40900_PRODUCTION=BLOCKED")
    print("M40900_STATUS=PASS_DISPOSABLE_ACL_FENCE_REHEARSAL_ONLY")
    return 0

if __name__=="__main__":
    sys.exit(main())
