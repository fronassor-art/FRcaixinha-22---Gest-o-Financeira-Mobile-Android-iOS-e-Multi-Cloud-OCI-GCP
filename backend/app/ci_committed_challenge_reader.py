"""M27600 — disposable PostgreSQL-only challenge attestation adapter.

A readback is accepted solely through an authenticated *CI attestor*
connection and a restricted SECURITY DEFINER function. This is NOT a
production identity proof, not a public API and not permission to send.
"""
from __future__ import annotations

import json
import os
from uuid import UUID

from .committed_challenge_handoff import SyntheticChallengeReadback


class CiReadbackBlocked(ValueError):
    """No token, email, digest or connection string is printed in errors."""


_REQUIRED = frozenset({
    "tenant_id", "event_id", "document_id", "outbox_id",
    "challenge_digest", "issued_at", "expires_at", "failed_attempts",
    "consumed", "challenge_status", "outbox_status", "terminal_quarantine",
})


def _deny() -> CiReadbackBlocked:
    return CiReadbackBlocked("M27600_DISPOSABLE_READBACK_BLOCKED")


def _strict_pairs(items):
    result = {}
    for k, v in items:
        if k in result:
            raise _deny()
        result[k] = v
    return result


def _uuid(value):
    if type(value) is not str:
        raise _deny()
    try:
        result = UUID(value)
    except (ValueError, AttributeError, TypeError):
        raise _deny() from None
    if str(result) != value or result.int == 0:
        raise _deny()
    return result


def _parse_readback(value, event_id: UUID):
    # This parser alone does NOT establish DB provenance; the caller checks
    # connection identity and uses only a trusted result of the SQL function.
    if type(value) is str:
        if len(value) > 2048:
            raise _deny()
        try:
            value = json.loads(value, object_pairs_hook=_strict_pairs)
        except (ValueError, TypeError):
            raise _deny() from None
    if type(value) is not dict or set(value) != _REQUIRED:
        raise _deny()
    if value["event_id"] != str(event_id):
        raise _deny()
    for col in ("issued_at", "expires_at", "failed_attempts"):
        if type(value[col]) is not int:
            raise _deny()
    if (value["failed_attempts"] != 0
            or not (1_600_000_000 <= value["issued_at"]
                    < value["expires_at"] <= 9_999_999_999)
            or value["consumed"] is not False
            or value["terminal_quarantine"] is not False
            or value["challenge_status"] != "CI_CHALLENGE_NOT_DELIVERED"
            or value["outbox_status"] != "HELD_CI_NOT_SENT"
            or type(value["challenge_digest"]) is not str
            or len(value["challenge_digest"]) != 64
            or any(c not in "0123456789abcdef" for c in value["challenge_digest"])):
        raise _deny()
    return SyntheticChallengeReadback(
        tenant_id=_uuid(value["tenant_id"]),
        event_id=_uuid(value["event_id"]),
        document_id=_uuid(value["document_id"]),
        outbox_id=_uuid(value["outbox_id"]),
        challenge_digest=value["challenge_digest"],
        issued_at=value["issued_at"],
        expires_at=value["expires_at"],
        failed_attempts=0, consumed=False,
        challenge_status="CI_CHALLENGE_NOT_DELIVERED",
        outbox_status="HELD_CI_NOT_SENT",
        terminal_quarantine=False,
        source="DISPOSABLE_POSTGRESQL_CI_READBACK",
    )


async def read_committed_ci_challenge(*, connection, event_id: UUID,
                                      lease_id: UUID) -> SyntheticChallengeReadback:
    """Require live authenticated CI database connection, then strict parse.

    The postcommit readback must be executed in a *new* connection after the
    producer's transaction commits. The caller must not share its session,
    transaction or role with the producer.
    """
    if (os.getenv("GITHUB_ACTIONS") != "true"
            or os.getenv("FRCAIXINHA_CI_ISOLATED") != "1"
            or type(event_id) is not UUID or event_id.int == 0
            or type(lease_id) is not UUID or lease_id.int == 0):
        raise _deny()
    try:
        identity = await connection.fetchrow(
            "SELECT current_database() AS db, session_user AS login_role, "
            "inet_server_port() AS pg_port"
        )
        if (identity is None or identity["db"] != "frcaixinha_staging"
                or identity["login_role"] != "frcaixinha_email_attestor_ci"
                or identity["pg_port"] != 5432):
            raise _deny()
        result = await connection.fetchval(
            "SELECT public.invite_challenge_readback_staging_ci("
            "$1::uuid,$2::uuid)", event_id, lease_id,
        )
        if result is None:
            raise _deny()
        return _parse_readback(result, event_id)
    except Exception:
        raise _deny() from None
