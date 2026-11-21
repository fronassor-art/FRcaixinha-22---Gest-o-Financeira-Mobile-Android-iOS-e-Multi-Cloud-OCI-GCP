#!/usr/bin/env python3
"""M39700: one read-only local FastAPI runtime & auth-readiness probe.

Run exclusively in original NATIVE TERMUX. Does not print secrets, DSNs,
response bodies, usernames, tokens or process arguments. No POST or shell
control. The /api/health/ready handler itself makes read-only DB metadata
queries; this script does not authenticate to PostgreSQL.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.app.m39700_runtime_contract import (
    CONTRACT, classify_checkpoint, classify_health,
    classify_readiness, classify_routes,
)

BASE = "http://127.0.0.1:8000"
PATHS = (
    "/api/health",
    "/api/health/checkpoint",
    "/openapi.json",
    "/api/health/ready",
)
MAX_BYTES = {
    "/api/health": 8192,
    "/api/health/checkpoint": 8192,
    "/openapi.json": 2_000_000,
    "/api/health/ready": 8192,
}


def source_loaded() -> bool:
    """Checks only the local Git checkout, not the running Python process."""
    main = ROOT / "backend/app/main.py"
    contract = ROOT / "backend/app/m39700_runtime_contract.py"
    if not main.is_file() or not contract.is_file() or main.is_symlink():
        return False
    try:
        text = main.read_text(encoding="utf-8")
        return (
            '@app.get("/api/health/checkpoint", include_in_schema=False)'
            in text
            and "def m39700_loaded_runtime_checkpoint():" in text
            and CONTRACT == "FR_FINANCE_M39700_RUNTIME_V1"
        )
    except (OSError, UnicodeError):
        return False


def native_termux() -> bool:
    """Hard stop against wrong checkout/Debian/FR Caixinha 2.2."""
    return (
        os.environ.get("PREFIX") == "/data/data/com.termux/files/usr"
        and str(Path.home()) == "/data/data/com.termux/files/home"
        and ROOT == Path.home() / "fr-finance"
        and not ROOT.is_symlink()
    )


def read_json_loopback(path: str) -> tuple[int, object]:
    """Only four constant GET paths. Errors classified without response leak."""
    if path not in PATHS:
        raise ValueError("M39700_NON_ALLOWLISTED_READ")
    request = Request(
        BASE + path,
        headers={"Accept": "application/json", "Cache-Control": "no-store"},
        method="GET",
    )
    try:
        with urlopen(request, timeout=4) as response:
            status = int(response.status)
            if status != 200:
                return status, None
            limit = MAX_BYTES[path]
            raw = response.read(limit + 1)
            if len(raw) > limit:
                return 413, None
        return 200, json.loads(raw)
    except HTTPError as exc:
        return int(exc.code), None
    except (URLError, TimeoutError, OSError):
        return 0, None
    except (ValueError, UnicodeDecodeError, TypeError):
        return 422, None


def review_runtime(fetch=read_json_loopback) -> dict[str, str]:
    """All statuses derived only from fixed strings; never return JSON bodies."""
    health_status, health = fetch(PATHS[0])
    checkpoint_status, checkpoint = fetch(PATHS[1])
    openapi_status, openapi = fetch(PATHS[2])
    # Never call a readiness route of an unidentified/wrong application.
    # It might point to the independent FR Caixinha 2.2 database.
    h = (classify_health(health) if health_status == 200
         else "HEALTH_HTTP_" + str(health_status))
    c = (classify_checkpoint(checkpoint) if checkpoint_status == 200
         else ("STALE_OR_NOT_LOADED" if checkpoint_status == 404
               else "CHECKPOINT_HTTP_" + str(checkpoint_status)))
    if openapi_status == 200:
        r, missing = classify_routes(openapi)
    else:
        r, missing = "OPENAPI_HTTP_" + str(openapi_status), ()
    identity_safe = (
        h == "FR_FINANCE_ONLINE"
        and c == "M39700_RUNNING_CODE_LOADED"
        and r == "GET_ROUTES_PRESENT"
    )
    if identity_safe:
        ready_status, ready = fetch(PATHS[3])
        a = classify_readiness(ready_status, ready)
    else:
        a = "SKIPPED_UNVERIFIED_RUNNING_APP"

    if (h == "FR_FINANCE_ONLINE"
            and c == "M39700_RUNNING_CODE_LOADED"
            and r == "GET_ROUTES_PRESENT"
            and a == "LOCAL_TEST_AUTH_READY"):
        state = "PASS_READ_ONLY_RUNTIME_AND_TEST_AUTH"
    elif (h == "FR_FINANCE_ONLINE"
          and c == "M39700_RUNNING_CODE_LOADED"
          and r == "GET_ROUTES_PRESENT"):
        state = "BLOCKED_AUTH_OR_DB_READINESS"
    else:
        state = "BLOCKED_RUNNING_API_OR_VERSION"
    return {
        "M39700_HEALTH": h,
        "M39700_LOADED_CODE": c,
        "M39700_GET_ROUTES": r,
        "M39700_MISSING_GET_ROUTES_COUNT": str(len(missing)),
        "M39700_AUTH_READINESS": a,
        "M39700_STATUS": state,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="M39700 local read-only API check")
    parser.add_argument("--source-only", action="store_true",
                        help="offline proof of source presence only, not API")
    args = parser.parse_args(argv)
    print("=== FR FINANCE M39700 — FASTAPI NATIVE READ ONLY ===")
    try:
        if not source_loaded():
            print("M39700_STATUS=BLOCKED_LOCAL_SOURCE_MISSING")
            return 2
        print("M39700_GIT_SOURCE=M39700_CODE_PRESENT")
        if args.source_only:
            print("M39700_STATUS=PASS_SOURCE_ONLY_NO_RUNTIME_ATTESTATION")
            return 0
        if not native_termux():
            print("M39700_STATUS=BLOCKED_NOT_NATIVE_TERMUX_PROJECT")
            return 2
        report = review_runtime()
        for key, val in report.items():
            print(key + "=" + val)
        return 0 if report["M39700_STATUS"] == (
            "PASS_READ_ONLY_RUNTIME_AND_TEST_AUTH") else 2
    finally:
        print("M39700_REQUESTS=GET_LOOPBACK_ONLY")
        print("M39700_HTTP_POST=NONE")
        print("M39700_TERMINAL_DB_CREDENTIALS=NONE")
        print("M39700_DIRECT_DB_CONNECTIONS=NONE")
        print("M39700_SERVER_READINESS=INTERNAL_READ_ONLY_CHECK")
        print("M39700_DB_WRITES=NONE")
        print("M39700_MIGRATIONS=NONE")
        print("M39700_FASTAPI_RESTART=NONE")
        print("M39700_REAL_PAYMENTS=OFF")
        print("M39700_PIX_REAL=OFF")
        print("M39700_PRODUCTION=BLOCKED")


if __name__ == "__main__":
    raise SystemExit(main())
