#!/usr/bin/env python3
"""FR Finance M38995: read-only preflight for ORIGINAL API and prior Brevo intake.

The purpose is to avoid repeating completed provider setup. No config, project,
database, directory, file, VM, SMTP message, or user is created or modified.
Never reveal SMTP login, DSN, keys, addresses, provider JSON or secret values.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import stat
import subprocess
from urllib.request import urlopen
from urllib.error import URLError, HTTPError

HOME = Path.home()
PROJECT = HOME / "fr-finance"
CONFIG = HOME / ".config/frcaixinha-aistudio-mobile/api.env"
PUBLIC = HOME / ".config/frfinance-aistudio/provider-public-inputs.json"
MAX_PRIVATE_BYTES = 65536
EXPECTED_BRANCH = "atualizacao-ai-studio-9b46a63187"
ROUTES = {
    "RESET_PASSWORD": "/api/v1/auth/reset-password",
    "VERIFY_INVITATION": "/api/v1/invitations/verify-email",
    "ISSUE_INVITATION": "/api/v1/invitations/submit",
}
PUBLIC_KEYS = ("APP_URL", "SMTP_HOST", "SMTP_PORT", "SMTP_USER", "FR_FINANCE_EMAIL_FROM")
PRIVATE_KEYS = (
    "AUTH_DATABASE_URL", "APP_URL", "SMTP_HOST", "SMTP_PORT", "SMTP_USER",
    "SMTP_PASSWORD", "FR_FINANCE_EMAIL_FROM",
    "FR_FINANCE_ACCESS_ENCRYPTION_KEY_B64", "FR_FINANCE_ACCESS_HMAC_KEY",
    "FR_FINANCE_ACCESS_MAIL_ENABLE", "FR_FINANCE_OUTBOX_047_VERIFIED",
    "FR_FINANCE_ACCESS_REDEMPTION_048_VERIFIED",
    "FR_FINANCE_SMTP_OPERATOR_APPROVED", "FR_FINANCE_ACCESS_MAIL_WORKER",
)
_ENV_LINE = re.compile(r"^\s*(?:export\s+)?([A-Z][A-Z0-9_]*)\s*=(.*)$")


def _protected_file(path: Path) -> bool:
    """Refuse symlinks, non-owner private config, large or world-readable files."""
    if path.is_symlink():
        return False
    try:
        info = path.stat()
    except OSError:
        return False
    return (stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid()
            and (stat.S_IMODE(info.st_mode) & 0o077) == 0
            and 0 < info.st_size <= MAX_PRIVATE_BYTES)


def _declared(path: Path) -> tuple[str, set[str]]:
    if not _protected_file(path):
        return "UNAVAILABLE_OR_UNPROTECTED", set()
    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return "UNREADABLE", set()
    values = set()
    for line in content.splitlines():
        match = _ENV_LINE.fullmatch(line)
        if match:
            # Only detect variable names. Never parse/print credential values.
            values.add(match.group(1))
    return "READABLE_REDACTED", values


def _public_intake(path: Path) -> tuple[str, set[str]]:
    if not _protected_file(path):
        return "UNAVAILABLE_OR_UNPROTECTED", set()
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
        fields = obj.get("public_inputs") if type(obj) is dict else None
        if type(fields) is not dict:
            return "INVALID_PUBLIC_INTAKE", set()
        return "READABLE_REDACTED", {
            key for key, val in fields.items()
            if type(key) is str and type(val) is str and val.strip()
        }
    except (ValueError, UnicodeError, OSError):
        return "INVALID_PUBLIC_INTAKE", set()


def _local_paths() -> tuple[str, set[str]]:
    try:
        with urlopen("http://127.0.0.1:8000/openapi.json", timeout=3) as r:
            obj = json.load(r)
            if r.status != 200 or type(obj) is not dict:
                return "NOT_ATTESTED", set()
            paths = obj.get("paths")
            if type(paths) is not dict:
                return "NOT_ATTESTED", set()
            return "ONLINE", set(paths)
    except (OSError, ValueError, URLError, HTTPError, TimeoutError):
        return "UNAVAILABLE", set()


def report() -> dict[str, str]:
    statuses: dict[str, str] = {}
    if not PROJECT.is_dir() or PROJECT.is_symlink():
        return {"M38995_PROJECT": "BLOCKED_WRONG_OR_MISSING_ORIGINAL"}
    # Read only the branch name of the ORIGINAL worktree; never git reset.
    try:
        branch = subprocess.run(
            ("git", "-C", str(PROJECT), "branch", "--show-current"),
            capture_output=True, text=True, timeout=5, check=True,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        branch = ""
    if branch != EXPECTED_BRANCH:
        return {"M38995_PROJECT": "BLOCKED_WRONG_BRANCH_OR_WORKTREE"}
    statuses["M38995_PROJECT"] = "ORIGINAL_FR_FINANCE_BRANCH"
    config_status, declared = _declared(CONFIG)
    public_status, public_fields = _public_intake(PUBLIC)
    statuses["M38995_API_ENV"] = config_status
    statuses["M38995_PRIOR_PUBLIC_INTAKE"] = public_status
    for key in PRIVATE_KEYS:
        statuses["M38995_ENV_" + key] = "DECLARED" if key in declared else "ABSENT"
    for key in PUBLIC_KEYS:
        statuses["M38995_INTAKE_" + key] = (
            "ALREADY_REGISTERED" if key in public_fields else "NOT_REGISTERED_HERE"
        )
    status, paths = _local_paths()
    statuses["M38995_ORIGINAL_FASTAPI"] = status
    for name, path in ROUTES.items():
        statuses["M38995_ROUTE_" + name] = (
            "LOADED" if path in paths else "NOT_LOADED_OR_NOT_EXPOSED"
        )
    statuses["M38995_EMAIL_REAL"] = "UNCHANGED_NO_SEND"
    statuses["M38995_PIX_REAL"] = "UNCHANGED_OFF"
    statuses["M38995_SQL_MIGRATIONS"] = "NONE"
    statuses["M38995_DATABASE_MUTATIONS"] = "NONE"
    statuses["M38995_CONFIG_MUTATIONS"] = "NONE"
    statuses["M38995_SECRET_VALUES_PRINTED"] = "NONE"
    statuses["M38995_PRODUCTION"] = "NOT_AUTHORIZED_BY_THIS_DIAGNOSTIC"
    return statuses


def main() -> int:
    print("=== FR FINANCE M38995 - EXISTING ACCESS RUNTIME READ ONLY ===")
    for key, value in report().items():
        print(f"{key}={value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
