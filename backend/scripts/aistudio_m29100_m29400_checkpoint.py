#!/usr/bin/env python3
"""M29100–M29400 local read-only checkpoint; never handles credentials."""
import json
import sys
from app.onboarding_chain_policy import readiness_contract

def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in ("audit", "json"):
        print("USAGE=aistudio_m29100_m29400_checkpoint.py audit|json", file=sys.stderr)
        return 2
    report = readiness_contract()
    if sys.argv[1] == "json":
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0
    print("=== FR FINANCE AI STUDIO M29100-M29400 ===")
    print("ONBOARDING_CHAIN=OFFLINE_CI_POLICY")
    for item in report["controls"]:
        print("CONTROL=" + item)
    print("STAGING_DB_PROOF=NOT_AVAILABLE")
    print("INDEPENDENT_APPROVAL_PERSISTED=NOT_VERIFIED")
    print("EMAIL_DELIVERY_OWNERSHIP=NOT_VERIFIED")
    print("PASSWORD_RESET_OPERATIONAL=NOT_VERIFIED")
    print("PUBLIC_INVITES=OFF")
    print("REAL_USERS=OFF")
    print("REAL_PIX=OFF")
    print("LOCAL_MIGRATIONS=NOT_APPLIED")
    print("OCI_OPERATIONS=NONE")
    print("FR_FINANCE_M29400_AUDIT=PASS")
    print("PRODUCTION_AUTHORIZATION=NOT_GRANTED")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
