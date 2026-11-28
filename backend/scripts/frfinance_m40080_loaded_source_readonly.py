#!/usr/bin/env python3
"""M40080: native Termux GET-only loaded source vs checkout comparison.

Checks an import-time source snapshot, not a Git SHA or bank. Uses M39800's
same-UID /proc owner proof if Android allows it; restricted /proc fails closed.
No tokens, proc/env disclosure, FastAPI restarts or DB access.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, ProxyHandler, build_opener

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.scripts.frfinance_m39700_termux_runtime_check import native_termux
from backend.scripts.frfinance_m39800_running_process_origin_readonly import review_origin
from backend.app.m39700_runtime_contract import classify_health

CONTRACT = "FR_FINANCE_M40080_LOADED_SOURCE_V1"
BASE = "http://127.0.0.1:8000"
MARKER = "/api/health/features/m40080"
HEALTH = "/api/health"
HEX64 = re.compile(r"^[0-9a-f]{64}$")
SOURCES = {
    "main_py_sha256_at_import": ROOT / "backend/app/main.py",
    "review_router_sha256_at_import":
        ROOT / "backend/app/routers/exclusive_cashbox_review_gaps.py",
    "marker_py_sha256_at_import":
        ROOT / "backend/app/m40080_loaded_source_marker.py",
}
_FALSE = (
    "git_commit_verified", "executable_bytecode_attested",
    "process_owner_verified", "real_session_revocation_attested",
    "review_policy_ratified", "financial_approval_enabled",
    "pix_real_enabled", "production_authorized",
)


def local_hashes() -> dict[str, str]:
    """Do not follow symlinks or substitute FR Caixinha legacy files."""
    result = {}
    for key, path in SOURCES.items():
        if not path.is_file() or path.is_symlink():
            raise ValueError("M40080_SOURCE_NOT_REGULAR_FILE")
        result[key] = sha256(path.read_bytes()).hexdigest()
    return result


def fetch_json(path: str) -> tuple[int, object]:
    if path not in (HEALTH, MARKER):
        raise ValueError("M40080_BLOCKED_UNAPPROVED_HTTP_PATH")
    req = Request(BASE + path,
                  headers={"Accept": "application/json",
                           "Cache-Control": "no-store"}, method="GET")
    # Disable environment-derived proxy settings for this local-only request.
    opener = build_opener(ProxyHandler({}))
    try:
        with opener.open(req, timeout=3) as resp:
            if resp.status != 200:
                return int(resp.status), None
            raw = resp.read(2049)
            if len(raw) > 2048:
                return 413, None
        return 200, json.loads(raw)
    except HTTPError as exc:
        return int(exc.code), None
    except (URLError, OSError, TimeoutError):
        return 0, None
    except (ValueError, UnicodeDecodeError, TypeError):
        return 422, None


def classify_marker(status: int, payload: object,
                    local: dict[str, str]) -> str:
    if status == 404:
        return "M40080_NOT_LOADED_OR_ROUTE_ABSENT"
    if status != 200:
        return "M40080_HTTP_UNVERIFIED"
    if type(payload) is not dict or set(payload) != {
        "product", "workstream", "contract",
        "source_fingerprints_captured_on_import", *SOURCES, *_FALSE
    }:
        return "M40080_MARKER_INVALID"
    if (payload["product"] != "FR Finance" or
        payload["workstream"] != "AI_STUDIO" or
        payload["contract"] != CONTRACT or
        payload["source_fingerprints_captured_on_import"] is not True or
        any(payload[k] is not False for k in _FALSE)):
        return "M40080_MARKER_INVALID"
    if any(type(payload[k]) is not str or HEX64.fullmatch(payload[k]) is None
           for k in SOURCES):
        return "M40080_MARKER_INVALID"
    if any(payload[k] != local[k] for k in SOURCES):
        return "M40080_LOADED_SOURCE_DIFFERS_FROM_CHECKOUT"
    return "M40080_IMPORT_SNAPSHOT_MATCHES_LOCAL_FILES"


def report(fetch=fetch_json, origin=review_origin,
           source_hashes=local_hashes) -> dict[str, str]:
    try:
        hashes = source_hashes()
    except (ValueError, OSError, UnicodeError):
        return {"M40080_STATUS": "BLOCKED_LOCAL_SOURCE_NOT_ATTESTED"}
    health_code, health = fetch(HEALTH)
    if health_code != 200 or classify_health(health) != "FR_FINANCE_ONLINE":
        return {
            "M40080_HEALTH": "NOT_ATTESTED",
            "M40080_STATUS": "BLOCKED_WRONG_OR_UNAVAILABLE_FASTAPI",
        }
    process = origin()
    proc_ok = process.get("M39800_STATUS") == (
        "PASS_ORIGINAL_FASTAPI_OWNER_IDENTIFIED"
    )
    code, payload = fetch(MARKER)
    marker_state = classify_marker(code, payload, hashes)
    full = proc_ok and marker_state == "M40080_IMPORT_SNAPSHOT_MATCHES_LOCAL_FILES"
    return {
        "M40080_HEALTH": "FR_FINANCE_ONLINE",
        "M40080_PROCESS_ORIGIN": ("VERIFIED_BY_M39800" if proc_ok
                                 else "NOT_ATTESTED_ANDROID_OR_UNKNOWN"),
        "M40080_LOADED_SNAPSHOT": marker_state,
        "M40080_STATUS": (
            "PASS_OWNER_AND_IMPORT_SNAPSHOT_MATCH"
            if full else "BLOCKED_NO_COMPLETE_RUNTIME_ATTESTATION"
        ),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="M40080 GET-only Termux probe")
    parser.add_argument("--source-only", action="store_true")
    args = parser.parse_args(argv)
    print("=== FR FINANCE M40080 — FASTAPI LOADED SOURCE CHECK ===")
    if args.source_only:
        try:
            hashes = local_hashes()
            ok = len(hashes) == 3
        except (ValueError, OSError, UnicodeError):
            ok = False
        print("M40080_SOURCE_ONLY=" + ("PASS" if ok else "BLOCKED"))
        print("M40080_LOADED_CODE=NOT_ATTESTED")
        return 0 if ok else 2
    if not native_termux():
        print("M40080_STATUS=BLOCKED_NOT_NATIVE_TERMUX_FR_FINANCE")
        return 2
    try:
        result = report()
        for key, value in result.items():
            print(key + "=" + value)
        return 0 if result["M40080_STATUS"] == (
            "PASS_OWNER_AND_IMPORT_SNAPSHOT_MATCH") else 2
    finally:
        print("M40080_HTTP=GET_127_0_0_1_ONLY")
        print("M40080_SECRETS_AND_PID_DISCLOSED=NONE")
        print("M40080_DATABASE_CONNECTIONS=NONE")
        print("M40080_DATABASE_WRITES=NONE")
        print("M40080_SQL_MIGRATIONS=NONE")
        print("M40080_FASTAPI_RESTART=NONE")
        print("M40080_REAL_REVIEW_APPROVAL=FALSE")
        print("M40080_PIX_REAL=OFF")
        print("M40080_PRODUCTION=BLOCKED")


if __name__ == "__main__":
    raise SystemExit(main())
