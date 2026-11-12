#!/usr/bin/env python3
"""M39057 — verifica sem exibir a credencial verifier guardada no api.env original.

Somente no Termux nativo/checkout FR Finance aprovado. Lê UM arquivo local
privado (nunca publica conteúdo), abre UMA conexão somente leitura ao
PostgreSQL FR Finance/5433 e emite indicadores sem dados sensíveis.
Não altera senha, roles, HBA, configuração, tabelas, sessões, Pix nem API.
"""
from __future__ import annotations

import os
from pathlib import Path
import shlex
import stat
import sys
from urllib.parse import urlsplit, unquote

from backend.scripts.frfinance_m39054_auth_pg18_preflight import verify_original
from backend.scripts.frfinance_m39026_credit_only_preflight import DB

ROLE = "frc_ai_verifier"
AUTH_ROLE = "frc_ai_auth"
ENV_PATH = Path("/data/data/com.termux/files/home/.config/frcaixinha-aistudio-mobile/api.env")
MAX_ENV_BYTES = 128 * 1024


class GuardBlocked(Exception):
    pass


def read_configured_urls(path: Path = ENV_PATH) -> dict[str, str]:
    """Lê só URLs necessárias, sem executar shell nem imprimir valores."""
    home = Path("/data/data/com.termux/files/home")
    allowed = home / ".config" / "frcaixinha-aistudio-mobile" / "api.env"
    if path != allowed:
        raise GuardBlocked("NONCANONICAL_CONFIG_PATH")
    for candidate in (path.parent.parent, path.parent, path):
        if candidate.is_symlink():
            raise GuardBlocked("CONFIG_SYMLINK_BLOCKED")
    try:
        info = path.stat()
    except (OSError, ValueError):
        raise GuardBlocked("CONFIG_MISSING_OR_UNREADABLE") from None
    if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_ENV_BYTES:
        raise GuardBlocked("CONFIG_FILE_TYPE_OR_SIZE_INVALID")
    if stat.S_IMODE(info.st_mode) & 0o077:
        raise GuardBlocked("CONFIG_FILE_PERMISSIONS_UNSAFE")
    if info.st_uid != os.getuid():
        raise GuardBlocked("CONFIG_FILE_OWNER_MISMATCH")
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError):
        raise GuardBlocked("CONFIG_UNREADABLE") from None
    required = {"AUTH_DATABASE_URL", "AUTH_VERIFIER_DATABASE_URL"}
    found: dict[str, str] = {}
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, sep, raw_value = line.partition("=")
        if not sep or key.strip() not in required:
            continue
        key = key.strip()
        if key in found:
            raise GuardBlocked("CONFIG_DUPLICATE_AUTH_URL")
        try:
            tokens = shlex.split(raw_value, posix=True)
        except ValueError:
            raise GuardBlocked("CONFIG_AUTH_URL_MALFORMED") from None
        if len(tokens) != 1 or not tokens[0]:
            raise GuardBlocked("CONFIG_AUTH_URL_MALFORMED")
        found[key] = tokens[0]
    if found.keys() != required:
        raise GuardBlocked("CONFIG_AUTH_URL_MISSING")
    return found


def check_target(url: str, expected_user: str) -> None:
    try:
        parsed = urlsplit(url)
        user = unquote(parsed.username or "")
        target = (parsed.scheme, user, parsed.hostname, parsed.port, parsed.path)
    except (ValueError, TypeError):
        raise GuardBlocked("CONFIG_AUTH_URL_MALFORMED") from None
    if target != ("postgresql", expected_user, "127.0.0.1", 5433, "/" + DB):
        raise GuardBlocked("WRONG_DATABASE_OR_ROLE_IN_PRIVATE_CONFIG")
    if not parsed.password or parsed.fragment or parsed.query:
        raise GuardBlocked("CONFIG_AUTH_URL_UNEXPECTED_SHAPE")


def verify_readonly_connection(conn) -> None:
    with conn.transaction():
        conn.execute("SET TRANSACTION READ ONLY")
        row = conn.execute(
            "SELECT current_database(),session_user,current_user,"
            "host(inet_server_addr()),inet_server_port(),"
            "current_setting('server_version_num')::integer,"
            "current_setting('transaction_read_only')"
        ).fetchone()
        if (row[:5] != (DB, ROLE, ROLE, "127.0.0.1", 5433)
                or not 180000 <= row[5] < 190000 or row[6] != "on"):
            raise GuardBlocked("CONNECTED_SERVER_IDENTITY_MISMATCH")


def main() -> int:
    print("=== FR FINANCE M39057 — TESTE DE CREDENCIAL SALVA READ ONLY ===")
    try:
        verify_original()
    except Exception:
        print("M39057_STATUS=BLOCKED_ORIGINAL_REPOSITORY_OR_SHA")
        return 2
    try:
        urls = read_configured_urls()
        check_target(urls["AUTH_DATABASE_URL"], AUTH_ROLE)
        check_target(urls["AUTH_VERIFIER_DATABASE_URL"], ROLE)
    except GuardBlocked as exc:
        print("M39057_STATUS=BLOCKED_" + str(exc))
        print("M39057_SECRET_DISPLAY=NONE")
        print("M39057_DATABASE_WRITES=NONE")
        return 2
    print("M39057_LOCAL_CONFIG=VALID_PRIVATE_FILE")
    print("M39057_AUTH_AND_VERIFIER_TARGET=SAME_FR_FINANCE_PG18_5433")
    try:
        import psycopg
    except ImportError:
        print("M39057_STATUS=BLOCKED_PSYCOPG_MISSING")
        return 2
    try:
        with psycopg.connect(
            urls["AUTH_VERIFIER_DATABASE_URL"], connect_timeout=5,
            options="-c default_transaction_read_only=on "
                    "-c statement_timeout=10000 -c lock_timeout=2000",
        ) as conn:
            verify_readonly_connection(conn)
    except GuardBlocked as exc:
        print("M39057_STORED_VERIFIER=BLOCKED_" + str(exc))
        print("M39057_STATUS=BLOCKED")
        return 2
    except Exception as exc:
        from backend.scripts.frfinance_m39056_verifier_connection_diag import (
            classify_connection_failure,
        )
        print("M39057_STORED_VERIFIER=" + classify_connection_failure(exc))
        print("M39057_DATABASE_WRITES=NONE")
        print("M39057_SESSIONS_CREATED=NONE")
        print("M39057_SECRET_DISPLAY=NONE")
        print("M39057_STATUS=BLOCKED")
        return 2
    print("M39057_STORED_VERIFIER=PASS")
    print("M39057_PREVIOUS_MANUAL_FAILURE=DOES_NOT_MATCH_STORED_CREDENTIAL_OR_INPUT")
    print("M39057_DATABASE_WRITES=NONE")
    print("M39057_SESSIONS_CREATED=NONE")
    print("M39057_PASSWORD_RESET=NONE")
    print("M39057_SECRET_DISPLAY=NONE")
    print("M39057_PIX_REAL=OFF")
    print("M39057_STATUS=PASS_READ_ONLY")
    return 0


if __name__ == "__main__":
    sys.exit(main())
