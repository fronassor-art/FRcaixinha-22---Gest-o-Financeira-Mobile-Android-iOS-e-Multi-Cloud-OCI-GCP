"""M37454 — synthetic, fail-closed SaaS contract consent correlation.

This module NEVER records a contract acceptance. It analyzes *hypothetical*
session, challenge, affirmative action and receipt records against the M37453
disposable database readback. A MAC supplied by a CI fixture is not a legal
signature, proof of the user's action, or an entitlement. No IO or API route.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import hmac
import re
from uuid import UUID

from .saas_disposable_checkout_readback_ci import evaluate_disposable_readback

_SHA = re.compile(r"[0-9a-f]{64}\Z")
_CONFIRM = "ACEITO_CONTRATO_DE_LICENCA_FR_FINANCE"
_MAX_WINDOW = timedelta(minutes=10)


@dataclass(frozen=True)
class SessionFixture:
    session_id: UUID
    tenant_id: UUID
    user_id: UUID
    role: str
    issued_at: datetime
    expires_at: datetime
    active: bool
    email_verified: bool
    source: str = "CI_SYNTHETIC_SERVER_SESSION"


@dataclass(frozen=True)
class ChallengeFixture:
    challenge_id: UUID
    tenant_id: UUID
    user_id: UUID
    session_id: UUID
    document_id: UUID
    document_sha256: str
    price_version_id: UUID
    preparation_id: UUID
    issued_at: datetime
    expires_at: datetime
    source: str = "CI_SYNTHETIC_ISSUED_CHALLENGE"


@dataclass(frozen=True)
class AffirmationFixture:
    challenge_id: UUID
    tenant_id: UUID
    user_id: UUID
    session_id: UUID
    document_id: UUID
    document_sha256: str
    confirmation_text: str
    checked: bool
    occurred_at: datetime
    source: str = "CI_SYNTHETIC_AFFIRMATIVE_ACTION"


@dataclass(frozen=True)
class ReceiptFixture:
    challenge_id: UUID
    tenant_id: UUID
    user_id: UUID
    evidence_mac: str
    recorded_at: datetime
    consume_count: int
    replay_count: int
    revoked: bool
    append_only_claim: bool
    source: str = "CI_SYNTHETIC_RECEIPT"


@dataclass(frozen=True)
class ConsentReview:
    state: str
    hypothetical_binding_consistent: bool = False
    document_integrity_operationally_verified: bool = False
    user_action_operationally_verified: bool = False
    durable_unique_consumption_verified: bool = False
    legal_consent_accepted: bool = False
    billing_authorized: bool = False
    license_activated: bool = False
    user_activated: bool = False
    pix_authorized: bool = False
    production_authorized: bool = False
    writes_performed: bool = False


def _uuid(v: object) -> bool:
    return type(v) is UUID and v.int != 0


def _aware(v: object) -> bool:
    return type(v) is datetime and v.tzinfo is not None and v.utcoffset() is not None


def _sha(v: object) -> bool:
    return type(v) is str and _SHA.fullmatch(v) is not None


def _claims(*, session: SessionFixture, challenge: ChallengeFixture,
            affirmation: AffirmationFixture) -> bytes:
    # Fixed domain separation, field order and UTC ISO-8601 canonicalization.
    # This is a test fixture digest, not a production signature.
    values = (
        "FR_FINANCE_M37454_CI_SYNTHETIC_V1",
        str(session.session_id), str(challenge.challenge_id),
        str(challenge.tenant_id), str(challenge.user_id),
        str(challenge.document_id), challenge.document_sha256,
        str(challenge.price_version_id), str(challenge.preparation_id),
        affirmation.confirmation_text,
        affirmation.occurred_at.astimezone(timezone.utc).isoformat(),
    )
    return "|".join(values).encode("ascii")


def synthetic_evidence_mac(*, ci_key: bytes, session: SessionFixture,
                           challenge: ChallengeFixture,
                           affirmation: AffirmationFixture) -> str:
    """CI-only fixture helper: no persistent secrets, token or provider access."""
    if type(ci_key) is not bytes or len(ci_key) < 32:
        raise ValueError("CI_KEY_INVALID")
    if (type(session) is not SessionFixture
            or type(challenge) is not ChallengeFixture
            or type(affirmation) is not AffirmationFixture
            or not _aware(affirmation.occurred_at)):
        raise ValueError("CI_CLAIMS_INVALID")
    return hmac.new(ci_key, _claims(session=session,challenge=challenge,
                                    affirmation=affirmation), sha256).hexdigest()


def review_saas_consent_ci(
    *, row: dict, request_id: UUID, tenant_id: UUID, admin_id: UUID,
    session: SessionFixture, challenge: ChallengeFixture,
    affirmation: AffirmationFixture, receipt: ReceiptFixture,
    ci_key: bytes, now: datetime,
) -> ConsentReview:
    """Review CI-only data; positive result is NEVER a real consent token."""
    deny = ConsentReview
    if (not _aware(now) or type(row) is not dict
            or not all(_uuid(x) for x in (request_id,tenant_id,admin_id))
            or type(ci_key) is not bytes or len(ci_key) < 32):
        return deny("INVALID_INPUT")
    base = evaluate_disposable_readback(
        row,request_id=request_id,tenant_id=tenant_id,admin_id=admin_id,now=now)
    if (base.state != "CI_PERSISTED_PREPARATION_REVIEW_ONLY"
            or base.structure_consistent_in_ci is not True):
        return deny("PERSISTED_PREPARATION_NOT_VERIFIED")
    if not all((
        type(session) is SessionFixture,
        type(challenge) is ChallengeFixture,
        type(affirmation) is AffirmationFixture,
        type(receipt) is ReceiptFixture,
    )):
        return deny("INVALID_TYPED_EVIDENCE")
    if (session.source != "CI_SYNTHETIC_SERVER_SESSION"
            or challenge.source != "CI_SYNTHETIC_ISSUED_CHALLENGE"
            or affirmation.source != "CI_SYNTHETIC_AFFIRMATIVE_ACTION"
            or receipt.source != "CI_SYNTHETIC_RECEIPT"):
        return deny("UNTRUSTED_EVIDENCE_SOURCE")
    if (not all(_uuid(v) for v in (
            session.session_id,session.tenant_id,session.user_id,
            challenge.challenge_id,challenge.tenant_id,challenge.user_id,
            challenge.session_id,challenge.document_id,
            challenge.price_version_id,challenge.preparation_id,
            affirmation.challenge_id,affirmation.tenant_id,affirmation.user_id,
            affirmation.session_id,affirmation.document_id,
            receipt.challenge_id,receipt.tenant_id,receipt.user_id))
            or not all(_aware(t) for t in (
                session.issued_at,session.expires_at,
                challenge.issued_at,challenge.expires_at,
                affirmation.occurred_at,receipt.recorded_at))
            or any(type(v) is not bool for v in (
                session.active,session.email_verified,affirmation.checked,
                receipt.revoked,receipt.append_only_claim))
            or any(type(v) is not int for v in (
                receipt.consume_count,receipt.replay_count))
            or not all(_sha(x) for x in (
                challenge.document_sha256,affirmation.document_sha256,
                receipt.evidence_mac))):
        return deny("MALFORMED_EVIDENCE")
    if (session.role != "TENANT_ADMIN" or session.active is not True
            or session.email_verified is not True
            or session.user_id != admin_id or session.tenant_id != tenant_id):
        return deny("ADMIN_SESSION_NOT_VERIFIED_IN_CI")
    if (challenge.tenant_id != tenant_id
            or challenge.user_id != admin_id
            or challenge.session_id != session.session_id
            or challenge.document_id != row["published_document_id"]
            or challenge.document_sha256 != row["published_sha"]
            or challenge.price_version_id != row["price_version_id"]
            or challenge.preparation_id != row["preparation_id"]):
        return deny("CONTRACT_PRICE_OR_TENANT_BINDING_MISMATCH")
    if (affirmation.challenge_id != challenge.challenge_id
            or affirmation.tenant_id != tenant_id
            or affirmation.user_id != admin_id
            or affirmation.session_id != session.session_id
            or affirmation.document_id != challenge.document_id
            or affirmation.document_sha256 != challenge.document_sha256):
        return deny("AFFIRMATION_BINDING_MISMATCH")
    if (affirmation.checked is not True
            or affirmation.confirmation_text != _CONFIRM):
        return deny("EXPLICIT_AFFIRMATIVE_ACTION_ABSENT")
    if (not row["published_at"] <= session.issued_at <= challenge.issued_at
            or not challenge.issued_at <= affirmation.occurred_at < challenge.expires_at
            or not session.issued_at <= affirmation.occurred_at < session.expires_at
            or challenge.expires_at > challenge.issued_at + _MAX_WINDOW
            or not affirmation.occurred_at <= receipt.recorded_at <= row["accepted_at"]
            or not row["accepted_at"] <= row["prepared_at"] <= now):
        return deny("EXPIRED_OUT_OF_ORDER_OR_UNPUBLISHED_CONSENT")
    if (receipt.challenge_id != challenge.challenge_id
            or receipt.tenant_id != tenant_id
            or receipt.user_id != admin_id
            or receipt.consume_count != 1
            or receipt.replay_count != 0
            or receipt.revoked is not False
            or receipt.append_only_claim is not True):
        return deny("REPLAY_REVOKED_OR_RECEIPT_SCOPE")
    expected = hmac.new(ci_key,
        _claims(session=session,challenge=challenge,affirmation=affirmation),
        sha256).hexdigest()
    if (not hmac.compare_digest(receipt.evidence_mac,expected)
            or not hmac.compare_digest(row["evidence_hash"],expected)):
        # Existing M30900 CI fixture has only a placeholder evidence hash.
        # Therefore it must NOT pass this stricter simulated claim binding.
        return deny("ACCEPTANCE_EVIDENCE_NOT_CRYPTOGRAPHICALLY_BOUND")
    return ConsentReview("CI_CONSENT_LINKAGE_REVIEW_ONLY", True)
