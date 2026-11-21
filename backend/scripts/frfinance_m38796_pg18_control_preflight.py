#!/usr/bin/env python3
"""M38796 FR Finance PostgreSQL 18 crash/recovery preflight: READ ONLY.

Never remove postmaster.pid, change pg_control, launch PostgreSQL, or access 2.2.
A pg_controldata state is not itself authorization for cluster recovery.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import subprocess

import frfinance_m38794_project_isolation as identity
import frfinance_m38795_pg18_runtime_probe as runtime

AUTH = "AUTHORIZE_FRFINANCE_PG18_CONTROL_READONLY"
CONTROL_STATE_CODES = {
    "shut down": "CLEAN_SHUTDOWN_REPORTED",
    "shut down in recovery": "RECOVERY_SHUTDOWN_REPORTED",
    "in production": "UNCLEAN_OR_RUNNING_STATE_REPORTED",
    "in archive recovery": "ARCHIVE_RECOVERY_STATE_REPORTED",
    "starting up": "STARTUP_STATE_REPORTED",
}


class PreflightBlocked(Exception):
    """Never use sensitive raw system error strings in the report."""


def parse_control_state(stdout: object) -> str:
    """Only return allowlisted state; don't expose WAL positions/cluster ID."""
    if type(stdout) is not str or not 0 < len(stdout) < 65536:
        raise PreflightBlocked("PG_CONTROLDATA_OUTPUT_INVALID")
    matches = re.findall(
        r"(?im)^Database cluster state:\s*([a-z ]+?)\s*$",
        stdout,
    )
    if len(matches) != 1:
        raise PreflightBlocked("PG_CONTROLDATA_STATE_NOT_FOUND")
    return CONTROL_STATE_CODES.get(matches[0].lower().strip(), "UNKNOWN_STATE")


def pg_controldata_readonly() -> str:
    """Target exactly the configured FR Finance PGDATA, no shell."""
    cluster = Path(identity.FINANCE_PGDATA)
    control = cluster / "global" / "pg_control"
    if control.is_symlink() or not control.is_file():
        raise PreflightBlocked("PG_CONTROL_MISSING_OR_LINKED")
    env = {key: value for key, value in os.environ.items()
           if not key.startswith("PG")}
    env["LC_ALL"] = "C"
    env["PG_COLOR"] = "never"
    try:
        cp = subprocess.run(
            ["pg_controldata", "-D", identity.FINANCE_PGDATA],
            env=env, text=True, capture_output=True,
            timeout=12, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        raise PreflightBlocked("PG_CONTROLDATA_UNAVAILABLE") from None
    if cp.returncode != 0:
        raise PreflightBlocked("PG_CONTROLDATA_READ_FAILED")
    return parse_control_state(cp.stdout)


def _stopped_snapshot() -> dict[str, str]:
    report = runtime.audit()
    if report.get("M38795_PROJECT_ISOLATION") != "PASS_STATIC":
        raise PreflightBlocked("PROJECT_NOT_ISOLATED")
    if report.get("M38795_PIDFILE") != "EXPECTED_PATH_PORT_5433":
        raise PreflightBlocked("PIDFILE_UNEXPECTED")
    if report.get("M38795_PID_REACHABLE") != "NOT_RUNNING":
        raise PreflightBlocked("PID_STILL_ALIVE_OR_UNKNOWN")
    if report.get("M38795_PG_CTL") != "NOT_RUNNING_REPORTED":
        raise PreflightBlocked("PG_CTL_NOT_CONFIRMED_STOPPED")
    if report.get("M38795_PG_ISREADY_5433") != "NO_RESPONSE":
        raise PreflightBlocked("PG_PORT_NOT_CONFIRMED_DOWN")
    return report


def local_audit() -> dict[str, str]:
    # Two checks straddling pg_controldata guard against changes mid-inspection.
    before = _stopped_snapshot()
    state = pg_controldata_readonly()
    after = _stopped_snapshot()
    for field in (
        "M38795_PIDFILE", "M38795_PID_REACHABLE", "M38795_PG_CTL",
        "M38795_PG_ISREADY_5433",
    ):
        if before[field] != after[field]:
            raise PreflightBlocked("RUNTIME_CHANGED_DURING_INSPECTION")
    if state == "CLEAN_SHUTDOWN_REPORTED":
        next_step = "STOPPED_WITH_PIDFILE_MANUAL_REVIEW_REQUIRED"
    elif state == "UNCLEAN_OR_RUNNING_STATE_REPORTED":
        next_step = "UNCLEAN_CONTROL_STATE_POSSIBLE_WAL_RECOVERY_NO_ACTION"
    elif state == "RECOVERY_SHUTDOWN_REPORTED":
        next_step = "RECOVERY_STATE_MANUAL_REVIEW_REQUIRED"
    elif state in ("ARCHIVE_RECOVERY_STATE_REPORTED", "STARTUP_STATE_REPORTED"):
        next_step = "RECOVERY_OR_STARTUP_STATE_MANUAL_REVIEW_REQUIRED"
    else:
        next_step = "UNKNOWN_CONTROL_STATE_BLOCKED"
    return {
        "M38796_PROJECT": "FR_FINANCE_AI_STUDIO",
        "M38796_PGDATA": "FR_FINANCE_PG18_ONLY",
        "M38796_PROCESS": "NOT_RUNNING_REPORTED",
        "M38796_PORT_5433": "NO_RESPONSE",
        "M38796_POSTMASTER_PID": "PRESENT_UNVERIFIED_STALE",
        "M38796_PG_CONTROL_STATE": state,
        "M38796_NEXT_STEP": next_step,
        "M38796_LIVE_CLUSTER_IDENTITY": "NOT_ATTESTED",
        "M38796_OPERATION_ALLOWED": "NONE",
    }


def _safety() -> None:
    print("M38796_POSTMASTER_PID_DELETE=NONE")
    print("M38796_PG_CONTROL_MUTATIONS=NONE")
    print("M38796_PG_START_STOP=NONE")
    print("M38796_SQL_QUERIES=NONE")
    print("M38796_FR22_ACCESS=NONE")
    print("M38796_PG_BACKUP_RESTORE=NONE")
    print("M38796_MIGRATIONS=NONE")
    print("M38796_PIX_REAL=OFF")
    print("M38796_ACTIVATION_REAL=OFF")
    print("M38796_PRODUCTION=BLOCKED")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="FR Finance PG control READ ONLY")
    parser.add_argument("mode", choices=("offline", "local"), nargs="?", default="offline")
    parser.add_argument("authorization", nargs="?")
    args = parser.parse_args(argv)
    print("=== FR FINANCE M38796 PG18 CRASH PREFLIGHT ===")
    if args.mode == "offline":
        if args.authorization is not None:
            print("M38796_AUDIT=BLOCKED_UNEXPECTED_AUTHORIZATION")
            _safety()
            return 2
        try:
            identity.manifest()
        except identity.IsolationBlocked:
            print("M38796_AUDIT=BLOCKED_PROJECT_MANIFEST")
            _safety()
            return 2
        print("M38796_AUDIT=OFFLINE_REFERENCE")
        print("M38796_PG_CONTROL_STATE=NOT_QUERIED")
        print("M38796_OPERATION_ALLOWED=NONE")
        _safety()
        return 0
    if args.authorization != AUTH:
        print("M38796_AUDIT=BLOCKED_AUTH_REQUIRED")
        _safety()
        return 2
    try:
        report = local_audit()
    except (identity.IsolationBlocked, runtime.ProbeBlocked, PreflightBlocked):
        print("M38796_AUDIT=BLOCKED_INCOMPLETE_EVIDENCE")
        print("M38796_OPERATION_ALLOWED=NONE")
        _safety()
        return 2
    except Exception:
        print("M38796_AUDIT=BLOCKED_UNCLASSIFIED")
        print("M38796_OPERATION_ALLOWED=NONE")
        _safety()
        return 2
    print("M38796_AUDIT=LOCAL_READONLY_CONTROL")
    for key, value in report.items():
        print(key + "=" + value)
    _safety()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
