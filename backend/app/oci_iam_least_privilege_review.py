"""FR Finance M37341-M37350: offline IAM least-privilege review, NEVER APPLY.

The template is deliberately non-executable and contains no real OCIDs.
The only accepted statements scope a single INSTANCE and a single SECRET.
Valid static text cannot authorize IAM, deployment, payment, or real users.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path

TEMPLATE_PATH="infra/oci/staging-reuse/iam-instance-principal.review.template"
EXPECTED=(
    "DYNAMIC_GROUP_NAME=fr-finance-staging-runtime",
    "DYNAMIC_GROUP_MATCHING_RULE=all {instance.compartment.id = '__STAGING_COMPARTMENT_OCID__', instance.id = '__STAGING_INSTANCE_OCID__'}",
    "POLICY_NAME=fr-finance-staging-read-single-secret",
    "POLICY_STATEMENT=Allow dynamic-group '__IDENTITY_DOMAIN__'/'fr-finance-staging-runtime' to read secret-bundles in compartment id __STAGING_COMPARTMENT_OCID__ where target.secret.id = '__APP_SECRET_OCID__'",
    "INSTANCE_PRINCIPAL_TESTED=NO",
    "EFFECTIVE_SECRET_READ_TESTED=NO",
    "MANUAL_OPERATOR_REVIEW_REQUIRED=YES",
    "OCI_RESOURCE_CREATION_AUTHORIZED=NO",
    "PIX_REAL=OFF",
    "REAL_USER_ACTIVATION=OFF",
)


class IAMReviewBlocked(ValueError):
    """Neutral error only; raw OCI policies and identifiers never exposed."""


@dataclass(frozen=True)
class IAMReviewReport:
    template_sha256: str
    expected_statements: int
    identity_domain_unverified: bool
    specific_instance_ocid_missing: bool
    staging_compartment_id_not_versioned: bool
    secret_ocid_missing: bool
    effective_instance_principal_not_verified: bool
    effective_secret_read_not_verified: bool
    operator_approval_required: bool
    read_only: bool = True
    policy_created: bool = False
    dynamic_group_created: bool = False
    vault_created: bool = False
    cloud_changes: bool = False
    deployment_authorized: bool = False
    real_pix_authorized: bool = False
    real_users_authorized: bool = False


def check_iam_template(repo: Path) -> IAMReviewReport:
    if not isinstance(repo,Path) or not repo.is_dir():
        raise IAMReviewBlocked("OCI_IAM_REVIEW_REPO_INVALID")
    target=repo/TEMPLATE_PATH
    if target.is_symlink() or not target.is_file():
        raise IAMReviewBlocked("OCI_IAM_REVIEW_TEMPLATE_MISSING")
    try:
        raw=target.read_bytes()
        if not 10<len(raw)<=8192 or b"\x00" in raw:
            raise ValueError("bad template")
        body=raw.decode("utf-8")
    except (OSError,UnicodeError,ValueError):
        raise IAMReviewBlocked("OCI_IAM_REVIEW_TEMPLATE_INVALID") from None
    lines=[line.strip() for line in body.splitlines()
           if line.strip() and not line.lstrip().startswith("#")]
    if tuple(lines)!=EXPECTED:
        raise IAMReviewBlocked("OCI_IAM_REVIEW_LEAST_PRIVILEGE_DENIED")
    # Guard against a template being replaced by apparently equivalent
    # text with real OCIDs or executable commands.
    if "ocid1." in body or "BEGIN PRIVATE KEY" in body or "sk_live_" in body:
        raise IAMReviewBlocked("OCI_IAM_REVIEW_PRIVATE_DATA_DENIED")
    return IAMReviewReport(
        template_sha256=hashlib.sha256(raw).hexdigest(),
        expected_statements=2,
        identity_domain_unverified=True,
        specific_instance_ocid_missing=True,
        staging_compartment_id_not_versioned=True,
        secret_ocid_missing=True,
        effective_instance_principal_not_verified=True,
        effective_secret_read_not_verified=True,
        operator_approval_required=True,
    )
