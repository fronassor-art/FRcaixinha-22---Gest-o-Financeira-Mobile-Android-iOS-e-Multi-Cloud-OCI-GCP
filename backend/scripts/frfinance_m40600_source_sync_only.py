#!/usr/bin/env python3
"""M40600: pinned fast-forward source-only sync on native Termux.

M39800 process-origin denial remains authoritative for runtime actions.
No database, service, signal, app launch, or privileged operation.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
BRANCH = "atualizacao-ai-studio-9b46a63187"
REPO = "fronassor-art/FRcaixinha-22---Gest-o-Financeira-Mobile-Android-iOS-e-Multi-Cloud-OCI-GCP"
ALLOWED_ORIGINS = {
    "https://github.com/" + REPO,
    "https://github.com/" + REPO + ".git",
    "git@github.com:" + REPO,
    "git@github.com:" + REPO + ".git",
}
HEX40 = re.compile(r"[a-f0-9]{40}\Z")
MARKER = re.compile(r"(M39800_[A-Z0-9_]+)=([A-Z0-9_]+)\Z")
RESTRICTED_PROC = {
    "ANDROID_PROC_RESTRICTED",
    "PROC_INSPECTION_RESTRICTED",
    "OWNER_NOT_VISIBLE_ANDROID",
}


def classify_probe(rc: int, markers: dict[str, str]) -> str:
    """Only a specific Android /proc visibility denial can be advisory."""
    if markers.get("M39800_HEALTH") != "FR_FINANCE_ONLINE":
        return "BLOCKED_UNATTESTED_HEALTH"
    if (rc == 0
            and markers.get("M39800_STATUS") == "PASS_ORIGINAL_FASTAPI_OWNER_IDENTIFIED"
            and markers.get("M39800_PROCESS_ORIGIN") == "ORIGINAL_FR_FINANCE_UVICORN_PROCESS"):
        return "SOURCE_SYNC_ALLOWED_RUNTIME_OWNER_ATTESTED_AT_PROBE"
    if (rc == 2
            and markers.get("M39800_STATUS") == "BLOCKED_NO_PROCESS_PROOF"
            and markers.get("M39800_PROC") in RESTRICTED_PROC
            and markers.get("M39800_PROCESS_ORIGIN") == "AMBIGUOUS_OR_NOT_VISIBLE"):
        return "SOURCE_SYNC_ALLOWED_RUNTIME_OWNER_NOT_ATTESTED"
    return "BLOCKED_UNEXPECTED_PROCESS_RESULT"


def git(*args: str) -> str:
    result = subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                            text=True, timeout=60, check=False)
    if result.returncode != 0:
        raise RuntimeError("M40600_GIT_COMMAND_FAILED")
    return result.stdout.strip()


def native_checkout() -> bool:
    return (
        os.environ.get("PREFIX") == "/data/data/com.termux/files/usr"
        and os.environ.get("HOME") == "/data/data/com.termux/files/home"
        and Path.home() == Path("/data/data/com.termux/files/home")
        and ROOT == Path("/data/data/com.termux/files/home/fr-finance")
        and not ROOT.is_symlink()
        and not (ROOT / ".git").is_symlink()
    )


def verify_checkout(old: str) -> None:
    if not native_checkout():
        raise RuntimeError("M40600_BLOCKED_NOT_NATIVE_TERMUX")
    if git("rev-parse", "--show-toplevel") != str(ROOT):
        raise RuntimeError("M40600_BLOCKED_WRONG_WORKTREE")
    if git("branch", "--show-current") != BRANCH:
        raise RuntimeError("M40600_BLOCKED_WRONG_BRANCH")
    if git("remote", "get-url", "origin") not in ALLOWED_ORIGINS:
        raise RuntimeError("M40600_BLOCKED_WRONG_REPOSITORY")
    if git("rev-parse", "HEAD") != old:
        raise RuntimeError("M40600_BLOCKED_UNEXPECTED_HEAD")
    if git("status", "--porcelain", "--untracked-files=no"):
        raise RuntimeError("M40600_BLOCKED_DIRTY_TRACKED_FILES")


def runtime_probe() -> str:
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    result = subprocess.run(
        [sys.executable, "-B",
         str(ROOT / "backend/scripts/frfinance_m39800_running_process_origin_readonly.py")],
        cwd=ROOT, env=env, capture_output=True, text=True, timeout=25,
        check=False,
    )
    markers = {}
    for line in result.stdout.splitlines():
        match = MARKER.fullmatch(line.strip())
        if match:
            markers[match.group(1)] = match.group(2)
    decision = classify_probe(result.returncode, markers)
    print("M40600_RUNTIME_DIAGNOSTIC=" + decision)
    if not decision.startswith("SOURCE_SYNC_ALLOWED_"):
        raise RuntimeError("M40600_BLOCKED_UNEXPECTED_RUNTIME_PROBE")
    return decision


def sync(old: str, target: str) -> None:
    git("fetch", "--no-tags", "origin", BRANCH)
    if git("rev-parse", "FETCH_HEAD") != target:
        raise RuntimeError("M40600_BLOCKED_UNAPPROVED_REMOTE_COMMIT")
    # No forced moves, merges or commits, and no execution of local git hooks.
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", old, "FETCH_HEAD"],
        cwd=ROOT, capture_output=True, timeout=20, check=False,
    )
    if ancestor.returncode != 0:
        raise RuntimeError("M40600_BLOCKED_NON_FAST_FORWARD")
    git("-c", "core.hooksPath=/dev/null", "merge", "--ff-only", "FETCH_HEAD")
    if git("rev-parse", "HEAD") != target:
        raise RuntimeError("M40600_BLOCKED_POST_SYNC_SHA_MISMATCH")


def static_sql_scan() -> None:
    result = subprocess.run(
        [sys.executable, "-B",
         str(ROOT / "backend/scripts/frfinance_m40580_sql_static_guard.py")],
        cwd=ROOT, capture_output=True, text=True, timeout=20, check=False,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    if (result.returncode != 0
            or "M40580_STATUS=PASS_STATIC_LITERAL_SQL_ONLY"
            not in result.stdout.splitlines()):
        raise RuntimeError("M40600_BLOCKED_STATIC_SQL_SCAN")
    print("M40600_STATIC_SQL=PASS_SOURCE_ONLY")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Pinned source-only FR Finance fast-forward")
    parser.add_argument("--expected-old", required=True)
    parser.add_argument("--target", required=True)
    args = parser.parse_args(argv)
    print("=== FR FINANCE M40600 — SOURCE SYNC ONLY ===")
    try:
        old, target = args.expected_old, args.target
        if not HEX40.fullmatch(old) or not HEX40.fullmatch(target):
            raise RuntimeError("M40600_BLOCKED_INVALID_SHA")
        verify_checkout(old)
        decision = runtime_probe()
        sync(old, target)
        static_sql_scan()
        print("M40600_SOURCE=SYNCED")
        print("M40600_HEAD=" + target[:12])
        print("M40600_RUNTIME_OWNER=" +
              ("NOT_ATTESTED" if "NOT_ATTESTED" in decision else "ATTESTED_AT_PROBE_ONLY"))
        return 0
    except (RuntimeError, OSError, subprocess.TimeoutExpired) as exc:
        print("M40600_STATUS=" + (str(exc) if isinstance(exc, RuntimeError)
                                   else "BLOCKED_RUNTIME_ERROR"))
        return 2
    finally:
        print("M40600_PROCESS_RESTART=NONE")
        print("M40600_RUNTIME_RELOAD=NONE")
        print("M40600_DB_CONNECTIONS=NONE")
        print("M40600_DB_WRITES=NONE")
        print("M40600_MIGRATIONS=NONE")
        print("M40600_PIX_REAL=OFF")
        print("M40600_PAGAMENTOS_REAIS=OFF")
        print("M40600_ATIVACAO_REAL=OFF")
        print("M40600_PRODUCTION=BLOCKED")


if __name__ == "__main__":
    raise SystemExit(main())
