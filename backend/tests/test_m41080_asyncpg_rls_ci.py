"""M41080 offline guards for asyncpg transaction capability and RLS proof."""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "backend" / "tests" / "m41050_sql_sealed_context_pg18_disposable.py"
M41050_WORKFLOW = ROOT / ".github" / "workflows" / "frfinance-m41050-signed-session-context-pg18-ci.yml"
M41060_WORKFLOW = ROOT / ".github" / "workflows" / "frfinance-m41060-write-rls-pg18-ci.yml"
DOC = ROOT / "docs" / "FR_FINANCE_M41080_ASYNCPG_RLS_INTEGRATION_NO_GO.md"
SOURCE = RUNNER.read_text(encoding="utf-8")


def test_asyncpg_driver_is_lazy_and_runner_preflights_before_execution():
    tree = ast.parse(SOURCE)
    assert not any(
        isinstance(node, ast.Import) and any(alias.name == "asyncpg" for alias in node.names)
        or isinstance(node, ast.ImportFrom) and node.module == "asyncpg"
        for node in tree.body
    )
    assert "import asyncpg" in SOURCE.split("async def _m41080_asyncpg_connect", 1)[1].split(
        "\nasync def ", 1
    )[0]
    main = SOURCE.split("def main()", 1)[1]
    assert main.index("require_disposable()") < main.index("run(dsn)")


def test_real_asyncpg_capability_calls_are_bound_inside_transactions():
    for marker in (
        "async def _m41080_asyncpg_visible_entries",
        "async def _m41080_asyncpg_insert_entry",
        "async with connection.transaction():",
        "await install_session_capability(connection, capability)",
        "SET LOCAL ROLE m40650_app",
        "pg_catalog.set_config($1, $2, true)",
        "CI_M41080_DISPOSABLE",
        "CI_M41080_DATABASE_URL",
        "M41080_ASYNCPG_MEMBER_RLS_FORGED_CONTEXT=PASS",
        "M41080_ASYNCPG_READ_SCOPE_CANNOT_WRITE=DENIED",
        "M41080_ASYNCPG_WRITE_SCOPE_CANNOT_READ=DENIED",
        "M41080_ASYNCPG_ADMIN_INSERT=PASS",
        "M41080_ASYNCPG_CROSS_TENANT_INSERT=DENIED",
        "M41080_ASYNCPG_IDEMPOTENCY_SINGLE_ROW=PASS",
        "M41080_ASYNCPG_CONCURRENT_IDEMPOTENCY_SINGLE_ROW=PASS",
    ):
        assert marker in SOURCE


def test_both_existing_disposable_workflows_include_m41080_without_real_flags():
    for workflow_path in (M41050_WORKFLOW, M41060_WORKFLOW):
        workflow = workflow_path.read_text(encoding="utf-8")
        for marker in (
            "postgres:18",
            "55439:5432",
            "CI_M41080_DISPOSABLE: '1'",
            "CI_M41080_DATABASE_URL: postgresql://postgres:only_m41050_disposable_ci@127.0.0.1:55439/fr_m40700_disposable_ci",
            "asyncpg==0.30.0",
            "backend/tests/test_m41080_asyncpg_rls_ci.py",
            "docs/FR_FINANCE_M41080_ASYNCPG_RLS_INTEGRATION_NO_GO.md",
            "PIX_REAL: 'OFF'",
            "PAGAMENTOS_REAIS: 'OFF'",
            "ATIVACAO_REAL: 'OFF'",
            "contents: read",
        ):
            assert marker in workflow
        for forbidden in (
            "127.0.0.1:5433",
            "backend/migrations/",
            "pg_ctl",
            "PIX_REAL: 'ON'",
            "PAGAMENTOS_REAIS: 'ON'",
            "ATIVACAO_REAL: 'ON'",
        ):
            assert forbidden not in workflow


def test_document_preserves_traceability_and_no_go_limits():
    doc = DOC.read_text(encoding="utf-8")
    for marker in (
        "CP26-0061", "CP26-0062", "CTM-07", "CTM-08", "330", "2,310",
        "M41070_ROUTE_INTEGRATION=NONE", "M41080_ROUTE_INTEGRATION=NONE",
        "M40570", "M40710", "M40730", "M40928", "M40929",
        "M40840", "M40930", "Issue #5", "MIGRATIONS=NONE",
        "ORIGINAL_DATABASE=NOT_ACCESSED", "PIX_REAL=OFF",
        "PAGAMENTOS_REAIS=OFF", "ATIVACAO_REAL=OFF",
        "PRODUCTION=BLOCKED", "PENDING_INDEPENDENT_EVIDENCE",
    ):
        assert marker in doc
    assert "production_verified=true" not in doc
    assert "PRODUCTION=GO" not in doc
