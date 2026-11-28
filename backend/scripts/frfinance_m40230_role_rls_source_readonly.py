#!/usr/bin/env python3
"""M40230 — FR Finance role/tenant/RLS source boundary preflight.

Static-only checkpoint. Checks source invariants but never imports the app,
connects to any PostgreSQL, creates a user/session, touches protected HTTP
routes or starts/stops a service. PASS is NOT runtime PostgreSQL RLS proof.
"""
from __future__ import annotations

import argparse
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

FILES = {
    "dependencies": ROOT / "backend/app/dependencies.py",
    "database": ROOT / "backend/app/database.py",
    "credit": ROOT / "backend/app/routers/special_credit.py",
    "review": ROOT / "backend/app/routers/exclusive_cashbox_review_gaps.py",
}

NEEDED = {
    ("dependencies", "get_current_session"): (
        "raw_token = bearer_token(request)",
        "await asyncpg.connect(auth_database_url(), timeout=5)",
        "auth_active_memberships(",
        "auth_refresh_session(",
        "POSTGRES_TOKEN_HASH_REFRESH",
    ),
    ("dependencies", "require_master"): (
        'session.role != "MASTER"',
        "not session.is_master",
        "session.tenant_id is not None",
        "status.HTTP_403_FORBIDDEN",
    ),
    ("dependencies", "require_tenant_access"): (
        'session.role == "MASTER"',
        'session.role == "TENANT_ADMIN"',
        'session.role == "TENANT_MEMBER"',
        "session.tenant_id != target_tenant_id",
        "status.HTTP_403_FORBIDDEN",
    ),
    ("database", "get_rls_db_connection"): (
        "Depends(get_current_session)",
        "await tx.start()",
        "set_config('app.current_user_id', $1, true)",
        "set_config('app.current_role', $1, true)",
        "set_config('app.current_tenant_id', $1, true)",
        "yield conn",
        "await tx.commit()",
        "await tx.rollback()",
        "RESET ALL; DISCARD TEMP;",
    ),
    ("credit", "_authorize"): (
        "require_tenant_access(str(tenant_id), session)",
        "session.role not in allowed_roles",
        "raise HTTPException(403",
        "if not _enabled()",
    ),
    ("review", "tenant_admin_review_policy_gaps"): (
        "Depends(get_current_session)",
        "Depends(get_rls_db_connection)",
        "verify_review_readiness(",
        "SELECT admin_user_id FROM public.tenants ",
        "owner != actor_id",
    ),
    ("review", "master_review_policy_gaps"): (
        "Depends(require_master)",
        "verify_review_readiness(",
    ),
}


def named_source(path: Path, name: str) -> str:
    if path.is_symlink() or not path.is_file():
        raise ValueError("SOURCE_FILE_UNAVAILABLE")
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in tree.body:
        if (isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name == name):
            return ast.get_source_segment(source, node) or ""
    raise ValueError("EXPECTED_FUNCTION_ABSENT")


def evaluate(paths=None):
    paths = paths or FILES
    for (group, name), snippets in NEEDED.items():
        try:
            body = named_source(paths[group], name)
        except (KeyError, OSError, ValueError, SyntaxError, UnicodeError):
            return "BLOCKED_" + group.upper() + "_" + name.upper() + "_SOURCE"
        if not all(s in body for s in snippets):
            return "BLOCKED_" + group.upper() + "_" + name.upper() + "_GUARD"
    return "PASS_SOURCE_BOUNDARIES_ONLY_NOT_RUNTIME_RLS"


def main(argv=None):
    parser = argparse.ArgumentParser(description="M40230 static role/RLS source gate")
    parser.add_argument("--source-only", action="store_true")
    parser.parse_args(argv)
    print("=== FR FINANCE M40230 — ROLE AND RLS SOURCE ONLY ===")
    outcome = evaluate()
    print("M40230_SOURCE_BOUNDARIES=" + outcome)
    print("M40230_ACTUAL_AUTHENTICATED_RLS=NOT_TESTED")
    print("M40230_CI_SYNTHETIC_ROLE_MATRIX=NOT_ATTESTED_BY_TERMUX")
    print("M40230_LIVE_POSTGRESQL=NOT_QUERIED")
    print("M40230_HTTP_REQUESTS=NONE")
    print("M40230_AUTH_SESSIONS_CREATED=NONE")
    print("M40230_DATABASE_WRITES=NONE")
    print("M40230_MIGRATIONS=NONE")
    print("M40230_FASTAPI_START_STOP=NONE")
    print("M40230_POSTGRESQL_START_STOP=NONE")
    print("M40230_FR_CAIXINHA_2_2=NOT_ACCESSED")
    print("M40230_PIX_REAL=OFF")
    print("M40230_PAGAMENTOS_REAIS=OFF")
    print("M40230_ATIVACAO_REAL=OFF")
    print("M40230_PRODUCTION=BLOCKED")
    return 0 if outcome.startswith("PASS_") else 2


if __name__ == "__main__":
    raise SystemExit(main())
