#!/usr/bin/env python3
"""M40170: offline WAL layout and recovery preflight, native Termux only.

Read-only filesystem METADATA probes of FR Finance PG18 after Android restart.
No PG startup, SQL, backup copy, file deletion, WAL changes or migrations.
WAL file presence never attests WAL validity, sufficient recovery or backup.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import stat
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.scripts.frfinance_m39700_termux_runtime_check import native_termux
from backend.scripts.frfinance_m40150_original_pg18_status_readonly import (
    identity, pg_ctl_status, pg_isready_status,
)
from backend.scripts.frfinance_m40160_original_pg_control_offline_readonly import (
    PGDATA, pg_control_snapshot, original_structure,
)

MAX_WAL_ENTRIES = 4096
MAX_TABLESPACE_ENTRIES = 512
WAL_FILE = re.compile(r"[0-9A-F]{24}\Z")
GIB = 1024 ** 3


def wal_layout(wal=None):
    """No WAL contents, filenames, transaction IDs or LSNs leave this probe."""
    if wal is None:
        wal = PGDATA / "pg_wal"
    try:
        info = wal.lstat()
        if not stat.S_ISDIR(info.st_mode):
            return "BLOCKED_WAL_DIRECTORY_OR_SYMLINK"
        found = False
        with os.scandir(wal) as items:
            for n, entry in enumerate(items):
                if n >= MAX_WAL_ENTRIES:
                    return "BLOCKED_WAL_ENTRY_LIMIT"
                if WAL_FILE.fullmatch(entry.name):
                    if not entry.is_file(follow_symlinks=False):
                        return "BLOCKED_WAL_SEGMENT_NOT_REGULAR"
                    if entry.stat(follow_symlinks=False).st_size > 0:
                        found = True
        return ("SEGMENT_FILES_PRESENT_CONTENT_NOT_VERIFIED" if found
                else "NO_WAL_SEGMENT_OBSERVED")
    except (OSError, ValueError):
        return "BLOCKED_WAL_LAYOUT_UNAVAILABLE"


def tablespace_layout(path=None):
    """Flag external tablespaces because cold backup must include their targets."""
    if path is None:
        path = PGDATA / "pg_tblspc"
    try:
        info = path.lstat()
        if not stat.S_ISDIR(info.st_mode):
            return "BLOCKED_TABLESPACE_DIRECTORY_OR_SYMLINK"
        external = False
        unexpected = False
        with os.scandir(path) as items:
            for n, entry in enumerate(items):
                if n >= MAX_TABLESPACE_ENTRIES:
                    return "BLOCKED_TABLESPACE_ENTRY_LIMIT"
                if entry.is_symlink():
                    external = True
                else:
                    unexpected = True
        if unexpected:
            return "TABLESPACE_LAYOUT_REQUIRES_REVIEW"
        return ("EXTERNAL_TABLESPACES_PRESENT_BACKUP_SCOPE_UNKNOWN"
                if external else "NO_EXTERNAL_TABLESPACE_POINTERS")
    except (OSError, ValueError):
        return "BLOCKED_TABLESPACE_LAYOUT_UNAVAILABLE"


def free_space(path=None, statvfs=os.statvfs):
    if path is None:
        path = PGDATA
    try:
        fs = statvfs(path)
        available = int(fs.f_bavail) * int(fs.f_frsize)
        if available < 0 or fs.f_frsize <= 0:
            return "SPACE_UNVERIFIED"
        if available < GIB:
            return "BELOW_1_GIB"
        if available < 4 * GIB:
            return "FROM_1_TO_4_GIB"
        if available < 16 * GIB:
            return "FROM_4_TO_16_GIB"
        return "AT_LEAST_16_GIB"
    except (OSError, ValueError, TypeError):
        return "SPACE_UNVERIFIED"


def report(project=identity, status=pg_ctl_status, ready=pg_isready_status,
           structure=original_structure, control=pg_control_snapshot,
           wal=wal_layout, tablespaces=tablespace_layout, space=free_space):
    output = {
        "M40170_PROJECT": "NOT_ATTESTED",
        "M40170_ORIGINAL_CLUSTER": "NOT_ATTESTED",
        "M40170_POSTGRES_5433": "NOT_ATTESTED",
        "M40170_PG_CONTROL": "SKIPPED",
        "M40170_WAL_FILES": "SKIPPED",
        "M40170_TABLESPACES": "SKIPPED",
        "M40170_DISK_FREE": "SKIPPED",
        "M40170_POSTGRES_FINAL": "SKIPPED",
        "M40170_PG_5433_FINAL": "SKIPPED",
        "M40170_WAL_INTEGRITY": "NOT_ATTESTED",
        "M40170_POST_MIGRATION_BACKUP": "NOT_ATTESTED",
        "M40170_BACKUP_CAPACITY": "NOT_ATTESTED",
        "M40170_PG_START_AUTHORIZED": "FALSE",
        "M40170_FASTAPI_START_AUTHORIZED": "FALSE",
    }
    p = project()
    output["M40170_PROJECT"] = p
    if p != "PASS_STATIC_ORIGINAL_FR_FINANCE_PG18":
        output["M40170_STATUS"] = "BLOCKED_WRONG_PROJECT"
        return output
    s = status()
    r = ready()
    output["M40170_ORIGINAL_CLUSTER"] = s
    output["M40170_POSTGRES_5433"] = r
    if (s != "ORIGINAL_PGDATA_PROCESS_REPORTED_STOPPED" or
            r != "PORT_5433_NO_RESPONSE"):
        output["M40170_STATUS"] = "BLOCKED_PG_MUST_BE_OFFLINE"
        return output
    if structure() != "PASS_SHALLOW_ORIGINAL_FILES_PRESENT_NOT_INTEGRITY":
        output["M40170_STATUS"] = "BLOCKED_ORIGINAL_LAYOUT"
        return output
    c = control()
    output["M40170_PG_CONTROL"] = c
    if c != "NON_CLEAN_OR_RUNNING_STATE_REPORTED":
        output["M40170_STATUS"] = "BLOCKED_CONTROL_STATE_CHANGED"
        return output
    output["M40170_WAL_FILES"] = wal()
    output["M40170_TABLESPACES"] = tablespaces()
    output["M40170_DISK_FREE"] = space()
    final_s = status()
    final_r = ready()
    output["M40170_POSTGRES_FINAL"] = final_s
    output["M40170_PG_5433_FINAL"] = final_r
    if final_s != s or final_r != r:
        state = "BLOCKED_CLUSTER_CHANGED_DURING_CHECK"
    elif output["M40170_WAL_FILES"] != "SEGMENT_FILES_PRESENT_CONTENT_NOT_VERIFIED":
        state = "BLOCKED_WAL_LAYOUT_NOT_ATTESTED"
    elif output["M40170_TABLESPACES"] != "NO_EXTERNAL_TABLESPACE_POINTERS":
        state = "BLOCKED_TABLESPACE_BACKUP_SCOPE_REVIEW"
    elif output["M40170_DISK_FREE"] in ("BELOW_1_GIB", "SPACE_UNVERIFIED"):
        state = "BLOCKED_DISK_SPACE"
    else:
        state = "BLOCKED_BACKUP_AND_CONTROLLED_RECOVERY_APPROVAL_PENDING"
    output["M40170_STATUS"] = state
    return output


def main(argv=None):
    parser = argparse.ArgumentParser(description="M40170 FR Finance offline WAL gate")
    parser.add_argument("--source-only", action="store_true")
    args = parser.parse_args(argv)
    print("=== FR FINANCE M40170 — POST ANDROID WAL PREFLIGHT ===")
    if args.source_only:
        print("M40170_SOURCE_ONLY=PASS")
        print("M40170_LIVE_CLUSTER=NOT_QUERIED")
        return 0
    if not native_termux():
        print("M40170_STATUS=BLOCKED_NOT_NATIVE_TERMUX")
        return 2
    try:
        for k, v in report().items():
            print(k + "=" + v)
        return 2
    finally:
        print("M40170_WAL_CONTENTS=NOT_READ")
        print("M40170_PRIVATE_BACKUPS=NOT_READ")
        print("M40170_DB_5432=NOT_ACCESSED")
        print("M40170_SQL_SESSIONS=NONE")
        print("M40170_DATABASE_WRITES=NONE")
        print("M40170_MIGRATIONS=NONE")
        print("M40170_PG_START_STOP=NONE")
        print("M40170_FASTAPI_START_STOP=NONE")
        print("M40170_PIX_REAL=OFF")
        print("M40170_PAGAMENTOS_REAIS=OFF")
        print("M40170_ATIVACAO_REAL=OFF")
        print("M40170_PRODUCTION=BLOCKED")


if __name__ == "__main__":
    raise SystemExit(main())
