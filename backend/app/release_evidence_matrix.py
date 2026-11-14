"""M28700–M29000: release evidence matrix for FR Finance AI Studio.

This is an audit inventory, NOT an authorization engine. No evidence is
promoted by the existence of source files, CI success, a public OCI VM,
or a provider-intake field. No remote services or database are queried.
"""
from __future__ import annotations

from collections import Counter
from typing import Mapping

from .launch_readiness import readiness_manifest
from .operator_release_worklist import release_worklist
from .provider_intake_schema import new_manifest, validate_manifest

# Order matters: stabilize account security first, then infrastructure,
# then financial settlement. This is a suggested engineering sequence only.
PRIORITY_ORDER = (
    "AUTH_PRODUCTION", "MASTER_MFA", "DUAL_CONTROL", "TENANT_RLS",
    "INVITE_TRANSACTION", "VERIFIED_EMAIL", "CANONICAL_CONTRACT",
    "CONTRACT_CONSENT", "MAIL_OUTBOX", "PASSWORD_RECOVERY",
    "OCI_PUBLIC_HTTPS", "OCI_BACKUP_RESTORE", "MIGRATION_PARITY",
    "RUNTIME_SHA", "ANDROID_RELEASE", "MP_CONNECT", "PIX_INBOUND",
    "PIX_OUTBOUND", "FINANCIAL_RECONCILIATION", "ANNUAL_CLOSING",
)

# Tests to be exercised on real staging after CI. They are not claimed
# to be passing because the source file exists.
ACCEPTANCE_PROOFS = {
    "AUTH_PRODUCTION": "AUTH_LOGIN_LOGOUT_PASSWORD_REVOKE_STAGING",
    "MASTER_MFA": "MASTER_MFA_REAL_CHALLENGE_AND_REPLAY",
    "DUAL_CONTROL": "INDEPENDENT_APPROVER_PERSISTED_TRANSACTION",
    "TENANT_RLS": "TENANT_A_B_ADVERSARIAL_DB_READ_WRITE",
    "INVITE_TRANSACTION": "INVITE_SINGLE_USE_RACE_AND_AUDIT",
    "VERIFIED_EMAIL": "OWNERSHIP_CHALLENGE_CONSUMED_ONCE",
    "CANONICAL_CONTRACT": "PUBLISHED_SHA256_FULL_BODY_CHECK",
    "CONTRACT_CONSENT": "RECIPIENT_AFFIRMATIVE_VERSIONED_CONSENT",
    "MAIL_OUTBOX": "DURABLE_SEND_BOUNCE_TIMEOUT_RECONCILIATION",
    "PASSWORD_RECOVERY": "RESET_ONCE_SESSION_FAMILY_REVOKED",
    "OCI_PUBLIC_HTTPS": "PUBLIC_TLS_AND_FIREWALL_STAGING",
    "OCI_BACKUP_RESTORE": "ISOLATED_POSTGRES_RESTORE_AND_RPO_RTO",
    "MIGRATION_PARITY": "SQL_HASHES_ROLES_RLS_REAL_STAGING",
    "RUNTIME_SHA": "API_SHA_MATCHES_SIGNED_APK_BUILD",
    "ANDROID_RELEASE": "SIGNED_RELEASE_UPGRADE_ON_DEVICE",
    "MP_CONNECT": "OAUTH_PKCE_STATE_REFRESH_SEPARATED_TENANTS",
    "PIX_INBOUND": "ORDER_WEBHOOK_SIGNATURE_AND_THREE_SOURCE_LEDGER",
    "PIX_OUTBOUND": "PROVIDER_COMMERCIAL_PERMISSION_AND_LIMITS",
    "FINANCIAL_RECONCILIATION": "APP_PROVIDER_LEDGER_THREE_SOURCE",
    "ANNUAL_CLOSING": "ANNUAL_15_85_ARREARS_EXIT_TWO_TENANTS",
}
PROVIDER_GATES = (
    "OCI_HOSTING", "OCI_VAULT_IAM", "MAIL_PROVIDER",
    "USER_ACTIVATION", "MP_CONNECT", "PIX_INBOUND", "PIX_OUTBOUND",
)


def build_release_matrix(
    public_manifest: Mapping | None = None,
    *,
    contract_baseline: Mapping | None = None,
) -> dict:
    """Produce a non-secret, deterministic snapshot; never authorize release."""
    safe_public = validate_manifest(
        new_manifest() if public_manifest is None else public_manifest
    )
    declared = readiness_manifest({})
    worklist = release_worklist(safe_public)
    ids = tuple(item["id"] for item in declared["requirements"])
    if (ids != PRIORITY_ORDER or set(ids) != set(ACCEPTANCE_PROOFS)
            or len(ids) != len(set(ids))):
        raise ValueError("M28700_RELEASE_GATE_INVENTORY_DRIFT")
    provider_ids = tuple(item["id"] for item in worklist["stages"])
    if provider_ids != PROVIDER_GATES:
        raise ValueError("M28700_PROVIDER_GATE_INVENTORY_DRIFT")

    gates = []
    for index, item in enumerate(declared["requirements"], start=1):
        source_present = item["engineering_source_present"] is True
        gates.append({
            "priority": index,
            "id": item["id"],
            "category": item["category"],
            "engineering_source_present": source_present,
            "status": (
                "SOURCE_MISSING_AND_STAGING_UNVERIFIED"
                if not source_present else "SOURCE_PRESENT_STAGING_UNVERIFIED"
            ),
            "required_evidence": item["required_evidence"],
            "acceptance_proof": ACCEPTANCE_PROOFS[item["id"]],
            "operationally_verified": False,
        })

    providers = []
    for item in worklist["stages"]:
        providers.append({
            "id": item["id"],
            "status": item["status"],
            "missing_public_fields": list(item["public_fields_missing"]),
            "provider_test_approved": False,
            "live_provider_authorized": False,
        })

    baseline = None
    if contract_baseline is not None:
        if (type(contract_baseline) is not dict
                or contract_baseline.get("kind")
                != "HISTORICAL_BASELINE_NOT_CURRENT_COMPLIANCE"
                or contract_baseline.get("production_release_authorized") is not False
                or type(contract_baseline.get("clauses")) is not list):
            raise ValueError("M28700_INVALID_147_BASELINE")
        clauses = contract_baseline["clauses"]
        if len(clauses) != 147 or len({x.get("id") for x in clauses}) != 147:
            raise ValueError("M28700_INVALID_147_BASELINE")
        if any(
            x.get("production_verified") is not False
            or x.get("review_state") != "AWAITING_CLAUSE_EVIDENCE"
            for x in clauses
        ):
            raise ValueError("M28700_UNTRUSTED_CLAUSE_PROMOTION")
        baseline = {
            "source": "HISTORICAL_147_CLAUSES_ONLY",
            "total": len(clauses),
            "counts": dict(sorted(Counter(x["baseline_status"] for x in clauses).items())),
            "live_compliance_claimed": False,
            "promoted_to_verified": 0,
        }

    return {
        "project": "FR_FINANCE_AI_STUDIO",
        "package": "M28700_M29000",
        "mode": "READ_ONLY_REPORT_NO_ACTIVATION",
        "environment": "UNATTESTED_NO_REMOTE_DB",
        "status": "PRODUCTION_NOT_AUTHORIZED",
        "gate_count": len(gates),
        "gates_unverified": len(gates),
        "missing_engineering_sources": [
            x["id"] for x in gates if not x["engineering_source_present"]
        ],
        "staging_acceptance_queue": [
            {"gate": x["id"], "proof": x["acceptance_proof"]}
            for x in gates
        ],
        "gates": gates,
        "provider_gates": providers,
        "provider_gate_count": len(providers),
        "provider_gates_verified": 0,
        "public_fields_absent": worklist_public_absent(safe_public),
        "historical_contract_baseline": baseline,
        "offline_tests_are_production_evidence": False,
        "oci_vm_created_by_this_audit": False,
        "ci_green_enables_user_activation": False,
        "writes_performed": False,
        "authorizations": {
            "real_admins": False,
            "real_members": False,
            "real_mail": False,
            "real_pix_inbound": False,
            "real_pix_outbound": False,
            "real_loans": False,
            "annual_payouts": False,
        },
    }


def worklist_public_absent(manifest: Mapping) -> list[str]:
    from .provider_intake_schema import FIELD_BY_KEY
    return sorted(set(FIELD_BY_KEY) - set(manifest["public_inputs"]))
