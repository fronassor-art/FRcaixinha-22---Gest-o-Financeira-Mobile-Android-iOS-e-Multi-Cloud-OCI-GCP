"""M27300 — tenant-bound keyed recipient index for future outbox migration.

This helper does not convert legacy SHA-256 indexes already in M25900.
It requires a distinct 32-byte key from a separately approved key provider;
never reuse an AES-GCM encryption key for recipient indexing.
There is no DB, SMTP, HTTP, OCI, environment or key-file access here.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import hmac
import re
from typing import Protocol
from uuid import UUID

from .onboarding_mail_transport import _mailbox, MailConfigurationBlocked


class RecipientIndexBlocked(ValueError):
    pass


class RecipientIndexKeyProvider(Protocol):
    def load_index_key(self, tenant_id: UUID, key_alias: str) -> bytes: ...


@dataclass(frozen=True, repr=False)
class RecipientIndex:
    tenant_id: UUID
    key_alias: str
    version: int
    digest: str

    def __repr__(self) -> str:
        return "RecipientIndex(version=1, redacted=True)"


_ALIAS = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{3,79}\Z")
_HEX = re.compile(r"[0-9a-f]{64}\Z")
_DOMAIN = b"FR_FINANCE_RECIPIENT_INDEX_V1\x00"


def _deny() -> RecipientIndexBlocked:
    return RecipientIndexBlocked("M27300_RECIPIENT_INDEX_BLOCKED")


def _canonical_address(address: str) -> bytes:
    try:
        raw = _mailbox(address)
    except (MailConfigurationBlocked, TypeError, AttributeError):
        raise _deny() from None
    # Match legacy M27000 canonicalization for a future controlled migration.
    # Provider-dependent local-part case rules require a later explicit policy.
    return raw.lower().encode("ascii")


def _key(*, provider: RecipientIndexKeyProvider, tenant_id: UUID, alias: str) -> bytes:
    try:
        raw = provider.load_index_key(tenant_id, alias)
    except Exception:
        raise _deny() from None
    if type(raw) is not bytes or len(raw) != 32:
        raise _deny()
    return raw


def _validate(tenant_id: UUID, alias: str) -> None:
    if (type(tenant_id) is not UUID or tenant_id.int == 0
            or type(alias) is not str or not _ALIAS.fullmatch(alias)):
        raise _deny()


def build_recipient_index(
    *, tenant_id: UUID, recipient: str, key_alias: str,
    provider: RecipientIndexKeyProvider,
) -> RecipientIndex:
    """Return an opaque tenant-scoped HMAC, never a raw-email SHA-256 index."""
    _validate(tenant_id, key_alias)
    canonical = _canonical_address(recipient)
    key = _key(provider=provider, tenant_id=tenant_id, alias=key_alias)
    payload = _DOMAIN + str(tenant_id).encode("ascii") + b"\x00" + canonical
    return RecipientIndex(
        tenant_id=tenant_id, key_alias=key_alias, version=1,
        digest=hmac.new(key, payload, sha256).hexdigest(),
    )


def matches_recipient_index(
    *, index: RecipientIndex, tenant_id: UUID,
    recipient: str, key_alias: str,
    provider: RecipientIndexKeyProvider,
) -> bool:
    _validate(tenant_id, key_alias)
    if (type(index) is not RecipientIndex or index.version != 1
            or index.tenant_id != tenant_id or index.key_alias != key_alias
            or type(index.digest) is not str or not _HEX.fullmatch(index.digest)):
        raise _deny()
    candidate = build_recipient_index(
        tenant_id=tenant_id, recipient=recipient,
        key_alias=key_alias, provider=provider,
    )
    return hmac.compare_digest(index.digest, candidate.digest)
