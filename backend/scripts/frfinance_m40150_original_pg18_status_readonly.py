#!/usr/bin/env python3
"""M40150 — inspect ORIGINAL FR Finance PostgreSQL 18 startup/readiness only.

Termux native, original worktree and PGDATA gate required. Runs `pg_ctl status`
against the exact PGDATA and `pg_isready` (unauthenticated protocol handshake)
against fixed loopback:5433 with no PostgreSQL environment overrides.
No password, SQL, new session, migration, database mutation or service control.
These probes do NOT attest authenticated DB identity or authorize FastAPI start.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.scripts.frfinance_m38794_project_isolation import (
    FINANCE_PGDATA, inspect_local, IsolationBlocked,
)
from backend.scripts.frfinance_m39700_termux_runtime_check import native_termux
from backend.scripts.frfinance_m40130_loopback_tcp_health_readonly import tcp_probe
from backend.scripts.frfinance_m40140_original_launcher_preflight_readonly import (
    launcher_snapshot,
)

TERMUX_BIN = Path("/data/data/com.termux/files/usr/bin")
PG_CTL = TERMUX_BIN / "pg_ctl"
PG_ISREADY = TERMUX_BIN / "pg_isready"
DB_NAME = "frcaixinha_aistudio_dev"
DB_OWNER = "frc_ai_owner"
TIMEOUT_SECONDS = 6
MAX_CAPTURED_BYTES = 65536


def safe_subprocess_env(source=None):
    """No PG*/DSN credentials or service target overrides are passed to tools."""
    if source is None:
        source = os.environ
    allowed = ("HOME", "PATH", "PREFIX", "TMPDIR", "LANG", "LC_ALL")
    return {key: source[key] for key in allowed if key in source}


def allowed_executables(ctl=PG_CTL, ready=PG_ISREADY):
    try:
        if any(p.is_symlink() or not p.is_file() for p in (ctl, ready)):
            return "PG_TOOLS_NOT_ATTESTED"
        return "TERMUX_POSTGRES_BINARIES_PRESENT_NOT_EXECUTED"
    except (OSError, ValueError):
        return "PG_TOOLS_NOT_ATTESTED"


def _run_status(args, *, run=subprocess.run):
    try:
        cp = run(args, capture_output=True, timeout=TIMEOUT_SECONDS,
                 check=False, env=safe_subprocess_env())
        if (len(cp.stdout) > MAX_CAPTURED_BYTES or
                len(cp.stderr) > MAX_CAPTURED_BYTES):
            return None
        return cp.returncode if type(cp.returncode) is int else None
    except (OSError, subprocess.SubprocessError, TypeError, ValueError):
        return None


def pg_ctl_status(run=subprocess.run):
    # pg_ctl status does not start/stop any process and does not connect to DB.
    command = [str(PG_CTL), "-D", FINANCE_PGDATA, "status"]
    rc = _run_status(command, run=run)
    if rc == 0:
        return "ORIGINAL_PGDATA_PROCESS_REPORTED_RUNNING"
    if rc == 3:
        return "ORIGINAL_PGDATA_PROCESS_REPORTED_STOPPED"
    return "ORIGINAL_PGDATA_PROCESS_NOT_ATTESTED"


def pg_isready_status(run=subprocess.run):
    # Fixed target, no secrets, SQL, or login. Readiness is NOT DB identity.
    command = [str(PG_ISREADY), "-q", "-t", "2", "-h", "127.0.0.1",
               "-p", "5433", "-U", DB_OWNER, "-d", DB_NAME]
    rc = _run_status(command, run=run)
    return {
        0: "PORT_5433_ACCEPTING_UNAUTHENTICATED",
        1: "PORT_5433_REJECTING_CONNECTIONS",
        2: "PORT_5433_NO_RESPONSE",
        3: "PORT_5433_PROBE_NOT_ATTEMPTED",
    }.get(rc, "PORT_5433_NOT_ATTESTED")


def identity(probe=inspect_local):
    try:
        result = probe(Path.home())
        return (
            "PASS_STATIC_ORIGINAL_FR_FINANCE_PG18"
            if (result.get("M38794_GIT_IDENTITY") == "FR_FINANCE_AI_STUDIO"
                and result.get("M38794_PGDATA_IDENTITY") ==
                    "FR_FINANCE_AI_STUDIO_PG18"
                and result.get("M38794_PGDATA_VERSION") == "18")
            else "BLOCKED_ORIGINAL_FR_FINANCE_PGDATA"
        )
    except (IsolationBlocked, OSError, ValueError, PermissionError, TypeError):
        return "BLOCKED_ORIGINAL_FR_FINANCE_PGDATA"


def report(project=identity, launcher=launcher_snapshot,
           tools=allowed_executables, status=pg_ctl_status,
           ready=pg_isready_status, tcp=tcp_probe):
    verified = project()
    launcher_state = launcher()
    binaries = tools()
    result = {
        "M40150_PROJECT": verified,
        "M40150_LAUNCHER": launcher_state,
        "M40150_POSTGRES_BINARIES": binaries,
        "M40150_PG_CTL_STATUS": "SKIPPED_PRECHECK",
        "M40150_PG_ISREADY_5433": "SKIPPED_PRECHECK",
        "M40150_TCP_8000": "SKIPPED_PRECHECK",
        "M40150_AUTHENTICATED_PG_IDENTITY": "NOT_ATTESTED",
        "M40150_DB_SQL_SESSIONS": "NONE",
        "M40150_LAUNCH_AUTHORIZED": "FALSE",
        "M40150_RESTART_AUTHORIZED": "FALSE",
    }
    if verified != "PASS_STATIC_ORIGINAL_FR_FINANCE_PG18":
        state = "BLOCKED_PROJECT_ISOLATION"
    elif launcher_state != "PASS_M38801_ORIGINAL_STATIC_CONTRACT":
        state = "BLOCKED_LAUNCHER_DRIFT"
    elif binaries != "TERMUX_POSTGRES_BINARIES_PRESENT_NOT_EXECUTED":
        state = "BLOCKED_POSTGRES_BINARIES"
    else:
        # Both are bounded read-only status checks. isready performs a fixed
        # unauthenticated TCP protocol handshake; neither opens a SQL session.
        ctl = status()
        readiness = ready()
        result["M40150_PG_CTL_STATUS"] = ctl
        result["M40150_PG_ISREADY_5433"] = readiness
        try:
            port = tcp()
        except (OSError, ValueError, TypeError, PermissionError):
            port = "TCP_NOT_ATTESTED"
        if port not in (
            "TCP_HANDSHAKE_ACCEPTED", "TCP_CONNECTION_REFUSED",
            "TCP_CONNECT_TIMEOUT", "TCP_UNREACHABLE_OR_RESTRICTED",
            "TCP_CONNECT_UNVERIFIED", "TCP_NOT_ATTESTED",
        ):
            port = "TCP_NOT_ATTESTED"
        result["M40150_TCP_8000"] = port
        if port == "TCP_HANDSHAKE_ACCEPTED":
            state = "BLOCKED_FASTAPI_PORT_OCCUPIED"
        elif ctl == "ORIGINAL_PGDATA_PROCESS_REPORTED_STOPPED":
            state = "BLOCKED_ORIGINAL_PG_NOT_RUNNING_DO_NOT_START"
        elif ctl != "ORIGINAL_PGDATA_PROCESS_REPORTED_RUNNING":
            state = "BLOCKED_ORIGINAL_PG_PROCESS_UNVERIFIED"
        elif readiness != "PORT_5433_ACCEPTING_UNAUTHENTICATED":
            state = "BLOCKED_ORIGINAL_PG_5433_NOT_ACCEPTING"
        elif port != "TCP_CONNECTION_REFUSED":
            state = "BLOCKED_TCP_8000_UNVERIFIED"
        else:
            state = "BLOCKED_DB_IDENTITY_AND_FASTAPI_LAUNCH_NOT_AUTHORIZED"
    result["M40150_STATUS"] = state
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description="Original PG18 read-only status")
    parser.add_argument("--source-only", action="store_true")
    args = parser.parse_args(argv)
    print("=== FR FINANCE M40150 — ORIGINAL PG18 STATUS READ ONLY ===")
    if args.source_only:
        print("M40150_SOURCE_ONLY=" + launcher_snapshot())
        print("M40150_LIVE_SERVER=NOT_ATTESTED")
        return 0 if launcher_snapshot() == "PASS_M38801_ORIGINAL_STATIC_CONTRACT" else 2
    if not native_termux():
        print("M40150_STATUS=BLOCKED_NOT_NATIVE_TERMUX")
        return 2
    try:
        for key, value in report().items():
            print(key + "=" + value)
        return 2
    finally:
        print("M40150_PG_CTL=STATUS_ONLY")
        print("M40150_PG_ISREADY=FIXED_UNAUTHENTICATED_PROBE_ONLY")
        print("M40150_PASSWORDS_AND_DSN=NOT_READ_OR_PRINTED")
        print("M40150_OTHER_PG_PORT_5432=NOT_TOUCHED")
        print("M40150_SQL_QUERIES=NONE")
        print("M40150_DATABASE_WRITES=NONE")
        print("M40150_MIGRATIONS=NONE")
        print("M40150_PG_START_STOP=NONE")
        print("M40150_FASTAPI_START_STOP_RESTART=NONE")
        print("M40150_PIX_REAL=OFF")
        print("M40150_PAGAMENTOS_REAIS=OFF")
        print("M40150_ATIVACAO_REAL=OFF")
        print("M40150_PRODUCTION=BLOCKED")


if __name__ == "__main__":
    raise SystemExit(main())
