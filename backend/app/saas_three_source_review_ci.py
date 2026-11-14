"""FR Finance AI Studio M36400-M36800: synthetic SaaS three-source review.

Pure, read-only bridge between M35800 provider review, the M36300
append-only staging history, and a *synthetic* settlement statement.
These values are NOT authenticated evidence and can NEVER activate users,
licences, SaaS invoices, bank movements, or Pix.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import re
from uuid import UUID

from .saas_persisted_license_preflight import LicenseReadback

SHA = re.compile(r"[0-9a-f]{64}\Z")
IDENTIFIER = re.compile(r"[0-9]{1,40}\Z")
REF = re.compile(r"[A-Za-z0-9._:-]{8,100}\Z")
MAX_CENTS = 999_999_999_999
GET_MAX_AGE_SECONDS = 900
STATEMENT_MAX_AGE_SECONDS = 86_400


@dataclass(frozen=True)
class SaaSIntentFixture:
    tenant_id: UUID
    payment_intent_id: UUID
    administrator_id: UUID
    provider_payment_id: str
    collector_id: str
    external_reference: str
    amount_cents: int
    price_version_cents: int
    status: str = "PENDING"
    currency: str = "BRL"
    live_mode: bool = False
    source: str = "CI_RLS_PAYMENT_INTENT_FIXTURE"


@dataclass(frozen=True)
class SaaSGetFixture:
    tenant_id: UUID
    payment_intent_id: UUID
    provider_payment_id: str
    collector_id: str
    external_reference: str
    amount_cents: int
    refunded_cents: int
    checked_at: datetime
    evidence_sha256: str
    status: str = "approved"
    currency: str = "BRL"
    live_mode: bool = False
    source: str = "CI_MP_AUTHENTICATED_GET_FIXTURE"


@dataclass(frozen=True)
class SaaSStatementFixture:
    tenant_id: UUID
    payment_intent_id: UUID
    provider_payment_id: str
    collector_id: str
    external_reference: str
    gross_cents: int
    fee_cents: int
    net_cents: int
    bank_reference: str
    settled_at: datetime
    observed_at: datetime
    evidence_sha256: str
    status: str = "SYNTHETIC_SETTLED"
    currency: str = "BRL"
    source: str = "CI_BANK_STATEMENT_FIXTURE"


@dataclass(frozen=True)
class SaaSReviewHistoryFixture:
    tenant_id: UUID
    payment_intent_id: UUID
    provider_payment_id: str
    kind: str
    digest: str
    created_at: datetime
    source: str = "CI_IMMUTABLE_REVIEW_LOG_FIXTURE"


@dataclass(frozen=True)
class SaaSReviewOperators:
    administrator_id: UUID
    provider_observer_id: UUID
    statement_observer_id: UUID
    independent_reviewer_id: UUID
    source: str = "CI_OPERATORS_FIXTURE"


@dataclass(frozen=True)
class SaaSSettlementReview:
    state: str
    consistent_in_ci: bool = False
    evidence_digest: str | None = None
    all_sources_synthetic: bool = True
    independent_real_provider_attested: bool = False
    bank_settlement_operationally_attested: bool = False
    reviewer_identity_operationally_verified: bool = False
    payment_marked_paid: bool = False
    license_activated: bool = False
    new_users_activated: bool = False
    pix_authorized: bool = False
    production_authorized: bool = False
    writes_performed: bool = False


def _cents(v: object, allow_zero: bool = False) -> bool:
    return type(v) is int and (0 if allow_zero else 1) <= v <= MAX_CENTS


def _utc(v: object) -> bool:
    return (type(v) is datetime and v.tzinfo is not None
            and v.utcoffset() is not None)


def _age_valid(now: datetime, observed: datetime, max_age: int) -> bool:
    age = (now - observed).total_seconds()
    return 0 <= age <= max_age


def evaluate_saas_staging_three_source(
    *, intent: SaaSIntentFixture, readback: LicenseReadback,
    provider: SaaSGetFixture, statement: SaaSStatementFixture,
    history: tuple[SaaSReviewHistoryFixture, ...],
    operators: SaaSReviewOperators, now: datetime,
) -> SaaSSettlementReview:
    """Evaluate synthetic source congruence, never authorize a financial action."""
    types = (type(intent) is SaaSIntentFixture,
             type(readback) is LicenseReadback,
             type(provider) is SaaSGetFixture,
             type(statement) is SaaSStatementFixture,
             type(history) is tuple, type(operators) is SaaSReviewOperators,
             _utc(now))
    if not all(types) or len(history) > 100:
        return SaaSSettlementReview("INVALID_THREE_SOURCE_INPUT")
    if (intent.source != "CI_RLS_PAYMENT_INTENT_FIXTURE"
            or provider.source != "CI_MP_AUTHENTICATED_GET_FIXTURE"
            or statement.source != "CI_BANK_STATEMENT_FIXTURE"
            or operators.source != "CI_OPERATORS_FIXTURE"):
        return SaaSSettlementReview("UNTRUSTED_OR_LIVE_SOURCE")
    if any(type(x) is not UUID or x.int == 0 for x in (
        intent.tenant_id,intent.payment_intent_id,intent.administrator_id,
        operators.administrator_id,operators.provider_observer_id,
        operators.statement_observer_id,operators.independent_reviewer_id,
    )):
        return SaaSSettlementReview("INVALID_IDENTITY")
    if (intent.administrator_id != operators.administrator_id
            or len(set((operators.administrator_id,operators.provider_observer_id,
                        operators.statement_observer_id,
                        operators.independent_reviewer_id))) != 4):
        return SaaSSettlementReview("SEPARATION_OF_DUTIES_DENIED")
    if (intent.tenant_id != provider.tenant_id
            or intent.tenant_id != statement.tenant_id
            or len({intent.payment_intent_id,provider.payment_intent_id,
                    statement.payment_intent_id}) != 1):
        return SaaSSettlementReview("CROSS_TENANT_OR_PAYMENT_MISMATCH")
    if (type(intent.provider_payment_id) is not str
            or IDENTIFIER.fullmatch(intent.provider_payment_id) is None
            or intent.provider_payment_id != provider.provider_payment_id
            or intent.provider_payment_id != statement.provider_payment_id
            or type(intent.collector_id) is not str
            or IDENTIFIER.fullmatch(intent.collector_id) is None
            or intent.collector_id != provider.collector_id
            or intent.collector_id != statement.collector_id
            or type(intent.external_reference) is not str
            or REF.fullmatch(intent.external_reference) is None
            or not intent.external_reference.startswith("saas:")
            or intent.external_reference != provider.external_reference
            or intent.external_reference != statement.external_reference):
        return SaaSSettlementReview("COLLECTOR_REFERENCE_OR_PAYMENT_ID_MISMATCH")
    if (intent.live_mode is not False or provider.live_mode is not False
            or intent.currency != "BRL"
            or provider.currency != "BRL" or statement.currency != "BRL"):
        return SaaSSettlementReview("LIVE_OR_CURRENCY_SCOPE_DENIED")
    if (intent.status not in ("PENDING","APPROVED")
            or provider.status != "approved"
            or statement.status != "SYNTHETIC_SETTLED"
            or not _cents(intent.amount_cents)
            or not _cents(intent.price_version_cents)
            or intent.price_version_cents != intent.amount_cents
            or not _cents(provider.amount_cents)
            or not _cents(provider.refunded_cents,allow_zero=True)
            or provider.refunded_cents != 0
            or provider.amount_cents != intent.amount_cents
            or not _cents(statement.gross_cents)
            or not _cents(statement.fee_cents,allow_zero=True)
            or not _cents(statement.net_cents)
            or statement.gross_cents != intent.amount_cents
            or statement.gross_cents != statement.fee_cents + statement.net_cents):
        return SaaSSettlementReview("PAYMENT_PRICE_REFUND_OR_SETTLEMENT_MISMATCH")
    if (type(statement.bank_reference) is not str
            or REF.fullmatch(statement.bank_reference) is None
            or not _utc(provider.checked_at)
            or not _utc(statement.settled_at) or not _utc(statement.observed_at)
            or statement.settled_at > statement.observed_at
            or statement.observed_at > now
            or not _age_valid(now,provider.checked_at,GET_MAX_AGE_SECONDS)
            or not _age_valid(now,statement.observed_at,STATEMENT_MAX_AGE_SECONDS)):
        return SaaSSettlementReview("STALE_FUTURE_OR_INVALID_EVIDENCE_TIME")
    if (type(provider.evidence_sha256) is not str
            or SHA.fullmatch(provider.evidence_sha256) is None
            or type(statement.evidence_sha256) is not str
            or SHA.fullmatch(statement.evidence_sha256) is None
            or provider.evidence_sha256 == statement.evidence_sha256
            or readback.state != "RLS_PRICE_PROVIDER_MATCH_REVIEW_ONLY"
            or readback.matched is not True
            or readback.digest != provider.evidence_sha256
            or any((
                readback.payment_settled,readback.license_activated,
                readback.member_activated,readback.pix_authorized,
                readback.production_authorized,readback.writes_performed
            ))):
        return SaaSSettlementReview("PROVIDER_READBACK_OR_DIGEST_NOT_BOUND")

    candidate_count=0
    seen=set()
    for event in history:
        if (type(event) is not SaaSReviewHistoryFixture
                or event.source != "CI_IMMUTABLE_REVIEW_LOG_FIXTURE"
                or event.tenant_id != intent.tenant_id
                or event.payment_intent_id != intent.payment_intent_id
                or event.provider_payment_id != intent.provider_payment_id
                or not _utc(event.created_at) or event.created_at > now
                or type(event.digest) is not str
                or SHA.fullmatch(event.digest) is None
                or event.kind not in (
                    "GET_MATCH_CANDIDATE","REVERSAL_HOLD","PROVIDER_UNAVAILABLE_HOLD"
                )):
            return SaaSSettlementReview("REVIEW_LOG_SCOPE_OR_INTEGRITY_DENIED")
        key=(event.kind,event.digest)
        if key in seen:
            return SaaSSettlementReview("DUPLICATED_REVIEW_EVIDENCE")
        seen.add(key)
        if event.kind in ("REVERSAL_HOLD","PROVIDER_UNAVAILABLE_HOLD"):
            return SaaSSettlementReview("RECONCILIATION_HOLD_ACTIVE")
        if event.digest == provider.evidence_sha256:
            candidate_count += 1
    if candidate_count != 1:
        return SaaSSettlementReview("APPEND_ONLY_GET_CANDIDATE_ABSENT_OR_MISMATCHED")
    safe={
        "tenant":str(intent.tenant_id),
        "intent":str(intent.payment_intent_id),
        "provider_payment_id":intent.provider_payment_id,
        "collector":intent.collector_id,
        "reference":intent.external_reference,
        "gross_cents":intent.amount_cents,
        "net_cents":statement.net_cents,
        "fee_cents":statement.fee_cents,
        "provider_digest":provider.evidence_sha256,
        "statement_digest":statement.evidence_sha256,
        "statement_ref":statement.bank_reference,
        "independent_review":str(operators.independent_reviewer_id),
    }
    digest=sha256(json.dumps(safe,sort_keys=True,separators=(",",":")).encode()).hexdigest()
    return SaaSSettlementReview(
        state="CI_THREE_SOURCE_CONGRUENCE_REVIEW_ONLY",
        consistent_in_ci=True,evidence_digest=digest,
    )
