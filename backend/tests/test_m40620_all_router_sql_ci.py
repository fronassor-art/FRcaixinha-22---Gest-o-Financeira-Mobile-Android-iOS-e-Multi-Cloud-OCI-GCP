"""M40620: all FastAPI routers SQL call boundary remains source-only."""
import ast
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from backend.scripts.frfinance_m40620_all_router_static_sql_guard import (
    ROUTERS, EXPECTED_HELPER_CALLS, MIN_ROUTER_FILES, audit_router,
    scan_paths, literal_sql,
)


def test_router_inventory_cannot_silently_shrink():
    paths = sorted(ROUTERS.glob("*.py"))
    assert len(paths) >= MIN_ROUTER_FILES
    sql, helper, findings = scan_paths(paths)
    assert sql > 0
    assert helper == EXPECTED_HELPER_CALLS
    assert not findings, findings


@pytest.mark.parametrize("unsafe", (
    "sql", "f'SELECT {actor}'", "'SELECT ' + actor",
    "'SELECT {}'.format(actor)", "'SELECT %s' % actor",
    "make_query(actor)",
))
def test_sql_text_from_untrusted_expression_rejected(unsafe):
    assert not literal_sql(ast.parse(unsafe, mode="eval").body)


def test_literal_string_concat_is_safe_for_python_sql_text():
    assert literal_sql(ast.parse("'SELECT ' + '1'", mode="eval").body)


def test_dynamic_direct_sql_rejected_even_if_connection_variable_renamed(tmp_path):
    p = tmp_path / "different_router.py"
    p.write_text("async def route(db,unsafe):\n    return await db.fetch(unsafe)\n")
    count, _, findings = audit_router(p)
    assert count == 1 and any("DYNAMIC_SQL_ARGUMENT" in x for x in findings)


def test_dynamic_sql_through_helper_call_rejected(tmp_path):
    p = tmp_path / "member_lifecycle_sandbox.py"
    p.write_text(
        "async def _fetch_request_rows(conn,sql,*args):\n"
        "    return await conn.fetch(sql,*args)\n"
        "async def endpoint(conn,sql):\n"
        "    return await _fetch_request_rows(conn,sql)\n"
        "async def endpoint2(conn):\n"
        "    return await _fetch_request_rows(conn,'SELECT 1')\n"
    )
    _, _, findings = audit_router(p)
    assert any("NONLITERAL_HELPER_QUERY" in x for x in findings)


def test_indirect_helper_import_from_other_router_rejected(tmp_path):
    p = tmp_path / "sample_router.py"
    p.write_text("async def endpoint(conn):\n    return await _fetch_request_rows(conn,'SELECT 1')\n")
    _, _, findings = audit_router(p)
    assert any("HELPER_USED_IN_UNREVIEWED_MODULE" in x for x in findings)


def test_extra_helper_call_requires_manual_review(tmp_path):
    p = tmp_path / "member_lifecycle_sandbox.py"
    p.write_text(
        "async def _fetch_request_rows(conn,sql,*args):\n"
        "    return await conn.fetch(sql,*args)\n"
        "async def endpoint(conn):\n"
        "    return await _fetch_request_rows(conn,'SELECT 1')\n"
    )
    _, _, findings = audit_router(p)
    assert "UNEXPECTED_HELPER_CALL_COUNT" in findings


def test_public_runtime_files_and_m40610_source_are_not_changed():
    code = (ROOT / "backend/app/database.py").read_text()
    assert "require_verified_rls_session(session)" in code
    assert code.index("require_verified_rls_session(session)") < code.index("pool = await get_db_pool()")
    helper = (ROOT / "backend/app/routers/member_lifecycle_sandbox.py").read_text()
    assert helper.count("_fetch_request_rows(conn,") == 3


def test_cli_fails_closed_and_reports_no_go():
    runner = ROOT / "backend/scripts/frfinance_m40620_all_router_static_sql_guard.py"
    r = subprocess.run([sys.executable, "-B", str(runner)],
                       capture_output=True, text=True, timeout=15, check=False)
    assert r.returncode == 0, r.stdout + r.stderr
    for marker in (
        "M40620_STATUS=PASS_ROUTER_LITERAL_SQL_WITH_REVIEWED_HELPER",
        "M40620_GUC_SPOOF_EXPOSURE=NOT_REMEDIATED",
        "M40620_ORIGINAL_DB=NOT_ACCESSED",
        "M40620_DB_WRITES=NONE",
        "M40620_MIGRATIONS=NONE",
        "M40620_SERVICE_RESTARTS=NONE",
        "M40620_PRODUCTION=BLOCKED",
    ):
        assert marker in r.stdout
