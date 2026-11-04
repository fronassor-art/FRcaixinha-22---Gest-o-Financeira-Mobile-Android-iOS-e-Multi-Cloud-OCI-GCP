"""M2600: provider GET sandbox-only, no FastAPI route or financial write.

An authenticated GET (even approved) is NOT bank settlement, paid status or
ledger evidence. No token is stored/logged by this module.
"""
from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Awaitable, Callable
from uuid import UUID

import httpx

from .mercado_pago_adapter import build_get_payment_request
from .mercado_pago_safety import ExpectedPayment, matches_approved_payment

CONTRACT = "AI_STUDIO_M2600_READONLY_GATEWAY_OCI_BLUEPRINT_V1"
RETRIES = 3
MAX_BYTES = 65536
RETRYABLE = frozenset((429, 502, 503, 504))
STATUSES = frozenset((
    "approved", "pending", "in_process", "rejected", "cancelled",
    "refunded", "charged_back", "in_mediation",
))


@dataclass(frozen=True)
class ReadonlyGetFinding:
    tenant_id: UUID
    payment_id: str
    seller_id: str
    finding: str
    attempts: int
    provider_status: str | None = None
    bank_reconciled: bool = False
    payment_marked_paid: bool = False
    ledger_written: bool = False
    financial_closing_authorized: bool = False
    payout_authorized: bool = False


def _unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _reject_constant(value):
    raise ValueError("invalid JSON constant")


def _backoff(retry_after, attempt):
    if isinstance(retry_after, str) and re.fullmatch(r"[0-9]{1,2}", retry_after):
        return float(min(int(retry_after), 4))
    return float(min(2 ** attempt, 4))


async def preview_sandbox_provider_get(
    *, tenant_id: UUID, expected: ExpectedPayment,
    bound_seller_id: str, seller_authorization_checked: bool,
    access_token: str, transport: httpx.AsyncBaseTransport,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> ReadonlyGetFinding:
    """Explicitly injected transport: no registered endpoint or background worker.

    Caller must independently prove seller->tenant binding and OAuth scope.
    The boolean alone is NOT proof; do not wire to production without it.
    """
    if (
        type(tenant_id) is not UUID or type(expected) is not ExpectedPayment
        or expected.live_mode is not False
        or type(expected.amount_cents) is not int
        or not 0 < expected.amount_cents <= 999_999_999_999
        or type(bound_seller_id) is not str
        or re.fullmatch(r"[0-9]{1,40}", bound_seller_id) is None
        or bound_seller_id != expected.collector_id
        or seller_authorization_checked is not True
        or type(access_token) is not str
        or not 20 <= len(access_token) <= 4096
        or any(x.isspace() for x in access_token)
        or not isinstance(transport, httpx.AsyncBaseTransport)
        or not callable(sleep)
    ):
        raise ValueError("GET sandbox: tenant, seller or token invalid")
    request = build_get_payment_request(
        access_token=access_token, provider_payment_id=expected.provider_payment_id,
    )
    if request.method != "GET" or request.url.host != "api.mercadopago.com" or request.url.scheme != "https":
        raise ValueError("Invalid provider URL")
    async with httpx.AsyncClient(
        transport=transport, trust_env=False, follow_redirects=False,
        timeout=httpx.Timeout(4.0),
    ) as client:
        for i in range(RETRIES):
            try:
                response = await client.send(request)
            except (httpx.TimeoutException, httpx.TransportError):
                if i < RETRIES - 1:
                    await sleep(_backoff(None, i))
                    continue
                return ReadonlyGetFinding(
                    tenant_id, expected.provider_payment_id, bound_seller_id,
                    "UNAVAILABLE", i+1,
                )
            status_code = response.status_code
            if status_code in RETRYABLE:
                if i < RETRIES - 1:
                    await sleep(_backoff(response.headers.get("retry-after"), i))
                    continue
                return ReadonlyGetFinding(
                    tenant_id, expected.provider_payment_id, bound_seller_id,
                    "RATE_LIMIT_OR_OUTAGE", i+1,
                )
            if status_code != 200:
                return ReadonlyGetFinding(
                    tenant_id, expected.provider_payment_id, bound_seller_id,
                    "UNEXPECTED_HTTP_STATUS", i+1,
                )
            if len(response.content) > MAX_BYTES:
                return ReadonlyGetFinding(
                    tenant_id, expected.provider_payment_id, bound_seller_id,
                    "OVERSIZE_BODY", i+1,
                )
            try:
                payload = json.loads(
                    response.content, parse_float=Decimal,
                    parse_constant=_reject_constant, object_pairs_hook=_unique_keys,
                )
            except (ValueError, TypeError, UnicodeError):
                payload = None
            if type(payload) is not dict:
                return ReadonlyGetFinding(
                    tenant_id, expected.provider_payment_id, bound_seller_id,
                    "INVALID_JSON", i+1,
                )
            provider_status = payload.get("status")
            if type(provider_status) is not str or provider_status not in STATUSES:
                return ReadonlyGetFinding(
                    tenant_id, expected.provider_payment_id, bound_seller_id,
                    "INVALID_PROVIDER_STATUS", i+1,
                )
            if provider_status != "approved":
                result = "NON_APPROVED_OR_REVERSAL"
            elif matches_approved_payment(expected, payload):
                result = "APPROVED_SANDBOX_UNSETTLED"
            else:
                result = "PROVIDER_FIELDS_MISMATCH"
            return ReadonlyGetFinding(
                tenant_id, expected.provider_payment_id, bound_seller_id,
                result, i+1, provider_status,
            )
    raise AssertionError("retry loop exceeded")
