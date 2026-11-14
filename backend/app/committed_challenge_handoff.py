"""M27400 — offline post-commit challenge issuance attestation.

A trusted worker may use this to check a DB readback BEFORE an eventual
separate provider-specific transport authorization. This does not attest
email ownership, delivery or consent, and never calls SMTP or PostgreSQL.
An arbitrary object or client-provided boolean is not authentic database
evidence; real deployment must supply readback via restricted RLS role,
a committed transaction and an independently attested service identity.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import hmac
import re
from uuid import UUID

from .email_challenge_material import PreparedCiEmailChallenge


class ChallengeHandoffBlocked(ValueError):
    pass


@dataclass(frozen=True, repr=False)
class SyntheticChallengeReadback:
    """Snapshot of an already-committed CI-only DB challenge row.

    A future real worker must construct this ONLY from an authenticated
    database connection, never from the HTTP request body or callback.
    """

    tenant_id: UUID
    event_id: UUID
    document_id: UUID
    outbox_id: UUID
    challenge_digest: str
    issued_at: int
    expires_at: int
    failed_attempts: int
    consumed: bool
    challenge_status: str
    outbox_status: str
    terminal_quarantine: bool
    source: str

    def __repr__(self) -> str:
        return "SyntheticChallengeReadback(redacted=True)"


@dataclass(frozen=True)
class PostCommitChallengeDecision:
    status: str = "CI_CHALLENGE_READBACK_MATCHED_NO_SEND"
    can_send_network: bool = False
    recipient_verified: bool = False
    provider_delivery_confirmed: bool = False
    contract_accepted: bool = False
    account_activated: bool = False


_DIGEST_RE = re.compile(r"[0-9a-f]{64}\Z")


def check_committed_challenge(
    *, prepared: PreparedCiEmailChallenge,
    readback: SyntheticChallengeReadback,
    now: int,
) -> PostCommitChallengeDecision:
    """Match exact event, tenant, document and token digest; leak nothing."""
    fail = ChallengeHandoffBlocked("M27400_POSTCOMMIT_HANDOFF_BLOCKED")
    if (type(prepared) is not PreparedCiEmailChallenge
            or type(readback) is not SyntheticChallengeReadback
            or type(now) is not int):
        raise fail
    if not all(type(uid) is UUID and uid.int != 0 for uid in (
        prepared.event_id,prepared.tenant_id,prepared.document_id,
        readback.event_id,readback.tenant_id,readback.document_id,readback.outbox_id,
    )):
        raise fail
    if (readback.event_id != prepared.event_id
            or readback.tenant_id != prepared.tenant_id
            or readback.document_id != prepared.document_id
            or readback.source != "DISPOSABLE_POSTGRESQL_CI_READBACK"
            or readback.challenge_status != "CI_CHALLENGE_NOT_DELIVERED"
            or readback.outbox_status != "HELD_CI_NOT_SENT"
            or readback.terminal_quarantine is not False
            or readback.consumed is not False
            or type(readback.failed_attempts) is not int
            or readback.failed_attempts != 0
            or type(readback.issued_at) is not int
            or type(readback.expires_at) is not int
            or type(prepared.expires_at) is not int
            or type(prepared.ttl_seconds) is not int
            or not (0 <= now - readback.issued_at <= 30)
            or not (now < readback.expires_at <= prepared.expires_at)
            or not (60 <= readback.expires_at - readback.issued_at <= prepared.ttl_seconds)
            or type(readback.challenge_digest) is not str
            or not _DIGEST_RE.fullmatch(readback.challenge_digest)
            or type(prepared.challenge_digest) is not str
            or not _DIGEST_RE.fullmatch(prepared.challenge_digest)
            or prepared.can_send_network is not False
            or prepared.recipient_verified is not False
            or prepared.contract_accepted is not False
            or prepared.account_activated is not False):
        raise fail
    if not hmac.compare_digest(readback.challenge_digest,prepared.challenge_digest):
        raise fail
    token = prepared.raw_token_for_trusted_worker
    if type(token) is not str or not re.fullmatch(r"[A-Za-z0-9_-]{64}",token):
        raise fail
    computed = sha256(token.encode("ascii")).hexdigest()
    if not hmac.compare_digest(computed,prepared.challenge_digest):
        raise fail
    return PostCommitChallengeDecision()
