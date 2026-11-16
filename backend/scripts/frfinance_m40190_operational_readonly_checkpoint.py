#!/usr/bin/env python3
"""M40190 — operational local read-only checkpoint, independent of Android /proc.

No authentication session, POST, PID inspection, process control, DB direct
connection, migration or real finance operation. A successful HTTP checkpoint
does NOT attest process owner, git SHA, actual executed bytecode or production.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.app.m39700_runtime_contract import (
    classify_checkpoint, classify_health, classify_readiness, classify_routes,
)
from backend.scripts.frfinance_m39700_termux_runtime_check import native_termux
from backend.scripts.frfinance_m40080_loaded_source_readonly import (
    classify_marker, local_hashes,
)

HEALTH = "/api/health"
CHECKPOINT = "/api/health/checkpoint"
MARKER = "/api/health/features/m40080"
ROUTES = "/openapi.json"
READY = "/api/health/ready"
ALLOWLIST = frozenset((HEALTH, CHECKPOINT, MARKER, ROUTES, READY))
MAX_BYTES = {HEALTH: 8192, CHECKPOINT: 8192, MARKER: 8192,
             ROUTES: 2_000_000, READY: 8192}
HOST = "http://127.0.0.1:8000"


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


def safe_get(path):
    """GET a constant loopback path; suppress redirects, proxy, raw bodies."""
    if path not in ALLOWLIST:
        raise ValueError("M40190_UNAPPROVED_HTTP_PATH")
    request = Request(HOST + path, method="GET",
                      headers={"Accept": "application/json",
                               "Cache-Control": "no-store"})
    opener = build_opener(ProxyHandler({}), NoRedirect())
    try:
        with opener.open(request, timeout=4) as response:
            if response.status != 200:
                return int(response.status), None
            raw = response.read(MAX_BYTES[path] + 1)
            if len(raw) > MAX_BYTES[path]:
                return 413, None
        return 200, json.loads(raw)
    except HTTPError as exc:
        return int(exc.code), None
    except (URLError, OSError, TimeoutError):
        return 0, None
    except (ValueError, UnicodeError, TypeError):
        return 422, None


def guarded(fetch, path):
    if path not in ALLOWLIST:
        raise ValueError("M40190_UNAPPROVED_HTTP_PATH")
    try:
        value = fetch(path)
        if (type(value) is not tuple or len(value) != 2
                or type(value[0]) is not int
                or not (0 <= value[0] <= 599)):
            return 0, None
        return value
    except (OSError, ValueError, TypeError, UnicodeError, TimeoutError):
        return 0, None


def report(fetch=safe_get, hashes=local_hashes):
    result = {
        "M40190_HEALTH": "NOT_ATTESTED",
        "M40190_CHECKPOINT": "SKIPPED",
        "M40190_LOADED_SOURCE": "SKIPPED",
        "M40190_EXPECTED_GET_ROUTES": "SKIPPED",
        "M40190_TEST_AUTH_READINESS": "SKIPPED",
        "M40190_HEALTH_FINAL": "SKIPPED",
        "M40190_PROCESS_OWNER": "NOT_ATTESTED_ANDROID_OR_UNKNOWN",
        "M40190_EXECUTED_BYTECODE": "NOT_ATTESTED",
        "M40190_GIT_SHA_IN_RUNNING_PROCESS": "NOT_ATTESTED",
        "M40190_REAL_PAYMENTS": "OFF",
        "M40190_PRODUCTION": "BLOCKED",
    }
    try:
        local = hashes()
        if not isinstance(local, dict) or len(local) != 3:
            raise ValueError("M40190_LOCAL_HASH_SET_INVALID")
    except (OSError, ValueError, UnicodeError, TypeError):
        result["M40190_STATUS"] = "BLOCKED_LOCAL_SOURCE_NOT_ATTESTED"
        return result

    health_code, health = guarded(fetch, HEALTH)
    if health_code != 200 or classify_health(health) != "FR_FINANCE_ONLINE":
        result["M40190_STATUS"] = "BLOCKED_HEALTH_IDENTITY"
        return result
    result["M40190_HEALTH"] = "FR_FINANCE_ONLINE"

    checkpoint_code, checkpoint = guarded(fetch, CHECKPOINT)
    if checkpoint_code != 200 or classify_checkpoint(checkpoint) != (
            "M39700_RUNNING_CODE_LOADED"):
        result["M40190_CHECKPOINT"] = "NOT_ATTESTED"
        result["M40190_STATUS"] = "BLOCKED_RUNTIME_CONTRACT"
        return result
    result["M40190_CHECKPOINT"] = "M39700_RUNNING_CODE_LOADED"

    marker_code, marker = guarded(fetch, MARKER)
    classification = classify_marker(marker_code, marker, local)
    result["M40190_LOADED_SOURCE"] = classification
    if classification != "M40080_IMPORT_SNAPSHOT_MATCHES_LOCAL_FILES":
        result["M40190_STATUS"] = "BLOCKED_LOADED_SOURCE_UNVERIFIED"
        return result

    paths_code, paths = guarded(fetch, ROUTES)
    route_state, missing = (
        classify_routes(paths) if paths_code == 200
        else ("OPENAPI_UNAVAILABLE", ())
    )
    result["M40190_EXPECTED_GET_ROUTES"] = (
        "SIX_OF_SIX_PRESENT" if route_state == "GET_ROUTES_PRESENT"
        and not missing else "NOT_ATTESTED"
    )
    if result["M40190_EXPECTED_GET_ROUTES"] != "SIX_OF_SIX_PRESENT":
        result["M40190_STATUS"] = "BLOCKED_EXPECTED_GET_ROUTES"
        return result

    readiness_code, ready = guarded(fetch, READY)
    readiness = classify_readiness(readiness_code, ready)
    result["M40190_TEST_AUTH_READINESS"] = readiness

    final_code, final_doc = guarded(fetch, HEALTH)
    if final_code == 200 and classify_health(final_doc) == "FR_FINANCE_ONLINE":
        result["M40190_HEALTH_FINAL"] = "FR_FINANCE_ONLINE"
    else:
        result["M40190_HEALTH_FINAL"] = "NOT_ATTESTED"
        result["M40190_STATUS"] = "BLOCKED_HEALTH_CHANGED_DURING_CHECK"
        return result

    result["M40190_STATUS"] = (
        "PASS_LOCAL_READONLY_FUNCTIONAL_SMOKE"
        if readiness == "LOCAL_TEST_AUTH_READY"
        else "BLOCKED_TEST_AUTH_READINESS"
    )
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description="M40190 operational read-only checkpoint")
    parser.add_argument("--source-only", action="store_true")
    args = parser.parse_args(argv)
    print("=== FR FINANCE M40190 — LOCAL READ ONLY FUNCTIONAL SMOKE ===")
    if args.source_only:
        print("M40190_SOURCE_ONLY=PASS")
        print("M40190_RUNTIME=NOT_ATTESTED")
        return 0
    if not native_termux():
        print("M40190_STATUS=BLOCKED_NOT_NATIVE_TERMUX")
        return 2
    try:
        result = report()
        for key, value in result.items():
            print(key + "=" + value)
        return 0 if result["M40190_STATUS"] == (
            "PASS_LOCAL_READONLY_FUNCTIONAL_SMOKE") else 2
    finally:
        print("M40190_HTTP=GET_ONLY_FIXED_LOOPBACK_ALLOWLIST")
        print("M40190_HTTP_RAW_BODIES=NOT_DISCLOSED")
        print("M40190_HTTP_POST=NONE")
        print("M40190_LOGIN_SESSIONS_CREATED=NONE")
        print("M40190_PROCESS_INSPECTION=NONE")
        print("M40190_FASTAPI_START_STOP=NONE")
        print("M40190_POSTGRESQL_START_STOP=NONE")
        print("M40190_TERMINAL_SQL_SESSIONS=NONE")
        print("M40190_MIGRATIONS=NONE")
        print("M40190_PIX_REAL=OFF")
        print("M40190_PAGAMENTOS_REAIS=OFF")
        print("M40190_ATIVACAO_REAL=OFF")
        print("M40190_PRODUCTION=BLOCKED")


if __name__ == "__main__":
    raise SystemExit(main())
