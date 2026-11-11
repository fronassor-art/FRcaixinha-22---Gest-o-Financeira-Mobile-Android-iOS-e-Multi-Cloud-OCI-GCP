#!/usr/bin/env python3
"""FR Finance M38996: carry existing VERIFIED provider public inputs into
the EXISTING private Termux api.env; optionally stage secret values there.

Creates NO database, cluster, repository, worktree, directory or new env.
Does NOT enable mail workers, issue invitations, send email or activate users.
The Brevo SMTP key is entered only through a hidden local TTY prompt.
The existing file is replaced atomically *at the same exact path*.
"""
from __future__ import annotations

import argparse
import base64
import getpass
import json
import os
from pathlib import Path
import re
import secrets
import shlex
import stat
import subprocess
import sys
import tempfile
from urllib.parse import urlsplit

HOME = Path.home()
ROOT = HOME / "fr-finance"
ENV = HOME / ".config/frcaixinha-aistudio-mobile/api.env"
PUBLIC = HOME / ".config/frfinance-aistudio/provider-public-inputs.json"
EXPECTED_BRANCH = "atualizacao-ai-studio-9b46a63187"
PUBLIC_FIELDS = ("APP_URL", "SMTP_HOST", "SMTP_PORT", "SMTP_USER", "FR_FINANCE_EMAIL_FROM")
SECRET_FIELDS = ("SMTP_PASSWORD", "FR_FINANCE_ACCESS_ENCRYPTION_KEY_B64",
                 "FR_FINANCE_ACCESS_HMAC_KEY")
DANGEROUS_FLAGS = ("FR_FINANCE_ACCESS_MAIL_ENABLE", "FR_FINANCE_ACCESS_MAIL_WORKER")
ASSIGN = re.compile(r"^\s*(?:export\s+)?([A-Z][A-Z0-9_]*)=(.*)$")
MAX_BYTES = 65536


class StageBlocked(ValueError):
    """Stable error code only, never prints input or private credentials."""


def _guard_original() -> None:
    if (not ROOT.is_dir() or ROOT.is_symlink()
            or not (ROOT / ".git").exists()):
        raise StageBlocked("WRONG_ORIGINAL_WORKTREE")
    try:
        branch = subprocess.run(
            ("git", "-C", str(ROOT), "branch", "--show-current"),
            text=True, capture_output=True, check=True, timeout=5,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        raise StageBlocked("ORIGINAL_GIT_CHECK_FAILED") from None
    if branch != EXPECTED_BRANCH:
        raise StageBlocked("WRONG_ORIGINAL_BRANCH")


def _secure_file(path: Path) -> None:
    parent = path.parent
    if parent.is_symlink() or path.is_symlink() or not parent.is_dir():
        raise StageBlocked("EXISTING_CONFIG_PATH_INVALID")
    try:
        d = parent.stat()
        s = path.stat()
    except OSError:
        raise StageBlocked("EXISTING_CONFIG_FILE_MISSING") from None
    if (not stat.S_ISREG(s.st_mode) or s.st_uid != os.getuid()
            or s.st_size <= 0 or s.st_size > MAX_BYTES
            or stat.S_IMODE(s.st_mode) != 0o600
            or d.st_uid != os.getuid()
            or (stat.S_IMODE(d.st_mode) & 0o077) != 0):
        raise StageBlocked("EXISTING_CONFIG_PERMISSIONS_INVALID")


def _load_public() -> dict[str, str]:
    _secure_file(PUBLIC)
    try:
        from app.provider_intake_schema import validate_manifest
        obj = json.loads(PUBLIC.read_text(encoding="utf-8"))
        manifest = validate_manifest(obj)
        fields = manifest["public_inputs"]
        selected = {key: fields[key] for key in PUBLIC_FIELDS if key in fields}
        if set(selected) != set(PUBLIC_FIELDS):
            raise StageBlocked("ALREADY_REGISTERED_PUBLIC_FIELDS_INCOMPLETE")
        return selected
    except (ValueError, UnicodeError, OSError, KeyError):
        raise StageBlocked("ALREADY_REGISTERED_PUBLIC_FIELDS_INVALID") from None


def _load_env() -> tuple[list[str], dict[str, str]]:
    _secure_file(ENV)
    try:
        lines = ENV.read_text(encoding="utf-8").splitlines()
    except (UnicodeError, OSError):
        raise StageBlocked("EXISTING_API_ENV_UNREADABLE") from None
    known: dict[str, str] = {}
    for line in lines:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        m = ASSIGN.fullmatch(line)
        if not m or m.group(1) in known:
            raise StageBlocked("EXISTING_API_ENV_SYNTAX_OR_DUPLICATE")
        key, raw = m.groups()
        try:
            values = shlex.split(raw, comments=False, posix=True)
        except ValueError:
            raise StageBlocked("EXISTING_API_ENV_QUOTING_INVALID") from None
        if len(values) != 1:
            raise StageBlocked("EXISTING_API_ENV_VALUE_FORMAT_INVALID")
        known[key] = values[0]
    return lines, known


def _verify_original_dsn(values: dict[str, str]) -> None:
    dsn = values.get("AUTH_DATABASE_URL", "")
    try:
        p = urlsplit(dsn)
        if (p.scheme != "postgresql"
                or p.username != "frc_ai_auth"
                or p.hostname != "127.0.0.1" or p.port != 5433
                or p.path != "/frcaixinha_aistudio_dev"
                or not p.password or p.query or p.fragment):
            raise ValueError()
    except (ValueError, AttributeError):
        raise StageBlocked("AUTH_DSN_NOT_ORIGINAL_FR_FINANCE") from None
    for flag in DANGEROUS_FLAGS:
        if values.get(flag, "OFF") not in ("OFF", "0", "NO", ""):
            raise StageBlocked("ACTIVE_MAIL_FLAG_CANNOT_BE_OVERWRITTEN")


def _changes(public: dict[str, str], existing: dict[str, str],
             *, include_private: bool, smtp_key: str | None) -> dict[str, str]:
    changes: dict[str, str] = {}
    for key, value in public.items():
        if key in existing:
            if existing[key] != value:
                raise StageBlocked("PUBLIC_CONFIGURATION_CONFLICT_" + key)
        else:
            changes[key] = value
    if include_private:
        if "SMTP_PASSWORD" not in existing:
            if (type(smtp_key) is not str or not 16 <= len(smtp_key) <= 512
                    or any(ord(c) < 33 or ord(c) > 126 for c in smtp_key)):
                raise StageBlocked("SMTP_SECRET_MISSING_OR_INVALID")
            changes["SMTP_PASSWORD"] = smtp_key
        if "FR_FINANCE_ACCESS_ENCRYPTION_KEY_B64" not in existing:
            changes["FR_FINANCE_ACCESS_ENCRYPTION_KEY_B64"] = (
                base64.b64encode(secrets.token_bytes(32)).decode("ascii"))
        if "FR_FINANCE_ACCESS_HMAC_KEY" not in existing:
            changes["FR_FINANCE_ACCESS_HMAC_KEY"] = secrets.token_urlsafe(48)
    return changes


def _save_original(lines: list[str], changes: dict[str, str]) -> None:
    """Atomic *in-place config replacement*; no new project or directory."""
    if not changes:
        return
    _secure_file(ENV)
    payload = ("\n".join(lines).rstrip("\n") + "\n"
               + "\n".join(f"{k}={shlex.quote(v)}" for k, v in changes.items())
               + "\n").encode("utf-8")
    if len(payload) > MAX_BYTES:
        raise StageBlocked("EXISTING_API_ENV_TOO_LARGE")
    tmp: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(mode="wb", dir=ENV.parent,
                                         prefix=".api-env-frfinance-",
                                         delete=False) as fp:
            tmp = Path(fp.name)
            os.fchmod(fp.fileno(), 0o600)
            fp.write(payload)
            fp.flush()
            os.fsync(fp.fileno())
        _secure_file(ENV)
        os.replace(tmp, ENV)
        tmp = None
    except OSError:
        raise StageBlocked("PRIVATE_CONFIG_ATOMIC_WRITE_FAILED") from None
    finally:
        if tmp is not None:
            tmp.unlink(missing_ok=True)


def stage(*, mode: str, smtp_key: str | None = None, approved: bool = False) -> dict:
    _guard_original()
    public = _load_public()
    lines, existing = _load_env()
    _verify_original_dsn(existing)
    if not approved:
        return {
            "mode": "PREVIEW_ONLY",
            "missing_public": sorted(set(public) - set(existing)),
            "missing_secret_names": sorted(set(SECRET_FIELDS) - set(existing)),
        }
    changed = _changes(public, existing,
                       include_private=mode == "private", smtp_key=smtp_key)
    _save_original(lines, changed)
    return {
        "mode": "PUBLIC_AND_PRIVATE_STAGED_NO_ACTIVATION"
            if mode == "private" else "PUBLIC_STAGED_NO_ACTIVATION",
        "public_fields_added": sum(k in PUBLIC_FIELDS for k in changed),
        "secret_names_added": sum(k in SECRET_FIELDS for k in changed),
        "mail_enabled": False,
        "database_mutations": False,
        "sql_migrations": False,
        "real_pix": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="FR Finance original private mail config only")
    parser.add_argument("mode", choices=("inspect", "stage-public", "stage-private"))
    args = parser.parse_args(argv)
    try:
        preview = stage(mode="private" if args.mode == "stage-private" else "public")
        print("=== FR FINANCE M38996 — ORIGINAL SMTP CONFIG STAGING ===")
        print("M38996_ORIGINAL_PROJECT=VERIFIED")
        print("M38996_EXISTING_PUBLIC_PROVIDER_FIELDS=REUSED")
        print("M38996_MISSING_PUBLIC_COUNT="+str(len(preview["missing_public"])))
        print("M38996_MISSING_SECRET_COUNT="+str(len(preview["missing_secret_names"])))
        if args.mode == "inspect":
            print("M38996_MODE=READ_ONLY")
            return 0
        if not (sys.stdin.isatty() and sys.stdout.isatty()):
            raise StageBlocked("INTERACTIVE_TTY_REQUIRED")
        print("Nenhum novo banco, diretorio, SMTP, usuario ou Pix sera ativado.")
        password = None
        if args.mode == "stage-private" and "SMTP_PASSWORD" in preview["missing_secret_names"]:
            # Existing SMTP credential from Brevo. Do not generate a new
            # provider credential, register a new sender, or print it.
            password = getpass.getpass("Chave SMTP Brevo ja existente (oculta): ")
        answer = input("Digite PREPARAR_CONFIG_FR_FINANCE: ").strip()
        if answer != "PREPARAR_CONFIG_FR_FINANCE":
            raise StageBlocked("OPERATOR_DECLINED")
        state = stage(mode="private" if args.mode == "stage-private" else "public",
                      smtp_key=password, approved=True)
        print("M38996_RESULT="+state["mode"])
        print("M38996_PUBLIC_FIELDS_ADDED="+str(state["public_fields_added"]))
        print("M38996_SECRET_NAMES_ADDED="+str(state["secret_names_added"]))
        print("M38996_MAIL_WORKER=OFF_UNCHANGED")
        print("M38996_PASSWORD_AND_TOKEN_VALUES_PRINTED=NONE")
        print("M38996_DATABASE_MUTATIONS=NONE")
        print("M38996_SQL_MIGRATIONS=NONE")
        print("M38996_PIX_REAL=OFF")
        print("M38996_PRODUCTION=BLOCKED")
        return 0
    except StageBlocked as exc:
        print("M38996_BLOCKED="+str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
