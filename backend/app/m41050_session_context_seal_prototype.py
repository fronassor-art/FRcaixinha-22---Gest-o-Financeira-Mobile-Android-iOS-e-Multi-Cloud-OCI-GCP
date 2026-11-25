"""M41050 lab helper for a ticket-bound PostgreSQL session capability.

Not wired into FR Finance routes or the authoritative database. The opaque
capability is issued by the disposable SQL fixture after a signed one-use
M40700 ticket is consumed; it is not a user-supplied identity claim.
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


async def install_session_capability(connection: object, value: object) -> None:
    """Bind the capability transaction-locally using asyncpg parameters."""
    capability = validate_session_capability(value)
    execute = getattr(connection, "execute", None)
    if not callable(execute):
        raise InvalidSessionCapability("M41050_INVALID_SESSION_CAPABILITY")
    result = execute(_SETTING_SQL, capability)
    if not inspect.isawaitable(result):
        raise InvalidSessionCapability("M41050_INVALID_SESSION_CAPABILITY")
    await result
