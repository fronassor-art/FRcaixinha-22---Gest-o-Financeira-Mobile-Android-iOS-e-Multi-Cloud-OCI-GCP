"""M41050 laboratory primitive: bind SQL row context to a signed short-lived claim.

This is not wired into FR Finance routes or the authoritative database.
The signer key must be held outside the SQL application/issuer credentials.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
from uuid import UUID

_DOMAIN = b"FRF-M41050|v1|SESSION|"
_ROLES = frozenset(("MASTER", "TENANT_ADMIN", "TENANT_MEMBER"))
_SCOPE = "READ_ONLY"


class InvalidSessionClaims(ValueError):
    """Constant validation failure; never include claim or key values."""


@dataclass(frozen=True)
class SessionClaims:
    session_id: UUID
    user_id: UUID
    role: str
    tenant_id: UUID | None
    nonce: UUID
    expires_epoch: int
    scope: str = _SCOPE


def canonical_session_claims(claims: SessionClaims) -> bytes:
    """Return a stable, delimiter-safe canonical representation for signing."""
    if type(claims) is not SessionClaims:
        raise InvalidSessionClaims("M41050_INVALID_SESSION_CLAIMS")
    ids = (claims.session_id, claims.user_id, claims.nonce)
    if any(type(value) is not UUID or value.int == 0 for value in ids):
        raise InvalidSessionClaims("M41050_INVALID_SESSION_CLAIMS")
    if (type(claims.role) is not str or claims.role not in _ROLES
            or type(claims.scope) is not str or claims.scope != _SCOPE):
        raise InvalidSessionClaims("M41050_INVALID_SESSION_CLAIMS")
    if claims.role == "MASTER":
        if claims.tenant_id is not None:
            raise InvalidSessionClaims("M41050_INVALID_SESSION_CLAIMS")
        tenant = "-"
    else:
        if (type(claims.tenant_id) is not UUID
                or claims.tenant_id.int == 0):
            raise InvalidSessionClaims("M41050_INVALID_SESSION_CLAIMS")
        tenant = str(claims.tenant_id)
    if (type(claims.expires_epoch) is not int
            or not 0 < claims.expires_epoch < 2**63):
        raise InvalidSessionClaims("M41050_INVALID_SESSION_CLAIMS")
    fields = (
        str(claims.session_id),
        str(claims.user_id),
        claims.role,
        tenant,
        str(claims.nonce),
        str(claims.expires_epoch),
        claims.scope,
    )
    try:
        return _DOMAIN + "|".join(fields).encode("ascii")
    except (UnicodeEncodeError, AttributeError):
        raise InvalidSessionClaims("M41050_INVALID_SESSION_CLAIMS") from None


def make_session_proof(*, key: bytes, claims: SessionClaims) -> bytes:
    """Create the test/prototype proof outside PostgreSQL; never log the key."""
    if type(key) is not bytes or len(key) != 32:
        raise InvalidSessionClaims("M41050_INVALID_SESSION_PROOF")
    return hmac.new(
        key, canonical_session_claims(claims), hashlib.sha256
    ).digest()
