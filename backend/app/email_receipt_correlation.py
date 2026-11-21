"""M27210 — CI-only correlation of synthetic receipt to sealed invitation.

The M26200 signature verifier authenticates mock bytes, not a real provider.
This bridge may classify a receipt but cannot persist an ACK, prove inbox
delivery or possession, authorize SMTP, or activate users.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from uuid import UUID

from .delivery_envelope import DeliveryScope, KeyProvider, SealedDelivery
from .delivery_key_lifecycle import TenantKeyCatalog
from .outbound_worker_preflight import (
    AuthenticatedLeaseSnapshot,
    DispatchPreflightBlocked,
    verify_sealed_outbox_before_dispatch,
)
from .synthetic_mail_receipt import VerifiedSyntheticReceipt


class ReceiptCorrelationBlocked(ValueError):
    """No external identifiers, token or personal data in errors."""


@dataclass(frozen=True)
class OfflineReceiptClassification:
    status: str
    durable_receipt_recorded: bool = False
    provider_delivery_confirmed: bool = False
    recipient_verified: bool = False
    contract_accepted: bool = False
    account_activated: bool = False
    can_send_network: bool = False


def correlate_ci_receipt_to_sealed_outbox(
    *,
    receipt: VerifiedSyntheticReceipt,
    lease: AuthenticatedLeaseSnapshot,
    scope: DeliveryScope,
    envelope: SealedDelivery,
    expected_recipient_digest: str,
    catalog: TenantKeyCatalog,
    provider: KeyProvider,
    now: int,
) -> OfflineReceiptClassification:
    """Correlate only; M26300 durable SQL handles idempotency and replay.

    A bounce is classified for quarantine; a synthetic SMTP ACK is NOT proof
    of delivery. There is no provider callback or DB write in this function.
    """
    blocked = ReceiptCorrelationBlocked("M27210_RECEIPT_CORRELATION_BLOCKED")
    if (type(receipt) is not VerifiedSyntheticReceipt
            or type(now) is not int
            or type(receipt.event_id) is not UUID
            or receipt.event_id.int == 0
            or type(receipt.invitation_event_id) is not UUID
            or receipt.invitation_event_id != getattr(lease, "event_id", None)
            or receipt.invitation_event_id != getattr(scope, "event_id", None)
            or receipt.kind not in ("CI_SMTP_ACCEPTED", "CI_BOUNCE")
            or receipt.signature_authenticated_in_ci is not True
            or receipt.provider_delivery_confirmed is not False
            or receipt.recipient_verified is not False
            or receipt.consent_recorded is not False
            or receipt.user_activated is not False
            or type(receipt.occurred_at) is not int
            or not now - 300 <= receipt.occurred_at <= now
            or type(receipt.body_sha256) is not str
            or len(receipt.body_sha256) != 64
            or any(c not in "0123456789abcdef" for c in receipt.body_sha256)):
        raise blocked
    try:
        preflight = verify_sealed_outbox_before_dispatch(
            lease=lease, scope=scope, envelope=envelope,
            expected_recipient_digest=expected_recipient_digest,
            catalog=catalog, provider=provider, now=now,
        )
        if preflight.can_send_network is not False:
            raise blocked
    except (DispatchPreflightBlocked, ValueError, TypeError):
        raise blocked from None
    # sha256 of the exact signed body is immutable metadata only, and M26300
    # requires a SQL UNIQUE event ID to prevent persistent replay.
    return OfflineReceiptClassification(
        status=("CI_BOUNCE_QUARANTINE_REQUIRED"
                if receipt.kind == "CI_BOUNCE"
                else "CI_SMTP_ACCEPTED_NOT_DELIVERED"),
    )
