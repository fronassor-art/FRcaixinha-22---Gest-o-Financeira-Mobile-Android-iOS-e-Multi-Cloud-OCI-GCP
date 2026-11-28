"""M29100-M29400: synthetic onboarding chain policy, never an execution authority.

This checks cross-step correlation of hypothetical evidence. It cannot assert
that an e-mail inbox was controlled, that an approval was persisted, that a
session was issued, or that PostgreSQL RLS was enforced. No DB, network, token,
credential or live identity is consumed. Real activation remains disabled.
"""
from __future__ import annotations

from dataclasses import dataclass
from hmac import compare_digest
import re
from uuid import UUID


@dataclass(frozen=True, kw_only=True)
class JourneyCase:
    flow: str  # ADMIN or MEMBER
    now: int
    tenant_id: UUID
    actor_id: UUID
    actor_role: str
    actor_tenant_id: UUID | None
    actor_is_master: bool
    recipient_id: UUID
    reviewer_id: UUID
    reviewer_tenant_id: UUID
    reviewer_approved: bool
    master_mfa_claimed: bool
    expected_revision: int
    observed_revision: int
    invitation_id: UUID
    invitation_tenant_id: UUID
    invitation_recipient_id: UUID
    invitation_target_role: str
    invitation_document_id: UUID
    invitation_expires_at: int
    invitation_consumptions: int
    invitation_revoked: bool
    challenge_invitation_id: UUID
    challenge_recipient_id: UUID
    challenge_expires_at: int
    challenge_consumptions: int
    email_verified_claimed: bool
    delivery_status: str
    published_document_id: UUID
    published_sha256: str
    accepted_sha256: str
    consent_actor_id: UUID
    consent_explicit: bool
    session_user_id: UUID
    session_role: str
    session_tenant_id: UUID | None
    session_active_claimed: bool
    password_reset_performed: bool = False
    reset_token_consumptions: int = 0
    previous_sessions_revoked: bool = False


def _uuid_ok(value: object) -> bool:
    return isinstance(value, UUID) and value.int != 0


def _digest_ok(value: object) -> bool:
    return type(value) is str and re.fullmatch(r"[a-f0-9]{64}", value) is not None


def assess_journey(case: JourneyCase) -> dict:
    """Evaluate evidence *consistency*, not evidence origin or production readiness.

    Values MUST come from trusted, independent durable authorities in a future
    staging adapter. The caller's assertions are untrusted here; therefore
    even a fully matching hypothetical case NEVER grants account activation.
    """
    if type(case) is not JourneyCase:
        raise ValueError("M29100_INVALID_CASE")
    ids = (
        case.tenant_id, case.actor_id, case.recipient_id, case.reviewer_id,
        case.reviewer_tenant_id, case.invitation_id, case.invitation_tenant_id,
        case.invitation_recipient_id, case.invitation_document_id,
        case.challenge_invitation_id, case.challenge_recipient_id,
        case.published_document_id, case.consent_actor_id, case.session_user_id,
    )
    if (any(not _uuid_ok(v) for v in ids)
            or (case.actor_tenant_id is not None and not _uuid_ok(case.actor_tenant_id))
            or (case.session_tenant_id is not None and not _uuid_ok(case.session_tenant_id))
            or any(type(v) is not bool for v in (
                case.actor_is_master, case.reviewer_approved,
                case.master_mfa_claimed, case.invitation_revoked,
                case.email_verified_claimed, case.consent_explicit,
                case.session_active_claimed, case.password_reset_performed,
                case.previous_sessions_revoked,
            ))
            or any(type(v) is not int for v in (
                case.now, case.expected_revision, case.observed_revision,
                case.invitation_expires_at, case.invitation_consumptions,
                case.challenge_expires_at, case.challenge_consumptions,
                case.reset_token_consumptions,
            ))):
        raise ValueError("M29100_MALFORMED_EVIDENCE")
    failures: list[str] = []
    def fail(condition: bool, code: str) -> None:
        if condition:
            failures.append(code)

    target_role = {"ADMIN": "TENANT_ADMIN", "MEMBER": "TENANT_MEMBER"}.get(case.flow)
    fail(target_role is None, "INVALID_FLOW")
    if case.flow == "ADMIN":
        fail(case.actor_role != "MASTER" or not case.actor_is_master
             or case.actor_tenant_id is not None, "MASTER_CONTEXT_INVALID")
        fail(not case.master_mfa_claimed, "MASTER_MFA_NOT_CLAIMED")
    elif case.flow == "MEMBER":
        fail(case.actor_role != "TENANT_ADMIN" or case.actor_tenant_id != case.tenant_id,
             "TENANT_ADMIN_CONTEXT_INVALID")
    fail(case.actor_id == case.recipient_id, "SELF_INVITATION_DENIED")
    fail(case.reviewer_id in (case.actor_id, case.recipient_id)
         or case.reviewer_tenant_id != case.tenant_id
         or not case.reviewer_approved, "INDEPENDENT_REVIEW_NOT_MATCHED")
    fail(case.expected_revision <= 0 or case.expected_revision != case.observed_revision,
         "REVIEW_REVISION_CONFLICT")

    fail(case.invitation_tenant_id != case.tenant_id
         or case.invitation_recipient_id != case.recipient_id
         or case.invitation_target_role != target_role, "INVITATION_SCOPE_MISMATCH")
    fail(case.invitation_revoked or case.invitation_expires_at <= case.now,
         "INVITATION_REVOKED_OR_EXPIRED")
    fail(case.invitation_consumptions != 1, "INVITATION_SINGLE_USE_NOT_MATCHED")
    fail(case.challenge_invitation_id != case.invitation_id
         or case.challenge_recipient_id != case.recipient_id, "EMAIL_CHALLENGE_BINDING_MISMATCH")
    fail(case.challenge_expires_at <= case.now
         or case.challenge_expires_at > case.invitation_expires_at,
         "EMAIL_CHALLENGE_EXPIRED_OR_OUT_OF_SCOPE")
    fail(case.challenge_consumptions != 1 or not case.email_verified_claimed,
         "EMAIL_OWNERSHIP_SINGLE_USE_NOT_MATCHED")
    fail(case.delivery_status != "DELIVERED", "DELIVERY_PROOF_NOT_MATCHED")

    fail(case.published_document_id != case.invitation_document_id,
         "PUBLISHED_CONTRACT_BINDING_MISMATCH")
    fail(not _digest_ok(case.published_sha256)
         or not _digest_ok(case.accepted_sha256)
         or not compare_digest(case.published_sha256, case.accepted_sha256),
         "VERSIONED_CONTRACT_DIGEST_MISMATCH")
    fail(not case.consent_explicit or case.consent_actor_id != case.recipient_id,
         "RECIPIENT_CONSENT_NOT_MATCHED")

    fail(case.session_user_id != case.recipient_id
         or case.session_tenant_id != case.tenant_id
         or case.session_role != target_role
         or not case.session_active_claimed, "INDIVIDUAL_SESSION_SCOPE_MISMATCH")
    if case.password_reset_performed:
        fail(case.reset_token_consumptions != 1 or not case.previous_sessions_revoked,
             "PASSWORD_RESET_SESSION_FAMILY_NOT_REVOKED")
    else:
        fail(case.reset_token_consumptions != 0 or case.previous_sessions_revoked,
             "UNREQUESTED_PASSWORD_RESET_EVIDENCE")
    return {
        "project": "FR_FINANCE_AI_STUDIO",
        "package": "M29100_M29400",
        "mode": "SYNTHETIC_CORRELATION_POLICY_NO_IO",
        "flow": case.flow,
        "policy_consistent_hypothetically": not failures,
        "violations": failures,
        "assertions_from_trusted_db": False,
        "email_ownership_operationally_verified": False,
        "contract_consent_operationally_verified": False,
        "independent_approval_persisted": False,
        "login_logout_operationally_verified": False,
        "production_authorized": False,
        "real_invitation_enabled": False,
        "real_account_activation_enabled": False,
        "writes_performed": False,
        "next_gate": "STAGING_POSTGRESQL_RLS_TRANSACTION_AND_PROVIDER_ATTESTATION",
    }


def readiness_contract() -> dict:
    """A fixed, non-secret manifest for Termux and CI checkpoints."""
    return {
        "project": "FR_FINANCE_AI_STUDIO",
        "package": "M29100_M29400",
        "mode": "OFFLINE_ONLY",
        "controls": (
            "M29100_ACTOR_ROLE_TENANT_AND_INDEPENDENT_REVIEW",
            "M29200_SINGLE_USE_INVITATION_EMAIL_BINDING_AND_EXPIRATION",
            "M29300_PUBLISHED_DOCUMENT_EXPLICIT_CONSENT_AND_SESSION_SCOPE",
            "M29400_PASSWORD_RECOVERY_REPLAY_AND_SESSION_FAMILY",
        ),
        "provider_evidence": False,
        "database_evidence": False,
        "master_mfa_operationally_verified": False,
        "public_routes_activated": False,
        "migrations_applied": False,
        "real_users_enabled": False,
        "real_pix_enabled": False,
        "production_authorized": False,
    }
