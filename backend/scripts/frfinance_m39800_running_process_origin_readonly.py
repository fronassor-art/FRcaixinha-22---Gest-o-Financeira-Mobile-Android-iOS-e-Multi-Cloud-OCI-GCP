#!/usr/bin/env python3
"""FR Finance M39800 — strictly read-only origin of current port 8000 listener.

Native Termux only. Scans local /proc TCP inode + same-UID process cwd/argv.
Does not print PIDs, process arguments, environment, usernames or secrets.
Never sends signals, starts servers, alters databases or touches port 5432.
If Android restricts /proc access, FAIL CLOSED rather than assuming ownership.
"""
from __future__ import annotations

import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.app.m39700_runtime_contract import classify_health
from backend.scripts.frfinance_m39700_termux_runtime_check import (
    native_termux, read_json_loopback,
)

TCP = Path("/proc/net/tcp")
PROC = Path("/proc")
LOCAL_HEX = "0100007F:1F40"  # 127.0.0.1:8000
MAX_PROCESSES = 100000
MAX_FDS_PER_PROCESS = 4096
MAX_CMDLINE = 4096


def listening_inodes(source: str) -> set[str]:
    inodes = set()
    for row in source.splitlines()[1:]:
        cols = row.split()
        if (len(cols) >= 10 and cols[1].upper() == LOCAL_HEX
                and cols[3] == "0A" and cols[9].isdigit()):
            inodes.add(cols[9])
    return inodes


def classify_argv(argv: list[str], cwd: Path, repo: Path = ROOT) -> str:
    """Only exact expected uvicorn launcher, no broad 'python' matches."""
    if cwd != repo or cwd.is_symlink():
        return "WRONG_WORKTREE"
    if not argv or len(argv) > 24:
        return "UNRECOGNIZED_COMMAND"
    # The original run_termux_fastapi.sh execs Python, so it is not the PID.
    uvicorn_mod = any(
        argv[i:i+3] == ["-m", "uvicorn", "app.main:app"]
        for i in range(len(argv)-2)
    )
    host = any(argv[i:i+2] == ["--host", "127.0.0.1"]
               for i in range(len(argv)-1))
    port = any(argv[i:i+2] == ["--port", "8000"]
               for i in range(len(argv)-1))
    if uvicorn_mod and host and port and (
        "--reload" not in argv and "--workers" not in argv
        and not any(v.startswith("--fd") for v in argv)
    ):
        return "ORIGINAL_FR_FINANCE_UVICORN_PROCESS"
    return "UNRECOGNIZED_COMMAND"


def owners_for_inodes(inodes: set[str], proc: Path = PROC) -> tuple[list[str], str]:
    if not inodes:
        return [], "LISTEN_SOCKET_NOT_FOUND"
    try:
        entries = list(proc.iterdir())
    except (OSError, PermissionError):
        return [], "PROC_INSPECTION_RESTRICTED"
    owner_classes = []
    uid = os.getuid()
    socket_links = {"socket:[" + inode + "]" for inode in inodes}
    count = 0
    for entry in entries:
        if not entry.name.isdecimal():
            continue
        count += 1
        if count > MAX_PROCESSES:
            return [], "PROC_PROCESS_LIMIT"
        try:
            if entry.stat().st_uid != uid:
                continue
            fdroot = entry / "fd"
            matched = False
            for i, fd in enumerate(fdroot.iterdir()):
                if i >= MAX_FDS_PER_PROCESS:
                    return [], "PROC_FD_LIMIT"
                try:
                    if os.readlink(fd) in socket_links:
                        matched = True
                        break
                except (PermissionError, OSError):
                    continue
            if not matched:
                continue
            cwd = Path(os.readlink(entry / "cwd"))
            with (entry / "cmdline").open("rb") as fh:
                cmd = fh.read(MAX_CMDLINE + 1)
            if not cmd or len(cmd) > MAX_CMDLINE:
                owner_classes.append("CMDLINE_NOT_ATTESTED")
                continue
            argv = [
                a.decode("utf-8", "replace") for a in
                cmd.rstrip(b"\x00").split(b"\x00") if a
            ]
            owner_classes.append(classify_argv(argv, cwd))
        except (PermissionError, OSError, ValueError):
            continue
    if not owner_classes:
        return [], "OWNER_NOT_VISIBLE_ANDROID"
    return owner_classes, "SOCKET_OWNER_CLASSIFIED"


def review_origin() -> dict[str, str]:
    code, payload = read_json_loopback("/api/health")
    if code != 200 or classify_health(payload) != "FR_FINANCE_ONLINE":
        return {
            "M39800_HEALTH": "NOT_ATTESTED",
            "M39800_PROCESS_ORIGIN": "BLOCKED_UNKNOWN_APP",
            "M39800_STATUS": "BLOCKED_NO_PROCESS_PROOF",
        }
    try:
        inodes = listening_inodes(TCP.read_text(encoding="ascii"))
        owners, proc_status = owners_for_inodes(inodes)
    except (OSError, UnicodeError, PermissionError):
        owners, proc_status = [], "ANDROID_PROC_RESTRICTED"
    origin = (
        owners[0] if len(owners) == 1
        else "AMBIGUOUS_OR_NOT_VISIBLE"
    )
    return {
        "M39800_HEALTH": "FR_FINANCE_ONLINE",
        "M39800_PROC": proc_status,
        "M39800_PROCESS_ORIGIN": origin,
        "M39800_STATUS": (
            "PASS_ORIGINAL_FASTAPI_OWNER_IDENTIFIED"
            if origin == "ORIGINAL_FR_FINANCE_UVICORN_PROCESS"
            else "BLOCKED_NO_PROCESS_PROOF"
        ),
    }


def main() -> int:
    print("=== FR FINANCE M39800 — PROCESSO FASTAPI ORIGINAL READ ONLY ===")
    if not native_termux():
        print("M39800_STATUS=BLOCKED_NOT_NATIVE_FR_FINANCE")
        return 2
    try:
        result = review_origin()
        for name, value in result.items():
            print(name + "=" + value)
        return 0 if result["M39800_STATUS"] == (
            "PASS_ORIGINAL_FASTAPI_OWNER_IDENTIFIED") else 2
    finally:
        print("M39800_PIDS_EXPOSED=NONE")
        print("M39800_COMMANDS_EXPOSED=NONE")
        print("M39800_PROC_ENV_READ=NONE")
        print("M39800_SIGNALS=NONE")
        print("M39800_FASTAPI_RESTART=NONE")
        print("M39800_PG_5432_ACCESS=NONE")
        print("M39800_PG_5433_ACCESS=NONE")
        print("M39800_DB_WRITES=NONE")
        print("M39800_MIGRATIONS=NONE")
        print("M39800_PIX_REAL=OFF")
        print("M39800_PRODUCTION=BLOCKED")


if __name__ == "__main__":
    raise SystemExit(main())
