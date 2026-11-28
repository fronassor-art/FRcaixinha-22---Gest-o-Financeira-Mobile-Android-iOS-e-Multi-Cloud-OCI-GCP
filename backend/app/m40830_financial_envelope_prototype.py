"""M40830: laboratory-only AES-GCM member record envelope.

NOT wired to live API, original schema, sessions, RLS or key manager.
Only an off-database key can open ciphertext; SQL GUCs cannot replace it.
This is a research prototype, not a production authentication control.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import os
from uuid import UUID

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .m40610_verified_rls_session import (
    UnverifiedRLSSession, require_verified_rls_session,
)

_DOMAIN = b"FRF_M40830_MEMBER_ENTRY_ENVELOPE_V1|"
_MAX_CENTS = 10**12


class SealedRecordDenied(ValueError):
    """Constant error with no ciphertext, metadata, key or raw session values."""


@dataclass(frozen=True, repr=False)
class SealedMemberRecord:
    tenant_id: UUID
    member_id: UUID
    record_id: UUID
    revision: int
    nonce: bytes = field(repr=False)
    ciphertext: bytes = field(repr=False)

    def __repr__(self) -> str:
        return "SealedMemberRecord(redacted=True,experimental=True)"


def _validate_ids(*values: UUID) -> None:
    if any(type(x) is not UUID or x.int == 0 for x in values):
        raise SealedRecordDenied("M40830_RECORD_DENIED")


def _key(key: bytes) -> None:
    if type(key) is not bytes or len(key) != 32:
        raise SealedRecordDenied("M40830_RECORD_DENIED")


def _aad(tenant_id: UUID, member_id: UUID,
         record_id: UUID, revision: int) -> bytes:
    _validate_ids(tenant_id, member_id, record_id)
    if type(revision) is not int or not 1 <= revision <= 2**31-1:
        raise SealedRecordDenied("M40830_RECORD_DENIED")
    return (_DOMAIN + tenant_id.bytes + member_id.bytes
            + record_id.bytes + revision.to_bytes(4, "big"))


def seal_member_record(*, key: bytes, tenant_id: UUID, member_id: UUID,
                       record_id: UUID, revision: int,
                       amount_cents: int) -> SealedMemberRecord:
    """Synthetic record builder; never pass production financial data here."""
    _key(key)
    aad = _aad(tenant_id, member_id, record_id, revision)
    if type(amount_cents) is not int or not 0 < amount_cents <= _MAX_CENTS:
        raise SealedRecordDenied("M40830_RECORD_DENIED")
    nonce = os.urandom(12)
    encrypted = AESGCM(key).encrypt(nonce, amount_cents.to_bytes(8, "big"), aad)
    return SealedMemberRecord(tenant_id, member_id, record_id,
                              revision, nonce, encrypted)


def open_member_record(*, key: bytes, record: SealedMemberRecord,
                       session: object, now: datetime | None = None) -> int:
    """Member-only local read: verified-session SHAPE + off-DB key required.

    Verified-session fields are still supplied by Python: authenticity must
    come from a trusted runtime. This does not supersede HTTP/SQL checks.
    """
    _key(key)
    if type(record) is not SealedMemberRecord:
        raise SealedRecordDenied("M40830_RECORD_DENIED")
    aad = _aad(record.tenant_id, record.member_id,
               record.record_id, record.revision)
    if (type(record.nonce) is not bytes or len(record.nonce) != 12
            or type(record.ciphertext) is not bytes
            or len(record.ciphertext) != 24):
        raise SealedRecordDenied("M40830_RECORD_DENIED")
    try:
        require_verified_rls_session(session, now=now)
    except UnverifiedRLSSession:
        raise SealedRecordDenied("M40830_RECORD_DENIED") from None
    if (getattr(session, "role", None) != "TENANT_MEMBER"
            or getattr(session, "tenant_id", None) != str(record.tenant_id)
            or getattr(session, "user_id", None) != str(record.member_id)):
        raise SealedRecordDenied("M40830_RECORD_DENIED")
    try:
        opened = AESGCM(key).decrypt(record.nonce, record.ciphertext, aad)
        if len(opened) != 8:
            raise SealedRecordDenied("M40830_RECORD_DENIED")
        amount = int.from_bytes(opened, "big")
        if not 0 < amount <= _MAX_CENTS:
            raise SealedRecordDenied("M40830_RECORD_DENIED")
        return amount
    except (InvalidTag, ValueError, OverflowError):
        raise SealedRecordDenied("M40830_RECORD_DENIED") from None
