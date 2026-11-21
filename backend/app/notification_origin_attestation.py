"""M17000: verify a signed *synthetic* event origin; never dispatch messages.

Signature verification is a pure boundary. A valid HMAC only proves possession
of a test key, not authenticated issuer identity, bank settlement or user consent.
No signing endpoint, no sender, no production key or auto-enqueue exists here.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import hmac
import json
from re import fullmatch
from typing import Mapping
from uuid import UUID

from .notifications_policy import (
    NoticeClaim, NoticeKind, NoticeRole, inspect_notification_claim,
)
from .pix_automation_contract import FinancialOperationBlocked

CONTRACT = "AI_STUDIO_M17000_NOTIFICATION_ORIGIN_SIGNED_SYNTHETIC_V1"
DOMAIN = b"AI_STUDIO_M17000_TEST_ONLY_SIGNED_EVENT\n"
MAX_AGE_SECONDS = 300
FUTURE_SKEW_SECONDS = 30
_ALLOWED = frozenset((
    "event_id", "event_kind", "tenant_id", "recipient_id", "role",
    "cycle_year", "occurred_at", "source_digest",
))


@dataclass(frozen=True)
class VerifiedSyntheticOrigin:
    event_id: UUID
    event_kind: NoticeKind
    tenant_id: UUID | None
    recipient_id: UUID
    role: NoticeRole
    cycle_year: int | None
    source_digest: str
    fingerprint: str
    verified_synthetic_hmac: bool = True
    authenticated_production_event: bool = False
    notification_delivery_authorized: bool = False
    financial_effect_applied: bool = False
    bank_reconciled: bool = False


def _canonical(raw: Mapping[str, object]) -> bytes:
    try:
        return json.dumps(raw, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=True, allow_nan=False).encode("ascii")
    except (TypeError, ValueError, UnicodeError) as exc:
        raise FinancialOperationBlocked("Evento sintético inválido") from exc


def verify_synthetic_origin(
    raw: Mapping[str, object],
    signature_hex: str,
    secret: bytes,
    *,
    now: datetime,
) -> VerifiedSyntheticOrigin:
    if (type(raw) is not dict or frozenset(raw) != _ALLOWED
            or type(secret) is not bytes or len(secret) < 32
            or type(signature_hex) is not str
            or fullmatch(r"[0-9a-f]{64}", signature_hex) is None
            or type(now) is not datetime or now.tzinfo is None
            or now.utcoffset() is None):
        raise FinancialOperationBlocked("Envelope de evento não confiável")
    expected = hmac.new(secret, DOMAIN + _canonical(raw), sha256).hexdigest()
    if not hmac.compare_digest(expected, signature_hex):
        raise FinancialOperationBlocked("Assinatura sintética incorreta")
    try:
        if (any(type(raw[key]) is not str for key in (
                "event_id", "event_kind", "recipient_id", "role",
                "occurred_at", "source_digest"))
                or (raw["tenant_id"] is not None
                    and type(raw["tenant_id"]) is not str)
                or (raw["cycle_year"] is not None
                    and type(raw["cycle_year"]) is not int)):
            raise ValueError("event types")
        if raw["occurred_at"][-1:] != "Z" or not fullmatch(
                r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", raw["occurred_at"]):
            raise ValueError("canonical timestamp")
        at = datetime.strptime(raw["occurred_at"],
                               "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        delta = (now.astimezone(timezone.utc) - at).total_seconds()
        if delta > MAX_AGE_SECONDS or delta < -FUTURE_SKEW_SECONDS:
            raise ValueError("expired/future event")
        event_id = UUID(raw["event_id"])
        recipient_id = UUID(raw["recipient_id"])
        tenant = UUID(raw["tenant_id"]) if raw["tenant_id"] else None
        if (str(event_id) != raw["event_id"]
                or str(recipient_id) != raw["recipient_id"]
                or (tenant is not None and str(tenant) != raw["tenant_id"])):
            raise ValueError("noncanonical UUID")
        claim = NoticeClaim(
            event_id=event_id, event_kind=NoticeKind(raw["event_kind"]),
            recipient_id=recipient_id, role=NoticeRole(raw["role"]),
            tenant_id=tenant, cycle_year=raw["cycle_year"],
            occurred_at=at, source_reference_digest=raw["source_digest"],
            authenticated_event_source=False, authenticated_recipient=False,
            tenant_membership_verified=False,
        )
        preview = inspect_notification_claim(claim)
    except (ValueError, TypeError, KeyError) as exc:
        raise FinancialOperationBlocked("Evento assinado sem contexto ou escopo válido") from exc

    return VerifiedSyntheticOrigin(
        event_id=claim.event_id, event_kind=claim.event_kind,
        tenant_id=claim.tenant_id, recipient_id=claim.recipient_id,
        role=claim.role, cycle_year=claim.cycle_year,
        source_digest=claim.source_reference_digest,
        fingerprint=preview.fingerprint,
    )
