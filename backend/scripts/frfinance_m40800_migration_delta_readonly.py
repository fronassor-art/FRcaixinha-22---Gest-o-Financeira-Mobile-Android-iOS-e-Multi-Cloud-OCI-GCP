#!/usr/bin/env python3
"""M40800: fail-closed local delta migration classifier, Git only, no SQL/DB.

Run ONLY after successful M40600 source-only sync, in native Termux.
This command NEVER applies migrations, connects to PG or restarts a service.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]
BRANCH = "atualizacao-ai-studio-9b46a63187"
HEX40 = re.compile(r"[0-9a-f]{40}\Z")
REPO = "fronassor-art/FRcaixinha-22---Gest-o-Financeira-Mobile-Android-iOS-e-Multi-Cloud-OCI-GCP"
ORIGINS = {
    "https://github.com/" + REPO,
    "https://github.com/" + REPO + ".git",
    "git@github.com:" + REPO,
    "git@github.com:" + REPO + ".git",
}

def needs_independent_migration_review(path: str) -> bool:
    return (
        path == "backend/migration_catalog_ai_studio.json"
        or path.startswith((
            "backend/migrations/", "backend/local_migrations/",
            "backend/staging_migrations/", "backend/ci_migrations/",
        ))
        or path.startswith("backend/") and path.endswith(".sql")
        or path in {
            "backend/scripts/aistudio_local_migration.sh",
            "backend/scripts/aistudio_db_local.sh",
            "backend/scripts/aistudio_migration_inventory.py",
        }
    )

def git(*args: str) -> str:
    p = subprocess.run(["git", *args], cwd=ROOT, text=True,
                       capture_output=True, check=False, timeout=30)
    if p.returncode != 0:
        raise ValueError("M40800_GIT_CHECK_DENIED")
    return p.stdout.strip()

def verify(old: str, target: str) -> None:
    if not HEX40.fullmatch(old) or not HEX40.fullmatch(target):
        raise ValueError("M40800_INVALID_COMMIT")
    if (os.environ.get("PREFIX") != "/data/data/com.termux/files/usr"
            or os.environ.get("HOME") != "/data/data/com.termux/files/home"
            or ROOT != Path("/data/data/com.termux/files/home/fr-finance")
            or ROOT.is_symlink() or (ROOT / ".git").is_symlink()):
        raise ValueError("M40800_NATIVE_TERMUX_REQUIRED")
    if (git("rev-parse", "--show-toplevel") != str(ROOT)
            or git("branch", "--show-current") != BRANCH
            or git("rev-parse", "HEAD") != target
            or git("remote", "get-url", "origin") not in ORIGINS
            or git("status", "--porcelain", "--untracked-files=no")):
        raise ValueError("M40800_WRONG_WORKTREE_OR_SHA")
    p = subprocess.run(["git", "merge-base", "--is-ancestor", old, target],
                       cwd=ROOT, capture_output=True, check=False, timeout=15)
    if p.returncode != 0:
        raise ValueError("M40800_NON_FAST_FORWARD_HISTORY")

def scan(old: str, target: str) -> list[str]:
    # Diff is read-only; no checkout, fetch, reset, database or network.
    names = git("diff", "--name-only", old, target, "--", "backend")
    return sorted(x for x in names.splitlines()
                  if needs_independent_migration_review(x))

def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-old", required=True)
    parser.add_argument("--target", required=True)
    args = parser.parse_args(argv)
    try:
        verify(args.expected_old, args.target)
        sensitive = scan(args.expected_old, args.target)
        if sensitive:
            print("M40800_MIGRATION_REVIEW=REQUIRED")
            print("M40800_SENSITIVE_FILE_COUNT=" + str(len(sensitive)))
            return 2
        print("M40800_MIGRATION_REVIEW=NO_SCHEMA_DELTA_IN_SYNC_RANGE")
        print("M40800_SENSITIVE_FILE_COUNT=0")
        return 0
    except (ValueError, OSError, subprocess.TimeoutExpired) as exc:
        print("M40800_STATUS=BLOCKED_" + type(exc).__name__)
        return 2
    finally:
        print("M40800_DB_CONNECTIONS=NONE")
        print("M40800_DB_WRITES=NONE")
        print("M40800_MIGRATIONS=NONE")
        print("M40800_SERVICE_RESTARTS=NONE")
        print("M40800_PIX_REAL=OFF")
        print("M40800_PAGAMENTOS_REAIS=OFF")
        print("M40800_ATIVACAO_REAL=OFF")
        print("M40800_PRODUCTION=BLOCKED")

if __name__ == "__main__":
    raise SystemExit(main())
