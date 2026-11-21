#!/usr/bin/env python3
"""M40620 — fail-closed source scan of every FastAPI router's direct SQL calls.

The sole known indirect SQL forwarding helper is audited explicitly.
No imports of backend runtime; no network, DB, test fixture or service effects.
"""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ROUTERS = ROOT / "backend/app/routers"
METHODS = frozenset(("fetch", "fetchval", "fetchrow", "execute", "executemany"))
HELPER_MODULE = "member_lifecycle_sandbox.py"
HELPER_NAME = "_fetch_request_rows"
EXPECTED_HELPER_CALLS = 2
MIN_ROUTER_FILES = 25


def literal_sql(node: ast.AST) -> bool:
    if isinstance(node, ast.Constant):
        return isinstance(node.value, str)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return literal_sql(node.left) and literal_sql(node.right)
    return False


def _enclosing_function(tree: ast.Module, target: ast.Call) -> str:
    """Identify a direct call's parent function, including nested functions."""
    for node in ast.walk(tree):
        if not isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)):
            continue
        if any(child is target for child in ast.walk(node)):
            return node.name
    return ""


def audit_router(path: Path) -> tuple[int, int, list[str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    sql_calls = 0
    helper_calls = 0
    problems: list[str] = []
    helper_defs = [
        node for node in tree.body
        if isinstance(node, ast.AsyncFunctionDef) and node.name == HELPER_NAME
    ]
    if path.name == HELPER_MODULE and len(helper_defs) != 1:
        problems.append("HELPER_DEFINITION_MISSING_OR_DUPLICATED")
    if path.name != HELPER_MODULE and any(
        isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef))
        and node.name == HELPER_NAME for node in tree.body
    ):
        problems.append("DUPLICATE_HELPER_OUTSIDE_EXPECTED_MODULE")

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name) and node.func.id == HELPER_NAME:
            if path.name != HELPER_MODULE:
                problems.append(f"LINE_{node.lineno}_HELPER_USED_IN_UNREVIEWED_MODULE")
                continue
            helper_calls += 1
            if (len(node.args) < 2 or node.keywords
                    or not literal_sql(node.args[1])
                    or not isinstance(node.args[0], ast.Name)
                    or node.args[0].id != "conn"):
                problems.append(f"LINE_{node.lineno}_NONLITERAL_HELPER_QUERY")
            continue
        if not isinstance(node.func, ast.Attribute) or node.func.attr not in METHODS:
            continue
        sql_calls += 1
        if node.args and literal_sql(node.args[0]):
            continue
        # Explicitly scoped exception: an internal function that forwards only
        # two source-level literal queries, through the exact conn.fetch(sql,*args).
        if (path.name == HELPER_MODULE
                and node.func.attr == "fetch"
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "conn"
                and len(node.args) == 2
                and isinstance(node.args[0], ast.Name)
                and node.args[0].id == "sql"
                and isinstance(node.args[1], ast.Starred)
                and isinstance(node.args[1].value, ast.Name)
                and node.args[1].value.id == "args"
                and _enclosing_function(tree, node) == HELPER_NAME):
            continue
        problems.append(f"LINE_{node.lineno}_DYNAMIC_SQL_ARGUMENT")

    if path.name == HELPER_MODULE:
        if helper_calls != EXPECTED_HELPER_CALLS:
            problems.append("UNEXPECTED_HELPER_CALL_COUNT")
        if len(helper_defs) == 1:
            forwards = [
                node for node in ast.walk(helper_defs[0])
                if isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in METHODS
            ]
            if len(forwards) != 1:
                problems.append("UNEXPECTED_HELPER_SQL_FORWARDERS")
    return sql_calls, helper_calls, problems


def scan_paths(paths: list[Path]) -> tuple[int, int, list[str]]:
    total_sql = 0
    total_helper = 0
    findings: list[str] = []
    for path in paths:
        count, helper, problems = audit_router(path)
        total_sql += count
        total_helper += helper
        findings.extend(f"{path.name}:{problem}" for problem in problems)
    return total_sql, total_helper, findings


def main() -> int:
    print("=== FR FINANCE M40620 — ALL ROUTER STATIC SQL BOUNDARY ===")
    paths = sorted(ROUTERS.glob("*.py"))
    count, helpers, problems = scan_paths(paths)
    if len(paths) < MIN_ROUTER_FILES:
        problems.append("ROUTER_COVERAGE_BELOW_BASELINE")
    if helpers != EXPECTED_HELPER_CALLS:
        problems.append("HELPER_CALLS_MISSING_OR_NEW")
    print("M40620_ROUTER_FILES=" + str(len(paths)))
    print("M40620_DIRECT_SQL_CALLS=" + str(count))
    print("M40620_AUDITED_LITERAL_HELPER_CALLS=" + str(helpers))
    for problem in problems:
        print("M40620_BLOCKED=" + problem)
    print("M40620_STATUS=" + (
        "PASS_ROUTER_LITERAL_SQL_WITH_REVIEWED_HELPER"
        if count > 0 and not problems else "BLOCKED_DYNAMIC_OR_UNREVIEWED_SQL"))
    print("M40620_GUC_SPOOF_EXPOSURE=NOT_REMEDIATED")
    print("M40620_ORIGINAL_DB=NOT_ACCESSED")
    print("M40620_DB_WRITES=NONE")
    print("M40620_MIGRATIONS=NONE")
    print("M40620_SERVICE_RESTARTS=NONE")
    print("M40620_PIX_REAL=OFF")
    print("M40620_PAGAMENTOS_REAIS=OFF")
    print("M40620_ATIVACAO_REAL=OFF")
    print("M40620_PRODUCTION=BLOCKED")
    return 0 if count > 0 and not problems else 2


if __name__ == "__main__":
    raise SystemExit(main())
