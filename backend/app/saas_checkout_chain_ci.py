"""M37452: deterministic SaaS checkout evidence chain, CI-only and no I/O.

This is NOT a payment, contract-consent or licence service. Every input is
synthetic and caller-asserted; no flag or digest is independent proof. A positive
result means only that hypothetical records are mutually consistent. Never
connect this decision to a production endpoint or entitlement writer.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from uuid import UUID
import re

SHA = re.compile(r"[0-9a-f]{64}\Z")
MP_ID = re.compile(r"[0-9]{1,40}\Z")
MAX_CENTS = 999_999_999_999


@dataclass(frozen=True)
class ContractProof:
    tenant_id: UUID
    administrator_id: UUID
    published_document_id: UUID
    accepted_document_id: UUID
    accepted_by: UUID
    published_sha256: str
    accepted_sha256: str
    published_at: datetime
    accepted_at: datetime
    explicit_consent: bool
    source: str = "CI_SYNTHETIC_CONTRACT"


@dataclass(frozen=True)
class OfferProof:
    tenant_id: UUID
    administrator_id: UUID
    price_version_id: UUID
    preparation_price_version_id: UUID
    tier: str
    preparation_tier: str
    plan_status: str
    period: str
    monthly_cents: int
    annual_cents: int
    expected_cents: int
    currency: str
    preparation_status: str
    prepared_at: datetime
    source: str = "CI_SYNTHETIC_DB_OFFER"


@dataclass(frozen=True)
class ProviderProof:
    tenant_id: UUID
    administrator_id: UUID
    payment_intent_id: UUID
    price_version_id: UUID
    provider_payment_id: str
    collector_id: str
    platform_collector_id: str
    external_reference: str
    provider_amount_cents: int
    refunded_cents: int
    status: str
    live_mode: bool
    checked_at: datetime
    evidence_sha256: str
    source: str = "CI_SYNTHETIC_AUTHENTICATED_GET"


@dataclass(frozen=True)
class ReconciliationProof:
    tenant_id: UUID
    payment_intent_id: UUID
    provider_payment_id: str
    provider_digest: str
    statement_digest: str
    review_digest: str
    gross_cents: int
    fee_cents: int
    net_cents: int
    observed_at: datetime
    administrator_id: UUID
    provider_observer_id: UUID
    statement_observer_id: UUID
    independent_reviewer_id: UUID
    state: str
    source: str = "CI_SYNTHETIC_THREE_SOURCE"


@dataclass(frozen=True)
class CheckoutDecision:
    state: str
    hypothetical_consistency: bool = False
    evidence_digest: str | None = None
    contract_legally_verified: bool = False
    provider_operationally_verified: bool = False
    payment_settled: bool = False
    license_created: bool = False
    user_activated: bool = False
    pix_authorized: bool = False
    production_authorized: bool = False
    writes_performed: bool = False


def _id(x: object) -> bool:
    return type(x) is UUID and x.int != 0


def _instant(x: object) -> bool:
    return type(x) is datetime and x.tzinfo is not None and x.utcoffset() is not None


def _cents(x: object, zero: bool = False) -> bool:
    return type(x) is int and (0 if zero else 1) <= x <= MAX_CENTS


def _sha(x: object) -> bool:
    return type(x) is str and SHA.fullmatch(x) is not None


def review_checkout(
    *, contract: ContractProof, offer: OfferProof,
    provider: ProviderProof | None = None,
    reconciliation: ReconciliationProof | None = None,
    now: datetime,
) -> CheckoutDecision:
    """Review synthetic checkout links; always return an inert decision."""
    if (type(contract) is not ContractProof or type(offer) is not OfferProof
            or not _instant(now)):
        return CheckoutDecision("INVALID_TYPED_SNAPSHOT")
    if (contract.source != "CI_SYNTHETIC_CONTRACT"
            or offer.source != "CI_SYNTHETIC_DB_OFFER"):
        return CheckoutDecision("UNTRUSTED_SOURCE")
    if (not all(_id(x) for x in (
            contract.tenant_id, contract.administrator_id,
            contract.published_document_id, contract.accepted_document_id,
            contract.accepted_by, offer.tenant_id, offer.administrator_id,
            offer.price_version_id, offer.preparation_price_version_id))
            or type(contract.explicit_consent) is not bool
            or not all(_instant(x) for x in (
                contract.published_at, contract.accepted_at, offer.prepared_at))):
        return CheckoutDecision("INVALID_CONTRACT_OR_OFFER_TYPES")
    if (contract.tenant_id != offer.tenant_id
            or contract.administrator_id != offer.administrator_id
            or contract.accepted_by != contract.administrator_id):
        return CheckoutDecision("TENANT_OR_ADMIN_SCOPE_MISMATCH")
    if (not contract.explicit_consent
            or contract.published_document_id != contract.accepted_document_id
            or not _sha(contract.published_sha256)
            or contract.accepted_sha256 != contract.published_sha256
            or not contract.published_at <= contract.accepted_at <= offer.prepared_at <= now):
        return CheckoutDecision("CONTRACT_CONSENT_UNVERIFIED")
    if (offer.price_version_id != offer.preparation_price_version_id
            or offer.tier not in ("ESSENCIAL", "INTERMEDIARIO", "AMPLIADO")
            or offer.preparation_tier != offer.tier
            or offer.plan_status != "ACTIVE"
            or offer.period not in ("MONTHLY", "ANNUAL")
            or offer.preparation_status != "PENDING_PAYMENT"
            or offer.currency != "BRL"
            or not _cents(offer.monthly_cents)
            or not _cents(offer.annual_cents)
            or not _cents(offer.expected_cents)
            # Preco anual independente conforme SQL112; esperado vem da versao.
            or offer.expected_cents != (
                offer.monthly_cents if offer.period == "MONTHLY"
                else offer.annual_cents)):
        return CheckoutDecision("UNBOUND_OR_INVALID_PRICE_VERSION")
    if provider is None and reconciliation is None:
        return CheckoutDecision("CONTRACT_OFFER_REVIEW_CI_ONLY", True)
    if type(provider) is not ProviderProof:
        return CheckoutDecision("MISSING_OR_INVALID_PROVIDER_EVIDENCE")
    if provider.source != "CI_SYNTHETIC_AUTHENTICATED_GET":
        return CheckoutDecision("UNTRUSTED_PROVIDER_SOURCE")
    if (not all(_id(x) for x in (
            provider.tenant_id, provider.administrator_id,
            provider.payment_intent_id, provider.price_version_id))
            or type(provider.live_mode) is not bool
            or not _instant(provider.checked_at)
            or not _cents(provider.provider_amount_cents)
            or not _cents(provider.refunded_cents, True)
            or not _sha(provider.evidence_sha256)):
        return CheckoutDecision("INVALID_PROVIDER_FIELDS")
    if (provider.tenant_id != contract.tenant_id
            or provider.administrator_id != contract.administrator_id
            or provider.price_version_id != offer.price_version_id):
        return CheckoutDecision("PROVIDER_TENANT_ADMIN_OR_PRICE_MISMATCH")
    if (provider.live_mode is not False
            or type(provider.provider_payment_id) is not str
            or MP_ID.fullmatch(provider.provider_payment_id) is None
            or type(provider.collector_id) is not str
            or MP_ID.fullmatch(provider.collector_id) is None
            or provider.collector_id != provider.platform_collector_id
            or provider.external_reference != f"saas:{provider.payment_intent_id}"
            or provider.provider_amount_cents != offer.expected_cents
            or provider.refunded_cents != 0
            or provider.status != "approved"
            or provider.checked_at < offer.prepared_at
            or not 0 <= (now - provider.checked_at).total_seconds() <= 900):
        return CheckoutDecision("PROVIDER_PAYMENT_NOT_ATTESTED_IN_CI")
    if reconciliation is None:
        return CheckoutDecision("PROVIDER_MATCH_REVIEW_CI_ONLY", True)
    if type(reconciliation) is not ReconciliationProof:
        return CheckoutDecision("INVALID_RECONCILIATION_EVIDENCE")
    if reconciliation.source != "CI_SYNTHETIC_THREE_SOURCE":
        return CheckoutDecision("UNTRUSTED_RECONCILIATION_SOURCE")
    if (not all(_id(x) for x in (
            reconciliation.tenant_id, reconciliation.payment_intent_id,
            reconciliation.administrator_id, reconciliation.provider_observer_id,
            reconciliation.statement_observer_id, reconciliation.independent_reviewer_id))
            or not _instant(reconciliation.observed_at)
            or not all(_cents(x) for x in (
                reconciliation.gross_cents, reconciliation.net_cents))
            or not _cents(reconciliation.fee_cents, True)
            or not all(_sha(x) for x in (
                reconciliation.provider_digest, reconciliation.statement_digest,
                reconciliation.review_digest))):
        return CheckoutDecision("INVALID_RECONCILIATION_FIELDS")
    if (reconciliation.tenant_id != contract.tenant_id
            or reconciliation.payment_intent_id != provider.payment_intent_id
            or reconciliation.provider_payment_id != provider.provider_payment_id
            or reconciliation.administrator_id != contract.administrator_id
            or len({reconciliation.administrator_id,
                    reconciliation.provider_observer_id,
                    reconciliation.statement_observer_id,
                    reconciliation.independent_reviewer_id}) != 4
            or reconciliation.provider_digest != provider.evidence_sha256
            or reconciliation.provider_digest == reconciliation.statement_digest
            or reconciliation.gross_cents != offer.expected_cents
            or reconciliation.fee_cents + reconciliation.net_cents
               != reconciliation.gross_cents
            or reconciliation.state != "CI_THREE_SOURCE_CONGRUENCE_REVIEW_ONLY"
            or not provider.checked_at <= reconciliation.observed_at <= now
            or (now - reconciliation.observed_at).total_seconds() > 86400):
        return CheckoutDecision("RECONCILIATION_INCONSISTENT_OR_UNATTESTED")
    # Fingerprint is a non-authoritative diagnostic, not a signed capability.
    fingerprint = sha256("|".join((
        str(contract.tenant_id), str(contract.administrator_id),
        contract.accepted_sha256, str(offer.price_version_id),
        offer.period, str(offer.expected_cents),
        str(provider.payment_intent_id), reconciliation.review_digest,
    )).encode("ascii")).hexdigest()
    return CheckoutDecision("CI_CHECKOUT_CHAIN_CONSISTENT_REVIEW_ONLY",
                            True, fingerprint)
