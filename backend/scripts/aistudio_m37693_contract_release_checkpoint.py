#!/usr/bin/env python3
"""Read-only FR Finance release/contract audit: summary | json | checklist."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.m37693_contract_release_audit import audit_checkpoint, checklist_markdown


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="M37693-M37973 offline checkpoint")
    p.add_argument("mode", nargs="?", choices=("summary", "json", "checklist"), default="summary")
    args = p.parse_args(argv)
    report = audit_checkpoint()
    if args.mode == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    elif args.mode == "checklist":
        print(checklist_markdown(report))
    else:
        print("=== FR FINANCE M37693-M37973 ===")
        print("PROJECT=FR_FINANCE_AI_STUDIO_ONLY")
        print("AUDIT_MODE=OFFLINE_READ_ONLY")
        print("START_CHECKPOINT=" + report["start_checkpoint"][:7])
        print("CANONICAL_DOC_REQUIREMENTS=57_PENDING")
        print("HISTORICAL_CLAUSES=147_PENDING_INDEPENDENT_REVALIDATION")
        for key, value in sorted(report["historical_baseline_counts"].items()):
            print("HISTORICAL_" + key.replace("Ã", "A").replace("Ç", "C").replace(" ", "_") + "=" + str(value))
        print("HISTORICAL_DIVERGENT_IDS=" + ",".join(report["historical_divergent_ids"]))
        print("LIVE_GATES=0/20")
        print("PROVIDER_GATES=0/7")
        print("AT01_AT50_REAL_E2E=0/50")
        print("PREVIOUS_M37500_TASKS=192_PLANNED")
        print("NEW_TASKS_M37693_M37973=281_PLANNED")
        print("CLOUD_MUTATIONS=NONE")
        print("SQL_MIGRATIONS=NONE")
        print("ORIGINAL_DATABASE_ACCESS=NONE")
        print("REAL_PIX=OFF")
        print("REAL_PAYMENTS=OFF")
        print("REAL_USER_ACTIVATION=OFF")
        print("PRODUCTION_RELEASE=BLOCKED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
