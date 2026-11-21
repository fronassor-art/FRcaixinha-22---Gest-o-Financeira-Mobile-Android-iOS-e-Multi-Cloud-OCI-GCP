"""M26800 — policy boundary for rotating tenant-scoped envelope keys.

This is an offline metadata check, not an OCI Vault/KMS integration.
Key material must come from the separately authenticated KeyProvider in
delivery_envelope.py. No secret is read from environment or repository.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping
from uuid import UUID

from .delivery_envelope import (
    DeliveryScope, DeliverySecret, SealedDelivery, KeyProvider,
    seal_delivery, open_delivery,
)


class KeyAccessBlocked(ValueError):
    pass


class KeyLifecycle(str, Enum):
    ACTIVE = "ACTIVE"
    DECRYPT_ONLY = "DECRYPT_ONLY"
    REVOKED = "REVOKED"


@dataclass(frozen=True)
class KeyMetadata:
    key_id: str
    tenant_id: UUID
    lifecycle: KeyLifecycle
    active_from: int
    encrypt_until: int
    decrypt_until: int


class TenantKeyCatalog:
    """In-memory facade for already attested metadata; no key bytes stored."""

    def __init__(self, entries: Mapping[str, KeyMetadata]):
        if type(entries) is not dict or not entries:
            raise KeyAccessBlocked("M26800_KEY_POLICY_BLOCKED")
        self._entries = dict(entries)
        for ident, item in self._entries.items():
            if (type(ident) is not str or not ident or not isinstance(item, KeyMetadata)
                    or ident != item.key_id or not isinstance(item.tenant_id, UUID)
                    or item.tenant_id.int == 0
                    or not isinstance(item.lifecycle, KeyLifecycle)
                    or type(item.active_from) is not int
                    or type(item.encrypt_until) is not int
                    or type(item.decrypt_until) is not int
                    or not (1_600_000_000 <= item.active_from
                            < item.encrypt_until <= item.decrypt_until <= 9_999_999_999)):
                raise KeyAccessBlocked("M26800_KEY_POLICY_BLOCKED")

    def authorize(self, *, key_id: str, scope: DeliveryScope,
                  now: int, decrypt: bool) -> None:
        if (type(key_id) is not str or not isinstance(scope, DeliveryScope)
                or type(now) is not int):
            raise KeyAccessBlocked("M26800_KEY_POLICY_BLOCKED")
        item=self._entries.get(key_id)
        if (item is None or item.tenant_id != scope.tenant_id
                or item.lifecycle is KeyLifecycle.REVOKED
                or scope.issued_at < item.active_from
                or now < item.active_from):
            raise KeyAccessBlocked("M26800_KEY_POLICY_BLOCKED")
        if decrypt:
            if (now >= item.decrypt_until or
                    scope.issued_at >= item.encrypt_until):
                raise KeyAccessBlocked("M26800_KEY_POLICY_BLOCKED")
        else:
            if (item.lifecycle is not KeyLifecycle.ACTIVE
                    or now >= item.encrypt_until
                    or scope.issued_at >= item.encrypt_until):
                raise KeyAccessBlocked("M26800_KEY_POLICY_BLOCKED")


def seal_with_key_policy(
    *, scope: DeliveryScope, secret: DeliverySecret,
    key_id: str, catalog: TenantKeyCatalog,
    provider: KeyProvider, now: int,
) -> SealedDelivery:
    if not isinstance(catalog, TenantKeyCatalog):
        raise KeyAccessBlocked("M26800_KEY_POLICY_BLOCKED")
    catalog.authorize(key_id=key_id,scope=scope,now=now,decrypt=False)
    return seal_delivery(scope=scope,secret=secret,key_id=key_id,
                         provider=provider,now=now)


def open_with_key_policy(
    *, envelope: SealedDelivery, scope: DeliveryScope,
    catalog: TenantKeyCatalog, provider: KeyProvider, now: int,
) -> DeliverySecret:
    if not isinstance(catalog, TenantKeyCatalog) or not isinstance(envelope, SealedDelivery):
        raise KeyAccessBlocked("M26800_KEY_POLICY_BLOCKED")
    catalog.authorize(key_id=envelope.key_id,scope=scope,now=now,decrypt=True)
    return open_delivery(envelope=envelope,scope=scope,provider=provider,now=now)
