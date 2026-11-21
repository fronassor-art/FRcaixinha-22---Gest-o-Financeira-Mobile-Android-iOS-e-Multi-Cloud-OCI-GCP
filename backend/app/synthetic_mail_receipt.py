"""M26200 — provider-neutral, CI-only signed mail receipt verifier.

This is an OFFLINE contract for a synthetic provider, not a real SMTP,
SendGrid, SES or Mercado Pago signature specification. No public webhook is
registered. A verifier does not prove inbox receipt or e-mail ownership.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import hmac
import json
import re
from typing import Any
from uuid import UUID


class ReceiptVerificationBlocked(ValueError):
    """No secrets, bodies, signatures or PII in exceptions."""


@dataclass(frozen=True)
class VerifiedSyntheticReceipt:
    event_id: UUID
    invitation_event_id: UUID
    kind: str
    occurred_at: int
    body_sha256: str
    signature_authenticated_in_ci: bool = True
    provider_delivery_confirmed: bool = False
    recipient_verified: bool = False
    consent_recorded: bool = False
    user_activated: bool = False


_RECOGNIZED = {"CI_SMTP_ACCEPTED", "CI_BOUNCE"}
_KEYS = {"event_id", "invitation_event_id", "kind", "occurred_at"}
_MAX_BODY_BYTES = 2048
_REPLAY_WINDOW_SECONDS = 300
_CONTEXT = b"FR_FINANCE_CI_MAIL_RECEIPT_V1\n"


def _unique_pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in items:
        if key in result:
            raise ReceiptVerificationBlocked("M26200_INVALID_RECEIPT")
        result[key] = value
    return result


def _uuid(value: Any) -> UUID:
    if type(value) is not str or not re.fullmatch(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}",
        value,
    ):
        raise ReceiptVerificationBlocked("M26200_INVALID_RECEIPT")
    try:
        result = UUID(value)
    except (ValueError, AttributeError):
        raise ReceiptVerificationBlocked("M26200_INVALID_RECEIPT") from None
    if result.int == 0 or str(result) != value:
        raise ReceiptVerificationBlocked("M26200_INVALID_RECEIPT")
    return result


def receipt_signature(secret: bytes, timestamp: int, body: bytes) -> str:
    """Generate TEST-ONLY fixture HMAC over timestamp + exact raw bytes."""
    if (type(secret) is not bytes or len(secret) < 32
            or type(timestamp) is not int or not 1_600_000_000 <= timestamp <= 9_999_999_999
            or type(body) is not bytes or not 1 <= len(body) <= _MAX_BODY_BYTES):
        raise ReceiptVerificationBlocked("M26200_INVALID_SIGNING_INPUT")
    signed = _CONTEXT + str(timestamp).encode("ascii") + b"\n" + body
    return hmac.new(secret, signed, sha256).hexdigest()


def verify_synthetic_mail_receipt(
    *,
    body: bytes,
    signature: str,
    timestamp: str,
    secret: bytes,
    now: int,
) -> VerifiedSyntheticReceipt:
    """Authenticate exact bytes, bounded time, strict schema, no replay claim.

    Caller MUST additionally enforce a durable unique event ID in SQL. This
    function performs no database I/O, HTTP, filesystem or network activity.
    """
    invalid = ReceiptVerificationBlocked("M26200_INVALID_RECEIPT")
    if (type(now) is not int or type(timestamp) is not str
            or not re.fullmatch(r"[1-9][0-9]{9}", timestamp)
            or type(signature) is not str
            or not re.fullmatch(r"[0-9a-f]{64}", signature)
            or type(body) is not bytes or not 1 <= len(body) <= _MAX_BODY_BYTES):
        raise invalid
    stamp = int(timestamp)
    if abs(now - stamp) > _REPLAY_WINDOW_SECONDS:
        raise invalid
    try:
        expected = receipt_signature(secret, stamp, body)
    except ReceiptVerificationBlocked:
        raise invalid from None
    if not hmac.compare_digest(expected, signature):
        raise invalid
    try:
        data = json.loads(
            body.decode("utf-8", errors="strict"), object_pairs_hook=_unique_pairs,
            parse_constant=lambda value: (_ for _ in ()).throw(invalid),
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ReceiptVerificationBlocked, ValueError):
        raise invalid from None
    if type(data) is not dict or set(data) != _KEYS:
        raise invalid
    kind = data["kind"]
    occurred = data["occurred_at"]
    if type(kind) is not str or kind not in _RECOGNIZED or type(occurred) is not int:
        raise invalid
    if abs(stamp - occurred) > _REPLAY_WINDOW_SECONDS:
        raise invalid
    return VerifiedSyntheticReceipt(
        event_id=_uuid(data["event_id"]),
        invitation_event_id=_uuid(data["invitation_event_id"]),
        kind=kind,
        occurred_at=occurred,
        body_sha256=sha256(body).hexdigest(),
    )
