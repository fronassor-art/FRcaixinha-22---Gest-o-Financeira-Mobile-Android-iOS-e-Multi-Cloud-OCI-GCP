"""M27000: offline outbox-to-AEAD worker preflight, NO network or send.

Only consume a database-authenticated tenant/lease/scope; never consume
identity/lease metadata directly from a public request. The result does
not contain the recipient, token, ciphertext or key material. Checking
this preflight does NOT approve actual SMTP submission or activation.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import hmac
import re
from uuid import UUID

from .delivery_envelope import DeliveryScope, SealedDelivery, KeyProvider
from .delivery_key_lifecycle import (
    TenantKeyCatalog, open_with_key_policy, KeyAccessBlocked,
)


class DispatchPreflightBlocked(ValueError):
    pass


@dataclass(frozen=True)
class AuthenticatedLeaseSnapshot:
    tenant_id: UUID
    event_id: UUID
    document_id: UUID
    target_role: str
    lease_id: UUID
    lease_expires_at: int
    invitation_expires_at: int
    attempts: int
    outbox_status: str
    terminal_quarantine: bool


@dataclass(frozen=True)
class RedactedDispatchPreflight:
    status: str = "CI_PAYLOAD_VERIFIED_NOT_SENT"
    sealed_payload_integrity_verified: bool = True
    lease_scope_verified: bool = True
    can_send_network: bool = False
    recipient_verified: bool = False
    provider_delivery_confirmed: bool = False
    account_activated: bool = False
    consent_recorded: bool = False


def verify_sealed_outbox_before_dispatch(
    *,
    lease: AuthenticatedLeaseSnapshot,
    scope: DeliveryScope,
    envelope: SealedDelivery,
    expected_recipient_digest: str,
    catalog: TenantKeyCatalog,
    provider: KeyProvider,
    now: int,
) -> RedactedDispatchPreflight:
    """No e-mail/token bytes escape. All rejected states are indistinguishable."""
    fail = DispatchPreflightBlocked("M27000_OUTBOX_PREFLIGHT_BLOCKED")
    if (not isinstance(lease, AuthenticatedLeaseSnapshot)
            or not isinstance(scope, DeliveryScope)
            or not isinstance(envelope, SealedDelivery)
            or not isinstance(catalog, TenantKeyCatalog)
            or type(now) is not int
            or type(expected_recipient_digest) is not str
            or not re.fullmatch(r"[0-9a-f]{64}", expected_recipient_digest)):
        raise fail
    if not all(isinstance(x,UUID) and x.int for x in (
        lease.tenant_id,lease.event_id,lease.document_id,lease.lease_id
    )):
        raise fail
    if (lease.tenant_id != scope.tenant_id
            or lease.event_id != scope.event_id
            or lease.document_id != scope.document_id
            or lease.target_role != scope.target_role
            or scope.purpose != "INVITATION"
            or lease.outbox_status != "HELD_CI_NOT_SENT"
            or lease.terminal_quarantine is not False
            or type(lease.attempts) is not int
            or not 1 <= lease.attempts <= 3
            or type(lease.lease_expires_at) is not int
            or type(lease.invitation_expires_at) is not int
            or not now < lease.lease_expires_at
            or not now < lease.invitation_expires_at
            or scope.expires_at > lease.invitation_expires_at):
        raise fail
    try:
        secret = open_with_key_policy(
            envelope=envelope,scope=scope,catalog=catalog,provider=provider,now=now,
        )
        canonical = secret.recipient.lower().strip().encode("utf-8")
        digest = sha256(canonical).hexdigest()
        if not hmac.compare_digest(digest,expected_recipient_digest):
            raise fail
    except Exception:
        raise fail from None
    finally:
        # Do not retain plaintext in any returned or logged result.
        secret = None
    return RedactedDispatchPreflight()
