"""FR Finance M40610: source-only proof-of-session guard before RLS pool access.

A verified backend session is required, not merely a role or tenant claim.
This does NOT cryptographically authenticate PostgreSQL custom GUC values.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID


class UnverifiedRLSSession(ValueError):
    """Intentionally generic: never leak session identifiers or claims."""


def _valid_uuid(text: object) -> bool:
    if not isinstance(text, str):
        return False
    try:
        value = UUID(text)
    except (ValueError, AttributeError, TypeError):
        return False
    return value.int != 0 and str(value) == text


def require_verified_rls_session(session: object, *, now: datetime | None = None) -> None:
    """Fail closed before opening *any* RLS financial connection.

    Proof fields originate from get_current_session after PostgreSQL token-hash
    lookup, active membership check, revocation/expiry and refresh. This function
    checks integrity/shape only: it is NOT independent database attestation.
    """
    now = datetime.now(timezone.utc) if now is None else now
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise UnverifiedRLSSession("UNVERIFIED_RLS_SESSION")

    if (getattr(session, "verification_source", None) != "POSTGRES_TOKEN_HASH_REFRESH"
            or not _valid_uuid(getattr(session, "verified_session_id", None))
            or not _valid_uuid(getattr(session, "user_id", None))):
        raise UnverifiedRLSSession("UNVERIFIED_RLS_SESSION")

    at = getattr(session, "verified_session_at", None)
    expires = getattr(session, "verified_session_expires_at", None)
    if (not isinstance(at, datetime) or at.tzinfo is None
            or at.utcoffset() is None
            or not isinstance(expires, datetime) or expires.tzinfo is None
            or expires.utcoffset() is None or at > now + timedelta(seconds=5)
            or expires <= now or expires <= at):
        raise UnverifiedRLSSession("UNVERIFIED_RLS_SESSION")

    role = getattr(session, "role", None)
    tenant = getattr(session, "tenant_id", None)
    is_master = getattr(session, "is_master", None)
    if role == "MASTER":
        if is_master is not True or tenant is not None:
            raise UnverifiedRLSSession("UNVERIFIED_RLS_SESSION")
    elif role in ("TENANT_ADMIN", "TENANT_MEMBER"):
        if is_master is not False or not _valid_uuid(tenant):
            raise UnverifiedRLSSession("UNVERIFIED_RLS_SESSION")
    else:
        raise UnverifiedRLSSession("UNVERIFIED_RLS_SESSION")
