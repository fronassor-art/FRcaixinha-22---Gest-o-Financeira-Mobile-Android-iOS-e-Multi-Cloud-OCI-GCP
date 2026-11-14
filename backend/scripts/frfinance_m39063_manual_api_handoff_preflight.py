#!/usr/bin/env python3
"""M39063 — preflight para troca MANUAL de FastAPI visual para homologação.

Read-only; não para, inicia, reinicia, envia, migra ou grava. Exige
Termux original, três DSNs privadas segregadas e flags externas OFF.
Nunca imprime segredos, URLs, PID ou argumentos do processo.
"""
from __future__ import annotations

import shlex
import socket
from pathlib import Path

from backend.scripts.frfinance_m39054_auth_pg18_preflight import verify_original
from backend.scripts.frfinance_m39057_stored_verifier_readonly import ENV_PATH, GuardBlocked
from backend.scripts.frfinance_m39058_three_roles_from_private_env import collect_urls
from backend.scripts.frfinance_m39059_existing_fastapi_anonymous_readonly import request_local

FLAGS = frozenset((
    "ENVIRONMENT", "FRCAIXINHA_TEST_AUTH", "FRCAIXINHA_TERMUX_LOCAL_API",
    "AUTH_RATE_LIMIT_HMAC_KEY", "AUTH_SECRET", "FR_FINANCE_PIX_REAL",
    "FR_FINANCE_ACCESS_MAIL_ENABLE", "FR_FINANCE_ACCESS_MAIL_WORKER",
    "FR_FINANCE_REAL_USER_ACTIVATION",
))
OFF_VALUES = frozenset(("", "OFF", "NO", "FALSE", "0"))
LAUNCHER = Path("/data/data/com.termux/files/home/fr-finance/backend/scripts/run_termux_fastapi.sh")


def read_private_flags() -> dict[str, str]:
    """Somente após collect_urls() confirmar caminho, dono, 0600 e symlinks."""
    result: dict[str, str] = {}
    try:
        lines = ENV_PATH.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError):
        raise GuardBlocked("PRIVATE_CONFIG_UNREADABLE") from None
    for line in lines:
        item = line.strip()
        if not item or item.startswith("#"):
            continue
        key, sep, val = item.partition("=")
        key = key.strip()
        if not sep or key not in FLAGS:
            continue
        if key in result:
            raise GuardBlocked("DUPLICATE_PRIVATE_FLAG")
        try:
            parsed = shlex.split(val, posix=True)
        except ValueError:
            raise GuardBlocked("MALFORMED_PRIVATE_FLAG") from None
        if len(parsed) != 1:
            raise GuardBlocked("MALFORMED_PRIVATE_FLAG")
        result[key] = parsed[0]
    return result


def check_private_homologation(flags: dict[str, str]) -> None:
    if (flags.get("ENVIRONMENT") != "homologation"
            or flags.get("FRCAIXINHA_TEST_AUTH") != "1"
            or flags.get("FRCAIXINHA_TERMUX_LOCAL_API") != "1"):
        raise GuardBlocked("TEST_MODE_FLAGS_NOT_READY")
    for key in ("AUTH_RATE_LIMIT_HMAC_KEY", "AUTH_SECRET"):
        if len(flags.get(key, "").encode("utf-8")) < 32:
            raise GuardBlocked("REQUIRED_AUTH_KEY_MISSING_OR_SHORT")
    for key in ("FR_FINANCE_PIX_REAL", "FR_FINANCE_ACCESS_MAIL_ENABLE",
                "FR_FINANCE_ACCESS_MAIL_WORKER", "FR_FINANCE_REAL_USER_ACTIVATION"):
        if flags.get(key, "OFF").strip().upper() not in OFF_VALUES:
            raise GuardBlocked("EXTERNAL_OR_PRODUCTION_FEATURE_ENABLED")


def api_state() -> str:
    code, health = request_local("/api/health")
    if code == 0:
        # Network failure is not necessarily a free port. Do not bind.
        try:
            with socket.create_connection(("127.0.0.1", 8000), timeout=1):
                return "BLOCKED_PORT_8000_OTHER_LISTENER"
        except OSError:
            return "PORT_8000_NO_TCP_LISTENER_DETECTED"
    if code != 200 or health.get("app") != "FR Finance" or (
        health.get("status") != "ONLINE"
    ):
        return "BLOCKED_PORT_8000_UNVERIFIED_APPLICATION"
    status_code, auth = request_local("/api/v1/auth/status")
    if status_code != 200 or auth.get("requires_authentication") is not True:
        return "BLOCKED_AUTH_STATUS_UNVERIFIED"
    if (health.get("database_configured") is False
            and auth.get("status") == "BLOCKED_PENDING_CONFIG"):
        return "VISUAL_MODE_LIKELY_MANUAL_STOP_REQUIRED"
    if (health.get("database_configured") is True
            and auth.get("status") == "TEST_MODE"):
        return "AUTH_TEST_MODE_ALREADY_ACTIVE_CHECK_READINESS"
    return "BLOCKED_API_RUNTIME_UNEXPECTED"


def main() -> int:
    print("=== FR FINANCE M39063 — HANDOFF MANUAL PREFLIGHT ===")
    try:
        verify_original()
    except Exception:
        print("M39063_STATUS=BLOCKED_ORIGINAL_REPO_OR_SHA")
        return 2
    try:
        collect_urls()
        flags = read_private_flags()
        check_private_homologation(flags)
        if not LAUNCHER.is_file() or LAUNCHER.is_symlink():
            raise GuardBlocked("CANONICAL_FASTAPI_LAUNCHER_MISSING")
    except GuardBlocked as exc:
        print("M39063_STATUS=BLOCKED_" + str(exc))
        print("M39063_SECRETS_EXPOSED=NONE")
        return 2
    except Exception:
        print("M39063_STATUS=BLOCKED_PRIVATE_CONFIG")
        print("M39063_SECRETS_EXPOSED=NONE")
        return 2
    print("M39063_FR_FINANCE_THREE_DSNS=VALID_ORIGINAL_PG18_5433")
    print("M39063_LOCAL_AUTH_CONFIG=READY_ON_DISK")
    print("M39063_PIX_REAL=OFF")
    print("M39063_ACCESS_MAIL_ENABLE=OFF")
    print("M39063_ACCESS_MAIL_WORKER=OFF")
    print("M39063_REAL_USER_ACTIVATION=OFF")
    state = api_state()
    print("M39063_ACTIVE_API_STATE=" + state)
    if state == "VISUAL_MODE_LIKELY_MANUAL_STOP_REQUIRED":
        print("M39063_NEXT=STOP_ONLY_IN_ORIGINAL_VISUAL_TERMUX_SESSION")
    elif state == "PORT_8000_NO_TCP_LISTENER_DETECTED":
        print("M39063_NEXT=START_EXISTING_RUN_TERMUX_FASTAPI_AFTER_OPERATOR_REVIEW")
    elif state == "AUTH_TEST_MODE_ALREADY_ACTIVE_CHECK_READINESS":
        print("M39063_NEXT=RECHECK_M39059_NO_RESTART")
    else:
        print("M39063_NEXT=DO_NOT_STOP_OR_START_ANY_SERVICE")
    print("M39063_PROCESS_START_STOP=NONE")
    print("M39063_DATABASE_WRITES=NONE")
    print("M39063_SESSIONS_CREATED=NONE")
    print("M39063_PASSWORD_RESET=NONE")
    print("M39063_SECRETS_EXPOSED=NONE")
    print("M39063_PRODUCTION=BLOCKED")
    passed = state in (
        "VISUAL_MODE_LIKELY_MANUAL_STOP_REQUIRED",
        "PORT_8000_NO_TCP_LISTENER_DETECTED",
        "AUTH_TEST_MODE_ALREADY_ACTIVE_CHECK_READINESS",
    )
    print("M39063_STATUS=" + ("PASS_PREFLIGHT_ONLY" if passed else "BLOCKED"))
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
