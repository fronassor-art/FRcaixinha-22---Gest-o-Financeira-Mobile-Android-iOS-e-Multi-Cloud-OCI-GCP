#!/usr/bin/env python3
"""FR Finance M39034: handshake REAL PG18 RLS + API offline, NO WRITES.

Debian PRoot, official PostgreSQL 18 on Termux :5433. No auth token, customer
record, session, network request, bank transaction or marketing transmission.
CI and local checks fail closed. No SQL migrations are executed.
"""
from __future__ import annotations

import getpass
import os
from pathlib import Path
import sys
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parent))
from frfinance_m39026_credit_only_preflight import (  # noqa: E402
    verify_repo, SPECIAL, DATA_DIRECTORY, DB, OWNER,
)

NO_ONE_TENANT = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"
NO_ONE_USER = "dddddddd-dddd-4ddd-8ddd-dddddddddddd"


def audit_local_rls(conn) -> None:
    """SET LOCAL ROLE and context live inside a READ ONLY PostgreSQL txn."""
    with conn.transaction():
        conn.execute("SET TRANSACTION READ ONLY")
        row = conn.execute(
            "SELECT current_database(),session_user,"
            "host(inet_server_addr()),inet_server_port(),"
            "current_setting('data_directory'),"
            "current_setting('server_version_num')::integer,"
            "current_setting('transaction_read_only')"
        ).fetchone()
        if (row[:2] != (DB, OWNER) or row[2] != "127.0.0.1"
                or row[3] != 5433 or row[4] != DATA_DIRECTORY
                or not 180000 <= row[5] < 190000 or row[6] != "on"):
            raise RuntimeError("ORIGINAL_PG18_READONLY_IDENTITY_INVALID")
        count = conn.execute(
            "SELECT count(*) FROM pg_catalog.pg_tables WHERE schemaname='public'"
        ).fetchone()[0]
        if count != 53:
            raise RuntimeError("POST_MIGRATION_TABLE_COUNT_NOT_53")

        conn.execute("SET LOCAL ROLE frc_ai_app")
        role = conn.execute("SELECT current_user,session_user").fetchone()
        if role != ("frc_ai_app", OWNER):
            raise RuntimeError("APPLICATION_ROLE_NOT_ACTIVE")
        if not conn.execute(
            "SELECT current_setting('transaction_read_only')"
        ).fetchone()[0] == "on":
            raise RuntimeError("POST_ROLE_READONLY_NOT_ACTIVE")

        for table in SPECIAL:
            relname = "public." + table
            active = conn.execute(
                "SELECT row_security_active(%s::regclass)", (relname,)
            ).fetchone()[0]
            if active is not True:
                raise RuntimeError("RLS_NOT_ACTIVE_FOR_APP_" + table)

        # No application context: no visibility. Never inspect actual rows.
        for table in SPECIAL:
            count = conn.execute(
                "SELECT count(*) FROM public." + table
            ).fetchone()[0]
            if count != 0:
                raise RuntimeError("RLS_NO_CONTEXT_VISIBILITY_" + table)

        # Synthetic tenant/user are deliberately nonexistent; the backend
        # normally binds these via SET LOCAL only after session verification.
        for var, value in (
            ("app.current_tenant_id", NO_ONE_TENANT),
            ("app.current_user_id", NO_ONE_USER),
            ("app.current_role", "TENANT_MEMBER"),
        ):
            conn.execute("SELECT set_config(%s,%s,true)", (var, value))
        for table in SPECIAL:
            count = conn.execute(
                "SELECT count(*) FROM public." + table
            ).fetchone()[0]
            if count != 0:
                raise RuntimeError("RLS_SYNTHETIC_CONTEXT_VISIBILITY_" + table)
    print("M39034_PG18_ORIGINAL=PASS")
    print("M39034_APP_ROLE=frc_ai_app")
    print("M39034_RLS_ACTIVE=6_OF_6")
    print("M39034_NO_CONTEXT_VISIBILITY=0_OF_6")
    print("M39034_SYNTHETIC_CONTEXT_VISIBILITY=0_OF_6")
    print("M39034_PG_READ_ONLY=PASS")


def audit_api_offline() -> None:
    """Local TestClient, no socket and no database dependency call."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.app.dependencies import AuthenticatedSession
    from backend.app.routers import special_credit as routes

    # This Python process never enables real functionality. Existing
    # environment variables are restored before leaving the function.
    old = os.environ.get("FR_FINANCE_SPECIAL_CREDIT_SANDBOX")
    os.environ["FR_FINANCE_SPECIAL_CREDIT_SANDBOX"] = "NO"
    try:
        app = FastAPI()
        app.include_router(routes.router, prefix="/api/v1")
        app.dependency_overrides[routes.get_rls_db_connection] = lambda: None
        base = "/api/v1/tenants/" + NO_ONE_TENANT + "/special-credit"
        with TestClient(app, raise_server_exceptions=True) as anonymous:
            if anonymous.get(base + "/capabilities").status_code != 401:
                raise RuntimeError("API_ANONYMOUS_CAPABILITIES_NOT_DENIED")
            if anonymous.get(base + "/members").status_code != 401:
                raise RuntimeError("API_ANONYMOUS_MEMBERS_NOT_DENIED")

        session = AuthenticatedSession(
            NO_ONE_USER, "TENANT_ADMIN", NO_ONE_TENANT,
            "synthetic@example.invalid", "Teste fictício", False,
        )
        app.dependency_overrides[routes.get_current_session] = lambda: session
        with TestClient(app, raise_server_exceptions=True) as admin:
            r = admin.get(base + "/capabilities")
            if r.status_code != 200:
                raise RuntimeError("API_CAPABILITIES_NOT_READABLE")
            value = r.json()
            if value.get("sandbox_enabled") is not False:
                raise RuntimeError("API_SANDBOX_WAS_ENABLED")
            if value.get("real_credit_enabled") is not False:
                raise RuntimeError("API_REAL_CREDIT_WAS_ENABLED")
            if value.get("pix_real_enabled") is not False:
                raise RuntimeError("API_REAL_PIX_WAS_ENABLED")
            if any(ch.get("real_delivery_enabled") is not False
                   for ch in value.get("channels", {}).values()):
                raise RuntimeError("API_EXTERNAL_CHANNEL_WAS_ENABLED")
            if admin.get(base + "/members").status_code != 503:
                raise RuntimeError("API_ADMIN_WRITE_SCOPE_NOT_DISABLED")

        print("M39034_API_ANONYMOUS_DENIED=PASS")
        print("M39034_API_SANDBOX_OFF=PASS")
        print("M39034_API_REAL_PIX_AND_CHANNELS=OFF")
        print("M39034_API_NETWORK_CALLS=NONE")
    finally:
        if old is None:
            os.environ.pop("FR_FINANCE_SPECIAL_CREDIT_SANDBOX", None)
        else:
            os.environ["FR_FINANCE_SPECIAL_CREDIT_SANDBOX"] = old


def main() -> int:
    print("=== FR FINANCE M39034 — PG18 RLS + API OFFLINE ===")
    try:
        verify_repo()
    except Exception:
        print("M39034_STATUS=BLOCKED_REPOSITORY_CHECK")
        return 2
    try:
        import psycopg
    except ImportError:
        print("M39034_STATUS=BLOCKED_EXISTING_PYTHON_VENV_REQUIRED")
        return 2
    passwd = getpass.getpass("Senha PostgreSQL frc_ai_owner (oculta): ")
    if not passwd:
        print("M39034_STATUS=BLOCKED_EMPTY_DB_PASSWORD")
        return 2
    try:
        with psycopg.connect(
            host="127.0.0.1", port=5433, dbname=DB, user=OWNER,
            password=passwd, connect_timeout=5,
            options="-c default_transaction_read_only=on "
                    "-c statement_timeout=12000 -c lock_timeout=2000",
        ) as conn:
            del passwd
            audit_local_rls(conn)
        audit_api_offline()
    except RuntimeError as e:
        print("M39034_STATUS=BLOCKED")
        print("M39034_REASON=" + str(e))
        print("M39034_DATABASE_WRITES=NONE")
        return 2
    except Exception:
        print("M39034_STATUS=BLOCKED_RUNTIME_OR_DATABASE_CHECK")
        print("M39034_DATABASE_WRITES=NONE")
        return 2
    print("M39034_SQL110_111=ALREADY_APPLIED_DO_NOT_REPEAT")
    print("M39034_DATABASE_WRITES=NONE")
    print("M39034_STATUS=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
