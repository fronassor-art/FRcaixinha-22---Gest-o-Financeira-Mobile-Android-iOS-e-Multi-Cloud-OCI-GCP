"""M27200 — Offline, CI-only one-time e-mail challenge material.

A trusted worker must first obtain an authenticated SQL outbox lease and sealed
AES-GCM invitation. This function neither persists nor delivers the token.
The SQL M27100 issue procedure is the only authority for durable issuance;
consumption in disposable CI NEVER proves actual ownership of an inbox.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
import re
import secrets
from uuid import UUID

from .delivery_envelope import DeliveryScope, KeyProvider, SealedDelivery
from .delivery_key_lifecycle import TenantKeyCatalog
from .outbound_worker_preflight import (
    AuthenticatedLeaseSnapshot,
    DispatchPreflightBlocked,
    verify_sealed_outbox_before_dispatch,
)


class EmailChallengeBlocked(ValueError):
    """Generic error: no token, e-mail, key, lease or recipient details."""


@dataclass(frozen=True, repr=False)
class PreparedCiEmailChallenge:
    """Sensitive in-memory worker hand-off; never serialize or log this value.

    The raw token is deliberately absent from repr and from SQL parameters.
    It can only be delivered by a SEPARATELY approved worker after durable
    issuance succeeds. No network authorization is granted by this object.
    """

    event_id: UUID
    tenant_id: UUID
    document_id: UUID
    challenge_digest: str
    ttl_seconds: int
    expires_at: int
    raw_token_for_trusted_worker: str = field(repr=False, compare=False)
    can_send_network: bool = False
    recipient_verified: bool = False
    contract_accepted: bool = False
    account_activated: bool = False

    def __repr__(self) -> str:
        return "PreparedCiEmailChallenge(redacted=True, sent=False, verified=False)"

    def issue_sql_parameters(self) -> tuple[UUID, str, int]:
        """Only nonsecret parameters for invite_issue_ci_email_challenge."""
        return self.event_id, self.challenge_digest, self.ttl_seconds


def prepare_ci_email_challenge(
    *,
    lease: AuthenticatedLeaseSnapshot,
    scope: DeliveryScope,
    envelope: SealedDelivery,
    expected_recipient_digest: str,
    catalog: TenantKeyCatalog,
    provider: KeyProvider,
    now: int,
    ttl_seconds: int = 600,
) -> PreparedCiEmailChallenge:
    """Fail closed on every mismatch; no database, provider or HTTP operation.

    M27100 SQL must atomically store challenge_digest before ANY future
    delivery attempt. Never let a public API caller supply lease or digest.
    """
    blocked = EmailChallengeBlocked("M27200_CHALLENGE_PREPARATION_BLOCKED")
    if (type(now) is not int or type(ttl_seconds) is not int
            or not 60 <= ttl_seconds <= 900):
        raise blocked
    try:
        verification = verify_sealed_outbox_before_dispatch(
            lease=lease, scope=scope, envelope=envelope,
            expected_recipient_digest=expected_recipient_digest,
            catalog=catalog, provider=provider, now=now,
        )
        if (verification.can_send_network is not False
                or verification.recipient_verified is not False
                or now + ttl_seconds + 1 >= scope.expires_at
                or now + ttl_seconds >= lease.invitation_expires_at):
            raise blocked
        # secrets uses the OS CSPRNG. 48 bytes => ~64 URL-safe characters.
        raw = secrets.token_urlsafe(48)
        if not re.fullmatch(r"[A-Za-z0-9_-]{64}", raw):
            raise blocked
        digest = sha256(raw.encode("ascii")).hexdigest()
        return PreparedCiEmailChallenge(
            event_id=scope.event_id,
            tenant_id=scope.tenant_id,
            document_id=scope.document_id,
            challenge_digest=digest,
            ttl_seconds=ttl_seconds,
            expires_at=now + ttl_seconds,
            raw_token_for_trusted_worker=raw,
        )
    except (DispatchPreflightBlocked, AttributeError, TypeError, ValueError):
        raise blocked from None
