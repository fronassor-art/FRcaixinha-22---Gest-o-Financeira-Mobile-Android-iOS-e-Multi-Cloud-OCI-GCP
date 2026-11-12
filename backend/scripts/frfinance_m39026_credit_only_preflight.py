#!/usr/bin/env python3
"""M39026 — crédito especial 110/111: preflight REAL e estritamente read-only.

Consulta somente catálogo do PostgreSQL 18 original. NÃO audita M20700 ou
reaplica migrações antigas; NÃO altera tabelas, contratos, Pix ou outbox.
Executar com /root/.venvs/frcaixinha-aistudio/bin/python (psycopg já instalado).
"""
from __future__ import annotations

import getpass
import os
from pathlib import Path
import subprocess
import sys

PROJECT = Path.home() / "fr-finance"
BRANCH = "atualizacao-ai-studio-9b46a63187"
DB = "frcaixinha_aistudio_dev"
OWNER = "frc_ai_owner"
DATA_DIRECTORY = "/data/data/com.termux/files/usr/var/lib/frcaixinha_aistudio_pg18"
SPECIAL = (
    "special_credit_grants",
    "special_credit_campaigns",
    "special_credit_recipients",
    "special_credit_preferences",
    "special_credit_outbox",
    "special_credit_audit",
)
GUARDS = (
    "sc_m39020_grant_transition",
    "sc_m39020_campaign_transition",
    "sc_m39020_recipient_insert",
    "sc_m39020_reply_transition",
    "sc_m39020_outbox_insert",
)
REQUIRED = {
    "users": {"id": "uuid"},
    "tenants": {"id": "uuid", "admin_user_id": "uuid", "status": "character varying"},
    "memberships": {
        "id": "uuid", "tenant_id": "uuid", "user_id": "uuid",
        "role": "character varying", "status": "character varying",
    },
    "cycles": {
        "id": "uuid", "tenant_id": "uuid", "status": "character varying",
        "start_date": "date", "end_date": "date",
    },
}

def blocked(reason: str) -> int:
    print("M39026_STATUS=BLOCKED", flush=True)
    print("M39026_REASON=" + reason, flush=True)
    print("M39026_DATABASE_WRITES=NONE", flush=True)
    return 2

def git(*args: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(PROJECT), *args],
        text=True, stderr=subprocess.DEVNULL,
    ).strip()

def verify_repo() -> None:
    if not PROJECT.is_dir() or not (PROJECT / ".git").exists():
        raise RuntimeError("DEBIAN_REPOSITORY_NOT_FOUND")
    approved = os.environ.get("AI_STUDIO_APPROVED_SHA", "")
    if len(approved) != 40 or not all(c in "0123456789abcdef" for c in approved):
        raise RuntimeError("APPROVED_SHA_REQUIRED")
    if git("branch", "--show-current") != BRANCH:
        raise RuntimeError("BRANCH_MISMATCH")
    if git("rev-parse", "HEAD") != approved:
        raise RuntimeError("HEAD_NOT_APPROVED")
    if git("rev-parse", "refs/remotes/origin/" + BRANCH) != approved:
        raise RuntimeError("LOCAL_REMOTE_NOT_APPROVED")
    if git("status", "--porcelain", "--untracked-files=no"):
        raise RuntimeError("TRACKED_LOCAL_CHANGES")
    for f in (
        "backend/migrations/110_fr_finance_special_credit_offline.sql",
        "backend/migrations/111_frfinance_special_credit_integrity_guards.sql",
    ):
        if not (PROJECT / f).is_file():
            raise RuntimeError("CREDIT_SQL_MISSING")
    # The historical inventory's repo-check is safe. NEVER call local-readonly:
    # it audits unrelated previous business rules and blocks this scope.
    proc = subprocess.run(
        [sys.executable, str(PROJECT/"backend/scripts/aistudio_migration_inventory.py"),
         "repo-check"],
        cwd=PROJECT, capture_output=True, text=True, check=False,
    )
    if proc.returncode != 0 or "M19200_REGISTRY_HASHES=PASS" not in proc.stdout:
        raise RuntimeError("SQL_REGISTRY_OR_HASH_MISMATCH")

def audit(conn) -> None:
    with conn.transaction():
        conn.execute("SET TRANSACTION READ ONLY")
        identity = conn.execute(
            "SELECT current_database(),current_user,session_user,"
            "host(inet_server_addr()),inet_server_port(),"
            "current_setting('data_directory'),"
            "current_setting('server_version_num')::integer"
        ).fetchone()
        if (identity[:3] != (DB, OWNER, OWNER)
                or identity[3] != "127.0.0.1"
                or identity[4] != 5433 or identity[5] != DATA_DIRECTORY
                or not 180000 <= identity[6] < 190000):
            raise RuntimeError("WRONG_POSTGRESQL_ORIGINAL_IDENTITY")

        roles = conn.execute(
            "SELECT rolname,rolsuper,rolbypassrls,rolcanlogin "
            "FROM pg_roles WHERE rolname IN ('frc_ai_app','frc_ai_auth')"
        ).fetchall()
        if len(roles) != 2 or any(superuser or bypass
                                 for _, superuser, bypass, _ in roles):
            raise RuntimeError("APPLICATION_ROLE_ISOLATION_INVALID")

        count = conn.execute(
            "SELECT count(*) FROM pg_catalog.pg_tables "
            "WHERE schemaname='public'"
        ).fetchone()[0]
        if count != 47:
            raise RuntimeError("EXPECTED_47_PRE_CREDIT_TABLES_FOUND_" + str(count))

        columns = conn.execute(
            "SELECT table_name,column_name,data_type "
            "FROM information_schema.columns WHERE table_schema='public' "
            "AND table_name=ANY(%s)",
            (list(REQUIRED),),
        ).fetchall()
        actual = {(t, col): dtype for t, col, dtype in columns}
        for table, spec in REQUIRED.items():
            for col, dtype in spec.items():
                if actual.get((table, col)) != dtype:
                    raise RuntimeError("BASELINE_COLUMN_INCOMPATIBLE_" + table + "_" + col)

        objects = conn.execute(
            "SELECT to_regclass('public.'||obj) IS NOT NULL "
            "FROM unnest(%s::text[]) AS obj",
            (list(SPECIAL),),
        ).fetchall()
        if any(item[0] for item in objects):
            raise RuntimeError("CREDIT_TABLE_ALREADY_EXISTS_OR_PARTIAL")

        existing_triggers = conn.execute(
            "SELECT count(*) FROM pg_trigger WHERE tgname=ANY(%s)",
            (list(GUARDS),),
        ).fetchone()[0]
        if existing_triggers:
            raise RuntimeError("CREDIT_TRIGGER_COLLISION")

        index_collision = conn.execute(
            "SELECT to_regclass('public.uq_special_active_member_cycle') IS NOT NULL"
        ).fetchone()[0]
        if index_collision:
            raise RuntimeError("CREDIT_INDEX_COLLISION")

        # Reference tables contain no customer data in the output. We do not
        # query member income, contribution values, credentials or balances.
        print("M39026_DB_IDENTITY=PG18_ORIGINAL_5433_PASS")
        print("M39026_APPLICATION_ROLES=ISOLATED_PASS")
        print("M39026_PUBLIC_TABLES_PRE_CREDIT=47")
        print("M39026_REFERENCE_COLUMNS=COMPATIBLE")
        print("M39026_CREDIT_TABLES=ABSENT_6_OF_6")
        print("M39026_CREDIT_TRIGGERS=ABSENT_5_OF_5")
        print("M39026_SQL_110_111=READY_FOR_SEPARATELY_APPROVED_BACKUP_AND_APPLY")
        print("M39026_OLD_MIGRATIONS=NOT_REAPPLIED")
        print("M39026_DATABASE_WRITES=NONE")
        print("M39026_PIX_REAL=UNCHANGED")
        print("M39026_STATUS=PASS")

def main() -> int:
    print("=== FR FINANCE M39026 — CREDIT-ONLY PREFLIGHT READ-ONLY ===")
    try:
        verify_repo()
    except Exception as e:
        return blocked(str(e) if isinstance(e, RuntimeError) else "REPO_CHECK_FAILED")
    try:
        import psycopg
    except ImportError:
        return blocked("USE_EXISTING_FRCAIXINHA_AISTUDIO_VENV_PYTHON")
    print("M39026_PYTHON=" + sys.executable)
    print("M39026_PSYCOPG=" + psycopg.__version__)
    password = getpass.getpass("Senha frc_ai_owner no Debian (oculta): ")
    if not password:
        return blocked("PASSWORD_REQUIRED")
    try:
        with psycopg.connect(
            host="127.0.0.1", port=5433, dbname=DB, user=OWNER,
            password=password, connect_timeout=5,
            options="-c default_transaction_read_only=on "
                    "-c statement_timeout=10000 -c lock_timeout=2000",
        ) as conn:
            del password
            audit(conn)
        return 0
    except RuntimeError as e:
        return blocked(str(e))
    except Exception:
        # Never echo SQL, DB password, tokens or sensitive diagnostics.
        return blocked("DATABASE_READ_ONLY_AUDIT_FAILED")

if __name__ == "__main__":
    raise SystemExit(main())
