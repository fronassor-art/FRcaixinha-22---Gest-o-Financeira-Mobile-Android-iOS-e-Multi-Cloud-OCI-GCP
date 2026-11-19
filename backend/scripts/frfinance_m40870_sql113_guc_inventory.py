"""M40870: source-only SQL113 authority inventory, never a live DB audit."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[2]
SQL=ROOT/"backend/migrations/113_frfinance_saas_new_admin_promotions.sql"
ROUTER=ROOT/"backend/app/routers/saas_promotions.py"
GATE=ROOT/"backend/app/m40840_financial_sql_release_no_go.py"

@dataclass(frozen=True)
class Risk:
    code: str
    status: str = "NO_GO"

def inspect(sql: str, router: str, gate: str) -> tuple[Risk,...]:
    result=[]
    for tag,pattern in (
        ("MASTER_SELECT_USES_GUC",r"CREATE POLICY frfinance_saas_promo_master_select[\s\S]*?current_setting\('app\.current_role'"),
        ("MASTER_INSERT_USES_GUC",r"CREATE POLICY frfinance_saas_promo_master_insert[\s\S]*?current_setting\('app\.current_user_id'"),
        ("SECURITY_DEFINER_USES_GUC",r"CREATE FUNCTION public\.frfinance_saas_new_admin_published_promotions\(\)[\s\S]*?SECURITY DEFINER[\s\S]*?current_setting\('app\.current_tenant_id'"),
        ("APP_ROLE_EXECUTES_DEFINER",r"GRANT EXECUTE ON FUNCTION public\.frfinance_saas_new_admin_published_promotions\(\)\s+TO frcaixinha_app_role"),
    ):
        if re.search(pattern,sql,re.IGNORECASE):
            result.append(Risk("M40870_"+tag))
    if "FROM public.frfinance_saas_new_admin_published_promotions()" in router:
        result.append(Risk("M40870_LIVE_ROUTE_USES_GUC_DEFINER"))
    if "M40840_FINANCIAL_SQL_NO_GO" not in gate:
        result.append(Risk("M40870_PRODUCTION_GATE_MISSING"))
    return tuple(result)

def inventory() -> tuple[Risk,...]:
    return inspect(SQL.read_text(encoding="utf-8"),
                   ROUTER.read_text(encoding="utf-8"),
                   GATE.read_text(encoding="utf-8"))

def main() -> int:
    try:
        findings=inventory()
    except (OSError,UnicodeError):
        print("M40870_AUDIT=BLOCKED_SOURCE_UNAVAILABLE")
        return 2
    for f in findings:
        print(f.code+"="+f.status)
    print("M40870_SOURCE_ONLY_RISKS="+str(len(findings)))
    print("M40870_LIVE_DATABASE_ATTESTED=FALSE")
    print("M40870_SQL_DELTA=NONE")
    print("M40870_DB_CONNECTIONS=NONE")
    print("M40870_DB_WRITES=NONE")
    print("M40870_PRODUCTION=BLOCKED")
    return 0 if findings else 2

if __name__ == "__main__":
    raise SystemExit(main())
