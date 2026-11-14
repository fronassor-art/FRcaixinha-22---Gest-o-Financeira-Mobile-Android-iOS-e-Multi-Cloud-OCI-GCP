#!/usr/bin/env python3
"""FR Finance M38798: stopped-PG18 full-cluster physical snapshot capacity preflight.

READ ONLY: no SQL, no PG startup/recovery, no file copies, no PID deletion.
PGDATA legacy 'frcaixinha_aistudio_pg18' belongs to FR Finance, NOT FR 2.2.
This estimates file sizes; it does NOT create or certify any usable backup.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import stat

import frfinance_m38794_project_isolation as identity
import frfinance_m38796_pg18_control_preflight as control
import frfinance_m38797_wal_storage_preflight as wal

AUTH = "AUTHORIZE_FRFINANCE_PG18_SNAPSHOT_CAPACITY_READONLY"
MAX_ENTRIES = 400000
MAX_DEPTH = 64
MIB = 1024 * 1024
GIB = 1024 * MIB
SPACE_RESERVE = 2 * GIB  # never treat this as an actual safe-to-copy authorization


class SnapshotBlocked(Exception):
    """Safe constant failure category; never expose filenames or file contents."""


def snapshot_manifest(pgdata: Path) -> tuple[int, int, int]:
    """Read only lstat/scandir, skip symlinks and block special files.

    st_size reports uncompressed logical bytes, not compressed tar size.
    Hard links are counted more than once (conservative).
    """
    if pgdata.is_symlink() or not pgdata.is_dir():
        raise SnapshotBlocked("PGDATA_INVALID_OR_LINKED")
    stack = [(pgdata, 0)]
    files = entries = links = total_bytes = 0
    while stack:
        directory, depth = stack.pop()
        if depth > MAX_DEPTH:
            raise SnapshotBlocked("DIRECTORY_DEPTH_LIMIT")
        try:
            with os.scandir(directory) as it:
                for entry in it:
                    entries += 1
                    if entries > MAX_ENTRIES:
                        raise SnapshotBlocked("FILE_COUNT_LIMIT")
                    info = entry.stat(follow_symlinks=False)
                    mode = info.st_mode
                    if stat.S_ISLNK(mode):
                        links += 1
                        continue
                    if stat.S_ISDIR(mode):
                        stack.append((Path(entry.path), depth + 1))
                    elif stat.S_ISREG(mode):
                        files += 1
                        total_bytes += info.st_size
                    else:
                        raise SnapshotBlocked("SPECIAL_FILE_REQUIRES_REVIEW")
        except (OSError, ValueError):
            raise SnapshotBlocked("METADATA_SCAN_UNAVAILABLE") from None
    return total_bytes, files, links


def _free_bytes(pgdata: Path) -> int:
    try:
        fs = os.statvfs(pgdata)
    except OSError:
        raise SnapshotBlocked("STATVFS_UNAVAILABLE") from None
    if fs.f_frsize <= 0 or fs.f_bavail < 0:
        raise SnapshotBlocked("STATVFS_INVALID")
    return fs.f_frsize * fs.f_bavail


def _bytes_mib_ceil(value: int) -> int:
    return (value + MIB - 1) // MIB


def local_audit() -> dict[str, str]:
    before = wal.local_audit()
    if (before.get("M38797_PROJECT") != "FR_FINANCE_AI_STUDIO"
            or before.get("M38797_CONTROL") != "UNCLEAN_OR_RUNNING_STATE_REPORTED"
            or before.get("M38797_RECOVERY_PERMISSION") != "NOT_GRANTED"):
        raise SnapshotBlocked("WRONG_PROJECT_OR_UNSAFE_RUNTIME")
    pgdata = Path(identity.FINANCE_PGDATA)
    if pgdata.is_symlink():
        raise SnapshotBlocked("PGDATA_SYMLINK_BLOCKED")
    total, files, symlinks = snapshot_manifest(pgdata)
    free = _free_bytes(pgdata)
    after = wal.local_audit()
    immutable = (
        "M38797_PROJECT", "M38797_PGDATA_IDENTITY", "M38797_CONTROL",
        "M38797_WAL_DIRECTORY", "M38797_TABLESPACE_POINTERS",
        "M38797_WAL_INTEGRITY", "M38797_RECOVERY_PERMISSION",
    )
    if any(before.get(k) != after.get(k) for k in immutable):
        raise SnapshotBlocked("PREFLIGHT_CHANGED_DURING_SCAN")
    if total <= 0 or files <= 0:
        raise SnapshotBlocked("EMPTY_OR_INCOMPLETE_CLUSTER")
    # Full physical-preservation copy size is conservatively planned at
    # 120% of logical sizes plus 2 GiB reserved on the destination.
    planned_bytes = (total * 6 + 4) // 5 + SPACE_RESERVE
    if symlinks:
        decision = "SYMLINKS_PRESENT_REVIEW_REQUIRED"
    elif free < planned_bytes:
        decision = "ON_DEVICE_UNCOMPRESSED_CAPACITY_INSUFFICIENT"
    else:
        decision = "ON_DEVICE_SPACE_CANDIDATE_ONLY_NO_BACKUP_APPROVAL"
    return {
        "M38798_PROJECT": "FR_FINANCE_AI_STUDIO",
        "M38798_CONTROL": "UNCLEAN_OR_RUNNING_STATE_REPORTED",
        "M38798_PGDATA_LOGICAL_MIB": str(_bytes_mib_ceil(total)),
        "M38798_PGDATA_REGULAR_FILE_COUNT": str(files),
        "M38798_PGDATA_SYMLINK_COUNT": str(symlinks),
        "M38798_DESTINATION_UNSELECTED_FREE_MIB": str(free // MIB),
        "M38798_PLANNED_CAPACITY_MIB": str(_bytes_mib_ceil(planned_bytes)),
        "M38798_CAPACITY_DECISION": decision,
        "M38798_BACKUP_CREATED": "NO",
        "M38798_BACKUP_RESTORABILITY": "NOT_ATTESTED",
        "M38798_PHYSICAL_MEDIA_DESTINATION": "NOT_SELECTED",
        "M38798_RECOVERY_PERMISSION": "NOT_GRANTED",
        "M38798_NEXT_STEP": "REVIEW_DESTINATION_AND_AUTHORIZE_PRESERVATION_SEPARATELY",
    }


def _closed() -> None:
    print("M38798_POSTGRESQL_START=NONE")
    print("M38798_PGDATA_MUTATIONS=NONE")
    print("M38798_POSTMASTER_PID_DELETE=NONE")
    print("M38798_SQL_QUERIES=NONE")
    print("M38798_FR22_ACCESS=NONE")
    print("M38798_BACKUP_CREATION=NONE")
    print("M38798_WAL_RECOVERY=NONE")
    print("M38798_MIGRATIONS=NONE")
    print("M38798_PIX_REAL=OFF")
    print("M38798_ACTIVATION_REAL=OFF")
    print("M38798_PRODUCTION=BLOCKED")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="FR Finance PG18 snapshot capacity no writes")
    parser.add_argument("mode", choices=("offline", "local"), nargs="?", default="offline")
    parser.add_argument("authorization", nargs="?")
    args = parser.parse_args(argv)
    print("=== FR FINANCE M38798 PHYSICAL PRESERVATION CAPACITY ===")
    if args.mode == "offline":
        if args.authorization is not None:
            print("M38798_AUDIT=BLOCKED_UNEXPECTED_AUTHORIZATION")
            _closed()
            return 2
        try:
            identity.manifest()
        except identity.IsolationBlocked:
            print("M38798_AUDIT=BLOCKED_MANIFEST")
            _closed()
            return 2
        print("M38798_AUDIT=OFFLINE_REFERENCE_NO_FILESYSTEM_SCAN")
        print("M38798_BACKUP_RESTORABILITY=NOT_ATTESTED")
        print("M38798_RECOVERY_PERMISSION=NOT_GRANTED")
        _closed()
        return 0
    if args.authorization != AUTH:
        print("M38798_AUDIT=BLOCKED_AUTHORIZATION_REQUIRED")
        _closed()
        return 2
    try:
        evidence = local_audit()
    except (
        identity.IsolationBlocked, control.PreflightBlocked,
        wal.StoragePreflightBlocked, SnapshotBlocked,
    ):
        print("M38798_AUDIT=BLOCKED_INCOMPLETE_EVIDENCE")
        _closed()
        return 2
    except Exception:
        print("M38798_AUDIT=BLOCKED_UNCLASSIFIED")
        _closed()
        return 2
    print("M38798_AUDIT=LOCAL_READONLY_METADATA_CAPACITY")
    for k, v in evidence.items():
        print(k + "=" + v)
    _closed()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
