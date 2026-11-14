"""M34900-M35300: platform SaaS payment readback, no financial writes.

This *read-only* service evaluates one persisted server-side SaaS payment
intent against an authenticated Mercado Pago GET. A matching HTTP response
does not authorize a license, member, payment settlement or Pix transfer.

No endpoint/worker invokes this service while production gates remain OFF.
The actual live provider, OCI, IAM and ledger proofs remain unverified.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from uuid import UUID
import hashlib
import json
import re

import httpx

from .mercado_pago_safety import ExpectedPayment, matches_approved_payment
from .platform_provider_adapters import (
    PlatformMpConfig, ProviderUnavailable, fetch_authoritative_saas_payment,
)

_MP_ID=re.compile(r"[0-9]{1,40}\Z")
_REFERENCE=re.compile(r"[A-Za-z0-9._:-]{1,100}\Z")


@dataclass(frozen=True)
class SaaSPlatformPaymentRecord:
    """Immutable values loaded from an authenticated, RLS-scoped DB intent.

    Never instantiate this from a webhook body, query string or frontend JSON.
    The source tag is a guardrail, not cryptographic origin authentication.
    """
    tenant_id: UUID
    admin_user_id: UUID
    provider_payment_id: str
    platform_collector_id: str
    external_reference: str
    expected_amount_cents: int
    live_mode: bool
    status: str
    currency: str = "BRL"
    source: str = "SERVER_SIDE_SAAS_PAYMENT_INTENT"


@dataclass(frozen=True)
class SaaSReadbackReview:
    state: str
    matching_fields: bool = False
    evidence_sha256: str | None = None
    provider_status: str | None = None
    payment_marked_paid: bool = False
    entitlement_created: bool = False
    membership_created: bool = False
    quota_created: bool = False
    ledger_written: bool = False
    pix_authorized: bool = False
    production_activation_authorized: bool = False
    writes_performed: bool = False


def _well_scoped(record: SaaSPlatformPaymentRecord, config: PlatformMpConfig) -> bool:
    return (
        type(record) is SaaSPlatformPaymentRecord
        and type(config) is PlatformMpConfig
        and type(record.tenant_id) is UUID and record.tenant_id.int != 0
        and type(record.admin_user_id) is UUID and record.admin_user_id.int != 0
        and type(record.provider_payment_id) is str
        and _MP_ID.fullmatch(record.provider_payment_id) is not None
        and type(record.platform_collector_id) is str
        and _MP_ID.fullmatch(record.platform_collector_id) is not None
        and type(record.external_reference) is str
        and _REFERENCE.fullmatch(record.external_reference) is not None
        and record.external_reference.startswith("saas:")
        and type(record.expected_amount_cents) is int
        and 0 < record.expected_amount_cents <= 999_999_999_999
        and type(record.live_mode) is bool
        and type(config.live_mode) is bool and config.live_mode is record.live_mode
        and record.platform_collector_id == config.collector_id
        and record.status in ("PENDING","APPROVED")
        and record.currency == "BRL"
        and record.source == "SERVER_SIDE_SAAS_PAYMENT_INTENT"
        and type(config.access_token) is str
        and 20 <= len(config.access_token) <= 4096
        and not any(c.isspace() for c in config.access_token)
    )


def _reversal_amount(payload: dict) -> bool:
    """Reject positive refunds (including partial) and malformed amounts."""
    refunded=payload.get("transaction_amount_refunded")
    if refunded is None:
        return False
    if type(refunded) not in (str,int,Decimal):
        return True
    try:
        value=Decimal(refunded)
        return not value.is_finite() or value < 0 or value != 0
    except (InvalidOperation,TypeError,ValueError):
        return True


def _digest_without_pii(record: SaaSPlatformPaymentRecord, payload: dict) -> str:
    # No token, e-mail, CPF, webhook body or private payment fields.
    safe={
        "id":record.provider_payment_id,
        "collector_id":record.platform_collector_id,
        "external_reference":record.external_reference,
        "amount_cents":record.expected_amount_cents,
        "live_mode":record.live_mode,
        "status":payload["status"],
    }
    return hashlib.sha256(json.dumps(safe,sort_keys=True,separators=(",",":")).encode()).hexdigest()


async def review_platform_saas_payment_get(
    *, record: SaaSPlatformPaymentRecord, config: PlatformMpConfig,
    client: httpx.AsyncClient,
) -> SaaSReadbackReview:
    """Read-only provider GET; response is a REVIEW CANDIDATE, never approval.

    The real caller must independently attest that record came from PostgreSQL,
    that the platform access token is obtained from a protected OCI secret,
    that the collector is the platform, and that financial permissions exist.
    No such attestation is established by an injected mock client in CI.
    """
    if not _well_scoped(record,config) or type(client) is not httpx.AsyncClient:
        return SaaSReadbackReview("PLATFORM_RECORD_OR_CREDENTIAL_SCOPE_DENIED")
    try:
        response=await fetch_authoritative_saas_payment(
            config=config,payment_id=record.provider_payment_id,client=client,
        )
    except (ProviderUnavailable, ValueError, httpx.HTTPError):
        return SaaSReadbackReview("AUTHENTICATED_GET_UNAVAILABLE_OR_BLOCKED")
    if type(response) is not dict:
        return SaaSReadbackReview("INVALID_PROVIDER_RESPONSE")
    status=response.get("status")
    if type(status) is not str:
        return SaaSReadbackReview("INVALID_PROVIDER_RESPONSE")
    if status != "approved":
        return SaaSReadbackReview("PROVIDER_NOT_APPROVED_OR_REVERSED",provider_status=status)
    if _reversal_amount(response):
        return SaaSReadbackReview("REFUND_OR_PARTIAL_REFUND_BLOCKED",provider_status=status)
    expected=ExpectedPayment(
        provider_payment_id=record.provider_payment_id,
        collector_id=record.platform_collector_id,
        external_reference=record.external_reference,
        amount_cents=record.expected_amount_cents,
        live_mode=record.live_mode,
    )
    if not matches_approved_payment(expected,response):
        return SaaSReadbackReview("PROVIDER_ID_COLLECTOR_REFERENCE_AMOUNT_OR_MODE_MISMATCH",
                                  provider_status=status)
    return SaaSReadbackReview(
        state="READBACK_MATCH_REVIEW_ONLY",
        matching_fields=True,
        evidence_sha256=_digest_without_pii(record,response),
        provider_status=status,
    )
