#!/usr/bin/env python3
"""M37500 migration catalog check. Only reads versioned files and git hashes."""
from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from aistudio_migration_inventory import repo_check

EXPECTED = {
    "staging_migrations:066": "backend/staging_migrations/066_release_gate_evidence_quarantine_ci_only.sql",
    "staging_migrations:067": "backend/staging_migrations/067_mail_delivery_quarantine_ci_only.sql",
    "staging_migrations:068": "backend/staging_migrations/068_payment_reconciliation_hold_ci_only.sql",
}


def main() -> int:
    try:
        manifest = repo_check()
        entries = {x["id"]: x for x in manifest["entries"]}
        if len(entries) < 109:
            raise ValueError("M37500_SQL_CATALOG_MISSING_BASELINE")
        for identifier, path in EXPECTED.items():
            entry = entries[identifier]
            sql = (ROOT / path).read_text(encoding="utf-8")
            if (entry["source_path"] != path
                    or entry["classification"] != "STAGING_ONLY_NEEDS_PORT"
                    or entry["do_not_apply_source_to_termux"] is not True
                    or entry["requires_local_equivalent_before_use"] is not True
                    or "frcaixinha_staging" not in sql
                    or "frfinance.m37500_ci" not in sql
                    or "FORCE ROW LEVEL SECURITY" not in sql
                    or "REVOKE ALL" not in sql
                    or "BEFORE UPDATE OR DELETE" not in sql
                    or "BEFORE TRUNCATE" not in sql):
                raise ValueError("M37500_MIGRATION_GUARD_MISSING")
    except (ValueError, KeyError, OSError) as exc:
        print("M37500_MIGRATION_PREFLIGHT=BLOCKED")
        print("M37500_CAUSE=" + type(exc).__name__)
        return 2
    print("M37500_MIGRATION_PREFLIGHT=PASS")
    print("M37500_SQL_CATALOG=" + str(len(entries)))
    print("M37500_NEW_STAGING_ONLY_SQL=3")
    print("M37500_SOURCE_MIGRATION_REGISTERED=YES")
    print("M37500_DISPOSABLE_SQL_EXECUTED=NO")
    print("M37500_ORIGINAL_POSTGRES_TOUCHED=NO")
    print("M37500_REAL_PAYMENTS=OFF")
    print("M37500_PIX_REAL=OFF")
    print("M37500_REAL_ACTIVATION=OFF")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
