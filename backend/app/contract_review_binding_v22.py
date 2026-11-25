"""M40962: V2.2 immutable review binding, pure candidate, NOT legal consent.

Future server-side readback must supply the snapshot. This module does not
authenticate users, issue/consume a nonce, persist a contract, record consent,
or authorize payment or activation. Never mount it as an acceptance route.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from uuid import UUID
import hmac
import json
import re

MAX_BYTES = 65536
HEX64 = re.compile(r"[0-9a-f]{64}")
VERSION = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,59}")


@dataclass(frozen=True, kw_only=True)
class ContractReviewSnapshot:
    kind: str
    document_id: UUID
    version: str
    body_sha256: str
    issuer_id: UUID
    recipient_id: UUID
    recipient_role: str
    nonce: UUID
    issued_at: datetime
    expires_at: datetime
    published_at: datetime
    state: str
    offer_id: UUID | None = None
    price_version_id: UUID | None = None
    tenant_id: UUID | None = None
    cycle_id: UUID | None = None
    policy_version_id: UUID | None = None


def _uuid(v):
    return type(v) is UUID and v.int != 0


def _aware(v):
    return type(v) is datetime and v.tzinfo is not None and v.utcoffset() is not None


def _hash(v):
    return type(v) is str and HEX64.fullmatch(v) is not None


def review_fingerprint(snapshot: ContractReviewSnapshot) -> str:
    """Bind document and recipient to ONE purpose/context. No authorization."""
    s = snapshot
    if type(s) is not ContractReviewSnapshot:
        raise ValueError("INVALID_REVIEW_SNAPSHOT")
    if (not all(_uuid(v) for v in (s.document_id, s.issuer_id, s.recipient_id, s.nonce))
            or not _hash(s.body_sha256)
            or any(type(v) is not str for v in (s.kind, s.recipient_role, s.state))
            or type(s.version) is not str or not VERSION.fullmatch(s.version)
            or not all(_aware(v) for v in (s.published_at, s.issued_at, s.expires_at))
            or not s.published_at <= s.issued_at < s.expires_at
            or s.state != "PUBLISHED"):
        raise ValueError("INVALID_REVIEW_METADATA")
    if s.kind == "SAAS_LICENSE":
        if (s.recipient_role != "TENANT_ADMIN"
                or not _uuid(s.offer_id) or not _uuid(s.price_version_id)
                or any(v is not None for v in (s.tenant_id, s.cycle_id, s.policy_version_id))):
            raise ValueError("INVALID_LICENSE_SCOPE")
    elif s.kind == "MEMBER_ADHESION":
        if (s.recipient_role != "TENANT_MEMBER"
                or not all(_uuid(v) for v in (s.tenant_id, s.cycle_id, s.policy_version_id))
                or s.offer_id is not None or s.price_version_id is not None):
            raise ValueError("INVALID_MEMBERSHIP_SCOPE")
    else:
        raise ValueError("UNKNOWN_CONTRACT_KIND")
    # Explicit serialization: all identifiers and UTC instants are canonical.
    values = {
        "schema": "FR_FINANCE_V22_REVIEW_BINDING_V1",
        **{k: str(getattr(s,k)) if getattr(s,k) is not None else None
           for k in ("kind","document_id","version","body_sha256","issuer_id",
                     "recipient_id","recipient_role","nonce","state","offer_id",
                     "price_version_id","tenant_id","cycle_id","policy_version_id")},
        **{k: getattr(s,k).astimezone(timezone.utc).isoformat()
           for k in ("published_at","issued_at","expires_at")},
    }
    return sha256(json.dumps(values, sort_keys=True, separators=(",",":"),
                             ensure_ascii=True).encode("ascii")).hexdigest()


def review_matches(*, expected: ContractReviewSnapshot, presented_fingerprint: str,
                   body: str, now: datetime) -> bool:
    """Exact-byte and context consistency ONLY. No proof of identity or consent."""
    try:
        digest = review_fingerprint(expected)
        if (not _aware(now) or not expected.issued_at <= now < expected.expires_at
                or not _hash(presented_fingerprint) or type(body) is not str
                or not 0 < len(body) <= MAX_BYTES):
            return False
        raw = body.encode("utf-8", errors="strict")
        return (0 < len(raw) <= MAX_BYTES
                and hmac.compare_digest(sha256(raw).hexdigest(), expected.body_sha256)
                and hmac.compare_digest(digest, presented_fingerprint))
    except (ValueError, TypeError, UnicodeError, OverflowError):
        return False
