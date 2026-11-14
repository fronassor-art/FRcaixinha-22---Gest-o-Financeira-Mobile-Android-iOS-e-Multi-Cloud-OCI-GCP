"""M22300: origin guard for cookie-authenticated state-changing requests.

Bearer-token Android requests without session cookies remain available.
CORS alone does not prevent CSRF, hence strict Origin for cookie writes.
"""
from __future__ import annotations
from typing import Sequence


def allow_cookie_request(
    *,method:str,session_cookie_present:bool,origins:Sequence[str],
    allowed_origins:Sequence[str],
)->bool:
    if type(method) is not str or type(session_cookie_present) is not bool:
        return False
    if method.upper() in ("GET","HEAD","OPTIONS"):
        return True
    if not session_cookie_present:
        return True
    # A missing/duplicated/malformed/null/foreign Origin is not authorized.
    if (len(origins)!=1 or type(origins[0]) is not str
            or len(origins[0])>253
            or not origins[0]
            or origins[0]!=origins[0].strip()):
        return False
    return origins[0] in allowed_origins
