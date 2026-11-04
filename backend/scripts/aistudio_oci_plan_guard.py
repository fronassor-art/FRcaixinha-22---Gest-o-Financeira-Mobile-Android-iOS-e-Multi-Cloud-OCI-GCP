#!/usr/bin/env python3
"""Offline M2700: validate Terraform JSON plan; never calls OCI or terraform apply."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.oci_staging_plan_guard import StagingPlanBlocked, audit_plan_file


def main() -> int:
    if len(sys.argv) != 2:
        print("USO: python backend/scripts/aistudio_oci_plan_guard.py <arquivo-plan-json>")
        return 2
    try:
        addresses = audit_plan_file(Path(sys.argv[1]))
    except (StagingPlanBlocked, OSError):
        # No path, raw plan, secrets or user data in output.
        print("OCI_STAGING_PLAN_GUARD=BLOCKED")
        return 3
    print("OCI_STAGING_PLAN_GUARD=PASS")
    print("RECURSOS_ISOLADOS="+str(len(addresses)))
    print("APPLY_AUTORIZADO=NAO")
    print("OCI_PROVISIONADA=NAO_VERIFICADO")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
