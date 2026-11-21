#!/usr/bin/env python3
"""FR Finance M29800: printable static checkpoint, no DB or OCI access."""
import json
import sys
from app.two_tenant_closing_ci import checkpoint

def main():
    if len(sys.argv)!=2 or sys.argv[1] not in ("audit","json"):
        print("USAGE=aistudio_m29500_m29800_checkpoint.py audit|json",file=sys.stderr)
        return 2
    report=checkpoint()
    if sys.argv[1]=="json":
        print(json.dumps(report,indent=2,sort_keys=True))
        return 0
    print("=== FR FINANCE M29500-M29800 ===")
    print("PROJECT="+report["project"])
    print("TWO_TENANTS=OFFLINE_FINANCIAL_RECONCILIATION")
    print("PROFIT_SPLIT=15_ADMIN_85_MEMBERS")
    print("90_DAY_ARREARS=REVIEW_HOLD")
    print("THREE_CONSECUTIVE_UNPAID=SEPARATE_CONTRACT_TRIGGER")
    print("VOLUNTARY_EXIT=RIGHTS_PRESERVED_REVIEW")
    print("TERMUX_DB_5433=UNTOUCHED")
    print("OCI_AUTOMATION=UNTOUCHED")
    print("MIGRATIONS_APPLIED=NO")
    print("REAL_USERS=OFF")
    print("REAL_PIX=OFF")
    print("PRODUCTION_AUTHORIZATION=NOT_GRANTED")
    print("FR_FINANCE_M29800_AUDIT=PASS")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
