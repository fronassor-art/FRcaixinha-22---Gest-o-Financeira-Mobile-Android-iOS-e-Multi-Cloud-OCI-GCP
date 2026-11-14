#!/usr/bin/env python3
"""FR Finance M39056 — diagnosticar conexão verifier original SEM mutações.

A execução exige ~/fr-finance nativo, SHA GitHub esperado e PostgreSQL
EXCLUSIVO frcaixinha_aistudio_dev:5433. Inspeciona SOMENTE metadados da role
através de frc_ai_owner e tenta UMA conexão com frc_ai_verifier (senha oculta).
Não imprime erros brutos/libpq, hashes, senhas ou dados de pessoas.
Não executa login, GRANT/ALTER ROLE, migrações, API ou operações financeiras.
"""
from __future__ import annotations

import datetime
import getpass
import os
import sys

from backend.scripts.frfinance_m39054_auth_pg18_preflight import verify_original
from backend.scripts.frfinance_m39026_credit_only_preflight import DB, DATA_DIRECTORY, OWNER

ROLE = "frc_ai_verifier"


def inspect_owner_metadata(conn) -> dict[str, object]:
    with conn.transaction():
        conn.execute("SET TRANSACTION READ ONLY")
        identity = conn.execute(
            "SELECT current_database(),session_user,host(inet_server_addr()),"
            "inet_server_port(),current_setting('data_directory'),"
            "current_setting('server_version_num')::integer,"
            "current_setting('transaction_read_only')"
        ).fetchone()
        if (identity[:5] != (DB, OWNER, "127.0.0.1", 5433, DATA_DIRECTORY)
                or not 180000 <= identity[5] < 190000 or identity[6] != "on"):
            raise RuntimeError("M39056_OWNER_ORIGINAL_PG18_REQUIRED")
        flags = conn.execute(
            "SELECT rolcanlogin,rolsuper,rolbypassrls,rolvaliduntil,rolconnlimit "
            "FROM pg_roles WHERE rolname=%s", (ROLE,)
        ).fetchone()
        if flags is None:
            raise RuntimeError("M39056_VERIFIER_ROLE_MISSING")
        canlogin, superuser, bypass, validuntil, connlimit = flags
        has_connect = conn.execute(
            "SELECT has_database_privilege(%s,current_database(),'CONNECT')",
            (ROLE,)
        ).fetchone()[0]
        # Prova somente presença da senha, sem ler ou imprimir seu hash.
        has_password = conn.execute(
            "SELECT EXISTS(SELECT 1 FROM pg_authid "
            "WHERE rolname=%s AND rolpassword IS NOT NULL)", (ROLE,)
        ).fetchone()[0]

    expired = bool(validuntil is not None and
                   validuntil <= datetime.datetime.now(datetime.timezone.utc))
    summary = {
        "role_exists": True,
        "canlogin": bool(canlogin),
        "privileges_safe": bool(not superuser and not bypass),
        "password_set": bool(has_password),
        "database_connect": bool(has_connect),
        "password_not_expired": not expired,
        "connection_limit_not_zero": connlimit != 0,
    }
    return summary


def classify_connection_failure(exc: BaseException) -> str:
    """Falha classificada sem expor mensagem libpq, host, senha ou role."""
    state = getattr(exc, "sqlstate", None)
    if state == "28P01":
        return "INVALID_PASSWORD"
    if state in ("28000", "42501"):
        return "AUTHORIZATION_OR_HBA_REJECTED"
    if state in ("53300", "53400"):
        return "CONNECTION_CAPACITY"
    msg = str(exc).lower()
    if "password authentication failed" in msg or "invalid password" in msg:
        return "INVALID_PASSWORD"
    if "no pg_hba.conf entry" in msg or "pg_hba" in msg:
        return "PG_HBA_REJECTED"
    if "permission denied for database" in msg:
        return "DATABASE_CONNECT_DENIED"
    if "role " in msg and "does not exist" in msg:
        return "ROLE_MISSING"
    if "too many connections" in msg or "remaining connection slots" in msg:
        return "CONNECTION_CAPACITY"
    if "connection refused" in msg or "could not connect to server" in msg:
        return "PG18_NOT_REACHABLE"
    if "timeout" in msg or "timed out" in msg:
        return "CONNECTION_TIMEOUT"
    if "password is required" in msg or "no password supplied" in msg:
        return "PASSWORD_REQUIRED"
    return "CONNECTION_REJECTED_UNCLASSIFIED"


def verify_verifier_connection(conn) -> None:
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
            raise RuntimeError("M39056_VERIFIER_ORIGINAL_PG18_REQUIRED")


def main() -> int:
    print("=== FR FINANCE M39056 — VERIFIER AUTH DIAG READ ONLY ===", flush=True)
    try:
        verify_original()
    except Exception:
        print("M39056_STATUS=BLOCKED_ORIGINAL_REPO_OR_SHA")
        return 2
    try:
        import psycopg
    except ImportError:
        print("M39056_STATUS=BLOCKED_PSYCOPG_MISSING")
        return 2

    owner_password = getpass.getpass("Senha frc_ai_owner (oculta): ")
    if not owner_password:
        print("M39056_STATUS=BLOCKED_OWNER_PASSWORD_MISSING")
        return 2
    try:
        with psycopg.connect(
            host="127.0.0.1", port=5433, dbname=DB, user=OWNER,
            password=owner_password, connect_timeout=5,
            options="-c default_transaction_read_only=on "
                    "-c statement_timeout=10000 -c lock_timeout=2000",
        ) as conn:
            owner_password = ""
            metadata = inspect_owner_metadata(conn)
    except Exception as exc:
        print("M39056_OWNER_INSPECTION=BLOCKED")
        print("M39056_OWNER_ERROR_TYPE=" + type(exc).__name__)
        return 2

    for key, ok in metadata.items():
        print("M39056_" + key.upper() + "=" + ("PASS" if ok else "BLOCKED"))
    if not all(metadata.values()):
        print("M39056_STATUS=BLOCKED_ROLE_METADATA")
        print("M39056_DATABASE_WRITES=NONE")
        return 2

    password = getpass.getpass("Senha frc_ai_verifier (oculta, uma tentativa): ")
    if not password:
        print("M39056_STATUS=BLOCKED_VERIFIER_PASSWORD_MISSING")
        return 2
    try:
        with psycopg.connect(
            host="127.0.0.1", port=5433, dbname=DB, user=ROLE,
            password=password, connect_timeout=5,
            options="-c default_transaction_read_only=on "
                    "-c statement_timeout=10000 -c lock_timeout=2000",
        ) as conn:
            password = ""
            verify_verifier_connection(conn)
    except RuntimeError as exc:
        print("M39056_VERIFIER_CHECK=BLOCKED")
        print("M39056_REASON=" + str(exc))
        print("M39056_DATABASE_WRITES=NONE")
        return 2
    except Exception as exc:
        print("M39056_VERIFIER_CONNECTION=BLOCKED")
        print("M39056_ERROR_TYPE=" + type(exc).__name__)
        print("M39056_REASON=" + classify_connection_failure(exc))
        print("M39056_DATABASE_WRITES=NONE")
        print("M39056_NO_PASSWORD_RESET=TRUE")
        return 2

    print("M39056_VERIFIER_CONNECTION=PASS")
    print("M39056_LOGIN_REAL=NOT_ATTEMPTED")
    print("M39056_DATABASE_WRITES=NONE")
    print("M39056_SESSIONS_CREATED=NONE")
    print("M39056_MIGRATIONS=NONE")
    print("M39056_PIX_REAL=OFF")
    print("M39056_STATUS=PASS_READ_ONLY")
    return 0


if __name__ == "__main__":
    sys.exit(main())
