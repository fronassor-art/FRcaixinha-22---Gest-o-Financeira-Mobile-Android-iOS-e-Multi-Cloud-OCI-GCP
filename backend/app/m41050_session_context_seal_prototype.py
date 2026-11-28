"""M41050 lab helper for a ticket-bound PostgreSQL session capability.

Not wired into FR Finance routes or the authoritative database. M41070 tightens
the prototype so the opaque capability is installed only inside the active
asyncpg transaction and only after PostgreSQL confirms the bound value.
"""
from __future__ import annotations

import inspect
import re

_CAPABILITY = re.compile(r"[0-9a-f]{64}\Z")
_SETTING_SQL = (
    "SELECT pg_catalog.set_config('app.session_capability', $1, true)"
)


class InvalidSessionCapability(ValueError):
    """Constant failure that does not include capability contents."""


def validate_session_capability(value: object) -> str:
    """Accept only the opaque lowercase 256-bit hex form returned by SQL."""
    if type(value) is not str or _CAPABILITY.fullmatch(value) is None:
        raise InvalidSessionCapability("M41050_INVALID_SESSION_CAPABILITY")
    return value


def _require_active_transaction(connection: object) -> None:
    checker = getattr(connection, "is_in_transaction", None)
    if not callable(checker):
        raise InvalidSessionCapability("M41050_INVALID_SESSION_CAPABILITY")
    try:
        active = checker()
    except Exception:
        raise InvalidSessionCapability(
            "M41050_INVALID_SESSION_CAPABILITY"
        ) from None
    if inspect.isawaitable(active):
        close = getattr(active, "close", None)
        if callable(close):
            close()
        raise InvalidSessionCapability("M41050_INVALID_SESSION_CAPABILITY")
    if active is not True:
        raise InvalidSessionCapability("M41050_INVALID_SESSION_CAPABILITY")


async def install_session_capability(connection: object, value: object) -> None:
    """Bind a SQL-issued capability and prove it stayed transaction-local."""
    capability = validate_session_capability(value)
    _require_active_transaction(connection)

    fetchval = getattr(connection, "fetchval", None)
    if not callable(fetchval):
        raise InvalidSessionCapability("M41050_INVALID_SESSION_CAPABILITY")
    result = fetchval(_SETTING_SQL, capability)
    if not inspect.isawaitable(result):
        raise InvalidSessionCapability("M41050_INVALID_SESSION_CAPABILITY")

    bound_value = await result
    _require_active_transaction(connection)
    if bound_value != capability:
        raise InvalidSessionCapability("M41050_INVALID_SESSION_CAPABILITY")
