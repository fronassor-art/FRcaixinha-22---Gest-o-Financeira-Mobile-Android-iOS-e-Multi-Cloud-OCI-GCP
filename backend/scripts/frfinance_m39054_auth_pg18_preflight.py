#!/usr/bin/env python3
"""FR Finance M39054 — identificação de requisitos do login no PG18 ORIGINAL.

APENAS leitura: inventário das roles e funções de autenticação.
Nunca cria sessões, altera credenciais, aplica migrações, executa API,
inicia outro servidor, ativa Pix ou escreve no banco.
A senha do owner é solicitada localmente e nunca é impressa.
"""
from __future__ import annotations

import getpass
import os
from pathlib import Path
import sys

from backend.scripts.frfinance_m39026_credit_only_preflight import (
    BRANCH, DB, DATA_DIRECTORY, OWNER, PROJECT,
)

REQUIRED_RELATIONS = (
    "users",
    "credentials",
    "sessions",
    "auth_login_proofs",
)
REQUIRED_FUNCTIONS = (
    "auth_login_rate_check",
    "auth_login_rate_failure",
    "auth_login_rate_success",
    "auth_issue_pending_session",
    "auth_active_memberships",
    "auth_promote_pending_session",
    "auth_refresh_session",
)

def verify_original() -> None:
    import subprocess

    home = "/data/data/com.termux/files/home"
    if os.environ.get("HOME") != home or Path.cwd().resolve() != PROJECT:
        raise RuntimeError("ONLY_ORIGINAL_TERMUX_WORKTREE")
    if not (PROJECT / ".git").is_dir():
        raise RuntimeError("ORIGINAL_GIT_NOT_FOUND")

    def git(*args: str) -> str:
        return subprocess.check_output(
            ["git", "-C", str(PROJECT), *args],
            text=True, stderr=subprocess.DEVNULL,
        ).strip()

    approved = os.environ.get("AI_STUDIO_APPROVED_SHA", "")
    if len(approved) != 40 or any(ch not in "0123456789abcdef" for ch in approved):
        raise RuntimeError("APPROVED_SHA_REQUIRED")
    if (git("branch", "--show-current") != BRANCH
            or git("rev-parse", "HEAD") != approved
            or git("rev-parse", "refs/remotes/origin/" + BRANCH) != approved):
        raise RuntimeError("BRANCH_OR_SHA_MISMATCH")
    if git("status", "--porcelain", "--untracked-files=all"):
        raise RuntimeError("ORIGINAL_WORKTREE_NOT_CLEAN")


def audit_original_database(conn) -> None:
    with conn.transaction():
        conn.execute("SET TRANSACTION READ ONLY")
        identity = conn.execute(
            "SELECT current_database(),session_user,host(inet_server_addr()),"
            "inet_server_port(),current_setting('data_directory'),"
            "current_setting('server_version_num')::integer,"
            "current_setting('transaction_read_only')"
        ).fetchone()
        if identity != (DB, OWNER, "127.0.0.1", 5433,
                        DATA_DIRECTORY, identity[5], "on") or not 180000 <= identity[5] < 190000:
            raise RuntimeError("NOT_ORIGINAL_PG18_READ_ONLY")

        roles = conn.execute(
            "SELECT rolname, rolcanlogin, rolsuper, rolbypassrls "
            "FROM pg_roles WHERE rolname LIKE 'frc_ai_%' ORDER BY rolname"
        ).fetchall()
        role_names = {r[0] for r in roles}
        if "frc_ai_app" not in role_names or "frc_ai_auth" not in role_names:
            raise RuntimeError("APPLICATION_AUTH_ROLE_MISSING")
        for name, canlogin, is_super, bypass in roles:
            if name in ("frc_ai_app", "frc_ai_auth") and (
                    not canlogin or is_super or bypass):
                raise RuntimeError("APPLICATION_AUTH_ROLE_PRIVILEGE_UNSAFE")

        relations = conn.execute(
            "SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
            "WHERE n.nspname='public' AND c.relkind IN ('r','p') "
            "AND c.relname=ANY(%s)", (list(REQUIRED_RELATIONS),)
        ).fetchall()
        found_relations = {row[0] for row in relations}

        functions = conn.execute(
            "SELECT DISTINCT p.proname FROM pg_proc p "
            "JOIN pg_namespace n ON n.oid=p.pronamespace "
            "WHERE n.nspname='public' AND p.proname=ANY(%s)",
            (list(REQUIRED_FUNCTIONS),)
        ).fetchall()
        found_functions = {row[0] for row in functions}

        print("M39054_PG18_ORIGINAL=PASS")
        print("M39054_APP_AND_AUTH_ROLES=PASS")
        # Only technical role identifiers and counts; never credentials.
        print("M39054_TECHNICAL_ROLES=" + ",".join(sorted(role_names)))
        print(f"M39054_AUTH_RELATIONS={len(found_relations)}_OF_{len(REQUIRED_RELATIONS)}")
        print(f"M39054_AUTH_FUNCTIONS={len(found_functions)}_OF_{len(REQUIRED_FUNCTIONS)}")
        if found_relations != set(REQUIRED_RELATIONS):
            print("M39054_MISSING_RELATIONS=" +
                  ",".join(sorted(set(REQUIRED_RELATIONS) - found_relations)))
            raise RuntimeError("AUTH_SCHEMA_INCOMPLETE")
        if found_functions != set(REQUIRED_FUNCTIONS):
            print("M39054_MISSING_FUNCTIONS=" +
                  ",".join(sorted(set(REQUIRED_FUNCTIONS) - found_functions)))
            raise RuntimeError("AUTH_FUNCTIONS_INCOMPLETE")
        # Verifier must use ANOTHER, non-superuser role. Do not guess its
        # name from inventory or reuse owner/app/auth credentials.
        candidates = [name for name, canlogin, superuser, bypass in roles
                      if canlogin and not superuser and not bypass
                      and name not in ("frc_ai_app", "frc_ai_auth")]
        print("M39054_VERIFIER_CANDIDATE_ROLES=" +
              (",".join(candidates) if candidates else "NOT_IDENTIFIED"))
        print("M39054_TRANSACTION=READ_ONLY")
        print("M39054_AUTH_LOGIN_PERFORMED=NO")
        print("M39054_SESSIONS_CREATED=NONE")
        print("M39054_DATABASE_WRITES=NONE")
        print("M39054_PIX_REAL=OFF")


def main() -> int:
    print("=== FR FINANCE M39054 — AUTH PG18 ORIGINAL READ ONLY ===")
    try:
        verify_original()
    except Exception as exc:
        print("M39054_STATUS=BLOCKED_ORIGINAL_CHECK")
        print("M39054_REASON=" + (
            str(exc) if isinstance(exc, RuntimeError) else type(exc).__name__))
        return 2
    try:
        import psycopg
    except ImportError:
        print("M39054_STATUS=BLOCKED_PSYCOPG_NOT_INSTALLED")
        return 2
    password = getpass.getpass("Senha PostgreSQL frc_ai_owner (oculta): ")
    if not password:
        print("M39054_STATUS=BLOCKED_EMPTY_PASSWORD")
        return 2
    try:
        with psycopg.connect(
            host="127.0.0.1", port=5433, dbname=DB, user=OWNER,
            password=password, connect_timeout=5,
            options="-c default_transaction_read_only=on "
                    "-c statement_timeout=12000 -c lock_timeout=2000",
        ) as conn:
            password = ""
            audit_original_database(conn)
    except RuntimeError as exc:
        print("M39054_STATUS=BLOCKED")
        print("M39054_REASON=" + str(exc))
        print("M39054_DATABASE_WRITES=NONE")
        return 2
    except Exception as exc:
        print("M39054_STATUS=BLOCKED_DATABASE")
        print("M39054_ERROR_TYPE=" + type(exc).__name__)
        print("M39054_DATABASE_WRITES=NONE")
        return 2
    print("M39054_STATUS=PASS_READ_ONLY_DISCOVERY")
    return 0


if __name__ == "__main__":
    sys.exit(main())
