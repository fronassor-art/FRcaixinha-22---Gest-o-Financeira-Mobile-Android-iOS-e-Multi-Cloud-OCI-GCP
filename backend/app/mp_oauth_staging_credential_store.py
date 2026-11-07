"""M24100: guarded OAuth encrypted-writer staging port, sandbox ONLY.

Not an OCI Vault implementation. It never stores/prints plaintext credentials
and cannot be enabled by environment variables or public API routes.
A future writer must guarantee actual encryption, durable orphan management,
per-tenant key separation and audited access before production.
"""
from __future__ import annotations

from typing import Protocol
from uuid import UUID, uuid4
import re
from hmac import compare_digest

from .mp_connect_http_runtime import OAuthTokens
from .mp_oauth_staging_token_sink import PendingTokenRevision

_SELLER=re.compile(r"[0-9]{1,40}\Z")
_REF=re.compile(r"[A-Za-z0-9._:/-]{16,512}\Z")


class ProtectedStorageUnavailable(RuntimeError):
    def __str__(self) -> str:
        return "PROTECTED_OAUTH_STAGING_UNAVAILABLE"


class EncryptedRevisionWriter(Protocol):
    """External protected writer, NOT provided by this module."""

    async def write_encrypted(
        self, *, tenant: UUID, actor: UUID, seller: str,
        revision: str, tokens: OAuthTokens,
    ) -> str:
        """Return opaque protected reference; never raw access/refresh tokens."""
        ...

    async def discard_confirmed_failed(
        self, *, tenant: UUID, actor: UUID, seller: str,
        revision: str, credential_ref: str,
    ) -> bool:
        """Delete only AFTER SQL verified PENDING->FAILED (caller gate)."""
        ...


class ConsentGenerationReader(Protocol):
    async def consent_generation(
        self, *, tenant: UUID, actor: UUID, seller: str
    ) -> int | None: ...

    async def failed_credential_ref(
        self, *, pending: PendingTokenRevision
    ) -> str | None: ...


class StagingProtectedCredentialStore:
    """M23500 ProtectedCredentialStore, for synthetic/staging orchestration.

    Not crash-durable: retaining unresolved encrypted revisions for external
    reconciliation is mandatory before a production adapter is created.
    """

    def __init__(
        self, *, registry: ConsentGenerationReader,
        writer: EncryptedRevisionWriter, enabled: bool = False,
    ):
        self._registry=registry
        self._writer=writer
        self._enabled=enabled is True
        self._pending: dict[str,PendingTokenRevision]={}

    async def stage(
        self, *, tenant: UUID, actor: UUID, tokens: OAuthTokens
    ) -> PendingTokenRevision:
        if (not self._enabled or type(tenant) is not UUID
                or type(actor) is not UUID or type(tokens) is not OAuthTokens
                or tokens.live_mode is not False
                or type(tokens.seller_id) is not str
                or _SELLER.fullmatch(tokens.seller_id) is None):
            raise ProtectedStorageUnavailable()
        try:
            generation=await self._registry.consent_generation(
                tenant=tenant,actor=actor,seller=tokens.seller_id)
        except Exception:
            raise ProtectedStorageUnavailable() from None
        if (type(generation) is not int or generation<0
                or generation>9_223_372_036_854_775_807):
            raise ProtectedStorageUnavailable()

        # New random revision, never reused between tenants or generations.
        revision="m24100-"+uuid4().hex
        try:
            ref=await self._writer.write_encrypted(
                tenant=tenant, actor=actor, seller=tokens.seller_id,
                revision=revision, tokens=tokens)
        except Exception:
            # An ambiguous protected-store acknowledgment must NOT trigger an
            # unsafe compensating delete; queue for operator reconciliation.
            raise ProtectedStorageUnavailable() from None

        if type(ref) is not str or _REF.fullmatch(ref) is None:
            raise ProtectedStorageUnavailable()

        result=PendingTokenRevision(
            tenant_id=tenant,actor_id=actor,seller_id=tokens.seller_id,
            revision=revision,credential_ref=ref,
            expected_generation=generation,
        )
        self._pending[revision]=result
        return result

    async def cancel(self, *, pending: PendingTokenRevision) -> bool:
        if not self._enabled or type(pending) is not PendingTokenRevision:
            return False
        existing=self._pending.get(pending.revision)
        if existing is None or existing!=pending:
            return False
        # Do not trust caller-owned state. Confirm FAILED for the exact
        # revision and opaque ref through a worker-only PostgreSQL function.
        # A pending or ACTIVE row, revoked identity, stale response or
        # unknown network outcome MUST NOT authorize deletion.
        try:
            verified_ref=await self._registry.failed_credential_ref(
                pending=pending)
        except Exception:
            return False
        if (type(verified_ref) is not str
                or not compare_digest(verified_ref,pending.credential_ref)):
            return False
        try:
            deleted=await self._writer.discard_confirmed_failed(
                tenant=pending.tenant_id,actor=pending.actor_id,
                seller=pending.seller_id,revision=pending.revision,
                credential_ref=pending.credential_ref)
        except Exception:
            return False
        if deleted is True:
            self._pending.pop(pending.revision,None)
            return True
        return False
