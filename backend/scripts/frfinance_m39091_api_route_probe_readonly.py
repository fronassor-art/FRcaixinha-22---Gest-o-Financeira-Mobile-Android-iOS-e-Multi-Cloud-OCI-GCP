#!/usr/bin/env python3
"""FR Finance M39091 — diagnostic GET-only on localhost without credentials.

Use in NATIVE TERMUX: python3 -B backend/scripts/frfinance_m39091_api_route_probe_readonly.py
No DB driver, shell process control, bearer, secrets, migrations or writes.
A FastAPI endpoint existing in Git does not prove the running process is current.
"""
from __future__ import annotations

import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
EXPECTED = {
    "/api/v1/tenants/{tenant_id}/special-credit/capabilities",
    "/api/v1/tenants/{tenant_id}/special-credit/members",
    "/api/v1/tenants/{tenant_id}/special-credit/campaigns",
    "/api/v1/tenants/{tenant_id}/special-credit/cycle-readiness",
    "/api/v1/master/exclusive-cashbox",
    "/api/v1/tenants/{tenant_id}/admin-exclusive-cashbox",
}


def source_route_presence() -> bool:
    credit = (ROOT / "backend/app/routers/special_credit.py").read_text()
    main = (ROOT / "backend/app/main.py").read_text()
    cashboxes = (ROOT / "backend/app/routers/exclusive_cashboxes.py").read_text()
    return all((
        'prefix="/tenants/{tenant_id}/special-credit"' in credit,
        '@router.get("/capabilities")' in credit,
        '@router.get("/cycle-readiness")' in credit,
        'app.include_router(_special_credit.router' in main,
        'app.include_router(_exclusive_cashboxes.master_router' in main,
        'app.include_router(_exclusive_cashboxes.tenant_router' in main,
        '@master_router.get("/exclusive-cashbox")' in cashboxes,
        '@tenant_router.get("/admin-exclusive-cashbox")' in cashboxes,
    ))


def inspect_local_openapi() -> tuple[str, set[str]]:
    request = Request(
        "http://127.0.0.1:8000/openapi.json",
        headers={"Accept": "application/json", "Cache-Control": "no-store"},
        method="GET",
    )
    try:
        with urlopen(request, timeout=3) as reply:
            if reply.status != 200:
                return "UNEXPECTED_HTTP", set()
            # Limit response; never print body or private endpoint metadata.
            payload = reply.read(1_000_001)
            if len(payload) > 1_000_000:
                return "OVERSIZED_RESPONSE", set()
        document = json.loads(payload)
        if not isinstance(document, dict) or not isinstance(document.get("paths"), dict):
            return "INVALID_OPENAPI", set()
        # Only GET endpoints are valid for these read-only capabilities.
        # A route with the correct name but only POST is not accepted.
        expected_get = {
            path for path, operations in document["paths"].items()
            if isinstance(path, str) and isinstance(operations, dict)
            and isinstance(operations.get("get"), dict)
        }
        return "OPENAPI_READY", expected_get
    except HTTPError as exc:
        return f"OPENAPI_HTTP_{exc.code}", set()
    except (URLError, TimeoutError, OSError):
        return "LOOPBACK_NOT_REACHABLE", set()
    except (ValueError, UnicodeDecodeError, TypeError):
        return "INVALID_OPENAPI", set()



def inspect_local_health() -> str:
    """Check the running service identity; never return the body or secrets."""
    request = Request(
        "http://127.0.0.1:8000/api/health",
        headers={"Accept": "application/json", "Cache-Control": "no-store"},
        method="GET",
    )
    try:
        with urlopen(request, timeout=3) as reply:
            if reply.status != 200:
                return "HEALTH_NOT_200"
            body = reply.read(4097)
            if len(body) > 4096:
                return "HEALTH_TOO_LARGE"
        result = json.loads(body)
        if (isinstance(result, dict)
                and result.get("app") == "FR Finance"
                and result.get("status") == "ONLINE"):
            return "FR_FINANCE_API_CONFIRMED"
        return "HEALTH_DIFFERENT_APP_OR_VERSION"
    except HTTPError:
        return "HEALTH_HTTP_ERROR"
    except (URLError, TimeoutError, OSError):
        return "HEALTH_BACKEND_UNREACHABLE"
    except (ValueError, UnicodeDecodeError, TypeError):
        return "HEALTH_INVALID_JSON"


def main() -> int:
    print("=== FR FINANCE M39091 — ROTEADOR LOCAL READ ONLY ===")
    if not source_route_presence():
        print("M39091_GIT_SOURCE=ROUTE_DRIFT")
        return 2
    print("M39091_GIT_SOURCE=EXPECTED_ROUTES_PRESENT")
    status, paths = inspect_local_openapi()
    print("M39091_LOCAL_SERVER=" + status)
    verified = False
    if status == "OPENAPI_READY":
        missing = sorted(EXPECTED - paths)
        if missing:
            print("M39091_SERVER_ROUTE_STATE=STALE_OR_DIFFERENT_APP")
            print("M39091_MISSING_ROUTE_COUNT=" + str(len(missing)))
            # Only static route templates; never leak tenant identifiers.
            for path in missing:
                print("M39091_EXPECTED_MISSING=" + path)
        else:
            health = inspect_local_health()
            print("M39091_HEALTH_IDENTITY=" + health)
            if health == "FR_FINANCE_API_CONFIRMED":
                print("M39091_SERVER_ROUTE_STATE=ROUTES_PRESENT")
                print("M39091_HINT=CHECK_401_403_503_OR_RUNTIME_DB_GATES")
                verified = True
            else:
                print("M39091_SERVER_ROUTE_STATE=APP_IDENTITY_UNVERIFIED")
    elif status == "LOOPBACK_NOT_REACHABLE":
        print("M39091_SERVER_ROUTE_STATE=BACKEND_NOT_REACHABLE")
    else:
        print("M39091_SERVER_ROUTE_STATE=INCONCLUSIVE_DO_NOT_CHANGE_DB")
    print("M39091_HTTP_METHOD=GET_OPENAPI_AND_HEALTH_ONLY")
    print("M39091_DATABASE_QUERIES=NONE")
    print("M39091_DATABASE_WRITES=NONE")
    print("M39091_MIGRATIONS=NONE")
    print("M39091_PIX_REAL=OFF")
    print("M39091_STATUS=" + ("PASS_READ_ONLY" if verified else "BLOCKED_READ_ONLY"))
    return 0 if verified else 2


if __name__ == "__main__":
    raise SystemExit(main())
