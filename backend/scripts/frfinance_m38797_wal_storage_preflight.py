#!/usr/bin/env python3
"""FR Finance M38797: read-only WAL layout / storage health review.

Preconditions: prior checks attest the FR Finance repository / PGDATA identity,
stopped PID, no listener on 5433, and pg_control 'in production'. This program
DOES NOT restore, copy, start, migrate, remove PID files, or read financial data.
Presence of WAL segments is NOT evidence that WAL is valid or sufficient.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import re

import frfinance_m38794_project_isolation as identity
import frfinance_m38795_pg18_runtime_probe as runtime
import frfinance_m38796_pg18_control_preflight as control

AUTH = "AUTHORIZE_FRFINANCE_PG18_WAL_STORAGE_READONLY"
MAX_WAL_ENTRIES = 4096
MAX_TABLESPACE_ENTRIES = 512
WAL_SEGMENT_NAME = re.compile(r"[0-9A-F]{24}")


class StoragePreflightBlocked(Exception):
    """Categorical failure, no filesystem paths or raw exceptions printed."""


def wal_directory_state(pgdata: Path) -> str:
    wal = pgdata / "pg_wal"
    if wal.is_symlink():
        raise StoragePreflightBlocked("PG_WAL_LINK_REQUIRES_MANUAL_REVIEW")
    if not wal.is_dir():
        raise StoragePreflightBlocked("PG_WAL_DIRECTORY_MISSING")
    seen_segment = False
    total = 0
    try:
        with os.scandir(wal) as iterator:
            for entry in iterator:
                total += 1
                if total > MAX_WAL_ENTRIES:
                    raise StoragePreflightBlocked("PG_WAL_SCAN_LIMIT_REACHED")
                if WAL_SEGMENT_NAME.fullmatch(entry.name) and entry.is_file(follow_symlinks=False):
                    seen_segment = True
    except OSError:
        raise StoragePreflightBlocked("PG_WAL_READ_UNAVAILABLE") from None
    return ("SEGMENT_FILES_OBSERVED_UNVERIFIED" if seen_segment
            else "NO_SEGMENT_FILES_OBSERVED_REVIEW")


def tablespace_pointer_state(pgdata: Path) -> str:
    tablespaces = pgdata / "pg_tblspc"
    if tablespaces.is_symlink() or not tablespaces.is_dir():
        raise StoragePreflightBlocked("TABLESPACE_DIRECTORY_UNAVAILABLE")
    links = False
    total = 0
    try:
        with os.scandir(tablespaces) as iterator:
            for entry in iterator:
                total += 1
                if total > MAX_TABLESPACE_ENTRIES:
                    raise StoragePreflightBlocked("TABLESPACE_SCAN_LIMIT_REACHED")
                if entry.is_symlink():
                    links = True
    except OSError:
        raise StoragePreflightBlocked("TABLESPACE_READ_UNAVAILABLE") from None
    return ("EXTERNAL_POINTERS_PRESENT_MANUAL_BACKUP_REVIEW" if links
            else "NO_EXTERNAL_POINTERS_OBSERVED")


def storage_space_bucket(pgdata: Path) -> str:
    try:
        stat = os.statvfs(pgdata)
    except OSError:
        raise StoragePreflightBlocked("STORAGE_SPACE_UNAVAILABLE") from None
    if stat.f_frsize <= 0 or stat.f_bavail < 0:
        raise StoragePreflightBlocked("STORAGE_SPACE_INVALID")
    available = stat.f_frsize * stat.f_bavail
    gib = 1024 ** 3
    if available < gib:
        return "LESS_THAN_1_GIB"
    if available < 4 * gib:
        return "FROM_1_TO_4_GIB"
    if available < 16 * gib:
        return "FROM_4_TO_16_GIB"
    return "AT_LEAST_16_GIB"


def local_audit() -> dict[str, str]:
    # Fully repeats M38796 isolated project / stopped process / control checks.
    evidence = control.local_audit()
    if evidence.get("M38796_PROJECT") != "FR_FINANCE_AI_STUDIO":
        raise StoragePreflightBlocked("WRONG_PROJECT")
    if evidence.get("M38796_PG_CONTROL_STATE") != "UNCLEAN_OR_RUNNING_STATE_REPORTED":
        raise StoragePreflightBlocked("PG_CONTROL_STATE_CHANGED_REVIEW")
    if evidence.get("M38796_OPERATION_ALLOWED") != "NONE":
        raise StoragePreflightBlocked("UNEXPECTED_OPERATION_AUTHORIZATION")
    pgdata = Path(identity.FINANCE_PGDATA)
    if pgdata.is_symlink():
        raise StoragePreflightBlocked("PGDATA_LINK_BLOCKED")
    wal_state = wal_directory_state(pgdata)
    tablespace_state = tablespace_pointer_state(pgdata)
    space = storage_space_bucket(pgdata)
    # Reverify stopped state and the same pg_control status after file reads.
    again = control.local_audit()
    for field in (
        "M38796_PROJECT", "M38796_PROCESS", "M38796_PORT_5433",
        "M38796_POSTMASTER_PID", "M38796_PG_CONTROL_STATE",
        "M38796_OPERATION_ALLOWED",
    ):
        if again.get(field) != evidence.get(field):
            raise StoragePreflightBlocked("STATE_CHANGED_DURING_INSPECTION")
    return {
        "M38797_PROJECT": "FR_FINANCE_AI_STUDIO",
        "M38797_PGDATA_IDENTITY": "FR_FINANCE_PG18_ONLY",
        "M38797_CONTROL": "UNCLEAN_OR_RUNNING_STATE_REPORTED",
        "M38797_WAL_DIRECTORY": wal_state,
        "M38797_TABLESPACE_POINTERS": tablespace_state,
        "M38797_STORAGE_FREE": space,
        "M38797_WAL_INTEGRITY": "NOT_ATTESTED",
        "M38797_RESTORABLE_BACKUP": "NOT_ATTESTED",
        "M38797_RECOVERY_PERMISSION": "NOT_GRANTED",
        "M38797_NEXT_STEP": "PRESERVATION_AND_BACKUP_PLAN_REQUIRED",
    }


def _safety() -> None:
    print("M38797_FR22_ACCESS=NONE")
    print("M38797_PG_START_STOP=NONE")
    print("M38797_POSTMASTER_PID_DELETE=NONE")
    print("M38797_PG_WAL_MUTATIONS=NONE")
    print("M38797_PG_CONTROL_MUTATIONS=NONE")
    print("M38797_PG_DUMP_RESTORE=NONE")
    print("M38797_BACKUP_CREATION=NONE")
    print("M38797_SQL_MIGRATIONS=NONE")
    print("M38797_PIX_REAL=OFF")
    print("M38797_ACTIVATION_REAL=OFF")
    print("M38797_PRODUCTION=BLOCKED")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="FR Finance WAL layout/readiness only")
    parser.add_argument("mode", choices=("offline", "local"), nargs="?", default="offline")
    parser.add_argument("authorization", nargs="?")
    args = parser.parse_args(argv)
    print("=== FR FINANCE M38797 PG18 WAL STORAGE PRECHECK ===")
    if args.mode == "offline":
        if args.authorization is not None:
            print("M38797_AUDIT=BLOCKED_UNEXPECTED_AUTHORIZATION")
            _safety()
            return 2
        try:
            identity.manifest()
        except identity.IsolationBlocked:
            print("M38797_AUDIT=BLOCKED_MANIFEST")
            _safety()
            return 2
        print("M38797_AUDIT=OFFLINE_REFERENCE")
        print("M38797_WAL_INTEGRITY=NOT_ATTESTED")
        print("M38797_RESTORABLE_BACKUP=NOT_ATTESTED")
        _safety()
        return 0
    if args.authorization != AUTH:
        print("M38797_AUDIT=BLOCKED_AUTHORIZATION_REQUIRED")
        _safety()
        return 2
    try:
        evidence = local_audit()
    except (identity.IsolationBlocked, runtime.ProbeBlocked,
            control.PreflightBlocked, StoragePreflightBlocked):
        print("M38797_AUDIT=BLOCKED_INCOMPLETE_EVIDENCE")
        _safety()
        return 2
    except Exception:
        print("M38797_AUDIT=BLOCKED_UNCLASSIFIED")
        _safety()
        return 2
    print("M38797_AUDIT=LOCAL_READONLY_WAL_LAYOUT")
    for name, value in evidence.items():
        print(name + "=" + value)
    _safety()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
