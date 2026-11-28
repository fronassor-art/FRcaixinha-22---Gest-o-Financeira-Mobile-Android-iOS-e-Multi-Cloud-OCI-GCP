"""M23500: tenant-scoped OAuth credential sink boundary, sandbox only.

No actual OCI Vault, DB transaction, external network or public route.
The CAS registry implementation MUST reject revoked consent atomically.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Protocol
from uuid import UUID

from .mp_connect_http_runtime import OAuthTokens
from .mp_oauth_connect_preflight import OAuthDraft


@dataclass(frozen=True, repr=False)
class PendingTokenRevision:
    tenant_id: UUID
    actor_id: UUID
    seller_id: str
    revision: str
    credential_ref: str
    expected_generation: int | None = None

    def __repr__(self) -> str:
        return "PendingTokenRevision(redacted=True, pending=True)"


class SellerRegistry(Protocol):
    async def eligible(self, *, tenant: UUID, actor: UUID, seller: str) -> bool: ...
    async def stage_pending(self, *, pending: PendingTokenRevision) -> bool: ...
    async def activate_cas(
        self, *, pending: PendingTokenRevision,
        access_hash: str, refresh_hash: str
    ) -> bool: ...
    async def mark_failed(self, *, pending: PendingTokenRevision) -> bool: ...


class ProtectedCredentialStore(Protocol):
    async def stage(
        self, *, tenant: UUID, actor: UUID, tokens: OAuthTokens
    ) -> PendingTokenRevision: ...
    async def cancel(self, *, pending: PendingTokenRevision) -> bool: ...


class StagingOAuthTokenSink:
    def __init__(
        self, *, registry: SellerRegistry,
        store: ProtectedCredentialStore, enabled: bool = False
    ):
        self._registry = registry
        self._store = store
        self._enabled = enabled is True

    async def persist_sandbox_connection(
        self, *, draft: OAuthDraft, tokens: OAuthTokens
    ) -> bool:
        if not self._enabled:
            return False
        if (type(draft) is not OAuthDraft or draft.live_mode is not False
                or type(tokens) is not OAuthTokens or tokens.live_mode is not False
                or type(tokens.seller_id) is not str
                or not tokens.seller_id.isascii()
                or not tokens.seller_id.isdecimal()
                or not 1 <= len(tokens.seller_id) <= 40
                or type(tokens.scope) is not str
                or not {"read", "offline_access"}.issubset(set(tokens.scope.split()))
                or type(tokens.expires_in) is not int
                or not 0 < tokens.expires_in <= 15_552_000
                or type(tokens.access_token) is not str
                or type(tokens.refresh_token) is not str
                or not 16 <= len(tokens.access_token) <= 4096
                or not 16 <= len(tokens.refresh_token) <= 4096):
            return False
        pending = None
        committed = False
        registration_attempted = False
        try:
            if await self._registry.eligible(
                tenant=draft.tenant_id, actor=draft.initiated_by,
                seller=tokens.seller_id
            ) is not True:
                return False
            pending = await self._store.stage(
                tenant=draft.tenant_id, actor=draft.initiated_by, tokens=tokens)
            if (type(pending) is not PendingTokenRevision
                    or pending.tenant_id != draft.tenant_id
                    or pending.actor_id != draft.initiated_by
                    or pending.seller_id != tokens.seller_id
                    or type(pending.revision) is not str
                    or not 16 <= len(pending.revision) <= 512
                    or type(pending.credential_ref) is not str
                    or not 16 <= len(pending.credential_ref) <= 512
                    or type(pending.expected_generation) is not int
                    or not 0 <= pending.expected_generation <= 9_223_372_036_854_775_807):
                return False
            # This is a preflight ONLY. A real DB activate_cas MUST
            # re-check the consent and seller binding atomically.
            if await self._registry.eligible(
                tenant=draft.tenant_id, actor=draft.initiated_by,
                seller=tokens.seller_id
            ) is not True:
                return False
            # SQL must register the PENDING row before any CAS activation.
            registration_attempted = True
            if await self._registry.stage_pending(pending=pending) is not True:
                return False
            if await self._registry.activate_cas(
                pending=pending,
                access_hash=sha256(tokens.access_token.encode()).hexdigest(),
                refresh_hash=sha256(tokens.refresh_token.encode()).hexdigest()
            ) is not True:
                return False
            committed = True
            return True
        except Exception:
            # Never disclose provider or Vault exception text.
            return False
        finally:
            if (not committed and type(pending) is PendingTokenRevision
                    and pending.tenant_id == draft.tenant_id
                    and pending.actor_id == draft.initiated_by
                    and pending.seller_id == tokens.seller_id):
                # Do not delete an opaque secret if a DB commit/response is
                # ambiguous. Once registration was attempted, only a positive
                # atomic SQL PENDING->FAILED transition proves safe disposal.
                # A failed check leaves the ref for controlled reconciliation.
                can_discard = not registration_attempted
                if registration_attempted:
                    try:
                        can_discard = (
                            await self._registry.mark_failed(pending=pending)
                        ) is True
                    except Exception:
                        can_discard = False
                if can_discard:
                    try:
                        await self._store.cancel(pending=pending)
                    except Exception:
                        pass
