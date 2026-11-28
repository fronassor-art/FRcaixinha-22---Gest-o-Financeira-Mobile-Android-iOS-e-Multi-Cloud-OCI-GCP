"""M37457: pre-preparation SaaS consent chronology policy (pure, CI-only).

This is a consistency checker for SYNTHETIC evidence, not an identity provider,
signature verifier, consent collector, database writer, invoice or license API.
A positive result permits only further engineering review. All production and
payment flags remain disabled. Existing M37455/M37456 post-preparation receipts
MUST fail the chronological authority test.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import hmac
import re
from uuid import UUID


_HEX = re.compile(r"[a-f0-9]{64}\Z")
_CONFIRM = "ACEITO_CONTRATO_DE_LICENCA_FR_FINANCE"
_MAX_CHALLENGE = timedelta(minutes=10)
_MAX_SESSION = timedelta(hours=12)
_MAX_READBACK_AGE = timedelta(minutes=15)


@dataclass(frozen=True, kw_only=True)
class ServerIdentityClaim:
    tenant_id: UUID
    administrator_id: UUID
    session_id: UUID
    session_user_id: UUID
    session_role: str
    session_tenant_id: UUID
    session_active: bool
    email_verified: bool
    issued_at: datetime
    expires_at: datetime
    checked_at: datetime
    source: str = "CI_SYNTHETIC_SERVER_SESSION_READBACK"


@dataclass(frozen=True, kw_only=True)
class PublishedSaaSOffer:
    tenant_id: UUID
    document_id: UUID
    document_kind: str
    document_sha256: str
    document_version: str
    published_at: datetime
    presented_at: datetime
    price_version_id: UUID
    billing_period: str
    price_cents: int
    currency: str
    source: str = "CI_SYNTHETIC_PUBLISHED_DOCUMENT_PRICE_READBACK"


@dataclass(frozen=True, kw_only=True)
class AffirmativeConsentClaim:
    challenge_id: UUID
    tenant_id: UUID
    administrator_id: UUID
    session_id: UUID
    document_id: UUID
    document_sha256: str
    price_version_id: UUID
    issued_at: datetime
    expires_at: datetime
    checked: bool
    confirmation_text: str
    confirmed_at: datetime
    receipt_recorded_at: datetime
    receipt_count: int
    replay_count: int
    revoked: bool
    receipt_digest: str
    source: str = "CI_SYNTHETIC_SERVER_CONSENT_RECEIPT"


@dataclass(frozen=True, kw_only=True)
class SaaSPreparationClaim:
    request_id: UUID
    tenant_id: UUID
    administrator_id: UUID
    document_id: UUID
    price_version_id: UUID
    consent_challenge_id: UUID
    billing_period: str
    price_cents: int
    requested_at: datetime
    state: str  # NOT_PREPARED or PREPARED_CI
    prepared_at: datetime | None
    payment_count: int
    entitlement_count: int
    source: str = "CI_SYNTHETIC_SERVER_PREPARATION"


@dataclass(frozen=True)
class PreparationConsentDecision:
    state: str
    hypothetical_preparation_eligible: bool = False
    real_identity_verified: bool = False
    legal_consent_verified: bool = False
    contract_signature_verified: bool = False
    payment_authorized: bool = False
    license_authorized: bool = False
    user_activation_authorized: bool = False
    pix_authorized: bool = False
    production_authorized: bool = False
    writes_performed: bool = False


def _id(v: object) -> bool:
    return type(v) is UUID and v.int != 0


def _time(v: object) -> bool:
    return type(v) is datetime and v.tzinfo is not None and v.utcoffset() is not None


def _hash(v: object) -> bool:
    return type(v) is str and _HEX.fullmatch(v) is not None


def _count(v: object) -> bool:
    return type(v) is int and 0 <= v <= 1000000000


def _positive_price(v: object) -> bool:
    return type(v) is int and 0 < v <= 999999999999


def assess_preparation_chronology_ci(
    *, identity: ServerIdentityClaim, offer: PublishedSaaSOffer,
    consent: AffirmativeConsentClaim, preparation: SaaSPreparationClaim,
    now: datetime,
) -> PreparationConsentDecision:
    denied = PreparationConsentDecision
    if (type(identity) is not ServerIdentityClaim
        or type(offer) is not PublishedSaaSOffer
        or type(consent) is not AffirmativeConsentClaim
        or type(preparation) is not SaaSPreparationClaim
        or not _time(now)):
        return denied("INVALID_TYPED_INPUT")
    if (identity.source != "CI_SYNTHETIC_SERVER_SESSION_READBACK"
        or offer.source != "CI_SYNTHETIC_PUBLISHED_DOCUMENT_PRICE_READBACK"
        or consent.source != "CI_SYNTHETIC_SERVER_CONSENT_RECEIPT"
        or preparation.source != "CI_SYNTHETIC_SERVER_PREPARATION"):
        return denied("UNTRUSTED_EVIDENCE_SOURCE")
    ids = (
        identity.tenant_id, identity.administrator_id, identity.session_id,
        identity.session_user_id, identity.session_tenant_id,
        offer.tenant_id, offer.document_id, offer.price_version_id,
        consent.challenge_id, consent.tenant_id, consent.administrator_id,
        consent.session_id, consent.document_id, consent.price_version_id,
        preparation.request_id, preparation.tenant_id,
        preparation.administrator_id, preparation.document_id,
        preparation.price_version_id, preparation.consent_challenge_id,
    )
    times = (
        identity.issued_at, identity.expires_at, identity.checked_at,
        offer.published_at, offer.presented_at, consent.issued_at,
        consent.expires_at, consent.confirmed_at, consent.receipt_recorded_at,
        preparation.requested_at,
    )
    if (not all(_id(x) for x in ids)
        or not all(_time(x) for x in times)
        or (preparation.prepared_at is not None and not _time(preparation.prepared_at))
        or not all(type(x) is bool for x in (
            identity.session_active, identity.email_verified,
            consent.checked, consent.revoked))
        or not all(_count(x) for x in (
            consent.receipt_count, consent.replay_count,
            preparation.payment_count, preparation.entitlement_count))
        or not all(_positive_price(x) for x in (
            offer.price_cents, preparation.price_cents))
        or not _hash(offer.document_sha256)
        or not _hash(consent.document_sha256)
        or not _hash(consent.receipt_digest)):
        return denied("MALFORMED_EVIDENCE")
    if (identity.tenant_id != offer.tenant_id
        or identity.tenant_id != consent.tenant_id
        or identity.tenant_id != preparation.tenant_id
        or identity.administrator_id != identity.session_user_id
        or identity.administrator_id != consent.administrator_id
        or identity.administrator_id != preparation.administrator_id
        or identity.session_tenant_id != identity.tenant_id
        or consent.session_id != identity.session_id):
        return denied("TENANT_ADMIN_OR_SESSION_SCOPE_MISMATCH")
    if (not identity.session_active or not identity.email_verified
        or identity.session_role != "TENANT_ADMIN"
        or not identity.issued_at < identity.expires_at
        or identity.expires_at - identity.issued_at > _MAX_SESSION):
        return denied("CI_SESSION_NOT_ACTIVE_OR_ADMIN")
    if (not 0 <= (now - identity.checked_at).total_seconds() <=
            _MAX_READBACK_AGE.total_seconds()
        or not identity.issued_at <= identity.checked_at < identity.expires_at
        or now >= identity.expires_at):
        return denied("CI_SESSION_READBACK_STALE")
    if (offer.document_kind != "PLATFORM_LICENSE"
        or type(offer.document_version) is not str
        or not 1 <= len(offer.document_version) <= 96
        or offer.document_version.strip() != offer.document_version
        or offer.document_id != consent.document_id
        or offer.document_id != preparation.document_id
        or not hmac.compare_digest(offer.document_sha256, consent.document_sha256)
        or offer.price_version_id != consent.price_version_id
        or offer.price_version_id != preparation.price_version_id
        or offer.billing_period not in ("MONTHLY", "ANNUAL")
        or offer.billing_period != preparation.billing_period
        or offer.price_cents != preparation.price_cents
        or offer.currency != "BRL"):
        return denied("PUBLISHED_DOCUMENT_OR_FROZEN_PRICE_MISMATCH")
    if (consent.challenge_id != preparation.consent_challenge_id
        or consent.checked is not True
        or consent.confirmation_text != _CONFIRM
        or consent.receipt_count != 1
        or consent.replay_count != 0
        or consent.revoked is not False):
        return denied("EXPLICIT_CONSENT_OR_SINGLE_USE_NOT_MATCHED")
    if (not offer.published_at <= offer.presented_at <= consent.issued_at
        or not identity.issued_at <= consent.issued_at
        or not consent.issued_at < consent.expires_at
        or consent.expires_at - consent.issued_at > _MAX_CHALLENGE
        or not consent.issued_at <= consent.confirmed_at < consent.expires_at
        or not consent.confirmed_at <= consent.receipt_recorded_at
        or not consent.receipt_recorded_at < identity.expires_at
        or identity.checked_at < consent.receipt_recorded_at
        or consent.receipt_recorded_at > now):
        return denied("CONSENT_EVENT_ORDER_OR_EXPIRATION_INVALID")
    # This check is deliberately before any positive result: prior
    # CI experiments M37455/56 created their new receipts *after*
    # preparation, so they may never be used to authorize one.
    if (preparation.prepared_at is not None
        and preparation.prepared_at < consent.receipt_recorded_at):
        return denied("PREPARATION_PRECEDED_CONSENT_DENIED")
    if (preparation.requested_at < consent.receipt_recorded_at
        or preparation.requested_at > now
        or (preparation.state == "NOT_PREPARED"
            and preparation.prepared_at is not None)
        or (preparation.state == "PREPARED_CI"
            and (preparation.prepared_at is None
                 or preparation.prepared_at < preparation.requested_at
                 or preparation.prepared_at > now))
        or preparation.state not in ("NOT_PREPARED", "PREPARED_CI")):
        return denied("PREPARATION_STATE_OR_CHRONOLOGY_INVALID")
    if preparation.payment_count != 0 or preparation.entitlement_count != 0:
        return denied("FINANCIAL_OR_LICENSE_RECORD_ALREADY_PRESENT")
    return denied("CI_PREPARATION_CHRONOLOGY_CONSISTENT_NOT_AUTHORITY", True)


def assess_persisted_temporal_order_ci(
    *, prepared_at: datetime, challenge_issued_at: datetime,
    receipt_recorded_at: datetime, now: datetime,
) -> PreparationConsentDecision:
    """Read-only DB probe: existing post-preparation receipts must fail."""
    denied = PreparationConsentDecision
    if not all(_time(v) for v in (
        prepared_at, challenge_issued_at, receipt_recorded_at, now)):
        return denied("INVALID_PERSISTED_TIMESTAMPS")
    if not (challenge_issued_at <= receipt_recorded_at <= now
            and prepared_at <= now):
        return denied("PERSISTED_EVENT_ORDER_INVALID")
    if prepared_at < challenge_issued_at or prepared_at < receipt_recorded_at:
        return denied("PREPARATION_PRECEDED_CONSENT_DENIED")
    return denied("CI_TEMPORAL_ORDER_ONLY_NO_PROOF", True)
