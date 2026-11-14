#!/usr/bin/env python3
"""M37469 offline release blocker report for Termux/GitHub CI.

Checks versioned test source integrity and existing canonical release
requirements without connecting to services or attempting deployment.
Zero external attestations can be inferred from an offline scan.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.saas_operational_blockers_m37469 import build_operational_blocker_report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="FR Finance M37469 — diagnóstico seguro e offline, sem ativação"
    )
    parser.add_argument(
        "action", choices=("audit", "plan", "json"),
        default="audit", nargs="?",
    )
    args = parser.parse_args(argv)
    try:
        report = build_operational_blocker_report(
            root=ROOT, env=os.environ,
        )
    except (ValueError, OSError, KeyError, TypeError):
        # Do not leak exception details from environment or data files.
        print("M37469_BLOCKED=READONLY_MATRIX_INVALID", file=sys.stderr)
        return 2
    if args.action == "json":
        print(json.dumps(
            report, ensure_ascii=False, indent=2, sort_keys=True,
        ))
        return 0
    print("=== FR FINANCE M37469 — RELEASE READINESS AUDIT ===")
    print("WORKSTREAM=AI_STUDIO")
    print("RELEASE="+report["release_status"])
    print("CI_SOURCE_PACKAGES="+str(report["ci_source_packages_present"])
          +"/"+str(report["ci_package_count"]))
    print("CI_SOURCE_FILES_ARE_REAL_ATTESTATION=NO")
    print("LIVE_PROOFS_VERIFIED="+str(report["live_gates_verified"])
          +"/"+str(report["live_gate_count"]))
    print("PROVIDER_GATES_VERIFIED=0/"
          +str(report["provider_gate_count"]))
    print("OCI_STAGING_VM="+report["oci_staging_vm_running"])
    print("REAL_IDENTITY_E2E=NOT_ATTESTED_BY_THIS_REPORT")
    print("REAL_LEGAL_CONSENT=NOT_ATTESTED_BY_THIS_REPORT")
    print("REAL_LICENSE_PAYMENT_PIX_ACTIVATION=OFF_NOT_AUTHORIZED")
    print("MIGRATIONS_LOCAL_OR_STAGING=NOT_EXECUTED")
    print("NETWORK_AND_DATABASE_IO=NONE")
    print("ORIGINAL_TERMUX_DATABASE=UNTOUCHED")
    for flag, status in report["runtime_flag_classifications_only"].items():
        print("LOCAL_FLAG_"+flag+"="+status)
    if args.action == "plan":
        for item in report["priority_external_proofs"]:
            print("PRIORIDADE_OPERACIONAL="+item["id"])
            print("NEXT_ACTION="+item["next_action"])
        for item in report["blockers"]:
            print("LIVE_GATE_UNVERIFIED="+item["gate_id"]
                  +"|REQUIRED_PROOF="+item["acceptance_proof"])
    print("M37469_READONLY_REPORT=PASS")
    print("PRODUCTION_RELEASE=BLOCKED")
    print("REAL_ACTIVATION_AUTHORIZED=NO")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
