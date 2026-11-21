"""M40810: offline authentication input gate, NOT session verification.

Rejects header ambiguity, unexpected whitespace, non-URL-safe token chars,
and unbounded strings before any token digest or SQL authorization.
"""
from __future__ import annotations

import re

URLSAFE_BEARER = re.compile(r"[A-Za-z0-9_-]{1,256}\Z", re.ASCII)

class BearerInputBlocked(ValueError):
    """Generic failure; do not echo cookie or Authorization input."""

def strict_bearer_candidate(
    authorization_headers: object, cookie_candidate: object,
) -> str:
    if type(authorization_headers) not in (list, tuple):
        raise BearerInputBlocked("INVALID_CREDENTIAL_SOURCE")
    if len(authorization_headers) > 1:
        raise BearerInputBlocked("AMBIGUOUS_AUTHORIZATION")
    if len(authorization_headers) == 1:
        header = authorization_headers[0]
        if type(header) is not str or not header.startswith("Bearer "):
            raise BearerInputBlocked("INVALID_AUTHORIZATION")
        token = header[7:]
    else:
        token = cookie_candidate
    if type(token) is not str or not URLSAFE_BEARER.fullmatch(token):
        raise BearerInputBlocked("INVALID_CREDENTIAL_TOKEN")
    return token
