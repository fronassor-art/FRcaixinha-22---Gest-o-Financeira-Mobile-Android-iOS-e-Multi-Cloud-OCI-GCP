#!/usr/bin/env python3
"""FR Finance M37350: print inert IAM review checklist; no OCI access."""
from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.oci_iam_least_privilege_review import IAMReviewBlocked,check_iam_template


def main()->int:
    print("=== FR FINANCE M37350 IAM PLAN ONLY ===")
    try:
        summary=check_iam_template(Path(__file__).resolve().parents[2])
    except IAMReviewBlocked as exc:
        print("M37350_IAM_PLAN=BLOCKED")
        print("M37350_CAUSE="+str(exc))
        print("OCI_DEPLOYMENT_AUTHORIZED=NO")
        print("PIX_REAL=OFF")
        return 2
    print("M37350_IAM_PLAN=PLAN_ONLY_PASS")
    print("M37350_STATIC_SHA256="+summary.template_sha256)
    print("M37350_SCOPED_STATEMENTS="+str(summary.expected_statements))
    print("OCI_INSTANCE_OCID_AVAILABLE_FOR_PLAN=NO")
    print("OCI_VAULT_SECRET_OCID_AVAILABLE_FOR_PLAN=NO")
    print("OCI_IDENTITY_DOMAIN_VALIDATED_FOR_PLAN=NO")
    print("OCI_PRINCIPAL_AUTH_VERIFIED=NO")
    print("OCI_EFFECTIVE_SECRET_ACCESS_VERIFIED=NO")
    print("OCI_MANUAL_OPERATOR_APPROVAL_REQUIRED=YES")
    print("OCI_DYNAMIC_GROUP_CREATED=NO")
    print("OCI_IAM_POLICY_CREATED=NO")
    print("OCI_RESOURCE_CREATED=NO")
    print("OCI_DEPLOYMENT_AUTHORIZED=NO")
    print("MERCADO_PAGO_REAL=OFF")
    print("PIX_REAL=OFF")
    print("REAL_USER_ACTIVATION=OFF")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
