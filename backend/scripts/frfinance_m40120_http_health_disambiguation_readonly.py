#!/usr/bin/env python3
"""FR Finance M40120 — bounded HTTP-only health disambiguation on native Termux.

No process inspection, service control, database access or credentials. HTTP
requests use the existing M40090 loopback-only allowlist and no-redirect client.
HTTP identity is not proof of the loaded code, listener owner or production.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.app.m39700_runtime_contract import classify_health
from backend.scripts.frfinance_m39700_termux_runtime_check import native_termux
from backend.scripts.frfinance_m40090_old_fastapi_diagnosis import (
    HEALTH, CHECKPOINT, MARKER, fetch_json,
)
from backend.scripts.frfinance_m40100_safe_runtime_triage import status_class

ENDPOINTS = frozenset((HEALTH, CHECKPOINT, MARKER))
VALID_IDENTITY = "FR_FINANCE_ONLINE"


def guarded_get(fetch, path):
    """Return bounded legacy HTTP result, never raw bodies or exception text."""
    if path not in ENDPOINTS:
        raise ValueError("M40120_ENDPOINT_NOT_ALLOWLISTED")
    try:
        result = fetch(path)
        if type(result) is not tuple or len(result) != 2:
            return 0, None
        status, document = result
        if type(status) is not int or not (0 <= status <= 599):
            return 0, None
        return status, document
    except (OSError, ValueError, TimeoutError, TypeError, UnicodeError):
        return 0, None


def identity(code, body):
    return (VALID_IDENTITY if code == 200 and
            classify_health(body) == VALID_IDENTITY else "NOT_ATTESTED")


def unavailable(code):
    if code == 0:
        return "BLOCKED_HEALTH_NO_RESPONSE"
    if code == 404:
        return "BLOCKED_HEALTH_ROUTE_NOT_FOUND"
    if code in (401, 403):
        return "BLOCKED_HEALTH_ACCESS_RESTRICTED"
    if code in (500, 502, 503, 504):
        return "BLOCKED_HEALTH_SERVER_ERROR"
    return "BLOCKED_HEALTH_HTTP_UNVERIFIED"


def report(fetch=fetch_json):
    """Two health probes first, optional marker probes, third health fence.

    Never inspects ps, lsof, /proc, PostgreSQL or original API credentials.
    A healthy response still leaves process ownership and loaded code unknown.
    """
    first_code, first_doc = guarded_get(fetch, HEALTH)
    second_code, second_doc = guarded_get(fetch, HEALTH)
    first_identity = identity(first_code, first_doc)
    second_identity = identity(second_code, second_doc)
    outcome = {
        "M40120_HEALTH_FIRST_HTTP": status_class(first_code),
        "M40120_HEALTH_SECOND_HTTP": status_class(second_code),
        "M40120_HEALTH_FIRST_IDENTITY": first_identity,
        "M40120_HEALTH_SECOND_IDENTITY": second_identity,
        "M40120_CHECKPOINT_HTTP": "SKIPPED_UNVERIFIED_HEALTH",
        "M40120_MARKER_HTTP": "SKIPPED_UNVERIFIED_HEALTH",
        "M40120_HEALTH_FINAL_HTTP": "SKIPPED",
        "M40120_HEALTH_FINAL_IDENTITY": "NOT_ATTESTED",
        "M40120_PROCESS_OWNER": "NOT_ATTESTED",
        "M40120_LOADED_CODE": "NOT_ATTESTED",
        "M40120_RESTART_AUTHORIZED": "FALSE",
    }

    if first_code != second_code:
        state = "BLOCKED_HEALTH_HTTP_CHANGED_BETWEEN_PROBES"
    elif first_code != 200:
        state = unavailable(first_code)
    elif first_identity != second_identity:
        state = "BLOCKED_HEALTH_IDENTITY_CHANGED_BETWEEN_PROBES"
    elif first_identity != VALID_IDENTITY:
        state = "BLOCKED_HEALTH_APP_IDENTITY_UNVERIFIED"
    else:
        checkpoint_code, _ = guarded_get(fetch, CHECKPOINT)
        marker_code, _ = guarded_get(fetch, MARKER)
        final_code, final_doc = guarded_get(fetch, HEALTH)
        final_identity = identity(final_code, final_doc)
        outcome["M40120_CHECKPOINT_HTTP"] = status_class(checkpoint_code)
        outcome["M40120_MARKER_HTTP"] = status_class(marker_code)
        outcome["M40120_HEALTH_FINAL_HTTP"] = status_class(final_code)
        outcome["M40120_HEALTH_FINAL_IDENTITY"] = final_identity
        if final_code != 200 or final_identity != VALID_IDENTITY:
            state = "BLOCKED_HEALTH_CHANGED_DURING_MARKER_PROBES"
        elif checkpoint_code == 404 and marker_code == 404:
            state = "BLOCKED_BOTH_RUNTIME_MARKERS_404_OWNER_UNVERIFIED"
        else:
            state = "BLOCKED_RUNTIME_OWNER_AND_LOADED_CODE_UNVERIFIED"
    outcome["M40120_STATUS"] = state
    return outcome


def main(argv=None):
    parser = argparse.ArgumentParser(description="M40120 HTTP-only Termux diagnosis")
    parser.add_argument("--source-only", action="store_true")
    args = parser.parse_args(argv)
    print("=== FR FINANCE M40120 — HTTP HEALTH DISAMBIGUATION ===")
    if args.source_only:
        print("M40120_SOURCE_ONLY=PASS")
        print("M40120_RUNTIME=NOT_ATTESTED")
        return 0
    if not native_termux():
        print("M40120_STATUS=BLOCKED_NOT_NATIVE_TERMUX")
        return 2
    try:
        for key, value in report().items():
            print(key + "=" + value)
        return 2  # Diagnostic never licenses a restart or production.
    finally:
        print("M40120_HTTP=GET_LOOPBACK_ALLOWLIST_ONLY")
        print("M40120_HTTP_RAW_BODIES=NOT_DISCLOSED")
        print("M40120_PS_LSOF_PROC=NOT_ACCESSED")
        print("M40120_PROCESS_SIGNAL=NONE")
        print("M40120_FASTAPI_RESTART=NONE")
        print("M40120_DATABASE_CONNECTIONS=NONE")
        print("M40120_LOCAL_DB_WRITES=NONE")
        print("M40120_MIGRATIONS=NONE")
        print("M40120_PIX_REAL=OFF")
        print("M40120_PAGAMENTOS_REAIS=OFF")
        print("M40120_ATIVACAO_REAL=OFF")
        print("M40120_PRODUCTION=BLOCKED")


if __name__ == "__main__":
    raise SystemExit(main())
