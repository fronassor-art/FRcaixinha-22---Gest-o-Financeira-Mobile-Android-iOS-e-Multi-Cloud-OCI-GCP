#!/usr/bin/env python3
"""FR Finance M39058 — três conexões locais de API, somente leitura.

Lê exclusivamente o api.env privado já existente, sem executar shell, expor
segredos ou modificar credenciais. Reutiliza guardas do M39057 e auditoria
de permissões do M39055. Não realiza login humano nem inicia API.
"""
from __future__ import annotations

import shlex
import sys

from backend.scripts.frfinance_m39054_auth_pg18_preflight import verify_original
from backend.scripts.frfinance_m39055_auth_roles_readonly import role_connection_audit
from backend.scripts.frfinance_m39057_stored_verifier_readonly import (
    ENV_PATH, GuardBlocked, check_target, read_configured_urls,
)

ROLE_KEYS = (
    ("frc_ai_app", "DATABASE_URL"),
    ("frc_ai_auth", "AUTH_DATABASE_URL"),
    ("frc_ai_verifier", "AUTH_VERIFIER_DATABASE_URL"),
)


def read_app_url() -> str:
    """Usado somente APÓS o controle de arquivo/owner/permissões do M39057."""
    try:
        lines = ENV_PATH.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError):
        raise GuardBlocked("CONFIG_UNREADABLE") from None
    values: list[str] = []
    for line in lines:
        candidate = line.strip()
        if not candidate or candidate.startswith("#"):
            continue
        key, sep, raw_value = candidate.partition("=")
        if not sep or key.strip() != "DATABASE_URL":
            continue
        try:
            tokens = shlex.split(raw_value, posix=True)
        except ValueError:
            raise GuardBlocked("APP_URL_MALFORMED") from None
        if len(tokens) != 1 or not tokens[0]:
            raise GuardBlocked("APP_URL_MALFORMED")
        values.append(tokens[0])
    if len(values) != 1:
        raise GuardBlocked("APP_URL_MISSING_OR_DUPLICATE")
    return values[0]


def collect_urls() -> dict[str, str]:
    # M39057 valida caminho canônico, symlinks, owner e 0600 antes de ler.
    auth = read_configured_urls()
    urls = {"DATABASE_URL": read_app_url(), **auth}
    for role, key in ROLE_KEYS:
        check_target(urls[key], role)
    if len({urls[key] for _, key in ROLE_KEYS}) != len(ROLE_KEYS):
        raise GuardBlocked("TECHNICAL_ROLE_DSNS_NOT_SEPARATE")
    return urls


def main() -> int:
    print("=== FR FINANCE M39058 — TRES ROLES CONFIGURADAS READ ONLY ===", flush=True)
    try:
        verify_original()
    except Exception:
        print("M39058_STATUS=BLOCKED_ORIGINAL_REPOSITORY_OR_SHA")
        return 2
    try:
        urls = collect_urls()
    except GuardBlocked as exc:
        print("M39058_CONFIG=BLOCKED_" + str(exc))
        print("M39058_SECRETS_PRINTED=NONE")
        print("M39058_DATABASE_WRITES=NONE")
        return 2
    print("M39058_THREE_TARGETS=FR_FINANCE_PG18_5433")
    print("M39058_CONFIG_PRIVATE=PASS")
    try:
        import psycopg
    except ImportError:
        print("M39058_STATUS=BLOCKED_PSYCOPG_MISSING")
        return 2
    for role, key in ROLE_KEYS:
        try:
            with psycopg.connect(
                urls[key], connect_timeout=5,
                options="-c default_transaction_read_only=on "
                        "-c statement_timeout=10000 -c lock_timeout=2000",
            ) as conn:
                role_connection_audit(conn, role)
        except RuntimeError:
            print("M39058_" + role.upper() + "=BLOCKED_ROLE_PERMISSION_OR_IDENTITY")
            print("M39058_STATUS=BLOCKED")
            print("M39058_DATABASE_WRITES=NONE")
            return 2
        except Exception as exc:
            from backend.scripts.frfinance_m39056_verifier_connection_diag import (
                classify_connection_failure,
            )
            print("M39058_" + role.upper() + "=" + classify_connection_failure(exc))
            print("M39058_STATUS=BLOCKED")
            print("M39058_DATABASE_WRITES=NONE")
            return 2
        print("M39058_" + role.upper() + "=PASS")
    print("M39058_THREE_ROLE_PERMISSIONS=PASS")
    print("M39058_LOGIN_REAL=NOT_ATTEMPTED")
    print("M39058_SESSIONS_CREATED=NONE")
    print("M39058_DATABASE_WRITES=NONE")
    print("M39058_PASSWORD_RESET=NONE")
    print("M39058_MIGRATIONS=NONE")
    print("M39058_SECRETS_PRINTED=NONE")
    print("M39058_PIX_REAL=OFF")
    print("M39058_STATUS=PASS_READ_ONLY")
    return 0


if __name__ == "__main__":
    sys.exit(main())
