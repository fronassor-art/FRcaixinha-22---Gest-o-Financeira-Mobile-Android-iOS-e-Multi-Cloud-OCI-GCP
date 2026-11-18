"""FR Finance M40580: fail-closed static SQL boundary scanner.

Works on AST only. No imports of application code, no DB, no SQL execution.
"""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SENSITIVE_PATHS = (
    "backend/app/database.py",
    "backend/app/dependencies.py",
    "backend/app/routers/saas_promotions.py",
)
SQL_METHODS = frozenset(("execute", "fetch", "fetchrow", "fetchval", "executemany"))


def is_literal_sql(node: ast.AST) -> bool:
    """Accept only string literals and concatenations of string literals.

    AST joins adjacent quoted lines into one Constant. No name, f-string,
    formatting, template call, or variable concatenation is allowed.
    """
    if isinstance(node, ast.Constant):
        return isinstance(node.value, str)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return is_literal_sql(node.left) and is_literal_sql(node.right)
    return False


def audit_source(path: Path) -> tuple[int, list[str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    checked = 0
    problems = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr not in SQL_METHODS:
            continue
        if not isinstance(node.func.value, ast.Name) or node.func.value.id != "conn":
            # Explicitly covers the project's conn query surface. A rename
            # of the SQL connection variable requires revising this scope.
            continue
        checked += 1
        if not node.args or not is_literal_sql(node.args[0]):
            problems.append(f"{path.name}:{node.lineno}:DYNAMIC_SQL_ARGUMENT")
    return checked, problems


def source_report() -> dict[str, tuple[int, list[str]]]:
    return {path: audit_source(ROOT / path) for path in SENSITIVE_PATHS}


def main() -> int:
    r = source_report()
    for path, (count, issues) in r.items():
        print(f"M40580_{Path(path).stem.upper()}_SQL_CALLS={count}")
        if issues:
            for issue in issues:
                print("M40580_DYNAMIC_SQL_BLOCKED=" + issue)
    counts = [r[k][0] for k in SENSITIVE_PATHS]
    safe = all(count > 0 and not r[path][1] for path, count in zip(SENSITIVE_PATHS, counts))
    print("M40580_STATUS=" + ("PASS_STATIC_LITERAL_SQL_ONLY" if safe else "BLOCKED_DYNAMIC_SQL"))
    print("M40580_SCOPE=THREE_CRITICAL_FILES_NOT_WHOLE_REPOSITORY")
    print("M40580_SQL_EXECUTION=NONE")
    print("M40580_ORIGINAL_DB=NOT_ACCESSED")
    print("M40580_GUC_SPOOF_EXPOSURE=NOT_REMEDIATED")
    print("M40580_PRODUCTION=BLOCKED")
    return 0 if safe else 2


if __name__=="__main__":
    raise SystemExit(main())