#!/usr/bin/env python3
"""M40110 — optional read-only ps/lsof correlation; native FR Finance Termux.

No package installation, sensitive outputs, PostgreSQL access, process signal
or restart. Missing lsof/Android restrictions fail closed.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from backend.app.m39700_runtime_contract import classify_health
from backend.scripts.frfinance_m39700_termux_runtime_check import native_termux
from backend.scripts.frfinance_m40100_safe_runtime_triage import candidate_type
from backend.scripts.frfinance_m40090_old_fastapi_diagnosis import (
    HEALTH, CHECKPOINT, MARKER, fetch_json,
)

MAX_BYTES = 131072
TIMEOUT = 4
LOOPBACK = "127.0.0.1:8000"


def own_uid_candidates(run=subprocess.run):
    command = ["ps", "-u", str(os.getuid()), "-o", "pid=,args="]
    try:
        cp = run(command, capture_output=True, timeout=TIMEOUT, check=False)
        if cp.returncode or len(cp.stdout) > MAX_BYTES or len(cp.stderr) > MAX_BYTES:
            return set(), "PS_NOT_ATTESTED"
        lines = cp.stdout.decode("utf-8", "strict").splitlines()
    except (OSError, UnicodeError, AttributeError, subprocess.SubprocessError):
        return set(), "PS_NOT_ATTESTED"
    pids = set()
    for line in lines:
        parts = line.strip().split(maxsplit=1)
        if len(parts) != 2 or not parts[0].isdigit():
            continue
        pid = int(parts[0])
        if not (1 <= pid <= 2147483647):
            continue
        if candidate_type(parts[1]) == "SAME_UID_UVICORN_COMMAND_CANDIDATE":
            pids.add(pid)
        if len(pids) > 16:
            return set(), "PS_AMBIGUOUS"
    return pids, ("PS_ONE_CANDIDATE" if len(pids)==1 else
                  "PS_AMBIGUOUS_OR_NOT_VISIBLE")


def parse_lsof(raw: bytes):
    if len(raw) > MAX_BYTES:
        return set(), "LSOF_UNVERIFIED"
    try:
        lines = raw.decode("utf-8", "strict").splitlines()
    except UnicodeError:
        return set(), "LSOF_UNVERIFIED"
    active = None
    names = []
    matched = set()
    for line in lines:
        if not line:
            continue
        kind, value = line[0], line[1:]
        if kind == "p":
            if not value.isdigit() or not (1 <= int(value) <= 2147483647):
                return set(), "LSOF_UNVERIFIED"
            active = int(value)
        elif kind == "n":
            if active is None:
                return set(), "LSOF_UNVERIFIED"
            names.append(value)
            if value == LOOPBACK:
                matched.add(active)
        elif kind not in "fcDtP":
            return set(), "LSOF_UNVERIFIED"
    if not names:
        return set(), "LSOF_NO_LISTENER_ATTESTED"
    if any(name != LOOPBACK for name in names):
        return set(), "LSOF_NON_LOOPBACK_OR_IPV6_REVIEW"
    if len(matched) != 1:
        return set(), "LSOF_AMBIGUOUS"
    return matched, "LSOF_SINGLE_LOOPBACK_LISTENER"


def lsof_listeners(which=shutil.which, run=subprocess.run):
    binary = which("lsof")
    if not binary or not Path(binary).is_file():
        return set(), "LSOF_NOT_INSTALLED_NO_INSTALL"
    try:
        cp = run([binary, "-nP", "-a", "-iTCP:8000", "-sTCP:LISTEN", "-Fpn"],
                 capture_output=True, timeout=TIMEOUT, check=False)
        if cp.returncode or len(cp.stderr)>MAX_BYTES or len(cp.stdout)>MAX_BYTES:
            return set(), "LSOF_UNAVAILABLE_OR_ANDROID_RESTRICTED"
        return parse_lsof(cp.stdout)
    except (OSError, subprocess.SubprocessError):
        return set(), "LSOF_UNAVAILABLE_OR_ANDROID_RESTRICTED"


def exact_worktree(pid, readlink=os.readlink):
    try:
        cwd = Path(readlink(f"/proc/{pid}/cwd"))
    except (OSError, ValueError, PermissionError):
        return "WORKTREE_ANDROID_RESTRICTED"
    if cwd == ROOT and not ROOT.is_symlink():
        return "EXACT_FR_FINANCE_WORKTREE"
    return "WORKTREE_DIFFERENT_OR_UNVERIFIED"


def correlate(candidates=own_uid_candidates, listeners=lsof_listeners,
              worktree=exact_worktree):
    ps_ids, ps_state = candidates()
    if len(ps_ids)!=1:
        return {"M40110_PS":ps_state, "M40110_LSOF":"SKIPPED_NO_UNIQUE_PS",
                "M40110_MATCH":"NOT_ATTESTED","M40110_WORKTREE":"NOT_ATTESTED"}
    tcp_ids, tcp_state = listeners()
    if len(tcp_ids)!=1 or tcp_ids!=ps_ids:
        return {"M40110_PS":ps_state, "M40110_LSOF":tcp_state,
                "M40110_MATCH":"NOT_ATTESTED","M40110_WORKTREE":"NOT_ATTESTED"}
    return {"M40110_PS":ps_state,"M40110_LSOF":tcp_state,
            "M40110_MATCH":"SAME_UID_COMMAND_AND_LOOPBACK_LISTENER_CORRELATED",
            "M40110_WORKTREE":worktree(next(iter(tcp_ids)))}


def report(fetch=fetch_json, link=correlate):
    before, health = fetch(HEALTH)
    if before!=200 or classify_health(health)!="FR_FINANCE_ONLINE":
        return {"M40110_STATUS":"BLOCKED_UNKNOWN_API"}
    checkpoint,_ = fetch(CHECKPOINT)
    marker,_ = fetch(MARKER)
    after, health = fetch(HEALTH)
    if after!=200 or classify_health(health)!="FR_FINANCE_ONLINE":
        return {"M40110_STATUS":"BLOCKED_IDENTITY_CHANGED"}
    try:
        evidence=link()
    except (OSError, ValueError, PermissionError):
        evidence={"M40110_PS":"NOT_ATTESTED","M40110_LSOF":"NOT_ATTESTED",
                  "M40110_MATCH":"NOT_ATTESTED","M40110_WORKTREE":"NOT_ATTESTED"}
    complete=(evidence.get("M40110_MATCH")==
              "SAME_UID_COMMAND_AND_LOOPBACK_LISTENER_CORRELATED" and
              evidence.get("M40110_WORKTREE")=="EXACT_FR_FINANCE_WORKTREE")
    return {"M40110_HTTP_IDENTITY":"FR_FINANCE_ONLINE_DOUBLE_CHECKED",
            "M40110_CHECKPOINT":("HTTP_404" if checkpoint==404 else "NOT_404"),
            "M40110_MARKER":("HTTP_404" if marker==404 else "NOT_404"),
            **evidence,
            "M40110_PROCESS_EVIDENCE":(
                "CORRELATED_READONLY_NOT_EXECUTABLE_ATTESTATION"
                if complete else "INSUFFICIENT"),
            "M40110_RESTART_AUTHORIZED":"FALSE",
            "M40110_STATUS":(
                "PASS_READONLY_CORRELATION_NO_RESTART_PERMISSION"
                if complete else "BLOCKED_OWNER_NOT_ATTESTED")}


def main(argv=None):
    parser=argparse.ArgumentParser(description="M40110 native Termux only")
    parser.add_argument("--source-only",action="store_true")
    args=parser.parse_args(argv)
    print("=== FR FINANCE M40110 — LOCAL OWNER CORRELATION ===")
    if args.source_only:
        print("M40110_SOURCE_ONLY=PASS")
        print("M40110_RUNTIME=NOT_ATTESTED")
        return 0
    if not native_termux():
        print("M40110_STATUS=BLOCKED_NOT_NATIVE_TERMUX")
        return 2
    try:
        results=report()
        for key,val in results.items():
            print(key+"="+val)
        return 0 if results["M40110_STATUS"]==(
            "PASS_READONLY_CORRELATION_NO_RESTART_PERMISSION") else 2
    finally:
        print("M40110_DIAGNOSTIC_SUBPROCESSES=PS_AND_OPTIONAL_LSOF_ONLY")
        print("M40110_PIDS_ARGS_PATHS_DISCLOSED=NONE")
        print("M40110_SERVICE_START_STOP=NONE")
        print("M40110_FASTAPI_RESTART=NONE")
        print("M40110_DATABASE_CONNECTIONS=NONE")
        print("M40110_LOCAL_DB_WRITES=NONE")
        print("M40110_MIGRATIONS=NONE")
        print("M40110_PIX_REAL=OFF")
        print("M40110_PRODUCTION=BLOCKED")

if __name__=="__main__":
    raise SystemExit(main())
