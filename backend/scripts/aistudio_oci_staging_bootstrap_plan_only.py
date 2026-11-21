#!/usr/bin/env python3
"""FR Finance M37330: offline bootstrap readiness verification only.

No OCI calls, shell commands, network, config writes, migrations, or secrets.
A PASS means repository templates are present and meet static safety rules;
it does not authorize a deployment or attest a working live server.
"""
from __future__ import annotations
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.oci_staging_bootstrap_plan import (
    BootstrapPlanBlocked,inspect_plan_only,
)


def main()->int:
    print("=== FR FINANCE M37330 OCI REUSE BOOTSTRAP PLAN ONLY ===")
    root=Path(__file__).resolve().parents[2]
    try:
        plan=inspect_plan_only(root)
    except BootstrapPlanBlocked as exc:
        print("M37330_BOOTSTRAP=BLOCKED")
        print("M37330_CAUSE="+str(exc))
        print("OCI_DEPLOYMENT_AUTHORIZED=NO")
        print("OCI_RESOURCE_CREATED=NO")
        print("PIX_REAL=OFF")
        return 2
    print("M37330_BOOTSTRAP=PLAN_ONLY_PASS")
    print("M37330_TEMPLATES="+str(plan.checked_templates))
    print("M37330_TEMPLATES_SHA256="+plan.content_sha256)
    print("M37330_EXISTING_VCN_REUSE_ONLY=YES")
    print("M37330_LOOPBACK_BIND_REQUIRED=YES")
    print("M37330_HTTPS_443_NEEDS_REVIEW=YES")
    print("M37330_EXISTING_CLOUD_BLOCKERS="+str(len(plan.blocked_gates)))
    print("M37330_NO_VM_OR_VAULT_CREATED=YES")
    print("M37330_EXECUTABLE_DEPLOYMENT=NO")
    print("M37330_PRIVATE_DB_PORTS=NOT_PUBLIC")
    print("M37330_SSH_PUBLIC=NOT_PROPOSED")
    print("OCI_DEPLOYMENT_AUTHORIZED=NO")
    print("OCI_RESOURCE_CREATED=NO")
    print("OCI_PAID_UPGRADE=NOT_REQUESTED")
    print("POSTGRESQL_5433=NOT_MODIFIED")
    print("MERCADO_PAGO_REAL=OFF")
    print("PIX_REAL=OFF")
    print("REAL_USER_ACTIVATION=OFF")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
