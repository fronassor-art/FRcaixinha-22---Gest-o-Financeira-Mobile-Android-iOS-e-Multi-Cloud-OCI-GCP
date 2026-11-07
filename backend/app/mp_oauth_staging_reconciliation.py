"""M24300: read-only recovery verdict for ambiguous OAuth revision states.

Does not authorize cloud calls, release secrets, cancel stored credentials,
reactivate a merchant, or enable payments. A historical ACTIVE revision may
still be unusable after revocation of tenant consent or administrator status.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .mp_oauth_staging_token_sink import PendingTokenRevision


@dataclass(frozen=True)
class OAuthRecoveryVerdict:
    state: str
    next_step: str
    automatic_deletion_allowed: bool = False
    merchant_connection_authorized: bool = False
    real_payments_authorized: bool = False


class RevisionStatusReader(Protocol):
    async def revision_status(
        self, *, pending: PendingTokenRevision
    ) -> str | None: ...


UNKNOWN = OAuthRecoveryVerdict("UNKNOWN", "RETAIN_FOR_MANUAL_RECONCILIATION")
NEXT = {
    "ACTIVE": OAuthRecoveryVerdict(
        "ACTIVE", "RETAIN_AND_RECHECK_CURRENT_CONSENT",
    ),
    "PENDING": OAuthRecoveryVerdict(
        "PENDING", "RETAIN_AND_RECONCILE_REGISTRATION",
    ),
    "FAILED": OAuthRecoveryVerdict(
        "FAILED", "REQUIRE_SEPARATE_FAILED_REF_PROOF_BEFORE_CLEANUP",
    ),
    "RETIRED": OAuthRecoveryVerdict(
        "RETIRED", "RETAIN_UNTIL_APPROVED_RETENTION_POLICY",
    ),
}


class StagingOAuthRecoveryInspector:
    """M24300: never mutates DB, Vault, token, or revision status."""

    def __init__(self, *, registry: RevisionStatusReader,
                 enabled: bool = False):
        self._registry = registry
        self._enabled = enabled is True

    async def inspect(self, *, pending: PendingTokenRevision) -> OAuthRecoveryVerdict:
        if not self._enabled or type(pending) is not PendingTokenRevision:
            return UNKNOWN
        try:
            state = await self._registry.revision_status(pending=pending)
        except Exception:
            return UNKNOWN
        return NEXT.get(state, UNKNOWN) if type(state) is str else UNKNOWN
