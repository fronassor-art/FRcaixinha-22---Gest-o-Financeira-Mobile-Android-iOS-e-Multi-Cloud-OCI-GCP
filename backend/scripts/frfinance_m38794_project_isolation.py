#!/usr/bin/env python3
"""FR Finance M38794: audit identities ONLY. No PostgreSQL start or connection.

The old 'aistudio' PGDATA name is intentional for FR Finance, never FR 2.2.
This utility never modifies a file, starts/stops PostgreSQL, or reads secrets.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "backend/config/frfinance_project_identity.json"
FINANCE_REPO = (
    "fronassor-art/FRcaixinha-22---Gest-o-Financeira-Mobile-Android-iOS-e-Multi-Cloud-OCI-GCP"
)
FINANCE_BRANCH = "atualizacao-ai-studio-9b46a63187"
FINANCE_PGDATA = "/data/data/com.termux/files/usr/var/lib/frcaixinha_aistudio_pg18"
FR22_PGDATA = "/data/data/com.termux/files/usr/var/lib/frcaixinha_2_2_pg18"
FINANCE_DB = "frcaixinha_aistudio_dev"
FR22_DB = "frcaixinha_2_2_dev"
FINANCE_OWNER = "frc_ai_owner"
FR22_OWNER = "frc22_owner"


class IsolationBlocked(Exception):
    """Fail closed, without showing private local file or process contents."""


def manifest() -> dict:
    try:
        payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
        finance = payload["active_project"]
        other = payload["excluded_project"]
        a, b = finance["postgresql"], other["postgresql"]
    except (OSError, ValueError, KeyError, TypeError):
        raise IsolationBlocked("M38794_MANIFEST_INVALID") from None
    if not (
        payload.get("schema") == "FR_FINANCE_PROJECT_ISOLATION_V1"
        and payload.get("never_start_server_from_project_identity") is True
        and payload.get("never_cross_connect_to_excluded_project") is True
        and payload.get("never_apply_migrations_during_preflight") is True
        and payload.get("production_authorized") is False
        and finance.get("id") == "FR_FINANCE_AI_STUDIO"
        and finance.get("repository") == FINANCE_REPO
        and finance.get("branch") == FINANCE_BRANCH
        and finance.get("termux_worktree") == "fr-finance"
        and a == {
            "host": "127.0.0.1", "port": 5433, "major_version": 18,
            "pgdata": FINANCE_PGDATA, "database": FINANCE_DB,
            "owner": FINANCE_OWNER
        }
        and other.get("id") == "FR_CAIXINHA_2_2"
        and other.get("repository") == "fronassor-art/FRcaixinha-2.2"
        and other.get("termux_worktree") == "FRcaixinha_2.2"
        and b == {
            "host": "127.0.0.1", "port": 5432, "major_version": 18,
            "pgdata": FR22_PGDATA, "database": FR22_DB,
            "owner": FR22_OWNER
        }
        and FINANCE_PGDATA != FR22_PGDATA
    ):
        raise IsolationBlocked("M38794_PROJECT_IDENTITY_DRIFT")
    return payload


def _git_output(*args: str) -> str:
    try:
        cp = subprocess.run(
            ["git", "-C", str(ROOT), *args],
            capture_output=True, text=True, timeout=8, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        raise IsolationBlocked("M38794_GIT_UNAVAILABLE") from None
    if cp.returncode != 0:
        raise IsolationBlocked("M38794_GIT_INVALID")
    return cp.stdout.strip()


def _repository_of_origin(origin: str) -> str | None:
    # No local/remote shell execution, no URL lookup; parse a fixed syntax.
    if not isinstance(origin, str):
        return None
    match = re.fullmatch(
        r"(?:https://github[.]com/|git@github[.]com:)"
        r"([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)(?:[.]git)?/?", origin,
    )
    return match.group(1) if match else None


def _assert_finance_worktree(home: Path) -> None:
    expected = (home / "fr-finance").resolve(strict=False)
    if ROOT != expected or not ROOT.is_dir():
        raise IsolationBlocked("M38794_WORKTREE_MISMATCH")
    if _git_output("rev-parse", "--show-toplevel") != str(ROOT):
        raise IsolationBlocked("M38794_GIT_ROOT_MISMATCH")
    if _repository_of_origin(_git_output("remote", "get-url", "origin")) != FINANCE_REPO:
        raise IsolationBlocked("M38794_REMOTE_MISMATCH")
    if _git_output("branch", "--show-current") != FINANCE_BRANCH:
        raise IsolationBlocked("M38794_BRANCH_MISMATCH")


def _read_pidfile(pgdata: Path) -> str:
    pidfile = pgdata / "postmaster.pid"
    if pidfile.is_symlink():
        raise IsolationBlocked("M38794_PIDFILE_SYMLINK_BLOCKED")
    if not pidfile.exists():
        return "ABSENT_NO_RUNNING_ASSERTION"
    try:
        lines = pidfile.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError):
        raise IsolationBlocked("M38794_PIDFILE_UNREADABLE") from None
    if len(lines) < 6:
        raise IsolationBlocked("M38794_PIDFILE_INVALID")
    if not (lines[0].strip().isdigit()
            and int(lines[0]) > 0
            and lines[1].strip() == FINANCE_PGDATA
            and lines[3].strip() == "5433"):
        raise IsolationBlocked("M38794_PIDFILE_IDENTITY_MISMATCH")
    # A PID file alone cannot prove that a PostgreSQL process is alive.
    return "EXPECTED_PATH_AND_PORT_UNVERIFIED_PROCESS"


def inspect_local(home: Path) -> dict[str, str]:
    manifest()
    _assert_finance_worktree(home)
    finance = Path(FINANCE_PGDATA)
    other = Path(FR22_PGDATA)
    if finance.is_symlink() or other.is_symlink():
        raise IsolationBlocked("M38794_PGDATA_SYMLINK_BLOCKED")
    if not finance.is_dir():
        raise IsolationBlocked("M38794_FINANCE_PGDATA_MISSING")
    try:
        version = (finance / "PG_VERSION")
        if version.is_symlink() or version.read_text(encoding="ascii").strip() != "18":
            raise IsolationBlocked("M38794_FINANCE_PG18_MISMATCH")
    except (OSError, UnicodeError):
        raise IsolationBlocked("M38794_FINANCE_PG18_UNREADABLE") from None
    if other.is_dir() and finance.samefile(other):
        raise IsolationBlocked("M38794_DATA_DIRECTORIES_OVERLAP")
    return {
        "M38794_GIT_IDENTITY": "FR_FINANCE_AI_STUDIO",
        "M38794_PGDATA_IDENTITY": "FR_FINANCE_AI_STUDIO_PG18",
        "M38794_PGDATA_VERSION": "18",
        "M38794_PGDATA_2_2": "SEPARATE_DIRECTORY_PRESENT" if other.is_dir() else "NOT_PRESENT",
        "M38794_PG_PIDFILE": _read_pidfile(finance),
        "M38794_LIVE_SERVER_IDENTITY": "NOT_ATTESTED",
    }


def _safety() -> None:
    print("M38794_POSTGRESQL_START=NONE")
    print("M38794_POSTGRESQL_STOP=NONE")
    print("M38794_POSTGRESQL_CONNECTIONS=NONE")
    print("M38794_DATABASE_MUTATIONS=NONE")
    print("M38794_MIGRATIONS=NONE")
    print("M38794_PIX_REAL=OFF")
    print("M38794_REAL_ACTIVATION=OFF")
    print("M38794_PRODUCTION=BLOCKED")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="FR Finance vs FR 2.2 identity: no writes")
    parser.add_argument("mode", choices=("reference", "inspect"), nargs="?", default="reference")
    args = parser.parse_args(argv)
    print("=== FR FINANCE M38794 PROJECT ISOLATION ===")
    try:
        manifest()
        print("M38794_REFERENCE_PROJECT=FR_FINANCE_AI_STUDIO")
        print("M38794_REFERENCE_DATABASE=" + FINANCE_DB)
        print("M38794_REFERENCE_PORT=5433")
        print("M38794_REFERENCE_PGDATA_NAME=frcaixinha_aistudio_pg18")
        print("M38794_EXCLUDED_PROJECT=FR_CAIXINHA_2_2")
        print("M38794_EXCLUDED_DATABASE=" + FR22_DB)
        print("M38794_EXCLUDED_PORT=5432")
        print("M38794_EXCLUDED_PGDATA_NAME=frcaixinha_2_2_pg18")
        if args.mode == "inspect":
            evidence = inspect_local(Path.home())
            for key, value in evidence.items():
                print(key + "=" + value)
            print("M38794_PROJECT_SEPARATION=PASS_STATIC")
        else:
            print("M38794_PROJECT_SEPARATION=REFERENCE_ONLY")
            print("M38794_LIVE_SERVER_IDENTITY=NOT_ATTESTED")
    except IsolationBlocked as exc:
        print("M38794_PROJECT_SEPARATION=BLOCKED")
        print("M38794_CAUSE=" + str(exc))
        _safety()
        return 2
    _safety()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
