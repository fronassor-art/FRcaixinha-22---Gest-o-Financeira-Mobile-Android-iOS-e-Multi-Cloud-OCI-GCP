#!/usr/bin/env python3
"""FR Finance M39500: source/PG18 original review without financial mutations.

Default --offline is pure standard library, CI-safe, credential free.
--original-readonly is OPTIONAL and requires an interactive terminal and the
existing owner password, which is never logged. No password reset or new DB.
Both modes forbid schema changes, sessions, Pix and external notifications.
"""
from __future__ import annotations
import argparse
import getpass
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.app.m39500_migration_reconciliation import (
    AttestationBlocked, verify_sources, verify_full_catalog,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="SQL 110..113 — READ ONLY")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--offline", action="store_true",
                      help="Source hashes and FR Finance identity, no database")
    mode.add_argument("--original-readonly", action="store_true",
                      help="Original PG18 catalog only, separate interactive approval")
    args = parser.parse_args(argv)
    print("=== FR FINANCE M39500 — SQL110–113 CHECKPOINT READ ONLY ===")
    result = 2
    try:
        sources = verify_sources()
        print("M39500_SQL_SOURCES=" + sources["sql_sources"])
        print("M39500_CONFIG_IDENTITY=" + sources["identity"])
        if not args.original_readonly:
            print("M39500_DB_SCHEMA=NOT_INSPECTED_OFFLINE")
            print("M39500_HISTORY=NOT_ATTESTED")
            print("M39500_STATUS=PASS_OFFLINE_SOURCE_ONLY")
            result = 0
        elif not sys.stdin.isatty():
            print("M39500_STATUS=BLOCKED_INTERACTIVE_TERMINAL_REQUIRED")
        else:
            try:
                import psycopg
            except ImportError:
                print("M39500_STATUS=BLOCKED_EXISTING_PSYCOPG_VENV_REQUIRED")
            else:
                password = getpass.getpass(
                    "Senha atual do banco FR Finance (oculta, sem alteração): ")
                if not password:
                    print("M39500_STATUS=BLOCKED_EMPTY_PASSWORD")
                else:
                    try:
                        with psycopg.connect(
                            host="127.0.0.1", port=5433,
                            dbname="frcaixinha_aistudio_dev",
                            user="frc_ai_owner", password=password,
                            connect_timeout=5, autocommit=True,
                            options="-c default_transaction_read_only=on "
                                    "-c statement_timeout=12000 "
                                    "-c lock_timeout=2000 "
                                    "-c idle_in_transaction_session_timeout=15000",
                        ) as conn:
                            password = None
                            review = verify_full_catalog(conn)
                        print("M39500_SQL110_111=" + review["sql_110_111"])
                        print("M39500_SQL112_113=" + review["sql_112_113"])
                        print("M39500_ORIGINAL_PG18=IDENTITY_RLS_ROLES_GUARDS_PASS")
                        print("M39500_PUBLIC_TABLE_COUNT_FIXED=NO")
                        print("M39500_HISTORY=NOT_ATTESTED_BY_SCHEMA_ALONE")
                        print("M39500_STATUS=PASS_READ_ONLY_CATALOG")
                        result = 0
                    except AttestationBlocked as exc:
                        print("M39500_STATUS=" + str(exc))
                    except Exception:
                        # Never report raw SQL/driver exceptions or DSN/password.
                        print("M39500_STATUS=BLOCKED_DB_CATALOG_RUNTIME")
                    finally:
                        password = None
    except AttestationBlocked as exc:
        print("M39500_STATUS=" + str(exc))
    except Exception:
        print("M39500_STATUS=BLOCKED_SOURCE_RUNTIME")
    finally:
        print("M39500_PG5432_ACCESS=NONE")
        print("M39500_DB_WRITES=NONE")
        print("M39500_MIGRATIONS=NONE")
        print("M39500_FASTAPI_RESTART=NONE")
        print("M39500_CLOUD_MUTATIONS=NONE")
        print("M39500_PIX_REAL=OFF")
        print("M39500_PAYMENTS_REAL=OFF")
        print("M39500_ACTIVATION_REAL=OFF")
    return result


if __name__ == "__main__":
    raise SystemExit(main())
