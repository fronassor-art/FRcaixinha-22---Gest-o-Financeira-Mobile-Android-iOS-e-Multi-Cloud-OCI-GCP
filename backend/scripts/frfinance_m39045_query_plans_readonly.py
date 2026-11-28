#!/usr/bin/env python3
"""FR Finance M39045 — planos de consultas FastAPI no PostgreSQL ORIGINAL, READ ONLY.

Executar APENAS no Termux nativo, diretório ~/fr-finance, por python -B -m.
Verifica compilação dos SELECTs da rota Crédito Especial com o papel real
frc_ai_app e contexto sintético, em transação somente leitura.
EXPLAIN SEM ANALYZE: não executa a consulta, não retorna dados pessoais.
Sem migração, banco descartável, API externa, Pix ou alteração de dados.
"""
from __future__ import annotations

import ast
import getpass
import os
from pathlib import Path
import re
import sys

from backend.scripts.frfinance_m39026_credit_only_preflight import (
    verify_repo, DB, OWNER, DATA_DIRECTORY,
)

CANONICAL = Path("/data/data/com.termux/files/home/fr-finance")
ROUTER = CANONICAL / "backend/app/routers/special_credit.py"
FAKE_UUID = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"
FAKE_USER = "dddddddd-dddd-4ddd-8ddd-dddddddddddd"
ALLOWED = {"fetch", "fetchrow", "fetchval"}
SQL_PARAM = re.compile(r"\$(\d+)(::uuid\[\])?")


def read_queries(source: str) -> list[tuple[int, str, str]]:
    """Extrai SOMENTE SQL SELECTs literais executados via asyncpg.

    Não avalia Python dinâmico e falha se surgirem queries dinâmicas nos
    três métodos de leitura do roteador: queremos prova de cobertura real.
    """
    tree = ast.parse(source)
    results: list[tuple[int, str, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr not in ALLOWED or not node.args:
            continue
        target = node.func.value
        if not isinstance(target, ast.Name) or target.id != "conn":
            continue
        query_node = node.args[0]
        if not isinstance(query_node, ast.Constant) or not isinstance(query_node.value, str):
            raise RuntimeError("DYNAMIC_READ_SQL_NOT_APPROVED_LINE_" + str(node.lineno))
        query = query_node.value
        if query.lstrip().upper().startswith("SELECT "):
            results.append((node.lineno, node.func.attr, query))
        elif not query.lstrip().upper().startswith(("INSERT ", "UPDATE ", "DELETE ")):
            raise RuntimeError("UNEXPECTED_READ_METHOD_SQL_LINE_" + str(node.lineno))
    results.sort()
    if len(results) < 12:
        raise RuntimeError("READ_SQL_COVERAGE_BELOW_BASELINE")
    return results


def explain_query(sql: str) -> str:
    """Substitui SOMENTE placeholders UUID por literais sintéticos tipados."""
    if not sql.lstrip().upper().startswith("SELECT "):
        raise RuntimeError("NON_SELECT_EXPLAIN_FORBIDDEN")
    if ";" in sql or "--" in sql or "/*" in sql:
        raise RuntimeError("MULTI_STATEMENT_OR_COMMENT_FORBIDDEN")
    matches = SQL_PARAM.findall(sql)
    indexes = {int(n) for n, _ in matches}
    if indexes and indexes != set(range(1, max(indexes) + 1)):
        raise RuntimeError("NONCONTIGUOUS_SQL_PARAMETERS")
    replacement = SQL_PARAM.sub(
        lambda m: (
            "ARRAY['" + FAKE_UUID + "'::uuid]::uuid[]" if m.group(2)
            else "'" + FAKE_UUID + "'::uuid"
        ),
        sql,
    )
    if "$" in replacement:
        raise RuntimeError("SQL_PLACEHOLDER_NOT_COVERED")
    return "EXPLAIN (COSTS OFF) " + replacement


def run_audit(conn, queries: list[tuple[int, str, str]]) -> None:
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
            raise RuntimeError("ORIGINAL_PG18_IDENTITY_OR_READONLY_MISMATCH")

        conn.execute("SET LOCAL ROLE frc_ai_app")
        if conn.execute("SELECT current_user,session_user").fetchone() != ("frc_ai_app", OWNER):
            raise RuntimeError("APPLICATION_ROLE_NOT_ACTIVE")

        # Contexto de usuário inexistente. Não busca qualquer registro real.
        completed = 0
        for role in ("TENANT_ADMIN", "TENANT_MEMBER"):
            for key, value in (
                ("app.current_tenant_id", FAKE_UUID),
                ("app.current_user_id", FAKE_USER),
                ("app.current_role", role),
            ):
                conn.execute("SELECT set_config(%s,%s,true)", (key, value))

            for line, operation, sql in queries:
                try:
                    # EXPLAIN sem ANALYZE: somente plano, sem ler linhas do usuário.
                    conn.execute(explain_query(sql)).fetchall()
                except Exception as exc:
                    # A exceção nunca inclui dados ou SQL; o diagnóstico usa só
                    # a posição do arquivo e o SQLSTATE para triagem.
                    state = getattr(exc, "sqlstate", "UNKNOWN")
                    raise RuntimeError(
                        f"READ_QUERY_PLAN_FAILED_{role}_LINE_{line}_{operation}_SQLSTATE_{state}"
                    ) from None
                completed += 1

    print("M39045_PG18_ORIGINAL=PASS")
    print("M39045_ROLE=frc_ai_app")
    print("M39045_EXECUTION=EXPLAIN_WITHOUT_ANALYZE")
    print("M39045_CONTEXT=SYNTHETIC_ONLY")
    print("M39045_QUERIES=" + str(len(queries)))
    print("M39045_PLANS=" + str(completed))
    print("M39045_REAL_CUSTOMER_ROWS_READ=NONE")
    print("M39045_DATABASE_WRITES=NONE")


def main() -> int:
    print("=== FR FINANCE M39045 — PLANEJAMENTO SQL READ ONLY ===")
    try:
        if (os.environ.get("HOME") != "/data/data/com.termux/files/home"
                or Path.cwd().resolve() != CANONICAL
                or not (CANONICAL / ".git").is_dir()):
            raise RuntimeError("ONLY_CANONICAL_TERMUX_REPOSITORY")
        verify_repo()
        queries = read_queries(ROUTER.read_text(encoding="utf-8"))
        for _, _, sql in queries:
            explain_query(sql)
    except Exception as exc:
        print("M39045_PREFLIGHT=BLOCKED")
        print("M39045_REASON=" + (str(exc) if isinstance(exc, RuntimeError) else type(exc).__name__))
        return 2
    try:
        import psycopg
    except ImportError:
        print("M39045_STATUS=BLOCKED_PSYCOPG_UNAVAILABLE")
        return 2
    password = getpass.getpass("Senha PostgreSQL frc_ai_owner (oculta): ")
    if not password:
        print("M39045_STATUS=BLOCKED_EMPTY_PASSWORD")
        return 2
    try:
        with psycopg.connect(
            host="127.0.0.1", port=5433, dbname=DB, user=OWNER,
            password=password, connect_timeout=5,
            options="-c default_transaction_read_only=on "
                    "-c statement_timeout=12000 -c lock_timeout=2000",
        ) as conn:
            password = ""
            run_audit(conn, queries)
    except RuntimeError as exc:
        print("M39045_STATUS=BLOCKED")
        print("M39045_REASON=" + str(exc))
        print("M39045_DATABASE_WRITES=NONE")
        return 2
    except Exception as exc:
        print("M39045_STATUS=BLOCKED_RUNTIME_OR_DATABASE")
        print("M39045_ERROR_TYPE=" + type(exc).__name__)
        print("M39045_DATABASE_WRITES=NONE")
        return 2
    print("M39045_SQL110_111=ALREADY_APPLIED_NO_REPEAT")
    print("M39045_NOTIFICATIONS_EXTERNAL=OFF")
    print("M39045_PIX_REAL=OFF")
    print("M39045_STATUS=PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
