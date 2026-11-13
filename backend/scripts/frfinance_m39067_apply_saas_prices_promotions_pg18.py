#!/usr/bin/env python3
"""M39067 — SQL112+SQL113 em transação única e backup PG18 original.

Sem acesso 5432, clones, CI/staging, Pix, e-mail, sessões ou licenças.
--inspect é estritamente read-only. --apply requer confirmação de operador
e backup custom prévio; NÃO é chamado por GitHub Actions.
"""
from __future__ import annotations

import argparse
import getpass
import os
from pathlib import Path
import stat
import subprocess
import sys

from backend.scripts.frfinance_m39066_master_prices_sql112_termux import (
    Blocked, ROOT, DB, OWNER,
    validate_context, database_identity, inspect_original, private_backup,
)

SQL112 = ROOT / "backend/migrations/112_frfinance_master_independent_saas_prices.sql"
SQL113 = ROOT / "backend/migrations/113_frfinance_saas_new_admin_promotions.sql"
SQL113_BLOB = "3e126f2b6ca43d0e73a4be2aa44e204b58bf3911"


def validate_sql113_hash() -> None:
    if SQL113.is_symlink() or not SQL113.is_file():
        raise Blocked("SQL113_FILE_MISSING_OR_SYMLINK")
    result = subprocess.run(
        ["git", "hash-object", str(SQL113)], cwd=ROOT,
        capture_output=True, text=True, check=False
    )
    if result.returncode != 0 or result.stdout.strip() != SQL113_BLOB:
        raise Blocked("SQL113_HASH_MISMATCH")


def is_sql113_installed(conn) -> tuple[bool,bool]:
    row = conn.execute(
        "SELECT to_regclass('public.platform_saas_promotion_revisions') IS NOT NULL,"
        "to_regprocedure('public.frfinance_saas_new_admin_published_promotions()') IS NOT NULL"
    ).fetchone()
    return (row[0] is True, row[1] is True)


def inspect_sql112_113(conn) -> tuple[str,str,int]:
    monthly_state = inspect_original(conn)
    with conn.transaction():
        conn.execute("SET TRANSACTION READ ONLY")
        installed_table, installed_function = is_sql113_installed(conn)
        if installed_table != installed_function:
            raise Blocked("SQL113_PARTIAL_INSTALLATION")
        total = conn.execute(
            "SELECT count(*) FROM public.platform_license_price_versions"
        ).fetchone()[0]
        if not installed_table:
            if monthly_state != "LEGACY_10X_GENERATED_READY_FOR_SQL112":
                raise Blocked("SQL112_ALREADY_APPLIED_SQL113_ABSENT_REVIEW_MANUALLY")
            return monthly_state, "SQL113_NOT_APPLIED", total

        if monthly_state != "SQL112_ALREADY_APPLIED_SAFE_NO_REPEAT":
            raise Blocked("SQL113_PRESENT_WITHOUT_SQL112")
        table_audit = conn.execute(
            "SELECT relrowsecurity,relforcerowsecurity "
            "FROM pg_catalog.pg_class "
            "WHERE oid='public.platform_saas_promotion_revisions'::regclass"
        ).fetchone()
        access = conn.execute(
            "SELECT "
            "has_table_privilege('frcaixinha_app_role',"
            "'public.platform_saas_promotion_revisions','SELECT'),"
            "has_table_privilege('frcaixinha_auth_role',"
            "'public.platform_saas_promotion_revisions','SELECT'),"
            "has_table_privilege('frcaixinha_app_role',"
            "'public.platform_saas_promotion_revisions','UPDATE'),"
            "has_table_privilege('frcaixinha_app_role',"
            "'public.platform_saas_promotion_revisions','DELETE'),"
            "has_function_privilege('frcaixinha_app_role',"
            "'public.frfinance_saas_new_admin_published_promotions()','EXECUTE'),"
            "has_function_privilege('frcaixinha_auth_role',"
            "'public.frfinance_saas_new_admin_published_promotions()','EXECUTE')"
        ).fetchone()
        if table_audit != (True,True) or access != (
            True,False,False,False,True,False,
        ):
            raise Blocked("SQL113_RLS_OR_PRIVILEGES_UNSAFE")
        return monthly_state, "SQL113_APPLIED_SAFE_NO_REPEAT", total


def apply_in_single_transaction(conn, count_before: int) -> None:
    ddl112 = SQL112.read_text(encoding="utf-8")
    ddl113 = SQL113.read_text(encoding="utf-8")
    required = (
        "ALTER COLUMN annual_price DROP EXPRESSION" in ddl112
        and "CREATE TABLE public.platform_saas_promotion_revisions" in ddl113
        and "CREATE FUNCTION public.frfinance_saas_new_admin_published_promotions()" in ddl113
        and "FORCE ROW LEVEL SECURITY" in ddl113
    )
    if not required:
        raise Blocked("SQL112_113_REQUIRED_STRUCTURE_MISSING")
    with conn.transaction():
        conn.execute("SET LOCAL statement_timeout='45000ms'")
        conn.execute("SET LOCAL lock_timeout='5000ms'")
        conn.execute(ddl112)
        conn.execute(ddl113)
        state = conn.execute(
            "SELECT attgenerated,attnotnull FROM pg_catalog.pg_attribute "
            "WHERE attrelid='public.platform_license_price_versions'::regclass "
            "AND attname='annual_price'"
        ).fetchone()
        installed = is_sql113_installed(conn)
        remaining = conn.execute(
            "SELECT count(*) FROM public.platform_license_price_versions"
        ).fetchone()[0]
        rls = conn.execute(
            "SELECT relrowsecurity AND relforcerowsecurity "
            "FROM pg_catalog.pg_class "
            "WHERE oid='public.platform_saas_promotion_revisions'::regclass"
        ).fetchone()[0]
        if (state != ("",True) or installed != (True,True) or
                remaining != count_before or rls is not True):
            raise Blocked("SQL112_113_ATOMIC_POSTCHECK_FAILED_ROLLBACK")
    # Somente depois do commit, revalidar grants e RLS.
    post_monthly, post_campaigns, after_count = inspect_sql112_113(conn)
    if (post_monthly != "SQL112_ALREADY_APPLIED_SAFE_NO_REPEAT"
            or post_campaigns != "SQL113_APPLIED_SAFE_NO_REPEAT"
            or after_count != count_before):
        raise Blocked("SQL112_113_POSTCOMMIT_INSPECTION_FAILED")


def main() -> int:
    parser = argparse.ArgumentParser()
    arg = parser.add_mutually_exclusive_group(required=True)
    arg.add_argument("--inspect", action="store_true")
    arg.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    print("=== FR FINANCE M39067 — PRECO SAAS E PROMOCOES SQL112+113 ===")
    try:
        validate_context()
        validate_sql113_hash()
        if args.apply and not sys.stdin.isatty():
            raise Blocked("INTERACTIVE_OPERATOR_REQUIRED")
        import psycopg
        password = getpass.getpass("Senha do PostgreSQL FR Finance frc_ai_owner (oculta): ")
        if not password:
            raise Blocked("EMPTY_ORIGINAL_OWNER_PASSWORD")
        with psycopg.connect(
            host="127.0.0.1",port=5433,dbname=DB,user=OWNER,
            password=password,connect_timeout=5,autocommit=True,
        ) as conn:
            monthly,campaigns,old_count = inspect_sql112_113(conn)
            print("M39067_ORIGINAL_PG18=FR_FINANCE_127_0_0_1_5433_PASS")
            print("M39067_SQL112=" + monthly)
            print("M39067_SQL113=" + campaigns)
            if args.inspect:
                print("M39067_DATABASE_WRITES=NONE")
                print("M39067_STATUS=PASS_READ_ONLY_PREFLIGHT")
                return 0
            if monthly == "SQL112_ALREADY_APPLIED_SAFE_NO_REPEAT" and campaigns == "SQL113_APPLIED_SAFE_NO_REPEAT":
                print("M39067_MIGRATION=ALREADY_APPLIED_NO_REPEAT")
                print("M39067_STATUS=PASS_ALREADY_APPLIED")
                return 0
            if (monthly != "LEGACY_10X_GENERATED_READY_FOR_SQL112"
                    or campaigns != "SQL113_NOT_APPLIED"):
                raise Blocked("UNSAFE_PARTIAL_SQL112_113_STATE")
            approval = input(
                "Digite APLICAR_SQL112_113_FR_FINANCE para migrar SOMENTE "
                "o banco original, após backup: "
            )
            if approval != "APLICAR_SQL112_113_FR_FINANCE":
                raise Blocked("OPERATOR_CANCELLED")
            backup = private_backup(password)
            print("M39067_BACKUP=PASS_PG18_CUSTOM_ARCHIVE_CATALOG")
            print("M39067_RESTORE_TEST=NOT_ATTESTED_SEPARATE_RECOVERY_TEST_REQUIRED")
            apply_in_single_transaction(conn,old_count)
        print("M39067_DB_BACKUP_SAVED=YES_PRIVATE_TERMUX")
        print("M39067_MIGRATIONS=SQL112_SQL113_APPLIED_ATOMICALLY")
        print("M39067_HISTORICAL_PRICE_VERSION_COUNT=UNCHANGED")
        print("M39067_STATUS=PASS_APPLIED_POSTCHECK")
        return 0
    except Blocked as error:
        print("M39067_STATUS=BLOCKED_" + str(error))
        return 2
    except Exception as error:
        print("M39067_STATUS=BLOCKED_RUNTIME_" + type(error).__name__)
        return 2
    finally:
        print("M39067_DB_5432_ACCESS=NONE")
        print("M39067_PASSWORD_RESET=NONE")
        print("M39067_REAL_PIX=OFF")
        print("M39067_EXTERNAL_DELIVERY=OFF")
        print("M39067_REAL_USER_ACTIVATION=OFF")
        print("M39067_FASTAPI_RESTART=NONE")
        print("M39067_APK_INSTALLATION=NONE")


if __name__ == "__main__":
    raise SystemExit(main())
