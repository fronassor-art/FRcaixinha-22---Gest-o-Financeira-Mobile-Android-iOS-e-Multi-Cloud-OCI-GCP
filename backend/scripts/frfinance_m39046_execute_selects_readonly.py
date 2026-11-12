#!/usr/bin/env python3
"""FR Finance M39046: executar SELECTs do Crédito Especial em READ ONLY no PG18 ORIGINAL.

Apenas ~/fr-finance Termux nativo. Usa papel frc_ai_app, tenant e usuário
fictícios confirmados ausentes. NUNCA executa SELECT ... FOR SHARE/UPDATE,
pois esses comandos exigem bloqueio de linhas incompatível com READ ONLY.
Esses SELECTs foram verificados por EXPLAIN sem ANALYZE em M39045.
NÃO cria, modifica ou apaga registros. NUNCA ativa Pix ou campanhas.
"""
from __future__ import annotations

import getpass
import os
from pathlib import Path
import re
import sys

from backend.scripts.frfinance_m39026_credit_only_preflight import (
    DATA_DIRECTORY, DB, OWNER, SPECIAL, verify_repo,
)
from backend.scripts.frfinance_m39045_query_plans_readonly import (
    CANONICAL, FAKE_USER, FAKE_UUID, ROUTER, explain_query, read_queries,
)

# Baseline congelada: qualquer nova consulta do roteador exige nova auditoria.
EXPECTED_QUERIES = 17
EXPECTED_LOCKING = 2
LOCKING = re.compile(r"\bFOR\s+(?:NO\s+KEY\s+)?UPDATE\b|\bFOR\s+(?:KEY\s+)?SHARE\b",
                     flags=re.IGNORECASE)


def is_locking(sql: str) -> bool:
    return bool(LOCKING.search(sql))


def executable_sql(sql: str) -> str:
    """Converte apenas SELECT previamente validado, sem placeholders reais."""
    if is_locking(sql):
        raise RuntimeError("LOCKING_SELECT_REQUIRES_WRITE_TXN")
    plan = explain_query(sql)  # garante SELECT único e só parâmetros UUID sintéticos
    prefix = "EXPLAIN (COSTS OFF) "
    if not plan.startswith(prefix + "SELECT "):
        raise RuntimeError("EXPLAIN_CONTRACT_INVALID")
    return plan.removeprefix(prefix)


def _scalar_zero(sql: str) -> bool:
    return bool(re.match(r"^\s*SELECT\s+(?:COUNT\s*\(|EXISTS\s*\()", sql,
                         re.IGNORECASE))


def audit_actual_selects(conn, queries: list[tuple[int, str, str]]) -> None:
    if len(queries) != EXPECTED_QUERIES:
        raise RuntimeError("READ_QUERY_COVERAGE_DRIFT")
    locks = [(line, operation, sql) for line, operation, sql in queries if is_locking(sql)]
    if len(locks) != EXPECTED_LOCKING:
        raise RuntimeError("LOCKING_QUERY_COVERAGE_DRIFT")

    # Garante que todas as consultas sejam aprovadas ANTES de abrir a transação.
    approved = [(line, method, sql, executable_sql(sql))
                for line, method, sql in queries if not is_locking(sql)]
    with conn.transaction():
        conn.execute("SET TRANSACTION READ ONLY")
        identity = conn.execute(
            "SELECT current_database(),session_user,host(inet_server_addr()),"
            "inet_server_port(),current_setting('data_directory'),"
            "current_setting('server_version_num')::integer,"
            "current_setting('transaction_read_only')"
        ).fetchone()
        if (identity[0] != DB or identity[1] != OWNER or
                identity[2] != "127.0.0.1" or identity[3] != 5433 or
                identity[4] != DATA_DIRECTORY or
                not 180000 <= identity[5] < 190000 or identity[6] != "on"):
            raise RuntimeError("ORIGINAL_PG18_IDENTITY_OR_READONLY_INVALID")
        # Sentinelas inexistentes: apenas booleanos, nunca registros identificáveis.
        present = conn.execute(
            "SELECT EXISTS(SELECT 1 FROM public.tenants WHERE id=%s::uuid),"
            "EXISTS(SELECT 1 FROM public.users WHERE id=%s::uuid)",
            (FAKE_UUID, FAKE_USER),
        ).fetchone()
        if present != (False, False):
            raise RuntimeError("SYNTHETIC_IDENTIFIERS_ALREADY_PRESENT")

        conn.execute("SET LOCAL ROLE frc_ai_app")
        if conn.execute("SELECT current_user,session_user").fetchone() != ("frc_ai_app", OWNER):
            raise RuntimeError("APPLICATION_ROLE_INCORRECT")
        if conn.execute("SELECT current_setting('transaction_read_only')").fetchone() != ("on",):
            raise RuntimeError("TRANSACTION_NOT_READ_ONLY")
        for table in SPECIAL:
            if conn.execute(
                "SELECT row_security_active(%s::regclass)", ("public." + table,)
            ).fetchone() != (True,):
                raise RuntimeError("RLS_DISABLED_" + table)

        executed = 0
        for role in ("TENANT_ADMIN", "TENANT_MEMBER"):
            for name, value in (
                ("app.current_tenant_id", FAKE_UUID),
                ("app.current_user_id", FAKE_USER),
                ("app.current_role", role),
            ):
                conn.execute("SELECT set_config(%s,%s,true)", (name, value))
            for line, method, original, sql in approved:
                try:
                    rows = conn.execute(sql).fetchall()
                    if _scalar_zero(original):
                        if len(rows) != 1 or rows[0][0] not in (0, False):
                            raise RuntimeError("SYNTHETIC_AGGREGATE_NOT_ZERO")
                    elif rows:
                        raise RuntimeError("SYNTHETIC_QUERY_RETURNED_ROWS")
                except Exception as exc:
                    # Não incluir SQL, ID de membro, conteúdo de mensagem ou traceback.
                    code = getattr(exc, "sqlstate", "CHECK_FAILED")
                    raise RuntimeError(
                        f"M39046_QUERY_FAILED_ROLE_{role}_LINE_{line}_{method}_STATE_{code}"
                    ) from None
                executed += 1

    print("M39046_PG18_ORIGINAL=PASS")
    print("M39046_ROLE=frc_ai_app")
    print("M39046_RLS_ACTIVE=6_OF_6")
    print("M39046_FAKE_IDS_VERIFIED_ABSENT=PASS")
    print("M39046_SELECTS_EXECUTED=" + str(executed))
    print("M39046_LOCKING_SELECTS_SKIPPED=" + str(len(locks)))
    print("M39046_LOCKING_SELECTS_APPROVED_BY_PREVIOUS_M39045=TRUE")
    print("M39046_REAL_CUSTOMER_ROWS_RETURNED=NONE")
    print("M39046_TRANSACTIONS=READ_ONLY")
    print("M39046_DATABASE_WRITES=NONE")


def main() -> int:
    print("=== FR FINANCE M39046 — SELECTS COM RLS ORIGINAL READ ONLY ===")
    try:
        if (os.environ.get("HOME") != "/data/data/com.termux/files/home"
                or Path.cwd().resolve() != CANONICAL
                or not (CANONICAL / ".git").is_dir()):
            raise RuntimeError("ONLY_ORIGINAL_TERMUX_DIRECTORY")
        verify_repo()
        queries = read_queries(ROUTER.read_text(encoding="utf-8"))
        if len(queries) != EXPECTED_QUERIES or sum(is_locking(q) for _, _, q in queries) != EXPECTED_LOCKING:
            raise RuntimeError("ROUTER_QUERY_COUNT_OR_LOCK_PROFILE_DRIFT")
        for _, _, sql in queries:
            if not is_locking(sql):
                executable_sql(sql)
            else:
                explain_query(sql)  # Plano somente, não execução de bloqueio
    except Exception as exc:
        print("M39046_PREFLIGHT=BLOCKED")
        print("M39046_REASON=" + (str(exc) if isinstance(exc, RuntimeError) else type(exc).__name__))
        return 2
    try:
        import psycopg
    except ImportError:
        print("M39046_STATUS=BLOCKED_PSYCOPG_MISSING")
        return 2
    password = getpass.getpass("Senha PostgreSQL frc_ai_owner (oculta): ")
    if not password:
        print("M39046_STATUS=BLOCKED_EMPTY_PASSWORD")
        return 2
    try:
        with psycopg.connect(
            host="127.0.0.1", port=5433, dbname=DB, user=OWNER,
            password=password, connect_timeout=5,
            options="-c default_transaction_read_only=on "
                    "-c statement_timeout=8000 -c lock_timeout=1500",
        ) as conn:
            password = ""
            audit_actual_selects(conn, queries)
    except RuntimeError as exc:
        print("M39046_STATUS=BLOCKED")
        print("M39046_REASON=" + str(exc))
        print("M39046_DATABASE_WRITES=NONE")
        return 2
    except Exception as exc:
        print("M39046_STATUS=BLOCKED_RUNTIME_OR_DATABASE")
        print("M39046_ERROR_TYPE=" + type(exc).__name__)
        print("M39046_DATABASE_WRITES=NONE")
        return 2
    print("M39046_SQL110_111=ALREADY_APPLIED_NO_REPEAT")
    print("M39046_EXTERNAL_MESSAGES=OFF")
    print("M39046_PIX_REAL=OFF")
    print("M39046_STATUS=PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
