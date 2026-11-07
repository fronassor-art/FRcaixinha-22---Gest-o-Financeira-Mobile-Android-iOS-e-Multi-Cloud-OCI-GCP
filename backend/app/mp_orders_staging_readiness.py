"""AI Studio M12700-M13000: STRICT UNAUTHENTICATED staging readiness matrix.

Every input flag is a CLAIM. Even if all flags are True, no real system
attestation, authenticated storage, migration approval, bank reconciliation,
payment permission or OCI deployment is established. No SQL, I/O or network.
"""
from __future__ import annotations

from dataclasses import dataclass, fields
from re import fullmatch
from uuid import UUID

from .pix_automation_contract import FinancialOperationBlocked

CONTRACT = "AI_STUDIO_M13000_STAGING_PERSISTENCE_READINESS_CLAIMS_V1"

# Enumerated requirements for an eventual independently attested deployment.
# All must be proven outside this model with actual DB/OCI evidence.
REQUIRED_EVIDENCE = (
    "tenant_rls_enabled",
    "tenant_rls_forced",
    "tenant_session_binding_verified",
    "least_privilege_application_role",
    "no_bypassrls_application_role",
    "append_only_audit_enforced",
    "audit_sequence_unique",
    "audit_actor_authenticated",
    "two_distinct_reviewers_verified",
    "global_operation_idempotency_unique",
    "global_order_alias_unique",
    "global_payment_alias_unique",
    "transaction_isolation_tested",
    "concurrent_duplicate_insert_rejected",
    "retry_lease_is_durable",
    "recovery_after_crash_tested",
    "bank_source_independently_authenticated",
    "provider_seller_binding_verified",
    "oauth_secrets_vault_protected",
    "webhook_signature_verified",
    "signed_checkpoint_root_independent",
    "backup_restore_with_rls_tested",
    "tls_and_credential_rotation_tested",
    "operator_revocation_tested",
)


@dataclass(frozen=True)
class StagingReadinessClaims:
    tenant_id: UUID
    provider_account_id: str
    tenant_rls_enabled: bool = False
    tenant_rls_forced: bool = False
    tenant_session_binding_verified: bool = False
    least_privilege_application_role: bool = False
    no_bypassrls_application_role: bool = False
    append_only_audit_enforced: bool = False
    audit_sequence_unique: bool = False
    audit_actor_authenticated: bool = False
    two_distinct_reviewers_verified: bool = False
    global_operation_idempotency_unique: bool = False
    global_order_alias_unique: bool = False
    global_payment_alias_unique: bool = False
    transaction_isolation_tested: bool = False
    concurrent_duplicate_insert_rejected: bool = False
    retry_lease_is_durable: bool = False
    recovery_after_crash_tested: bool = False
    bank_source_independently_authenticated: bool = False
    provider_seller_binding_verified: bool = False
    oauth_secrets_vault_protected: bool = False
    webhook_signature_verified: bool = False
    signed_checkpoint_root_independent: bool = False
    backup_restore_with_rls_tested: bool = False
    tls_and_credential_rotation_tested: bool = False
    operator_revocation_tested: bool = False


@dataclass(frozen=True)
class ReadinessReport:
    tenant_id: UUID
    requirements_total: int
    claims_true: int
    claims_missing: tuple[str, ...]
    all_requirements_claimed: bool
    all_evidence_authenticated: bool = False
    apply_migration_authorized: bool = False
    oci_deploy_authorized: bool = False
    authenticated_persistence_ready: bool = False
    independent_bank_reconciliation_passed: bool = False
    real_payment_authorized: bool = False
    financial_closing_authorized: bool = False
    ledger_write_authorized: bool = False
    payout_authorized: bool = False


@dataclass(frozen=True)
class ReadinessBatchReport:
    tenant_count: int
    requirements_total: int
    claims_true_total: int
    claimed_complete_tenants: int
    all_evidence_authenticated: bool = False
    deployment_authorized: bool = False
    real_payment_authorized: bool = False
    ledger_write_authorized: bool = False


def inspect_readiness_claims(claims: StagingReadinessClaims) -> ReadinessReport:
    if (
        type(claims) is not StagingReadinessClaims
        or type(claims.tenant_id) is not UUID or claims.tenant_id.int == 0
        or type(claims.provider_account_id) is not str
        or fullmatch(r"[0-9]{1,40}", claims.provider_account_id) is None
        or any(type(getattr(claims, key)) is not bool
               for key in REQUIRED_EVIDENCE)
    ):
        raise FinancialOperationBlocked("Declarações de pré-voo inválidas")
    missing = tuple(
        key for key in REQUIRED_EVIDENCE if not getattr(claims, key)
    )
    total = len(REQUIRED_EVIDENCE)
    return ReadinessReport(
        tenant_id=claims.tenant_id,
        requirements_total=total,
        claims_true=total-len(missing),
        claims_missing=missing,
        all_requirements_claimed=not bool(missing),
    )


def summarize_readiness_claims(
    snapshots: tuple[StagingReadinessClaims, ...],
) -> ReadinessBatchReport:
    if type(snapshots) is not tuple or len(snapshots) > 100:
        raise FinancialOperationBlocked("Lote de preparação de staging inválido")
    seen_tenants: set[UUID] = set()
    seen_sellers: dict[str, UUID] = {}
    count_true = 0
    completed = 0
    for claims in snapshots:
        report = inspect_readiness_claims(claims)
        if report.tenant_id in seen_tenants:
            raise FinancialOperationBlocked("Caixinha duplicada em staging")
        seen_tenants.add(report.tenant_id)
        seller_owner = seen_sellers.setdefault(
            claims.provider_account_id, claims.tenant_id
        )
        if seller_owner != claims.tenant_id:
            raise FinancialOperationBlocked(
                "Conta seller real não pode ser compartilhada entre caixinhas"
            )
        count_true += report.claims_true
        completed += int(report.all_requirements_claimed)
    return ReadinessBatchReport(
        tenant_count=len(seen_tenants),
        requirements_total=len(REQUIRED_EVIDENCE) * len(seen_tenants),
        claims_true_total=count_true,
        claimed_complete_tenants=completed,
    )
