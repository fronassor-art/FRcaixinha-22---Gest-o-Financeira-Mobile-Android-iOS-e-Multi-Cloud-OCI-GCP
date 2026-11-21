#!/usr/bin/env python3
"""M40090: read-only local FastAPI compatibility / socket scope decision.

Runs ONLY in native FR Finance Termux, not Debian or FR Caixinha 2.2.
No PID, command line, credentials, DB queries, signals or restarts.
Classifies absent M40080 endpoint WITHOUT assuming a PostgreSQL failure.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.app.m39700_runtime_contract import (
    classify_health, classify_checkpoint,
)
from backend.scripts.frfinance_m39700_termux_runtime_check import native_termux
from backend.scripts.frfinance_m39800_running_process_origin_readonly import (
    review_origin,
)
from backend.scripts.frfinance_m40080_loaded_source_readonly import (
    classify_marker, local_hashes,
)

BASE = "http://127.0.0.1:8000"
HEALTH = "/api/health"
CHECKPOINT = "/api/health/checkpoint"
MARKER = "/api/health/features/m40080"
ALLOWED_GET = frozenset((HEALTH, CHECKPOINT, MARKER))
TCP4 = Path("/proc/net/tcp")
TCP6 = Path("/proc/net/tcp6")
PORT = "1F40"  # TCP port 8000 hexadecimal


def fetch_json(path: str) -> tuple[int, object]:
    """Constant loopback GET paths; no redirects, cookies, auth or proxy."""
    if path not in ALLOWED_GET:
        raise ValueError("M40090_BLOCKED_NON_ALLOWLISTED_ENDPOINT")
    req = Request(
        BASE + path, method="GET",
        headers={"Accept": "application/json", "Cache-Control": "no-store"},
    )
    # Environment proxy settings and HTTP redirects must not escape loopback.
    opener = build_opener(ProxyHandler({}), NoRedirect())
    try:
        with opener.open(req, timeout=3) as response:
            if response.status != 200:
                return int(response.status), None
            body = response.read(8193)
            if len(body) > 8192:
                return 413, None
        return 200, json.loads(body)
    except HTTPError as exc:
        return int(exc.code), None
    except (URLError, TimeoutError, OSError):
        return 0, None
    except (ValueError, UnicodeDecodeError, TypeError):
        return 422, None


class NoRedirect(__import__("urllib.request", fromlist=["HTTPRedirectHandler"]).HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def socket_addresses(text: str, *, ipv6: bool) -> tuple[str, ...]:
    """Inspect local port and LISTEN state only. Never return inode or PID."""
    observed = []
    for row in text.splitlines()[1:]:
        cols = row.split()
        if len(cols) < 4 or cols[3] != "0A" or ":" not in cols[1]:
            continue
        address, port = cols[1].rsplit(":", 1)
        if port.upper() != PORT:
            continue
        if ipv6:
            observed.append("IPV6_UNCLASSIFIED")
        elif address.upper() == "0100007F":
            observed.append("IPV4_LOOPBACK")
        else:
            observed.append("IPV4_OTHER_BIND")
    return tuple(observed)


def inspect_socket_scope(tcp4: Path = TCP4, tcp6: Path = TCP6) -> str:
    try:
        v4 = socket_addresses(tcp4.read_text(encoding="ascii"), ipv6=False)
        ok4 = True
    except (OSError, UnicodeError, PermissionError):
        v4, ok4 = (), False
    try:
        v6 = socket_addresses(tcp6.read_text(encoding="ascii"), ipv6=True)
        ok6 = True
    except (OSError, UnicodeError, PermissionError):
        v6, ok6 = (), False
    if not ok4 or not ok6:
        return "ANDROID_SOCKET_VISIBILITY_PARTIAL_OR_RESTRICTED"
    if "IPV4_OTHER_BIND" in v4:
        return "NON_LOOPBACK_IPV4_BIND_REVIEW_REQUIRED"
    if v6:
        return "IPV6_BIND_SCOPE_NOT_ATTESTED"
    if v4 and all(x == "IPV4_LOOPBACK" for x in v4):
        return "IPV4_LOOPBACK_ONLY_OBSERVED"
    return "PORT_8000_LISTEN_NOT_VISIBLE"


def report(fetch=fetch_json, process=review_origin,
           scope=inspect_socket_scope, hashes=local_hashes) -> dict[str, str]:
    """Instruments observations, never constructs a restart decision."""
    try:
        local = hashes()
    except (ValueError, OSError, UnicodeError):
        return {
            "M40090_LOCAL_SOURCE": "NOT_ATTESTED",
            "M40090_STATUS": "BLOCKED_LOCAL_SOURCE",
        }
    first_status, first_body = fetch(HEALTH)
    if first_status != 200 or classify_health(first_body) != "FR_FINANCE_ONLINE":
        return {
            "M40090_API_IDENTITY": "NOT_ATTESTED",
            "M40090_STATUS": "BLOCKED_UNKNOWN_OR_OFFLINE_API",
        }
    checkpoint_status, checkpoint_body = fetch(CHECKPOINT)
    checkpoint_state = (
        classify_checkpoint(checkpoint_body)
        if checkpoint_status == 200
        else "CHECKPOINT_MISSING_OR_UNAVAILABLE"
    )
    marker_status, marker_body = fetch(MARKER)
    marker_state = classify_marker(marker_status, marker_body, local)
    second_status, second_body = fetch(HEALTH)
    if (second_status != 200
            or classify_health(second_body) != "FR_FINANCE_ONLINE"):
        return {
            "M40090_API_IDENTITY": "CHANGED_OR_NOT_ATTESTED",
            "M40090_STATUS": "BLOCKED_API_CHANGED_DURING_PROBES",
        }
    try:
        proc_result = process()
        owner_proved = (
            proc_result.get("M39800_STATUS") ==
            "PASS_ORIGINAL_FASTAPI_OWNER_IDENTIFIED"
        )
    except (OSError, ValueError, PermissionError):
        owner_proved = False
    socket_scope = scope()
    source_matches = (
        marker_state == "M40080_IMPORT_SNAPSHOT_MATCHES_LOCAL_FILES"
    )
    safe_endpoint = (
        checkpoint_state == "M39700_RUNNING_CODE_LOADED"
        and source_matches and owner_proved
        and socket_scope == "IPV4_LOOPBACK_ONLY_OBSERVED"
    )
    if marker_state == "M40080_NOT_LOADED_OR_ROUTE_ABSENT":
        state = "BLOCKED_M40080_ROUTE_MISSING_IN_RUNNING_API"
    elif socket_scope == "NON_LOOPBACK_IPV4_BIND_REVIEW_REQUIRED":
        state = "BLOCKED_NON_LOOPBACK_BIND_REVIEW"
    elif safe_endpoint:
        state = "PASS_RUNTIME_COMPATIBILITY_READ_ONLY_ONLY"
    else:
        state = "BLOCKED_INCOMPLETE_RUNTIME_EVIDENCE"

    return {
        "M40090_API_IDENTITY": "FR_FINANCE_ONLINE_DOUBLE_CHECKED",
        "M40090_M39700_CHECKPOINT": checkpoint_state,
        "M40090_M40080_IMPORT_SNAPSHOT": marker_state,
        "M40090_PROCESS_OWNER": (
            "M39800_OWNER_ATTESTED" if owner_proved else
            "NOT_ATTESTED_ANDROID_OR_UNKNOWN"
        ),
        "M40090_PORT_8000_SCOPE": socket_scope,
        "M40090_POSTGRES_STATUS": "NOT_CHECKED",
        "M40090_RESTART_AUTHORIZED": "FALSE",
        "M40090_STATUS": state,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="M40090 read-only runtime review")
    parser.add_argument("--source-only", action="store_true")
    args = parser.parse_args(argv)
    print("=== FR FINANCE M40090 — OLD FASTAPI DIAGNOSIS ONLY ===")
    if args.source_only:
        try:
            ok = len(local_hashes()) == 3
        except (OSError, ValueError, UnicodeError):
            ok = False
        print("M40090_SOURCE_ONLY=" + ("PASS" if ok else "BLOCKED"))
        print("M40090_RUNTIME=NOT_ATTESTED")
        return 0 if ok else 2
    if not native_termux():
        print("M40090_STATUS=BLOCKED_NOT_NATIVE_TERMUX")
        return 2
    try:
        results = report()
        for key, value in results.items():
            print(key + "=" + value)
        return (
            0 if results["M40090_STATUS"] ==
            "PASS_RUNTIME_COMPATIBILITY_READ_ONLY_ONLY" else 2
        )
    finally:
        print("M40090_HTTP=GET_LOOPBACK_ONLY")
        print("M40090_PID_AND_SECRETS_DISCLOSED=NONE")
        print("M40090_PROCESS_SIGNAL=NONE")
        print("M40090_FASTAPI_RESTART=NONE")
        print("M40090_DATABASE_CONNECTIONS=NONE")
        print("M40090_MIGRATIONS=NONE")
        print("M40090_LOCAL_DATABASE_WRITES=NONE")
        print("M40090_REAL_REVOCATION=NOT_ATTESTED")
        print("M40090_REVIEW_POLICY_RATIFIED=FALSE")
        print("M40090_REAL_PAYMENTS=OFF")
        print("M40090_PIX_REAL=OFF")
        print("M40090_PRODUCTION=BLOCKED")


if __name__ == "__main__":
    raise SystemExit(main())
