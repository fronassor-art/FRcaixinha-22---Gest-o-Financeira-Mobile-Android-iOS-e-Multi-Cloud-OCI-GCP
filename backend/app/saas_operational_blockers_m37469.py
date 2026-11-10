"""M37469 — offline FR Finance operational launch-blocker inventory.

This is NOT a production release/authorization gate. Source-file presence,
GitHub test logs and provider configuration cannot attest live acceptance.
This module makes the remaining real-world work explicit, without sending
credentials, connecting to PostgreSQL, contacting OCI/MP/Brevo, or writing.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Mapping

from .release_evidence_matrix import (
    ACCEPTANCE_PROOFS, PRIORITY_ORDER, PROVIDER_GATES,
    build_release_matrix,
)

CI_MILESTONES = (
    ("M37458", ("backend/tests/test_m37458_saas_consent_before_preparation_ci.py",)),
    ("M37459", (
        "backend/tests/test_m37459_saas_api_contract_ci.py",
        "backend/tests/test_m37459_saas_api_transaction_ci.py",
    )),
    ("M37460", ("backend/tests/test_m37460_saas_authenticated_boundary_ci.py",)),
    ("M37461", ("backend/tests/test_m37461_saas_server_context_readback_ci.py",)),
    ("M37462", ("backend/tests/test_m37462_verified_session_binding_ci.py",)),
    ("M37463", ("backend/tests/test_m37463_token_scoped_offer_readback_ci.py",)),
    ("M37464", ("backend/tests/test_m37464_atomic_consent_lock_ci.py",)),
    ("M37465", ("backend/tests/test_m37465_saas_http_atomic_adapter_ci.py",)),
    ("M37466", ("backend/tests/test_m37466_post_commit_audit_ci.py",)),
    ("M37467", ("backend/tests/test_m37467_frozen_offer_idempotence_ci.py",)),
    ("M37468", ("backend/tests/test_m37468_frozen_receipt_audit_ci.py",)),
)
# These are the operational domains a green CI CANNOT prove, no matter how
# many disposable SQL, HTTP or static tests succeeded.
REQUIRED_LIVE_DOMAINS = {
    "IDENTITY_REAL_E2E": (
        "AUTH_PRODUCTION","MASTER_MFA","DUAL_CONTROL",
        "TENANT_RLS","VERIFIED_EMAIL","PASSWORD_RECOVERY",
    ),
    "CONTRACT_LEGAL_ACCEPTANCE": (
        "CANONICAL_CONTRACT","CONTRACT_CONSENT","INVITE_TRANSACTION",
    ),
    "OCI_AND_PRODUCTION_RUNTIME": (
        "OCI_PUBLIC_HTTPS","OCI_BACKUP_RESTORE","MIGRATION_PARITY",
        "RUNTIME_SHA","ANDROID_RELEASE",
    ),
    "SMTP_DELIVERY": ("MAIL_OUTBOX",),
    "PAYMENTS_AND_LICENSE": (
        "MP_CONNECT","PIX_INBOUND","PIX_OUTBOUND",
        "FINANCIAL_RECONCILIATION","ANNUAL_CLOSING",
    ),
}
REAL_ACTIONS = (
    "REAL_ADMIN_ACTIVATION","REAL_MEMBER_ACTIVATION","LICENSE_ISSUANCE",
    "PAYMENT_COLLECTION","PIX_INBOUND","PIX_OUTBOUND","USER_EMAIL_SEND",
)
KNOWN_RUNTIME_FLAGS = (
    "FR_FINANCE_PIX_REAL","FR_FINANCE_SAAS_REAL",
    "FR_FINANCE_LICENSE_REAL","FR_FINANCE_PAYMENT_REAL",
    "FR_FINANCE_ACTIVATION_REAL",
)
NEXT_OPERATOR_PROOFS = (
    ("OCI_STAGING_RUNNING_INSTANCE", "OCI_PUBLIC_HTTPS",
     "Verificar VM OCI RUNNING na região sa-saopaulo-1; registrar OCID não secreto, VCN, DNS e HTTPS real"),
    ("OCI_TLS_RLS_BACKUP", "MIGRATION_PARITY",
     "Implantar ambiente de staging, testar TLS/PostgreSQL roles e RLS de dois tenants; restaurar backup isolado"),
    ("AUTH_REAL_LOGIN_REVOKE_MFA", "AUTH_PRODUCTION",
     "Exercitar login, logout, revogação e MFA com duas contas de teste autorizadas no staging"),
    ("PUBLISHED_CONTRACT_LEGAL_CONSENT", "CONTRACT_CONSENT",
     "Aprovar texto jurídico, publicar hash do documento, provar identidade e aceite expresso de uma conta de teste"),
    ("SMTP_BREVO_DELIVERY", "MAIL_OUTBOX",
     "Validar SPF/DKIM/DMARC, envio e recebimento em caixa de teste e recuperação após falhas"),
    ("MP_OAUTH_CONNECT_TENANT", "MP_CONNECT",
     "Homologar OAuth Connect e autorização de cada administrador em conta de teste; segredos no Vault"),
    ("PIX_PROVIDER_SETTLEMENT", "PIX_INBOUND",
     "Homologar Orders/webhook assinado e conciliar PSP, aplicativo e Livro-Razão em sandbox"),
    ("PIX_OUTBOUND_COMMERCIALLY_APPROVED", "PIX_OUTBOUND",
     "Obter habilitação comercial/documental Money Out do provedor antes de qualquer transferência"),
    ("SIGNED_ANDROID_RUNTIME_EQUIVALENCE", "ANDROID_RELEASE",
     "Testar APK/AAB de release assinado e checar SHA compatível com a API em staging"),
)
READ_ONLY_STATE = {
    "real_admins": False,
    "real_members": False,
    "license_issue": False,
    "payment_collection": False,
    "pix_inbound": False,
    "pix_outbound": False,
    "mail_send": False,
    "migration_apply": False,
    "cloud_mutation": False,
    "deploy": False,
}


@dataclass(frozen=True)
class PackageFileEvidence:
    milestone: str
    files_present: bool
    file_sha256: tuple[str, ...]
    verified_in_real_staging: bool = False


def _check_ci_sources(root: Path) -> tuple[PackageFileEvidence, ...]:
    """Hash code bytes only; never confuse a source hash with test success."""
    found = []
    for milestone, paths in CI_MILESTONES:
        digests = []
        complete = True
        for relative in paths:
            file = root / relative
            # Forbid symlinks and unexpected large files from declaring
            # coverage. Missing source never becomes a deployment approval.
            try:
                if (file.is_symlink() or not file.is_file()
                        or file.stat().st_size > 2_000_000):
                    complete = False
                    continue
                digests.append(sha256(file.read_bytes()).hexdigest())
            except (OSError, ValueError):
                complete = False
        found.append(PackageFileEvidence(
            milestone=milestone,
            files_present=complete and len(digests) == len(paths),
            file_sha256=tuple(digests) if complete else (),
        ))
    return tuple(found)


def build_operational_blocker_report(
    *, root: Path, env: Mapping[str, str] | None = None,
) -> dict:
    """Pure offline report. Returns no authority even for all green sources."""
    if type(root) is not Path:
        raise ValueError("M37469_TRUSTED_REPOSITORY_ROOT_REQUIRED")
    # No environment secrets are copied, printed, hashed or validated. Only
    # exact OFF/NOT_DECLARED/NON_OFF classification of five known flag names.
    environment = {} if env is None else env
    if not isinstance(environment, Mapping):
        raise ValueError("M37469_ENVIRONMENT_MAPPING_REQUIRED")
    matrix = build_release_matrix()
    gates = matrix["gates"]
    ids = tuple(g["id"] for g in gates)
    if (ids != PRIORITY_ORDER
            or len(gates) != 20
            or tuple(g["id"] for g in matrix["provider_gates"])
                != PROVIDER_GATES
            or any(g["operationally_verified"] for g in gates)
            or set(ACCEPTANCE_PROOFS) != set(ids)):
        raise ValueError("M37469_BASELINE_GATE_DRIFT")
    grouped = {
        gate_id for items in REQUIRED_LIVE_DOMAINS.values() for gate_id in items
    }
    if grouped != set(ids) or sum(map(len, REQUIRED_LIVE_DOMAINS.values())) != len(ids):
        raise ValueError("M37469_UNMAPPED_RELEASE_REQUIREMENT")

    files = _check_ci_sources(root)
    flag_states = {}
    for key in KNOWN_RUNTIME_FLAGS:
        value = environment.get(key)
        flag_states[key] = (
            "DECLARED_OFF" if value == "OFF"
            else "NOT_DECLARED" if value is None
            else "NON_OFF_DO_NOT_DEPLOY"
        )
    # Values for environment/DSNs/OCI tokens are NEVER returned.
    blocks = []
    for domain, members in REQUIRED_LIVE_DOMAINS.items():
        for gate in members:
            entry = next(g for g in gates if g["id"] == gate)
            blocks.append({
                "domain": domain,
                "gate_id": gate,
                "required_evidence": entry["required_evidence"],
                "acceptance_proof": ACCEPTANCE_PROOFS[gate],
                "source_code_present": entry["engineering_source_present"],
                "verified_live": False,
                "status": "EXTERNAL_STAGING_PROOF_REQUIRED",
            })
    priorities = [{
        "id": action,
        "gate_id": linked_gate,
        "responsible": "OPERATOR_AND_DEVELOPER",
        "next_action": instructions,
        "state": "REAL_WORLD_EVIDENCE_NOT_COLLECTED_BY_THIS_REPORT",
    } for action, linked_gate, instructions in NEXT_OPERATOR_PROOFS]
    return {
        "project": "FR_FINANCE_AI_STUDIO",
        "package": "M37469",
        "mode": "LOCAL_READ_ONLY_NO_NETWORK_NO_DB",
        "release_status": "BLOCKED_REQUIRES_INDEPENDENT_LIVE_PROOFS",
        "production_authorized": False,
        "staging_deployment_authorized": False,
        "ci_only_code_cannot_activate_users": True,
        "ci_proof_is_live_attestation": False,
        "infrastructure_state": "NOT_QUERIED_UNVERIFIED",
        "psp_provider_state": "NOT_QUERIED_UNVERIFIED",
        "email_provider_state": "NOT_QUERIED_UNVERIFIED",
        "oci_staging_vm_running": "NOT_QUERIED_UNVERIFIED",
        "sql_migrations_applied": False,
        "financial_tables_written": False,
        "ci_package_count": len(files),
        "ci_source_packages_present": sum(x.files_present for x in files),
        "ci_test_run_passed_by_this_report": False,
        "ci_package_sources": [
            {
                "id": x.milestone,
                "source_files_present": x.files_present,
                "sha256_of_code_only_not_ci_proof": list(x.file_sha256),
                "real_staging_verified": x.verified_in_real_staging,
            } for x in files
        ],
        "live_gate_count": len(blocks),
        "live_gates_verified": 0,
        "live_gates_unverified": len(blocks),
        "provider_gate_count": len(PROVIDER_GATES),
        "provider_gates_verified": 0,
        "blockers": blocks,
        "priority_external_proofs": priorities,
        "runtime_flag_classifications_only": flag_states,
        "all_live_actions_disabled_by_this_tool": dict(READ_ONLY_STATE),
        "release_approval_decision": "NOT_ISSUED",
        "writes_performed": False,
        "network_calls_performed": False,
    }
