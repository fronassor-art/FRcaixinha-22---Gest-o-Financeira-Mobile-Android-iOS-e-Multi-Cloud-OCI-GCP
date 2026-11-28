#!/usr/bin/env python3
"""FR Finance M40160 — offline PostgreSQL 18 control-state review on native Termux.

No cluster start/stop, migration, SQL, credentials, secret file access or new
PGDATA. The PostgreSQL binary pg_controldata only READS control metadata.
A clean state is not a full integrity check or authorization to start PG.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import stat
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.scripts.frfinance_m38794_project_isolation import FINANCE_PGDATA
from backend.scripts.frfinance_m39700_termux_runtime_check import native_termux
from backend.scripts.frfinance_m40150_original_pg18_status_readonly import (
    identity, pg_ctl_status, pg_isready_status, safe_subprocess_env,
)

PGDATA = Path(FINANCE_PGDATA)
PG_CONTROLDATA = Path("/data/data/com.termux/files/usr/bin/pg_controldata")
MAX_CONTROL_BYTES = 65536
TIMEOUT = 6
CLEAN_STATES = frozenset(("shut down", "shut down in recovery"))
NON_CLEAN_STATES = frozenset(("in production", "starting up", "in crash recovery",
                             "in archive recovery"))


def original_structure(root=PGDATA, uid=None):
    """Shallow ownership/file-shape checks only; do not claim full integrity."""
    if uid is None:
        uid = os.getuid()
    try:
        info = root.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != uid:
            return "BLOCKED_PGDATA_OWNER_OR_DIRECTORY"
        if stat.S_IMODE(info.st_mode) & 0o007:
            return "BLOCKED_PGDATA_OTHER_PERMISSIONS"
        for name in ("base", "global", "pg_wal"):
            entry = (root / name).lstat()
            if not stat.S_ISDIR(entry.st_mode) or entry.st_uid != uid:
                return "BLOCKED_CLUSTER_DIRECTORY_LAYOUT"
        control = (root / "global" / "pg_control").lstat()
        if not stat.S_ISREG(control.st_mode) or control.st_uid != uid:
            return "BLOCKED_CONTROL_FILE_LAYOUT"
        version = root / "PG_VERSION"
        if version.is_symlink() or version.read_text(encoding="ascii").strip() != "18":
            return "BLOCKED_PG_VERSION"
        return "PASS_SHALLOW_ORIGINAL_FILES_PRESENT_NOT_INTEGRITY"
    except (OSError, UnicodeError, ValueError):
        return "BLOCKED_CLUSTER_FILE_METADATA"


def parse_control_state(raw):
    """Parse one and only one exact PostgreSQL C-locale state line.

    No system identifier, transaction ID, WAL location, checkpoint or raw
    executable output is ever included in the result.
    """
    if type(raw) is not bytes or len(raw) > MAX_CONTROL_BYTES:
        return "CONTROL_DATA_UNVERIFIED"
    try:
        contents = raw.decode("utf-8", "strict")
    except UnicodeError:
        return "CONTROL_DATA_UNVERIFIED"
    matches = re.findall(r"^Database cluster state:\s*([^\r\n]+?)\s*$",
                         contents, re.MULTILINE)
    if len(matches) != 1:
        return "CONTROL_DATA_UNVERIFIED"
    state = matches[0].strip()
    if state in CLEAN_STATES:
        return "CLEAN_SHUTDOWN_STATE_REPORTED"
    if state in NON_CLEAN_STATES:
        return "NON_CLEAN_OR_RUNNING_STATE_REPORTED"
    return "CONTROL_STATE_NOT_RECOGNIZED"


def pg_control_snapshot(run=subprocess.run, program=PG_CONTROLDATA):
    try:
        executable = program.lstat()
        if not stat.S_ISREG(executable.st_mode):
            return "CONTROL_TOOL_MISSING_OR_LINKED"
        env = safe_subprocess_env()
        env["LC_ALL"] = "C"
        env["LANG"] = "C"
        cp = run([str(program), "-D", FINANCE_PGDATA],
                 capture_output=True, check=False, timeout=TIMEOUT, env=env)
        if (cp.returncode != 0 or len(cp.stdout) > MAX_CONTROL_BYTES
                or len(cp.stderr) > MAX_CONTROL_BYTES):
            return "CONTROL_DATA_UNVERIFIED"
        return parse_control_state(cp.stdout)
    except (OSError, TypeError, ValueError, subprocess.SubprocessError):
        return "CONTROL_DATA_UNVERIFIED"


def report(project=identity, pgstatus=pg_ctl_status, readiness=pg_isready_status,
           layout=original_structure, control=pg_control_snapshot):
    result = {
        "M40160_PROJECT": "NOT_ATTESTED",
        "M40160_PG_STATUS_BEFORE": "SKIPPED",
        "M40160_PG_READY_BEFORE": "SKIPPED",
        "M40160_ORIGINAL_FILES": "SKIPPED",
        "M40160_CLUSTER_CONTROL_STATE": "SKIPPED",
        "M40160_PG_STATUS_AFTER": "SKIPPED",
        "M40160_PG_READY_AFTER": "SKIPPED",
        "M40160_FULL_DATA_INTEGRITY": "NOT_ATTESTED",
        "M40160_PG_START_AUTHORIZED": "FALSE",
        "M40160_FASTAPI_START_AUTHORIZED": "FALSE",
        "M40160_PRODUCTION_AUTHORIZED": "FALSE",
    }
    verified = project()
    result["M40160_PROJECT"] = verified
    if verified != "PASS_STATIC_ORIGINAL_FR_FINANCE_PG18":
        result["M40160_STATUS"] = "BLOCKED_ORIGINAL_CLUSTER_IDENTITY"
        return result

    before = pgstatus()
    before_ready = readiness()
    result["M40160_PG_STATUS_BEFORE"] = before
    result["M40160_PG_READY_BEFORE"] = before_ready
    if (before != "ORIGINAL_PGDATA_PROCESS_REPORTED_STOPPED"
            or before_ready != "PORT_5433_NO_RESPONSE"):
        result["M40160_STATUS"] = "BLOCKED_NOT_VERIFIED_OFFLINE"
        return result

    files = layout()
    result["M40160_ORIGINAL_FILES"] = files
    if files != "PASS_SHALLOW_ORIGINAL_FILES_PRESENT_NOT_INTEGRITY":
        result["M40160_STATUS"] = "BLOCKED_CLUSTER_LAYOUT_REVIEW"
        return result

    result["M40160_CLUSTER_CONTROL_STATE"] = control()

    after = pgstatus()
    after_ready = readiness()
    result["M40160_PG_STATUS_AFTER"] = after
    result["M40160_PG_READY_AFTER"] = after_ready

    if before != after or before_ready != after_ready:
        state = "BLOCKED_CLUSTER_STATUS_CHANGED_DURING_INSPECTION"
    elif result["M40160_CLUSTER_CONTROL_STATE"] == "CLEAN_SHUTDOWN_STATE_REPORTED":
        state = "BLOCKED_OFFLINE_CLEAN_REPORTED_START_NOT_AUTHORIZED"
    elif result["M40160_CLUSTER_CONTROL_STATE"] == "NON_CLEAN_OR_RUNNING_STATE_REPORTED":
        state = "BLOCKED_RECOVERY_REVIEW_REQUIRED_NO_START"
    else:
        state = "BLOCKED_CONTROL_DATA_UNVERIFIED_NO_START"
    result["M40160_STATUS"] = state
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description="Offline FR Finance PG18 control only")
    parser.add_argument("--source-only", action="store_true")
    args = parser.parse_args(argv)
    print("=== FR FINANCE M40160 — PG18 OFFLINE CONTROL REVIEW ===")
    if args.source_only:
        print("M40160_SOURCE_ONLY=PASS")
        print("M40160_LOCAL_CLUSTER=NOT_INSPECTED")
        return 0
    if not native_termux():
        print("M40160_STATUS=BLOCKED_NOT_NATIVE_TERMUX")
        return 2
    try:
        for key, value in report().items():
            print(key + "=" + value)
        return 2
    finally:
        print("M40160_PG_CONTROLDATA=READ_ONLY_METADATA")
        print("M40160_RAW_CONTROL_OUTPUT=NOT_DISCLOSED")
        print("M40160_PGDATA_2_2=NOT_ACCESSED")
        print("M40160_SQL_QUERIES=NONE")
        print("M40160_DATABASE_CONNECTIONS=NO_SQL_SESSIONS")
        print("M40160_DATABASE_WRITES=NONE")
        print("M40160_MIGRATIONS=NONE")
        print("M40160_PG_START_STOP=NONE")
        print("M40160_FASTAPI_START_STOP=NONE")
        print("M40160_PIX_REAL=OFF")
        print("M40160_PAGAMENTOS_REAIS=OFF")
        print("M40160_ATIVACAO_REAL=OFF")
        print("M40160_PRODUCTION=BLOCKED")


if __name__ == "__main__":
    raise SystemExit(main())
