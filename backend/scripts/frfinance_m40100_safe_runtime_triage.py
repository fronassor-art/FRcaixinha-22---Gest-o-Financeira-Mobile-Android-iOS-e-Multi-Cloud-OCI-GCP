#!/usr/bin/env python3
"""M40100 — FR Finance native Termux, non-invasive stale FastAPI triage.

Checks exact HTTP status codes on a fixed loopback allowlist and optionally
classifies same-UID process command CANDIDATES. ps is not proof that a
candidate owns 127.0.0.1:8000. Never prints process lines/PIDs/credentials.
No database, startup, stop, signal, service or migration operations.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import shlex
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.scripts.frfinance_m39700_termux_runtime_check import native_termux
from backend.app.m39700_runtime_contract import classify_health, classify_checkpoint
from backend.scripts.frfinance_m40090_old_fastapi_diagnosis import (
    HEALTH, CHECKPOINT, MARKER, fetch_json, inspect_socket_scope,
)
from backend.scripts.frfinance_m40080_loaded_source_readonly import (
    classify_marker, local_hashes,
)

MAX_PS_BYTES = 131072
PS_TIMEOUT_SECONDS = 3
PS_ARGS = ("ps", "-u", str(os.getuid()), "-o", "args=")


def candidate_type(line: str) -> str:
    """Conservative argv comparison: never certify socket or worktree."""
    if len(line) > 2048 or any(c in line for c in ("\n", "\r", "\x00")):
        return "OTHER_COMMAND"
    try:
        args = shlex.split(line, posix=True)
    except ValueError:
        return "OTHER_COMMAND"
    if len(args) > 32:
        return "OTHER_COMMAND"
    has_target = any(args[i:i+3] == ["-m", "uvicorn", "app.main:app"]
                     for i in range(max(0, len(args)-2)))
    has_host = any(args[i:i+2] == ["--host", "127.0.0.1"]
                   for i in range(max(0, len(args)-1)))
    has_port = any(args[i:i+2] == ["--port", "8000"]
                   for i in range(max(0, len(args)-1)))
    # ps itself may contain keywords as arguments. We deliberately require a
    # python executable and exact -m invocation, but still label candidate.
    binary = Path(args[0]).name if args else ""
    valid_python = binary.startswith("python") or binary.startswith("pypy")
    if (valid_python and has_target and has_host and has_port
            and "--reload" not in args and "--workers" not in args):
        return "SAME_UID_UVICORN_COMMAND_CANDIDATE"
    return "OTHER_COMMAND"


def candidate_snapshot(run=subprocess.run) -> str:
    """Read only own UID's ps arguments; never expose raw stdout/stderr."""
    try:
        cp = run(
            list(PS_ARGS), capture_output=True,
            timeout=PS_TIMEOUT_SECONDS, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return "PS_SAME_UID_UNAVAILABLE_OR_RESTRICTED"
    if (cp.returncode != 0 or len(cp.stdout) > MAX_PS_BYTES
            or len(cp.stderr) > MAX_PS_BYTES):
        return "PS_SAME_UID_UNAVAILABLE_OR_RESTRICTED"
    try:
        lines = cp.stdout.decode("utf-8", errors="strict").splitlines()
    except (UnicodeError, AttributeError):
        return "PS_SAME_UID_UNAVAILABLE_OR_RESTRICTED"
    count = sum(candidate_type(line) == "SAME_UID_UVICORN_COMMAND_CANDIDATE"
                for line in lines)
    if count == 0:
        return "NO_MATCHING_COMMAND_VISIBLE_NOT_PROOF_OF_ABSENCE"
    if count == 1:
        return "ONE_SAME_UID_COMMAND_CANDIDATE_NOT_SOCKET_OWNER"
    return "MULTIPLE_SAME_UID_CANDIDATES_AMBIGUOUS"


def status_class(http_status: int) -> str:
    """Never collapse 404 with auth failure, 503 or timeout."""
    return {
        200: "HTTP_200", 401: "HTTP_401", 403: "HTTP_403",
        404: "HTTP_404", 405: "HTTP_405", 413: "HTTP_TOO_LARGE",
        422: "HTTP_UNPARSEABLE", 429: "HTTP_429",
        500: "HTTP_500", 502: "HTTP_502", 503: "HTTP_503",
        504: "HTTP_504", 0: "HTTP_NO_RESPONSE",
    }.get(http_status, "HTTP_OTHER")


def report(fetch=fetch_json, candidates=candidate_snapshot,
           socket_scope=inspect_socket_scope, hashes=local_hashes):
    """No ps or socket introspection if application identity is wrong."""
    try:
        local = hashes()
    except (OSError, ValueError, UnicodeError):
        return {"M40100_STATUS": "BLOCKED_LOCAL_SOURCE_UNAVAILABLE"}
    health_before, body = fetch(HEALTH)
    if health_before != 200 or classify_health(body) != "FR_FINANCE_ONLINE":
        return {
            "M40100_HEALTH_STATUS": status_class(health_before),
            "M40100_STATUS": "BLOCKED_WRONG_OR_UNKNOWN_API",
        }

    checkpoint_code, checkpoint_doc = fetch(CHECKPOINT)
    checkpoint = (
        classify_checkpoint(checkpoint_doc) if checkpoint_code == 200
        else "NOT_ATTESTED"
    )
    marker_code, marker_doc = fetch(MARKER)
    marker = classify_marker(marker_code, marker_doc, local)
    after_code, after = fetch(HEALTH)
    if after_code != 200 or classify_health(after) != "FR_FINANCE_ONLINE":
        return {
            "M40100_HEALTH_STATUS": "CHANGED_DURING_PROBE",
            "M40100_STATUS": "BLOCKED_API_IDENTITY_CHANGED",
        }

    try:
        command_candidates = candidates()
    except (OSError, ValueError, PermissionError):
        command_candidates = "PS_SAME_UID_UNAVAILABLE_OR_RESTRICTED"
    try:
        socket = socket_scope()
    except (OSError, ValueError, PermissionError):
        socket = "ANDROID_SOCKET_VISIBILITY_PARTIAL_OR_RESTRICTED"

    stale = (
        checkpoint_code == 404 and marker_code == 404
    )
    if stale:
        state = "BLOCKED_PRE_M39700_RUNTIME_LIKELY_NOT_PROVEN"
    elif marker_code == 404:
        state = "BLOCKED_M40080_MARKER_ABSENT"
    elif checkpoint != "M39700_RUNNING_CODE_LOADED":
        state = "BLOCKED_M39700_CHECKPOINT_NOT_ATTESTED"
    elif marker != "M40080_IMPORT_SNAPSHOT_MATCHES_LOCAL_FILES":
        state = "BLOCKED_IMPORT_MARKER_UNVERIFIED"
    else:
        # M40100 does not have a trustworthy socket-owner mapping.
        state = "BLOCKED_RUNTIME_OWNER_NOT_ATTESTED"

    return {
        "M40100_HEALTH_STATUS": "FR_FINANCE_ONLINE_DOUBLE_CHECKED",
        "M40100_M39700_HTTP": status_class(checkpoint_code),
        "M40100_M39700_CONTRACT": checkpoint,
        "M40100_M40080_HTTP": status_class(marker_code),
        "M40100_M40080_SNAPSHOT": marker,
        "M40100_SAME_UID_PROCESS_CANDIDATES": command_candidates,
        "M40100_SOCKET_SCOPE": socket,
        "M40100_PORT_OWNER_VERIFIED": "FALSE",
        "M40100_POSTGRESQL_CHECK": "NOT_PERFORMED",
        "M40100_RESTART_AUTHORIZED": "FALSE",
        "M40100_STATUS": state,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="M40100 read-only runtime triage")
    parser.add_argument("--source-only", action="store_true")
    args = parser.parse_args(argv)
    print("=== FR FINANCE M40100 — SAFE RUNTIME TRIAGE ===")
    if args.source_only:
        try:
            good = len(local_hashes()) == 3
        except (OSError, ValueError, UnicodeError):
            good = False
        print("M40100_SOURCE_ONLY=" + ("PASS" if good else "BLOCKED"))
        print("M40100_RUNTIME=NOT_ATTESTED")
        return 0 if good else 2
    if not native_termux():
        print("M40100_STATUS=BLOCKED_NOT_NATIVE_TERMUX")
        return 2
    try:
        outcome = report()
        for key, value in outcome.items():
            print(key + "=" + value)
        return 2  # Even a full source match never authorizes process restart.
    finally:
        print("M40100_HTTP=GET_127_0_0_1_ONLY")
        print("M40100_PROCESS_COMMANDS_AND_PIDS_PRINTED=NONE")
        print("M40100_PROCESS_SIGNAL=NONE")
        print("M40100_FASTAPI_START_STOP_RESTART=NONE")
        print("M40100_POSTGRESQL_CONNECTIONS=NONE")
        print("M40100_DATABASE_WRITES=NONE")
        print("M40100_MIGRATIONS=NONE")
        print("M40100_PIX_REAL=OFF")
        print("M40100_REAL_PAYMENTS=OFF")
        print("M40100_PRODUCTION=BLOCKED")


if __name__ == "__main__":
    raise SystemExit(main())
