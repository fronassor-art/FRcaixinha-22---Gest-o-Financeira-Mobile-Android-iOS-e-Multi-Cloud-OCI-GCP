#!/usr/bin/env python3
"""M39066 SQL112 — inspeção e aplicação EXPLICITA no PG18 FR Finance original.

--inspect é sempre read-only. --apply exige confirmação interativa, backup
PG18, check de identidade, do hash SQL e transação DDL atômica.
Nunca cria banco, clone ou role; não executa SQL110/111/CI/staging;
não altera senhas, sessões, planos contratados, Pix ou e-mail.
"""
from __future__ import annotations

import argparse
import getpass
import os
from pathlib import Path
import stat
import subprocess
import sys
from datetime import datetime, timezone

from backend.scripts.frfinance_m39054_auth_pg18_preflight import verify_original

HOME = Path("/data/data/com.termux/files/home")
ROOT = HOME / "fr-finance"
PGDATA = Path("/data/data/com.termux/files/usr/var/lib/frcaixinha_aistudio_pg18")
PG_BIN = Path("/data/data/com.termux/files/usr/bin")
MIGRATION = ROOT / "backend/migrations/112_frfinance_master_independent_saas_prices.sql"
BACKUP_DIR = HOME / ".config/frcaixinha-aistudio-mobile/backups/m39066"
DB = "frcaixinha_aistudio_dev"
OWNER = "frc_ai_owner"
EXPECTED_SQL_BLOB = "10da8aaef7beb3d6559a14d064be53e1aae5a01f"
EXPECTED_TABLES = (
    "public.platform_license_plans",
    "public.platform_license_price_versions",
)


class Blocked(RuntimeError):
    pass


def validate_context() -> None:
    verify_original()
    if Path.cwd().resolve() != ROOT or os.environ.get("HOME") != str(HOME):
        raise Blocked("NONCANONICAL_NATIVE_TERMUX")
    if PGDATA.is_symlink() or not (PGDATA / "PG_VERSION").is_file():
        raise Blocked("NONCANONICAL_PGDATA")
    if (PGDATA / "PG_VERSION").read_text(encoding="utf-8").strip() != "18":
        raise Blocked("PG18_ORIGINAL_REQUIRED")
    if any(os.environ.get(v) for v in (
        "PGOPTIONS", "PGSERVICE", "PGHOSTADDR", "PGPASSFILE"
    )):
        raise Blocked("EXTERNAL_LIBPQ_OVERRIDE_BLOCKED")
    blob = subprocess.run(
        ["git", "hash-object", str(MIGRATION)],
        capture_output=True, text=True, check=False,
    )
    if blob.returncode != 0 or blob.stdout.strip() != EXPECTED_SQL_BLOB:
        raise Blocked("SQL112_HASH_MISMATCH")
    from backend.scripts.aistudio_migration_inventory import repo_check
    repo_check()


def database_identity(row: tuple) -> bool:
    return (
        len(row) == 7
        and row[0] == DB and row[1] == OWNER and row[2] == OWNER
        and row[3] == "127.0.0.1" and row[4] == 5433
        and row[5] == str(PGDATA) and 180000 <= row[6] < 190000
    )


def inspect_original(conn) -> str:
    with conn.transaction():
        conn.execute("SET TRANSACTION READ ONLY")
        row = conn.execute(
            "SELECT current_database(),session_user,current_user,"
            "host(inet_server_addr()),inet_server_port(),"
            "current_setting('data_directory'),"
            "current_setting('server_version_num')::integer"
        ).fetchone()
        if not database_identity(row):
            raise Blocked("WRONG_POSTGRESQL_OR_OWNER")
        for table in EXPECTED_TABLES:
            if conn.execute("SELECT to_regclass(%s) IS NOT NULL", (table,)).fetchone()[0] is not True:
                raise Blocked("PLATFORM_LICENSE_BASELINE_MISSING")
        details = conn.execute(
            "SELECT attgenerated,attnotnull FROM pg_catalog.pg_attribute "
            "WHERE attrelid='public.platform_license_price_versions'::regclass "
            "AND attname='annual_price' AND NOT attisdropped"
        ).fetchone()
        if details is None:
            raise Blocked("ANNUAL_COLUMN_MISSING")
        rows = conn.execute(
            "SELECT count(*)::integer,count(*) FILTER "
            "(WHERE monthly_price<=0 OR annual_price<=0)::integer "
            "FROM public.platform_license_price_versions"
        ).fetchone()
        if rows[1] != 0:
            raise Blocked("EXISTING_PRICE_VERSION_INVALID")
        if details[0] == "s":
            state = "LEGACY_10X_GENERATED_READY_FOR_SQL112"
        elif details[0] == "" and details[1] is True:
            granted = conn.execute(
                "SELECT has_column_privilege('frcaixinha_app_role',"
                "'public.platform_license_price_versions','annual_price','INSERT')"
            ).fetchone()[0]
            constraint = conn.execute(
                "SELECT EXISTS(SELECT 1 FROM pg_catalog.pg_constraint "
                "WHERE conrelid='public.platform_license_price_versions'::regclass "
                "AND conname='platform_license_annual_price_positive')"
            ).fetchone()[0]
            if not granted or not constraint:
                raise Blocked("PARTIAL_MIGRATION_OR_PRIVILEGE_MISMATCH")
            state = "SQL112_ALREADY_APPLIED_SAFE_NO_REPEAT"
        else:
            raise Blocked("UNEXPECTED_ANNUAL_COLUMN_STATE")
    return state


def private_backup(password: str) -> Path:
    if BACKUP_DIR.is_symlink():
        raise Blocked("BACKUP_DIRECTORY_SYMLINK")
    BACKUP_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    if stat.S_IMODE(BACKUP_DIR.stat().st_mode) & 0o077:
        raise Blocked("BACKUP_DIRECTORY_PERMISSIONS")
    dump = PG_BIN / "pg_dump"
    restore = PG_BIN / "pg_restore"
    for tool in (dump, restore):
        if not tool.is_file() or not os.access(tool, os.X_OK):
            raise Blocked("PG18_BACKUP_CLIENT_MISSING")
        result = subprocess.run(
            [str(tool), "--version"], capture_output=True, text=True
        )
        if result.returncode != 0 or "(PostgreSQL) 18." not in result.stdout:
            raise Blocked("PG18_BACKUP_CLIENT_VERSION_MISMATCH")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    backup = BACKUP_DIR / ("frfinance_sql112_pre_" + stamp + "_" + str(os.getpid()) + ".dump")
    if backup.exists() or backup.is_symlink():
        raise Blocked("BACKUP_NAME_COLLISION")
    child_env = dict(os.environ)
    child_env["PGPASSWORD"] = password
    try:
        result = subprocess.run(
            [str(dump), "-w", "-h", "127.0.0.1", "-p", "5433",
             "-U", OWNER, "-d", DB, "--format=custom",
             "--file", str(backup)],
            env=child_env, capture_output=True, timeout=180,
        )
        if result.returncode != 0 or not backup.is_file() or backup.stat().st_size == 0:
            raise Blocked("PG18_BACKUP_FAILED_NO_SQL_APPLIED")
        backup.chmod(0o600)
        catalog = subprocess.run(
            [str(restore), "--list", str(backup)],
            env=child_env, capture_output=True, timeout=30,
        )
        if catalog.returncode != 0:
            raise Blocked("PG18_BACKUP_CATALOG_UNREADABLE")
    except (OSError, subprocess.SubprocessError):
        raise Blocked("PG18_BACKUP_TOOL_FAILED_NO_SQL_APPLIED") from None
    finally:
        child_env.pop("PGPASSWORD", None)
    return backup


def apply_migration(conn) -> None:
    source = MIGRATION.read_text(encoding="utf-8")
    if (
        "ALTER COLUMN annual_price DROP EXPRESSION" not in source
        or "GRANT INSERT (annual_price)" not in source
    ):
        raise Blocked("SQL112_REQUIRED_GUARDS_MISSING")
    # Primeiro inspect e backup COMPLETOS. Aqui começa a única transação DDL.
    with conn.transaction():
        conn.execute("SET LOCAL lock_timeout='5000ms'")
        conn.execute("SET LOCAL statement_timeout='30000ms'")
        # SQL112 exige PGDATA/role/coluna gerada antes da alteracao.
        conn.execute(source)
        # Validar DENTRO da transacao: erro aqui desfaz TODA a DDL.
        flag = conn.execute(
            "SELECT attgenerated FROM pg_catalog.pg_attribute "
            "WHERE attrelid='public.platform_license_price_versions'::regclass "
            "AND attname='annual_price' AND NOT attisdropped"
        ).fetchone()
        priv = conn.execute(
            "SELECT has_column_privilege('frcaixinha_app_role',"
            "'public.platform_license_price_versions','annual_price','INSERT')"
        ).fetchone()[0]
        if flag is None or flag[0] != "" or priv is not True:
            raise Blocked("SQL112_ATOMIC_VERIFICATION_FAILED")
    post = inspect_original(conn)
    if post != "SQL112_ALREADY_APPLIED_SAFE_NO_REPEAT":
        raise Blocked("SQL112_POSTCHECK_FAILED")


def main() -> int:
    parser = argparse.ArgumentParser()
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--inspect", action="store_true")
    modes.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    print("=== FR FINANCE M39066 — SQL112 PRECO MASTER INDEPENDENTE ===")
    try:
        validate_context()
        import psycopg
        if args.apply and not sys.stdin.isatty():
            raise Blocked("INTERACTIVE_OPERATOR_REQUIRED")
        password = getpass.getpass("Senha exclusiva frc_ai_owner (oculta): ")
        if not password:
            raise Blocked("EMPTY_OWNER_PASSWORD")
        with psycopg.connect(
            host="127.0.0.1", port=5433, dbname=DB, user=OWNER,
            password=password, connect_timeout=5, autocommit=True,
        ) as conn:
            state = inspect_original(conn)
            print("M39066_ORIGINAL_PG18_5433=PASS")
            print("M39066_PRICE_COLUMN=" + state)
            if args.inspect:
                print("M39066_DATABASE_WRITES=NONE")
                print("M39066_STATUS=PASS_READ_ONLY_PREFLIGHT")
                return 0
            if state != "LEGACY_10X_GENERATED_READY_FOR_SQL112":
                if state == "SQL112_ALREADY_APPLIED_SAFE_NO_REPEAT":
                    print("M39066_MIGRATION=ALREADY_APPLIED_NO_REPEAT")
                    print("M39066_STATUS=PASS_ALREADY_APPLIED")
                    return 0
                raise Blocked("UNSAFE_MIGRATION_STATE")
            print("M39066_BACKUP=REQUIRED_BEFORE_CONFIRMATION")
            answer = input("Digite APLICAR_SQL112_FR_FINANCE para criar backup e migrar SOMENTE o PG18 original: ")
            if answer != "APLICAR_SQL112_FR_FINANCE":
                raise Blocked("OPERATOR_CANCELLED_NO_SQL")
            backup = private_backup(password)
            print("M39066_BACKUP=PASS_CUSTOM_ARCHIVE_LIST_ONLY")
            print("M39066_BACKUP_RESTORE_PROOF=NOT_TESTED_NO_SECOND_DATABASE")
            apply_migration(conn)
        print("M39066_MIGRATION=APPLIED_ORIGINAL_PG18_ONLY")
        print("M39066_PRICE_HISTORY=EXISTING_VALUES_PRESERVED")
        print("M39066_DB_BACKUP_PATH=" + str(backup))
        print("M39066_DATABASE_WRITES=SQL112_ONLY")
        print("M39066_STATUS=PASS_APPLIED_WITH_POSTCHECK")
        return 0
    except Blocked as exc:
        print("M39066_STATUS=BLOCKED_" + str(exc))
        return 2
    except Exception as exc:
        # Nunca imprime URL, senha, SQL ou erro bruto do driver.
        print("M39066_STATUS=BLOCKED_RUNTIME_" + type(exc).__name__)
        return 2
    finally:
        print("M39066_NO_SECOND_DATABASE=TRUE")
        print("M39066_PIX_REAL=OFF")
        print("M39066_ACCESS_MAIL_WORKER=OFF")
        print("M39066_REAL_USER_ACTIVATION=OFF")
        print("M39066_DB_5432_ACCESS=NONE")
        print("M39066_SECRETS_DISPLAYED=NONE")


if __name__ == "__main__":
    sys.exit(main())
