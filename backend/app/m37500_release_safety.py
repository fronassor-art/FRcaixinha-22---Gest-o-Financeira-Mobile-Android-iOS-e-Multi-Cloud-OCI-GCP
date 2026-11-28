"""FR Finance M37500: pure offline gates. Never activates users, money or cloud.

These deterministic checks are preflight evidence only. Passing them does not
prove a database transaction, real identity, provider settlement or consent.
No HTTP, SQL, filesystem, subprocess, secrets or mutable global state.
"""
from __future__ import annotations

from dataclasses import dataclass
from hmac import compare_digest
import re
from uuid import UUID

_HEX = re.compile(r"[0-9a-f]{64}\Z")
_KEY = re.compile(r"[A-Za-z0-9_-]{24,100}\Z")
_STATE = frozenset(("PENDING", "ACCEPTED", "DELIVERED", "BOUNCED"))


def _uuid(value: object) -> bool:
    if type(value) is not str:
        return False
    try:
        parsed = UUID(value)
        return parsed.int != 0 and str(parsed) == value
    except (ValueError, TypeError, AttributeError):
        return False


def _digest(value: object) -> bool:
    return type(value) is str and bool(_HEX.fullmatch(value))


def _key(value: object) -> bool:
    return type(value) is str and bool(_KEY.fullmatch(value))


@dataclass(frozen=True)
class GateDecision:
    code: str
    failures: tuple[str, ...]
    sandbox_candidate: bool = False
    real_activation_authorized: bool = False
    provider_payment_authorized: bool = False
    pix_real_authorized: bool = False

    def __post_init__(self) -> None:
        if (self.real_activation_authorized or self.provider_payment_authorized
                or self.pix_real_authorized):
            raise ValueError("M37500_REAL_OPERATION_FORBIDDEN")
        if not self.failures and not self.sandbox_candidate:
            raise ValueError("M37500_EMPTY_DECISION")
        if self.sandbox_candidate and self.failures:
            raise ValueError("M37500_CONTRADICTORY_DECISION")


def _result(prefix: str, failures: list[str]) -> GateDecision:
    if failures:
        return GateDecision(prefix + "_BLOCKED", tuple(dict.fromkeys(failures)))
    return GateDecision(prefix + "_SANDBOX_CANDIDATE_ONLY", (), True)


@dataclass(frozen=True)
class MemberAdmission:
    tenant_id: str
    invitation_tenant_id: str
    subject_id: str
    invitation_subject_id: str
    admin_id: str
    independent_approver_id: str
    request_key: str
    previous_request_key: str | None
    published_contract_sha: str
    accepted_contract_sha: str
    email_ownership_consumed: bool
    subject_identity_verified: bool
    consent_affirmative: bool
    admin_approved: bool
    independent_approved: bool
    master_mfa_verified: bool
    contribution_cents: int
    overdue_days: int


def review_member(e: MemberAdmission) -> GateDecision:
    if type(e) is not MemberAdmission:
        return GateDecision("MEMBER_BLOCKED", ("WRONG_EVIDENCE_TYPE",))
    failures: list[str] = []
    if not all(_uuid(v) for v in (
        e.tenant_id, e.invitation_tenant_id, e.subject_id,
        e.invitation_subject_id, e.admin_id, e.independent_approver_id,
    )):
        failures.append("IDENTITY_FORMAT")
    if (e.tenant_id != e.invitation_tenant_id
            or e.subject_id != e.invitation_subject_id):
        failures.append("TENANT_OR_SUBJECT_MISMATCH")
    if (e.subject_id in (e.admin_id, e.independent_approver_id)
            or e.admin_id == e.independent_approver_id):
        failures.append("SEGREGATION_DENIED")
    if not _key(e.request_key):
        failures.append("REQUEST_KEY_INVALID")
    if e.previous_request_key is not None:
        failures.append("REPLAY_OR_CONFLICT_REQUIRES_PERSISTED_READBACK")
    if (not _digest(e.published_contract_sha)
            or not _digest(e.accepted_contract_sha)
            or not compare_digest(e.published_contract_sha,
                                  e.accepted_contract_sha)):
        failures.append("CONTRACT_VERSION_MISMATCH")
    for name, value in (
        ("EMAIL_NOT_VERIFIED", e.email_ownership_consumed),
        ("IDENTITY_NOT_VERIFIED", e.subject_identity_verified),
        ("CONSENT_NOT_AFFIRMATIVE", e.consent_affirmative),
        ("ADMIN_NOT_APPROVED", e.admin_approved),
        ("INDEPENDENT_APPROVER_MISSING", e.independent_approved),
        ("MASTER_MFA_MISSING", e.master_mfa_verified),
    ):
        if value is not True:
            failures.append(name)
    if type(e.contribution_cents) is not int or not 15000 <= e.contribution_cents <= 10**11:
        failures.append("MINIMUM_150_BRL_OR_AMOUNT_INVALID")
    if type(e.overdue_days) is not int or e.overdue_days < 0:
        failures.append("ARREARS_INVALID")
    elif e.overdue_days >= 90:
        failures.append("ARREARS_90_DAY_HOLD")
    return _result("MEMBER", failures)


@dataclass(frozen=True)
class MailOutbox:
    tenant_id: str
    request_key: str
    recipient_digest: str
    encrypted_envelope_digest: str
    challenged_at_epoch: int
    expires_at_epoch: int
    now_epoch: int
    attempts: int
    provider_state: str
    ownership_proven: bool
    duplicate_claim_observed: bool


def review_mail(e: MailOutbox) -> GateDecision:
    if type(e) is not MailOutbox:
        return GateDecision("MAIL_BLOCKED", ("WRONG_EVIDENCE_TYPE",))
    f: list[str] = []
    if not _uuid(e.tenant_id):
        f.append("TENANT_INVALID")
    if not _key(e.request_key):
        f.append("IDEMPOTENCY_KEY_INVALID")
    if not _digest(e.recipient_digest) or not _digest(e.encrypted_envelope_digest):
        f.append("ENVELOPE_OR_RECIPIENT_DIGEST_INVALID")
    if any(type(x) is not int for x in (
        e.challenged_at_epoch, e.expires_at_epoch, e.now_epoch)):
        f.append("CLOCK_INVALID")
    elif (e.challenged_at_epoch <= 0 or e.now_epoch < e.challenged_at_epoch
          or e.expires_at_epoch <= e.challenged_at_epoch
          or e.expires_at_epoch - e.challenged_at_epoch > 900
          or e.now_epoch >= e.expires_at_epoch):
        f.append("CHALLENGE_EXPIRED_OR_CLOCK_INVALID")
    if type(e.attempts) is not int or not 0 <= e.attempts < 3:
        f.append("ATTEMPT_LIMIT")
    if e.provider_state not in _STATE:
        f.append("PROVIDER_STATUS_INVALID")
    elif e.provider_state == "BOUNCED":
        f.append("PROVIDER_BOUNCE_HOLD")
    elif e.provider_state != "DELIVERED":
        f.append("DELIVERY_NOT_PROVEN")
    if e.ownership_proven is not True:
        f.append("EMAIL_OWNERSHIP_NOT_PROVEN")
    if e.duplicate_claim_observed is not False:
        f.append("DUPLICATE_OR_REPLAY")
    return _result("MAIL", f)


@dataclass(frozen=True)
class PaymentReconciliation:
    tenant_id: str
    provider_tenant_id: str
    ledger_tenant_id: str
    request_key: str
    provider_payment_id: str
    order_amount_cents: int
    provider_amount_cents: int
    ledger_amount_cents: int
    currency: str
    provider_state: str
    webhook_signature_verified: bool
    direct_provider_readback_verified: bool
    provider_test_mode: bool
    ledger_reference_unique: bool
    reversal_or_dispute_observed: bool
    previously_seen_request: bool


def review_payment(e: PaymentReconciliation) -> GateDecision:
    if type(e) is not PaymentReconciliation:
        return GateDecision("PAYMENT_BLOCKED", ("WRONG_EVIDENCE_TYPE",))
    f: list[str] = []
    if (not all(_uuid(v) for v in
                (e.tenant_id, e.provider_tenant_id, e.ledger_tenant_id))
            or len({e.tenant_id, e.provider_tenant_id, e.ledger_tenant_id}) != 1):
        f.append("TENANT_ISOLATION_DENIED")
    if not _key(e.request_key):
        f.append("REQUEST_KEY_INVALID")
    if not (type(e.provider_payment_id) is str
            and re.fullmatch(r"[0-9]{1,40}", e.provider_payment_id)):
        f.append("PROVIDER_ID_INVALID")
    amounts = (e.order_amount_cents, e.provider_amount_cents, e.ledger_amount_cents)
    if any(type(x) is not int or not 1 <= x <= 10**12 for x in amounts):
        f.append("AMOUNT_INVALID")
    elif len(set(amounts)) != 1:
        f.append("THREE_SOURCE_AMOUNT_MISMATCH")
    if e.currency != "BRL":
        f.append("CURRENCY_DENIED")
    if e.provider_state != "APPROVED":
        f.append("PROVIDER_NOT_APPROVED")
    for name, value in (
        ("WEBHOOK_SIGNATURE_NOT_VERIFIED", e.webhook_signature_verified),
        ("DIRECT_PROVIDER_READBACK_MISSING", e.direct_provider_readback_verified),
        ("SANDBOX_REQUIRED", e.provider_test_mode),
        ("LEDGER_REFERENCE_NOT_UNIQUE", e.ledger_reference_unique),
    ):
        if value is not True:
            f.append(name)
    if e.reversal_or_dispute_observed is not False:
        f.append("REVERSAL_DISPUTE_HOLD")
    if e.previously_seen_request is not False:
        f.append("REPLAY_REQUIRES_STORED_RESULT")
    return _result("PAYMENT", f)


@dataclass(frozen=True)
class StagingInfrastructure:
    region: str
    staging_vm_running: int
    staging_vm_provisioning: int
    active_vaults: int
    project_dynamic_groups: int
    internet_route_configured: bool
    public_https_443_ingress: bool
    public_ssh_22_ingress: bool
    public_database_ingress: bool
    tls_endpoint_verified: bool
    backup_restore_verified: bool
    iam_instance_principal_verified: bool


def review_infrastructure(e: StagingInfrastructure) -> GateDecision:
    if type(e) is not StagingInfrastructure:
        return GateDecision("OCI_BLOCKED", ("WRONG_EVIDENCE_TYPE",))
    f: list[str] = []
    if e.region != "sa-saopaulo-1":
        f.append("WRONG_REGION")
    counts = (e.staging_vm_running, e.staging_vm_provisioning,
              e.active_vaults, e.project_dynamic_groups)
    if any(type(x) is not int or not 0 <= x <= 100000 for x in counts):
        f.append("COUNTS_INVALID")
    elif e.staging_vm_running == 0:
        f.append("NO_RUNNING_STAGING_VM")
    for label, flag in (
        ("IGW_ROUTE_MISSING", e.internet_route_configured),
        ("HTTPS_443_INGRESS_MISSING", e.public_https_443_ingress),
        ("TLS_ENDPOINT_NOT_VERIFIED", e.tls_endpoint_verified),
        ("BACKUP_RESTORE_NOT_VERIFIED", e.backup_restore_verified),
        ("INSTANCE_PRINCIPAL_NOT_VERIFIED", e.iam_instance_principal_verified),
    ):
        if flag is not True:
            f.append(label)
    if e.public_ssh_22_ingress is not False:
        f.append("PUBLIC_SSH_REVIEW_REQUIRED")
    if e.public_database_ingress is not False:
        f.append("PUBLIC_DATABASE_PORT_DENIED")
    if any(type(x) is int and x == 0 for x in (e.active_vaults, e.project_dynamic_groups)):
        f.append("VAULT_OR_IAM_GROUP_NOT_READY")
    return _result("OCI", f)


def review_annual_distribution(
    *, total_profit_cents: object, admin_cents: object,
    members_cents: object, overdue_member_included: object,
) -> GateDecision:
    f: list[str] = []
    if any(type(v) is not int or not 0 <= v <= 10**15 for v in
           (total_profit_cents, admin_cents, members_cents)):
        f.append("CENTS_INVALID")
    else:
        expected_admin = total_profit_cents * 15 // 100
        if (admin_cents != expected_admin
                or members_cents != total_profit_cents - expected_admin):
            f.append("FIFTEEN_EIGHTYFIVE_MISMATCH")
    if overdue_member_included is not False:
        f.append("ARREARS_MEMBER_IN_DISTRIBUTION")
    return _result("ANNUAL", f)


def all_real_actions_off(*decisions: GateDecision) -> bool:
    return bool(decisions) and all(
        type(d) is GateDecision and not (
            d.real_activation_authorized or d.provider_payment_authorized
            or d.pix_real_authorized
        ) for d in decisions
    )
