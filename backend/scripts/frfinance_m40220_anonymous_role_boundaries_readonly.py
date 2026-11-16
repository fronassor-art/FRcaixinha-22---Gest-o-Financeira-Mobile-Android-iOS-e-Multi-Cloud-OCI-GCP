#!/usr/bin/env python3
"""M40220: public HTTP anonymous-denial smoke of *existing* FR Finance routes.

Never sends authentication cookies, tokens, POSTs or SQL. Never reads body
of protected endpoints; checks only HTTP 401, with no proxy or redirects.
M40190 and M40210 must pass first. An anonymous denial is NOT authenticated
RBAC/RLS proof and never grants permission for live finance operations.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, ProxyHandler, build_opener

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.app.m39700_runtime_contract import classify_health
from backend.scripts.frfinance_m39700_termux_runtime_check import native_termux
from backend.scripts.frfinance_m40190_operational_readonly_checkpoint import (
    HEALTH, HOST, NoRedirect, guarded, report as operational_report, safe_get,
)
from backend.scripts.frfinance_m40210_hidden_route_openapi_correction import (
    hidden_source_check,
)

TENANT_SENTINEL = "00000000-0000-4000-8000-000000000000"
TENANT_PATH = "/api/v1/tenants/" + TENANT_SENTINEL
CREDIT_PATH = TENANT_PATH + "/special-credit"

# Fixed public-local routing probes; synthetic tenant UUID is NOT a real member.
# These paths are verified to be access-protected by the sources and CI.
PROBES = {
    "MASTER_HIDDEN_REVIEW": "/api/v1/master/exclusive-cashbox/review-policy-gaps",
    "ADMIN_HIDDEN_REVIEW": TENANT_PATH + "/admin-exclusive-cashbox/review-policy-gaps",
    "MASTER_CASHBOX": "/api/v1/master/exclusive-cashbox",
    "ADMIN_CASHBOX": TENANT_PATH + "/admin-exclusive-cashbox",
    "ADMIN_MEMBERS": TENANT_PATH + "/members",
    "TENANT_DASHBOARD": TENANT_PATH + "/dashboard",
    "ADMIN_CREDIT_GRANTS": CREDIT_PATH + "/grants",
    "ADMIN_CREDIT_CAMPAIGNS": CREDIT_PATH + "/campaigns",
    "MEMBER_OPPORTUNITIES": CREDIT_PATH + "/opportunities",
    "MEMBER_CONTRACTS": TENANT_PATH + "/my-contracts",
    "AUTHENTICATED_PROFILE": "/api/v1/auth/me",
    "MEMBER_INBOX": "/api/v1/notifications",
}
ALLOWED = frozenset(PROBES.values())


def anonymous_http_status(path):
    """A pure unauthenticated GET: never inspect body, secrets or process."""
    if path not in ALLOWED:
        raise ValueError("M40220_HTTP_TARGET_NOT_ALLOWLISTED")
    req = Request(HOST + path, method="GET", headers={
        "Accept": "application/json", "Cache-Control": "no-store",
    })
    opener = build_opener(ProxyHandler({}), NoRedirect())
    try:
        with opener.open(req, timeout=3) as response:
            return int(response.status)
    except HTTPError as exc:
        try:
            return int(exc.code)
        finally:
            exc.close()
    except (URLError, TimeoutError, OSError, ValueError):
        return 0


def guarded_status(fetch, path):
    if path not in ALLOWED:
        raise ValueError("M40220_UNAUTHORIZED_TARGET")
    try:
        status = fetch(path)
        return status if type(status) is int and 0 <= status <= 599 else 0
    except (OSError, ValueError, TypeError, TimeoutError):
        return 0


def anonymous_guard_source(path=None):
    """Static precondition: absent bearer/cookie is rejected BEFORE auth SQL."""
    if path is None:
        path = ROOT / "backend/app/dependencies.py"
    try:
        if path.is_symlink() or not path.is_file():
            return "BLOCKED_AUTH_SOURCE_UNAVAILABLE"
        source = path.read_text(encoding="utf-8")
        start = source.index("async def get_current_session(")
        end = source.index("\n\ndef require_master(", start)
        session = source[start:end]
        token = session.index("raw_token = bearer_token(request)")
        connect = session.index("await asyncpg.connect(")
        if token >= connect:
            return "BLOCKED_AUTH_LOOKUP_BEFORE_TOKEN"
        bearer_start = source.index("def bearer_token(")
        bearer_end = source.index("\n\nasync def get_current_session(", bearer_start)
        bearer = source[bearer_start:bearer_end]
        if not ("raise HTTPException(status_code=401" in bearer
                and "Authorization" in bearer and "request.cookies" in bearer):
            return "BLOCKED_ANONYMOUS_DENIAL_NOT_FOUND"
        return "PASS_NO_TOKEN_REJECTED_BEFORE_DB"
    except (OSError, ValueError, UnicodeError):
        return "BLOCKED_AUTH_SOURCE_UNVERIFIED"


def report(preflight=operational_report, hidden=hidden_source_check,
           auth=anonymous_guard_source, fetch=anonymous_http_status,
           health_fetch=safe_get):
    out = {
        "M40220_OPERATIONAL_GATE": "NOT_ATTESTED",
        "M40220_HIDDEN_ROUTER_GUARD": "NOT_ATTESTED",
        "M40220_ANONYMOUS_SOURCE_GUARD": "NOT_ATTESTED",
        "M40220_EXPECTED_ANONYMOUS_401": str(len(PROBES)),
        "M40220_ANONYMOUS_401_COUNT": "NOT_ATTESTED",
        "M40220_LIVE_ROLE_RBAC": "NOT_TESTED",
        "M40220_POSTGRESQL_RLS": "NOT_TESTED",
        "M40220_MEMBER_SESSIONS": "NOT_CREATED_BY_THIS_PROBE",
        "M40220_REAL_REVIEW_APPROVAL": "FALSE",
        "M40220_PRODUCTION": "BLOCKED",
    }
    if preflight().get("M40190_STATUS") != "PASS_LOCAL_READONLY_FUNCTIONAL_SMOKE":
        out["M40220_STATUS"] = "BLOCKED_M40190_READINESS"
        return out
    out["M40220_OPERATIONAL_GATE"] = "PASS_M40190"
    state = hidden()
    out["M40220_HIDDEN_ROUTER_GUARD"] = state
    if state != "PASS_TWO_HIDDEN_SOURCE_DECLARATIONS_NOT_RUNTIME_TESTED":
        out["M40220_STATUS"] = "BLOCKED_HIDDEN_ROUTE_SOURCE"
        return out
    gate = auth()
    out["M40220_ANONYMOUS_SOURCE_GUARD"] = gate
    if gate != "PASS_NO_TOKEN_REJECTED_BEFORE_DB":
        out["M40220_STATUS"] = "BLOCKED_SESSION_GUARD_SOURCE"
        return out

    passed = 0
    for name, path in PROBES.items():
        status = guarded_status(fetch, path)
        if status == 401:
            out["M40220_" + name] = "HTTP_401_ANONYMOUS_DENIED"
            passed += 1
        else:
            # No response payload or data ever returned; fail at first error.
            out["M40220_" + name] = "BLOCKED_EXPECTED_401_GOT_" + str(status)
            out["M40220_ANONYMOUS_401_COUNT"] = str(passed)
            out["M40220_STATUS"] = "BLOCKED_ANONYMOUS_ROUTE_GUARD"
            return out
    out["M40220_ANONYMOUS_401_COUNT"] = str(passed)
    last_code, last_doc = guarded(health_fetch, HEALTH)
    if last_code != 200 or classify_health(last_doc) != "FR_FINANCE_ONLINE":
        out["M40220_STATUS"] = "BLOCKED_HEALTH_CHANGED"
    else:
        out["M40220_STATUS"] = "PASS_ANONYMOUS_401_BOUNDARIES_ONLY"
    return out


def main(argv=None):
    p = argparse.ArgumentParser(description="M40220 anonymous access 401 smoke")
    p.add_argument("--source-only", action="store_true")
    args = p.parse_args(argv)
    print("=== FR FINANCE M40220 — ANONYMOUS ROLE BOUNDARIES READ ONLY ===")
    if args.source_only:
        state = anonymous_guard_source()
        print("M40220_SOURCE_ONLY=" + state)
        print("M40220_LIVE_ENDPOINTS=NOT_QUERIED")
        return 0 if state == "PASS_NO_TOKEN_REJECTED_BEFORE_DB" else 2
    if not native_termux():
        print("M40220_STATUS=BLOCKED_NOT_NATIVE_TERMUX")
        return 2
    try:
        outcome = report()
        for key, val in outcome.items():
            print(key + "=" + val)
        return 0 if outcome["M40220_STATUS"] == (
            "PASS_ANONYMOUS_401_BOUNDARIES_ONLY") else 2
    finally:
        print("M40220_HTTP=GET_ONLY_LOOPBACK_WITHOUT_AUTH_OR_COOKIES")
        print("M40220_PROTECTED_RESPONSE_BODIES=NOT_READ")
        print("M40220_POST_REQUESTS=NONE")
        print("M40220_REAL_LOGIN=NONE")
        print("M40220_SQL_DIRECT=NONE")
        print("M40220_DATABASE_WRITES_BY_TERMINAL=NONE")
        print("M40220_MIGRATIONS=NONE")
        print("M40220_FASTAPI_RESTART=NONE")
        print("M40220_POSTGRESQL_RESTART=NONE")
        print("M40220_PIX_REAL=OFF")
        print("M40220_PAGAMENTOS_REAIS=OFF")
        print("M40220_ATIVACAO_REAL=OFF")
        print("M40220_PRODUCTION=BLOCKED")


if __name__ == "__main__":
    raise SystemExit(main())
