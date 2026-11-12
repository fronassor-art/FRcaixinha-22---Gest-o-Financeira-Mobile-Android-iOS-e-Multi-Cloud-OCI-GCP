#!/usr/bin/env python3
"""M39055 — preflight de LOGIN local FR Finance no PG18 original.

Apenas Termux Nativo: ~/fr-finance; uma única instância e banco.
Exige senhas locais e ocultas de frc_ai_app, frc_ai_auth e frc_ai_verifier.
Não lê linhas de usuários, não verifica senhas de clientes, não cria sessão,
não habilita login, não abre API, não grava DB, não altera migrações.
Este teste não comprova que um usuário real está autorizado/ativo.
"""
from __future__ import annotations

from getpass import getpass
import os
import sys
from pathlib import Path

from backend.scripts.frfinance_m39054_auth_pg18_preflight import verify_original
from backend.scripts.frfinance_m39026_credit_only_preflight import (
    DB
)

ROLES = ("frc_ai_app", "frc_ai_auth", "frc_ai_verifier")
# A role financeira usa SELECT de tabela apenas onde ja homologado.
# Auth e verifier usam apenas colunas de SQL efetivamente consultado pelas
# rotas oficiais auth.py/dependencies.py; exigir SELECT geral e indevido.
TABLE_GRANTS = {
    "frc_ai_app": ("public.tenants", "public.memberships"),
    "frc_ai_auth": (),
    "frc_ai_verifier": (),
}
COLUMN_SELECT = {
    "frc_ai_app": {},
    "frc_ai_auth": {
        "public.users": ("id", "status", "is_master", "email", "full_name"),
        "public.sessions": (
            "id", "user_id", "token_hash", "active_role",
            "active_tenant_id", "expires_at", "revoked_at", "created_at",
        ),
    },
    "frc_ai_verifier": {
        "public.users": ("id", "email", "full_name", "status", "is_master"),
        "public.credentials": ("user_id", "password_hash"),
    },
}
AUTH_FUNCTIONS = (
    "auth_login_rate_check",
    "auth_login_rate_failure",
    "auth_login_rate_success",
    "auth_issue_pending_session",
    "auth_active_memberships",
    "auth_promote_pending_session",
    "auth_refresh_session",
)

def role_connection_audit(conn, role: str) -> dict:
    if role not in ROLES:
        raise RuntimeError("UNAPPROVED_ROLE")
    with conn.transaction():
        conn.execute("SET TRANSACTION READ ONLY")
        info = conn.execute(
            "SELECT current_database(),current_user,session_user,"
            "host(inet_server_addr()),inet_server_port(),"
            "current_setting('server_version_num')::integer,"
            "current_setting('transaction_read_only')"
        ).fetchone()
        # Original data_directory was already attested with owner in M39054.
        # Limited app/auth/verifier roles must not need pg_read_all_settings.
        if (info[:5] != (DB, role, role, "127.0.0.1", 5433)
                or not 180000 <= info[5] < 190000
                or info[6] != "on"):
            raise RuntimeError("ROLE_NOT_ON_ORIGINAL_PG18_READONLY")
        flags = conn.execute(
            "SELECT rolcanlogin,rolsuper,rolbypassrls FROM pg_roles "
            "WHERE rolname=current_user"
        ).fetchone()
        if flags != (True, False, False):
            raise RuntimeError("ROLE_LOGIN_OR_PRIVILEGE_UNSAFE")
        granted = []
        for relation in TABLE_GRANTS[role]:
            table_grant = conn.execute(
                "SELECT has_table_privilege(current_user,%s,'SELECT')",
                (relation,),
            ).fetchone()
            if table_grant != (True,):
                raise RuntimeError("MISSING_ROLE_TABLE_GRANT_" + relation.removeprefix("public."))
            granted.append(relation)

        granted_columns = 0
        for relation, columns in COLUMN_SELECT[role].items():
            # Papel pode ler colunas contratuais, mas nao a tabela toda.
            table_wide = conn.execute(
                "SELECT has_table_privilege(current_user,%s,'SELECT')",
                (relation,),
            ).fetchone()
            if table_wide != (False,):
                raise RuntimeError(
                    "UNEXPECTED_ROLE_TABLE_WIDE_SELECT_" + relation.removeprefix("public.")
                )
            for column in columns:
                permitted = conn.execute(
                    "SELECT has_column_privilege(current_user,%s,%s,'SELECT')",
                    (relation, column),
                ).fetchone()
                if permitted != (True,):
                    raise RuntimeError(
                        "MISSING_ROLE_COLUMN_SELECT_"
                        + relation.removeprefix("public.") + "_" + column
                    )
                granted_columns += 1

        allowed_funcs = None
        if role == "frc_ai_auth":
            permission = conn.execute(
                "SELECT DISTINCT p.proname FROM pg_proc p "
                "JOIN pg_namespace n ON n.oid=p.pronamespace "
                "WHERE n.nspname='public' AND p.proname=ANY(%s) "
                "AND has_function_privilege(current_user,p.oid,'EXECUTE')",
                (list(AUTH_FUNCTIONS),),
            ).fetchall()
            allowed_funcs = {item[0] for item in permission}
            if allowed_funcs != set(AUTH_FUNCTIONS):
                raise RuntimeError("AUTH_FUNCTION_EXECUTE_GRANTS_INCOMPLETE")

    return {"role": role, "tables": len(granted), "columns": granted_columns, "auth_functions": len(allowed_funcs or ())}


def main() -> int:
    print("=== FR FINANCE M39055 — CONEXOES AUTH ORIGINAL READ ONLY ===",flush=True)
    try:
        verify_original()
    except Exception:
        print("M39055_STATUS=BLOCKED_ORIGINAL_REPO_OR_SHA")
        return 2
    try:
        import psycopg
    except ImportError:
        print("M39055_STATUS=BLOCKED_PSYCOPG_MISSING")
        return 2

    print("M39055_TENANTS_AND_SESSIONS=NO_DATA_READ")
    print("M39055_PASSWORDS=HIDDEN_NOT_SAVED")
    for role in ROLES:
        print("M39055_CHECK_ROLE=" + role,flush=True)
        password = getpass(f"Senha PostgreSQL {role} (oculta): ")
        if not password:
            print("M39055_STATUS=BLOCKED_EMPTY_ROLE_PASSWORD")
            return 2
        try:
            with psycopg.connect(
                host="127.0.0.1", port=5433, dbname=DB,
                user=role, password=password, connect_timeout=5,
                options="-c default_transaction_read_only=on "
                        "-c statement_timeout=10000 -c lock_timeout=2000",
            ) as conn:
                password = ""
                result = role_connection_audit(conn,role)
            print("M39055_" + role.upper() + "=PASS")
            print("M39055_" + role.upper() + "_TABLE_GRANTS=" + str(result["tables"]))
            print("M39055_" + role.upper() + "_COLUMN_GRANTS=" + str(result["columns"]))
            if role == "frc_ai_auth":
                print("M39055_AUTH_FUNCTIONS_EXECUTABLE=" + str(result["auth_functions"]))
        except RuntimeError as exc:
            print("M39055_STATUS=BLOCKED_ROLE_PERMISSIONS")
            print("M39055_REASON=" + str(exc))
            print("M39055_DATABASE_WRITES=NONE")
            return 2
        except Exception as exc:
            print("M39055_STATUS=BLOCKED_ROLE_CONNECTION")
            print("M39055_ROLE=" + role)
            print("M39055_ERROR_TYPE=" + type(exc).__name__)
            print("M39055_DATABASE_WRITES=NONE")
            return 2

    print("M39055_AUTH_CREDENTIAL_SEPARATION=PASS")
    print("M39055_SESSIONS_CREATED=NONE")
    print("M39055_LOGIN_REAL=NOT_ATTEMPTED")
    print("M39055_DATABASE_WRITES=NONE")
    print("M39055_MIGRATIONS=NONE")
    print("M39055_EXTERNAL_NOTIFICATIONS=OFF")
    print("M39055_PIX_REAL=OFF")
    print("M39055_STATUS=PASS_READ_ONLY")
    return 0


if __name__ == "__main__":
    sys.exit(main())
