#!/usr/bin/env python3
"""M39060 — configuração privada no disco versus FastAPI já ativo, read-only.

Lê chaves estritamente autorizadas do api.env original (sem mostrar valores)
e consulta só GET /api/health, /api/v1/auth/status na API existente.
Não lê /proc/PID/environ, não executa shell, não liga, reinicia ou substitui
serviços, não toca no PostgreSQL nem realiza login/sessões/envio/Pix.
"""
from __future__ import annotations

import shlex
import sys

from backend.scripts.frfinance_m39054_auth_pg18_preflight import verify_original
from backend.scripts.frfinance_m39057_stored_verifier_readonly import (
    ENV_PATH, GuardBlocked,
)
from backend.scripts.frfinance_m39058_three_roles_from_private_env import collect_urls
from backend.scripts.frfinance_m39059_existing_fastapi_anonymous_readonly import (
    request_local,
)

FLAGS = frozenset((
    "ENVIRONMENT",
    "FRCAIXINHA_TEST_AUTH",
    "FRCAIXINHA_TERMUX_LOCAL_API",
    "AUTH_RATE_LIMIT_HMAC_KEY",
    "FR_FINANCE_PIX_REAL",
    "FR_FINANCE_ACCESS_MAIL_ENABLE",
    "FR_FINANCE_ACCESS_MAIL_WORKER",
))


def read_flag_status() -> dict[str, str]:
    # collect_urls() já validou a origem/owner/0600 e as três URLs privadas.
    flags: dict[str, str] = {}
    try:
        lines = ENV_PATH.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError):
        raise GuardBlocked("PRIVATE_CONFIG_UNREADABLE") from None
    for line in lines:
        candidate = line.strip()
        if not candidate or candidate.startswith("#"):
            continue
        key, sep, value = candidate.partition("=")
        key = key.strip()
        if not sep or key not in FLAGS:
            continue
        if key in flags:
            raise GuardBlocked("DUPLICATE_PRIVATE_FLAG")
        try:
            tokens = shlex.split(value, posix=True)
        except ValueError:
            raise GuardBlocked("MALFORMED_PRIVATE_FLAG") from None
        if len(tokens) != 1:
            raise GuardBlocked("MALFORMED_PRIVATE_FLAG")
        flags[key] = tokens[0]
    return {
        "M39060_SAVED_TEST_AUTH": (
            "ENABLED" if flags.get("FRCAIXINHA_TEST_AUTH") == "1"
            else "NOT_ENABLED"
        ),
        "M39060_SAVED_LOCAL_API": (
            "ENABLED" if flags.get("FRCAIXINHA_TERMUX_LOCAL_API") == "1"
            else "NOT_ENABLED"
        ),
        "M39060_SAVED_RATE_LIMIT_KEY": (
            "SUFFICIENT_LENGTH" if len(
                flags.get("AUTH_RATE_LIMIT_HMAC_KEY", "").encode("utf-8")
            ) >= 32 else "MISSING_OR_SHORT"
        ),
        "M39060_SAVED_ENVIRONMENT": (
            "NON_PRODUCTION" if flags.get("ENVIRONMENT") != "production"
            else "BLOCKED_PRODUCTION"
        ),
        "M39060_SAVED_PIX_FLAG": (
            "NOT_EXPLICITLY_ENABLED"
            if flags.get("FR_FINANCE_PIX_REAL", "OFF").strip().upper()
            in ("", "OFF", "NO", "FALSE", "0")
            else "REVIEW_REQUIRED"
        ),
        "M39060_SAVED_MAIL_WORKER": (
            "NOT_EXPLICITLY_ENABLED"
            if flags.get("FR_FINANCE_ACCESS_MAIL_WORKER", "OFF").strip().upper()
            in ("", "OFF", "NO", "FALSE", "0")
            else "REVIEW_REQUIRED"
        ),
    }


def diagnosis(saved: dict[str, str], health: dict, auth: dict) -> str:
    db = health.get("database_configured")
    mode = auth.get("status")
    if db is False and mode == "BLOCKED_PENDING_CONFIG":
        return "DISK_HAS_VALID_DSNS_BUT_ACTIVE_API_DATABASE_URL_EMPTY"
    if db is True and mode == "BLOCKED_PENDING_IMPLEMENTATION":
        return "ACTIVE_API_AUTH_FLAGS_OR_CREDENTIALS_NOT_LOADED"
    if db is True and mode == "TEST_MODE":
        return "ACTIVE_API_TEST_MODE_READY_REQUIRES_SEPARATE_READINESS"
    return "ACTIVE_API_CONFIG_INCONSISTENT_REVIEW_REQUIRED"


def main() -> int:
    print("=== FR FINANCE M39060 — ARQUIVO PRIVADO X PROCESSO FASTAPI ===")
    try:
        verify_original()
    except Exception:
        print("M39060_STATUS=BLOCKED_ORIGINAL_REPO_OR_SHA")
        return 2
    try:
        collect_urls()
        saved = read_flag_status()
    except GuardBlocked as exc:
        print("M39060_STATUS=BLOCKED_" + str(exc))
        print("M39060_SECRETS_DISPLAYED=NONE")
        return 2
    except Exception:
        print("M39060_STATUS=BLOCKED_PRIVATE_CONFIG")
        print("M39060_SECRETS_DISPLAYED=NONE")
        return 2
    print("M39060_SAVED_DSNS=THREE_VALID_FR_FINANCE_TARGETS_5433")
    for k, value in saved.items():
        print(k + "=" + value)

    hcode, health = request_local("/api/health")
    acode, auth = request_local("/api/v1/auth/status")
    if (hcode != 200 or health.get("app") != "FR Finance"
            or health.get("status") != "ONLINE"
            or type(health.get("database_configured")) is not bool
            or acode != 200 or auth.get("requires_authentication") is not True
            or auth.get("status") not in (
                "TEST_MODE", "BLOCKED_PENDING_IMPLEMENTATION", "BLOCKED_PENDING_CONFIG"
            )):
        print("M39060_STATUS=BLOCKED_EXISTING_API_NOT_ATTESTED")
        print("M39060_SECRETS_DISPLAYED=NONE")
        return 2
    print("M39060_ACTIVE_FASTAPI=FR_FINANCE_ONLINE")
    print("M39060_ACTIVE_DATABASE_CONFIGURED="
          + ("TRUE" if health["database_configured"] else "FALSE"))
    print("M39060_ACTIVE_AUTH_MODE=" + auth["status"])
    print("M39060_DIAGNOSIS=" + diagnosis(saved, health, auth))
    print("M39060_FASTAPI_START_STOP=NONE")
    print("M39060_PG_WRITES=NONE")
    print("M39060_REAL_LOGIN=NOT_ATTEMPTED")
    print("M39060_SESSIONS_CREATED=NONE")
    print("M39060_SECRETS_DISPLAYED=NONE")
    print("M39060_FR22_ACCESS=NONE")
    print("M39060_PRODUCTION=BLOCKED")
    print("M39060_STATUS=PASS_READ_ONLY_DIAGNOSIS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
