#!/usr/bin/env python3
"""M39068 — diagnóstico pós-COMMIT read-only das SQL112/113 originais.

A falha BLOCKED_SQL113_RLS_PRIVILEGES_TRIGGER_OR_FUNCTION_UNSAFE veio
de inspeção depois de COMMIT; este programa nunca aplica/repete migrações.
Verifica 5433, PG18, PGDATA, papeis e catálogo Git; imprime somente
bool/status do schema. Nunca exibe senha, DSN, dados de usuário ou tokens.
"""
from __future__ import annotations

import getpass
import sys

from backend.scripts.frfinance_m39066_master_prices_sql112_termux import (
    DB, OWNER, Blocked, database_identity, validate_context
)
from backend.scripts.frfinance_m39067_apply_saas_prices_promotions_pg18 import (
    validate_sql113_hash,
)


def search_path_is_restricted(proconfig) -> bool:
    """O PostgreSQL pode inserir espaço após vírgula ao armazenar proconfig."""
    if not isinstance(proconfig, (list, tuple)):
        return False
    matches = [
        part.split("=", 1)[1]
        for part in proconfig
        if isinstance(part, str) and part.startswith("search_path=")
    ]
    return len(matches) == 1 and [
        p.strip().lower() for p in matches[0].split(",")
    ] == ["pg_catalog", "pg_temp"]


def inspect_schema(conn) -> dict[str, bool | str]:
    with conn.transaction():
        conn.execute("SET TRANSACTION READ ONLY")
        identity = conn.execute(
            "SELECT current_database(),session_user,current_user,"
            "host(inet_server_addr()),inet_server_port(),"
            "current_setting('data_directory'),"
            "current_setting('server_version_num')::integer"
        ).fetchone()
        if not database_identity(identity):
            raise Blocked("WRONG_DATABASE_PORT_ROLE_OR_PGDATA")
        annual = conn.execute(
            "SELECT attgenerated,attnotnull "
            "FROM pg_catalog.pg_attribute "
            "WHERE attrelid=to_regclass("
            "'public.platform_license_price_versions') "
            "AND attname='annual_price' AND NOT attisdropped"
        ).fetchone()
        table, function = conn.execute(
            "SELECT "
            "to_regclass('public.platform_saas_promotion_revisions') IS NOT NULL,"
            "to_regprocedure("
            "'public.frfinance_saas_new_admin_published_promotions()') IS NOT NULL"
        ).fetchone()
        result = {
            "SQL112_ANNUAL_INDEPENDENT": annual == ("", True),
            "SQL113_TABLE_EXISTS": table is True,
            "SQL113_READER_EXISTS": function is True,
        }
        if not table or not function:
            return result
        table_flags = conn.execute(
            "SELECT relrowsecurity,relforcerowsecurity "
            "FROM pg_catalog.pg_class "
            "WHERE oid='public.platform_saas_promotion_revisions'::regclass"
        ).fetchone()
        privileges = conn.execute(
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
        trigger = conn.execute(
            "SELECT count(*) FROM pg_catalog.pg_trigger "
            "WHERE tgrelid='public.platform_saas_promotion_revisions'::regclass "
            "AND tgname='frfinance_guard_saas_promo_append' "
            "AND tgenabled='O' AND NOT tgisinternal"
        ).fetchone()[0]
        metadata = conn.execute(
            "SELECT prosecdef,proconfig FROM pg_catalog.pg_proc "
            "WHERE oid='public.frfinance_saas_new_admin_published_promotions()'::regprocedure"
        ).fetchone()
        cols = conn.execute(
            "SELECT has_column_privilege('frcaixinha_app_role',"
            "'public.platform_license_price_versions','annual_price','INSERT'),"
            "EXISTS(SELECT 1 FROM pg_catalog.pg_constraint "
            "WHERE conrelid='public.platform_license_price_versions'::regclass "
            "AND conname='platform_license_annual_price_positive')"
        ).fetchone()
        result.update({
            "SQL112_COLUMN_INSERT_AND_CONSTRAINT": cols == (True,True),
            "SQL113_RLS_ENABLED": table_flags[0] is True,
            "SQL113_RLS_FORCE": table_flags[1] is True,
            "SQL113_APP_SELECT_ALLOWED": privileges[0] is True,
            "SQL113_AUTH_SELECT_DENIED": privileges[1] is False,
            "SQL113_APP_UPDATE_DENIED": privileges[2] is False,
            "SQL113_APP_DELETE_DENIED": privileges[3] is False,
            "SQL113_APP_READER_ALLOWED": privileges[4] is True,
            "SQL113_AUTH_READER_DENIED": privileges[5] is False,
            "SQL113_TRIGGER_ACTIVE": trigger == 1,
            "SQL113_READER_SECURITY_DEFINER": metadata[0] is True,
            "SQL113_READER_PATH_RESTRICTED": search_path_is_restricted(metadata[1]),
            "M39067_POSTCHECK_EXACT_TEXT": (
                metadata[1] is not None
                and "search_path=pg_catalog,pg_temp" in ",".join(metadata[1])
            ),
        })
        return result


def main() -> int:
    print("=== FR FINANCE M39068 — AUDITORIA READ ONLY APOS COMMIT ===")
    try:
        validate_context()
        validate_sql113_hash()
        import psycopg
        password = getpass.getpass("Senha existente frc_ai_owner (oculta): ")
        if not password:
            raise Blocked("EMPTY_PASSWORD")
        with psycopg.connect(
            host="127.0.0.1",port=5433,dbname=DB,user=OWNER,
            password=password,connect_timeout=5,autocommit=True,
        ) as conn:
            flags = inspect_schema(conn)
        print("M39068_DATABASE_IDENTITY=FR_FINANCE_PG18_5433_PASS")
        for name, status in flags.items():
            print(f"M39068_{name}={'PASS' if status else 'FAIL'}")
        basic = all(
            value for name, value in flags.items()
            if name != "M39067_POSTCHECK_EXACT_TEXT"
        )
        if basic and not flags.get("M39067_POSTCHECK_EXACT_TEXT", False):
            print("M39068_DIAGNOSIS=LIKELY_POSTCOMMIT_SEARCH_PATH_TEXT_FORMAT_BUG")
        elif basic:
            print("M39068_DIAGNOSIS=SQL112_113_STRUCTURAL_GUARDS_PASS")
        else:
            print("M39068_DIAGNOSIS=TRUE_STRUCTURE_OR_ROLE_GRANTS_MISMATCH_REVIEW")
        print("M39068_STATUS=" + (
            "PASS_READ_ONLY_POSTCOMMIT_ATTESTATION"
            if basic else "BLOCKED_REVIEW_ONLY"
        ))
        return 0 if basic else 2
    except Blocked as e:
        print("M39068_STATUS=BLOCKED_" + str(e))
        return 2
    except Exception as e:
        print("M39068_STATUS=BLOCKED_RUNTIME_" + type(e).__name__)
        return 2
    finally:
        print("M39068_DATABASE_WRITES=NONE")
        print("M39068_MIGRATIONS=NONE")
        print("M39068_DB_5432_ACCESS=NONE")
        print("M39068_PASSWORD_RESET=NONE")
        print("M39068_FASTAPI_RESTART=NONE")
        print("M39068_APK_INSTALL=NONE")
        print("M39068_PIX_REAL=OFF")


if __name__ == "__main__":
    sys.exit(main())
