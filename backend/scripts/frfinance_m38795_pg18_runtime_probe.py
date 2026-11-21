#!/usr/bin/env python3
"""FR Finance M38795: targeted PG18 process/port probe, no SQL and no server startup.

Requires M38794 project/worktree/PGDATA validation. NEVER uses FR Caixinha 2.2
port 5432 or data directory. Does not remove postmaster.pid or modify PGDATA.
An unauthenticated pg_isready handshake is NOT evidence of cluster identity.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys

import frfinance_m38794_project_isolation as identity

AUTH = "AUTHORIZE_FRFINANCE_PG18_5433_READONLY_PROBE"
PGDATA = identity.FINANCE_PGDATA
STATUS_CODES = {
    "pg_ctl": {0: "RUNNING_REPORTED", 3: "NOT_RUNNING_REPORTED"},
    "pg_isready": {0: "ACCEPTING", 1: "REJECTING", 2: "NO_RESPONSE"},
}


class ProbeBlocked(Exception):
    """Safe constant error: never expose process or PG diagnostic text."""


def _pid_info() -> tuple[int | None, str]:
    pidfile = Path(PGDATA) / "postmaster.pid"
    if pidfile.is_symlink():
        raise ProbeBlocked("PIDFILE_SYMLINK_BLOCKED")
    if not pidfile.exists():
        return None, "ABSENT"
    try:
        lines = pidfile.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError):
        raise ProbeBlocked("PIDFILE_UNREADABLE") from None
    if (len(lines) < 6 or not lines[0].isdigit()
            or not (0 < int(lines[0]) <= 4194304)
            or lines[1] != PGDATA or lines[3] != "5433"):
        raise ProbeBlocked("PIDFILE_IDENTITY_MISMATCH")
    return int(lines[0]), "EXPECTED_PATH_PORT_5433"


def _pid_reachable(pid: int | None) -> str:
    if pid is None:
        return "NO_PIDFILE"
    try:
        # os.kill(pid, 0) only probes existence/permission. Never signals.
        os.kill(pid, 0)
    except ProcessLookupError:
        return "NOT_RUNNING"
    except PermissionError:
        return "PERMISSION_UNKNOWN"
    except OSError:
        return "UNKNOWN"
    return "PID_EXISTS_PROCESS_UNVERIFIED"


def _run_readonly_probe(name: str) -> str:
    if name == "pg_ctl":
        argv = ["pg_ctl", "-D", PGDATA, "status"]
        timeout = 8
    elif name == "pg_isready":
        # PG protocol readiness check, no authentication and no SQL issued.
        argv = [
            "pg_isready", "-q", "-t", "3",
            "-h", "127.0.0.1", "-p", "5433",
            "-U", identity.FINANCE_OWNER, "-d", identity.FINANCE_DB,
        ]
        timeout = 8
    else:
        raise ProbeBlocked("UNEXPECTED_PROBE_TOOL")
    # Prevent inherited PGHOST, PGPORT, PGSERVICE, PGOPTIONS, etc.
    env = {key: value for key, value in os.environ.items()
           if not key.startswith("PG")}
    try:
        result = subprocess.run(
            argv, capture_output=True, text=True,
            check=False, timeout=timeout, env=env,
        )
    except (OSError, subprocess.SubprocessError):
        return "UNAVAILABLE"
    return STATUS_CODES[name].get(result.returncode, "UNKNOWN")


def audit() -> dict[str, str]:
    # Includes manifest identity, git origin/branch/root, PG18 and separated
    # FR2.2 PGDATA. Fail without invoking pg_ctl or pg_isready if any mismatch.
    inspected = identity.inspect_local(Path.home())
    if inspected["M38794_PGDATA_IDENTITY"] != "FR_FINANCE_AI_STUDIO_PG18":
        raise ProbeBlocked("ACTIVE_PROJECT_MISMATCH")
    pid, pidfile = _pid_info()
    # Never interact with the 2.2 PGDATA or 5432.
    pid_state = _pid_reachable(pid)
    ctl = _run_readonly_probe("pg_ctl")
    port = _run_readonly_probe("pg_isready")
    if port == "ACCEPTING":
        finding = "PG_PROTOCOL_5433_ACCEPTED_CLUSTER_STILL_UNATTESTED"
    elif pid_state == "NOT_RUNNING" and ctl == "NOT_RUNNING_REPORTED":
        finding = "POSSIBLY_STALE_PIDFILE_DO_NOT_DELETE"
    elif ctl == "RUNNING_REPORTED" and port == "NO_RESPONSE":
        finding = "PG_CTL_RUNNING_BUT_PORT_5433_NO_RESPONSE"
    else:
        finding = "PG_5433_NOT_READY_DO_NOT_START"
    return {
        "M38795_PROJECT_ISOLATION": "PASS_STATIC",
        "M38795_PIDFILE": pidfile,
        "M38795_PID_REACHABLE": pid_state,
        "M38795_PG_CTL": ctl,
        "M38795_PG_ISREADY_5433": port,
        "M38795_DIAGNOSIS": finding,
        "M38795_CLUSTER_IDENTITY": "NOT_ATTESTED",
    }


def _safety() -> None:
    print("M38795_PG_CTL_MUTATIONS=NONE")
    print("M38795_PG_PIDFILE_REMOVAL=NONE")
    print("M38795_PG_SERVER_START_STOP=NONE")
    print("M38795_PG_PROTOCOL_CHECK=5433_ONLY_NO_SQL")
    print("M38795_DATABASE_CONNECTION_AUTHENTICATED=NONE")
    print("M38795_PG_2_2_ACCESS=NONE")
    print("M38795_MIGRATIONS=NONE")
    print("M38795_EMAIL_REAL=OFF")
    print("M38795_PIX_REAL=OFF")
    print("M38795_USER_ACTIVATION_REAL=OFF")
    print("M38795_PRODUCTION=BLOCKED")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="FR Finance PG18 process status only; no SQL/mutations")
    parser.add_argument("mode", choices=("offline", "local"), nargs="?", default="offline")
    parser.add_argument("authorization", nargs="?")
    args = parser.parse_args(argv)
    print("=== FR FINANCE M38795 PG18 PID / PORT DIAGNOSTIC ===")
    if args.mode == "offline":
        if args.authorization is not None:
            print("M38795_AUDIT=BLOCKED_UNEXPECTED_AUTHORIZATION")
            _safety()
            return 2
        try:
            identity.manifest()
        except identity.IsolationBlocked:
            print("M38795_AUDIT=BLOCKED_PROJECT_MANIFEST")
            _safety()
            return 2
        print("M38795_AUDIT=OFFLINE_REFERENCE")
        print("M38795_CLUSTER_IDENTITY=NOT_ATTESTED")
        _safety()
        return 0
    if args.authorization != AUTH:
        print("M38795_AUDIT=BLOCKED_AUTHORIZATION_REQUIRED")
        _safety()
        return 2
    try:
        report = audit()
    except (identity.IsolationBlocked, ProbeBlocked) as exc:
        print("M38795_AUDIT=BLOCKED")
        print("M38795_CAUSE=" + type(exc).__name__)
        # No raw exception/path/PID/credentials in logs.
        print("M38795_CLUSTER_IDENTITY=NOT_ATTESTED")
        _safety()
        return 2
    except Exception:
        print("M38795_AUDIT=BLOCKED_UNCLASSIFIED")
        print("M38795_CLUSTER_IDENTITY=NOT_ATTESTED")
        _safety()
        return 2
    print("M38795_AUDIT=READONLY_PROCESS_PROBE")
    for key, value in report.items():
        print(key + "=" + value)
    _safety()
    return 0


if __name__ == "__main__":
    sys.exit(main())
