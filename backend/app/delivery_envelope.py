"""M26400 — AES-256-GCM envelope for outbox payloads, no live delivery.

Only authenticated workers holding a separately provisioned key may decrypt.
No key/environment fallback, no public route, no cloud or SMTP I/O.
The AEAD AAD binds tenant, event, document, purpose, role and expiration.
A KMS/Vault key provider must be implemented and independently approved
before this module is connected to any real persistence or network worker.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass
import json
import os
import re
from typing import Protocol
from uuid import UUID

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .onboarding_mail_transport import _mailbox, MailConfigurationBlocked


class EnvelopeBlocked(ValueError):
    """Intentionally contains no token, key, recipient, plaintext or ciphertext."""


class KeyProvider(Protocol):
    def load_key(self, key_id: str) -> bytes: ...


@dataclass(frozen=True)
class DeliveryScope:
    tenant_id: UUID
    event_id: UUID
    document_id: UUID | None
    target_role: str
    purpose: str
    issued_at: int
    expires_at: int


@dataclass(frozen=True, repr=False)
class DeliverySecret:
    recipient: str
    token: str

    def __repr__(self) -> str:
        return "DeliverySecret(redacted=True)"


@dataclass(frozen=True, repr=False)
class SealedDelivery:
    version: int
    key_id: str
    nonce_b64: str
    ciphertext_b64: str

    def __repr__(self) -> str:
        return "SealedDelivery(version=1, payload=redacted)"


_MAX_BYTES = 2048
_TOKEN_RE = re.compile(r"[A-Za-z0-9_-]{32,256}\Z")
_KEY_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{3,79}\Z")
_B64_RE = re.compile(r"[A-Za-z0-9_-]+={0,2}\Z")
_ROLES = {"TENANT_MEMBER", "TENANT_ADMIN"}
_PURPOSES = {"INVITATION", "PASSWORD_RESET"}


def _deny() -> EnvelopeBlocked:
    return EnvelopeBlocked("M26400_ENVELOPE_BLOCKED")


def _validate_scope(scope: DeliveryScope, now: int, *, opening: bool) -> None:
    if not isinstance(scope, DeliveryScope) or type(now) is not int:
        raise _deny()
    if not all(isinstance(x, UUID) and x.int != 0 for x in (scope.tenant_id, scope.event_id)):
        raise _deny()
    if scope.document_id is not None and (
        not isinstance(scope.document_id, UUID) or scope.document_id.int == 0
    ):
        raise _deny()
    if scope.purpose not in _PURPOSES or scope.target_role not in _ROLES:
        raise _deny()
    if scope.purpose == "INVITATION" and scope.document_id is None:
        raise _deny()
    if type(scope.issued_at) is not int or type(scope.expires_at) is not int:
        raise _deny()
    if not (1_600_000_000 <= scope.issued_at <= scope.expires_at <= 9_999_999_999):
        raise _deny()
    if not (0 < scope.expires_at - scope.issued_at <= 86_400):
        raise _deny()
    if opening:
        if not scope.issued_at <= now < scope.expires_at:
            raise _deny()
    elif not scope.issued_at <= now <= scope.issued_at + 30:
        raise _deny()


def _associated_data(scope: DeliveryScope, key_id: str) -> bytes:
    if type(key_id) is not str or not _KEY_ID_RE.fullmatch(key_id):
        raise _deny()
    payload = {
        "version": 1, "key_id": key_id,
        "tenant_id": str(scope.tenant_id),
        "event_id": str(scope.event_id),
        "document_id": str(scope.document_id) if scope.document_id else None,
        "target_role": scope.target_role,
        "purpose": scope.purpose,
        "issued_at": scope.issued_at,
        "expires_at": scope.expires_at,
    }
    return ("FR_FINANCE_MAIL_ENVELOPE_V1\n" + json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
    )).encode("ascii")


def _load_key(provider: KeyProvider, key_id: str) -> bytes:
    try:
        key = provider.load_key(key_id)
    except Exception:
        raise _deny() from None
    if type(key) is not bytes or len(key) != 32:
        raise _deny()
    return key


def _encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii")


def _decode(value: str, max_raw: int) -> bytes:
    if type(value) is not str or len(value) > (max_raw + 4) * 2 or not _B64_RE.fullmatch(value):
        raise _deny()
    try:
        decoded = base64.b64decode(value, altchars=b"-_", validate=True)
    except (ValueError, base64.binascii.Error):
        raise _deny() from None
    if len(decoded) > max_raw or _encode(decoded) != value:
        raise _deny()
    return decoded


def seal_delivery(
    *, scope: DeliveryScope, secret: DeliverySecret, key_id: str,
    provider: KeyProvider, now: int,
) -> SealedDelivery:
    """Encrypt small private recipient/token payload using a fresh 96-bit nonce."""
    _validate_scope(scope, now, opening=False)
    aad = _associated_data(scope, key_id)
    if not isinstance(secret, DeliverySecret):
        raise _deny()
    try:
        recipient = _mailbox(secret.recipient)
    except MailConfigurationBlocked:
        raise _deny() from None
    if type(secret.token) is not str or not _TOKEN_RE.fullmatch(secret.token):
        raise _deny()
    plaintext = json.dumps(
        {"recipient": recipient, "token": secret.token},
        separators=(",", ":"), ensure_ascii=True, sort_keys=True,
    ).encode("utf-8")
    if not 1 <= len(plaintext) <= _MAX_BYTES:
        raise _deny()
    key = _load_key(provider, key_id)
    nonce = os.urandom(12)
    ciphertext = AESGCM(key).encrypt(nonce, plaintext, aad)
    return SealedDelivery(
        version=1, key_id=key_id,
        nonce_b64=_encode(nonce), ciphertext_b64=_encode(ciphertext),
    )


def open_delivery(
    *, envelope: SealedDelivery, scope: DeliveryScope,
    provider: KeyProvider, now: int,
) -> DeliverySecret:
    """Fail closed on wrong tenant, event, document, expiration, key or tag."""
    _validate_scope(scope, now, opening=True)
    if not isinstance(envelope, SealedDelivery) or type(envelope.version) is not int or envelope.version != 1:
        raise _deny()
    aad = _associated_data(scope, envelope.key_id)
    nonce = _decode(envelope.nonce_b64, 12)
    ciphertext = _decode(envelope.ciphertext_b64, _MAX_BYTES + 16)
    if len(nonce) != 12 or not 17 <= len(ciphertext) <= _MAX_BYTES + 16:
        raise _deny()
    key = _load_key(provider, envelope.key_id)
    try:
        plaintext = AESGCM(key).decrypt(nonce, ciphertext, aad)
        payload = json.loads(plaintext.decode("utf-8", errors="strict"))
    except (InvalidTag, ValueError, UnicodeError, TypeError):
        raise _deny() from None
    if type(payload) is not dict or set(payload) != {"recipient", "token"}:
        raise _deny()
    try:
        recipient = _mailbox(payload["recipient"])
    except (MailConfigurationBlocked, TypeError):
        raise _deny() from None
    if type(payload["token"]) is not str or not _TOKEN_RE.fullmatch(payload["token"]):
        raise _deny()
    return DeliverySecret(recipient=recipient, token=payload["token"])
