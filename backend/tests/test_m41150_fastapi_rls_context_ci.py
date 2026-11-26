"""M41150/M41160 offline contract checks for the FastAPI/SQL capability boundary."""
from __future__ import annotations

from pathlib import Path

import pytest

from backend.app.m41150_fastapi_rls_context import (
    InvalidSessionTicket,
    validate_signed_session_ticket,
)

ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "backend/app/m41150_fastapi_rls_context.py"
ROUTER = ROOT / "backend/app/routers/ledger.py"
RUNNER = ROOT / "backend/tests/m41150_fastapi_rls_context_pg18_disposable.py"
WORKFLOW = ROOT / ".github/workflows/frfinance-m41150-fastapi-rls-context-pg18.yml"
DOC = ROOT / "docs/FR_FINANCE_M41150_FASTAPI_SQL_CONTEXT_NO_GO.md"
DOC_M41160 = ROOT / "docs/FR_FINANCE_M41160_LEDGER_READ_CAPABILITY_NO_GO.md"


def test_ticket_is_opaque_fixed_length_and_never_echoed():
    assert validate_signed_session_ticket("a" * 64) == "a" * 64
    for value in (None, "", "A" * 64, "g" * 64, "a" * 63, "a" * 65, 123):
        with pytest.raises(InvalidSessionTicket):
            validate_signed_session_ticket(value)


def test_capability_route_uses_transaction_local_context_and_read_only_transaction():
    source = MODULE.read_text(encoding="utf-8")
    for marker in (
        "require_verified_rls_session(session)",
        "require_nonproduction_financial_sql(os.environ)",
        '"issue_ticket"',
        '"bind_ticket"',
        "async with connection.transaction(readonly=True)",
        "install_session_capability(connection, capability)",
        "RESET ALL; DISCARD TEMP;",
        "connection.terminate()",
        "PROVIDER_STATE_ATTRIBUTE",
        "READ_SCOPE = \"READ_ENTRIES\"",
    ):
        assert marker in source
    for forbidden in (
        "set_config('app.current_user_id'",
        "set_config('app.current_role'",
        "set_config('app.current_tenant_id'",
        "raw_token",
        "DATABASE_URL",
        "PIX_REAL = \"ON\"",
        "PAGAMENTOS_REAIS = \"ON\"",
        "ATIVACAO_REAL = \"ON\"",
    ):
        assert forbidden not in source


def test_all_read_only_ledger_routes_use_optional_capability_dependency():
    source = ROUTER.read_text(encoding="utf-8")
    assert (
        "from ..m41150_fastapi_rls_context import "
        "get_ledger_readonly_db_connection"
    ) in source
    for function_name in (
        "get_ledger_integrity_preview",
        "list_ledger_account_directory",
        "list_ledger_accounts",
        "list_ledger_transactions",
        "list_ledger_account_entries",
        "list_ledger_account_entries_keyset",
    ):
        start = source.index(f"async def {function_name}(")
        end = source.find("\n\n@", start)
        route = source[start:] if end < 0 else source[start:end]
        assert "Depends(get_ledger_readonly_db_connection)" in route
        assert "Depends(get_rls_db_connection)" not in route
    assert "Depends(get_rls_db_connection)" not in source


def test_m41160_document_preserves_independent_evidence_and_production_gates():
    doc = DOC_M41160.read_text(encoding="utf-8")
    for marker in (
        "CP26-0061", "CP26-0062", "CTM-07", "CTM-08",
        "330 IDs", "2.310 etapas", "M40570", "M40730", "M40840",
        "M40930", "M41160_AUTHENTICATION=OVERRIDDEN_SYNTHETIC",
        "M41160_PROVIDER=CUSTODY_NOT_CONFIGURED",
        "ORIGINAL_DATABASE=NOT_ACCESSED", "MIGRATIONS=NONE",
        "PIX_REAL=OFF", "PAGAMENTOS_REAIS=OFF", "ATIVACAO_REAL=OFF",
        "PRODUCTION=BLOCKED", "NO-GO",
    ):
        assert marker in doc
    assert "PRODUCTION=GO" not in doc


def test_runner_preflights_exact_disposable_postgres_before_driver_imports():
    source = RUNNER.read_text(encoding="utf-8")
    main = source.split("def main()", 1)[1]
    assert main.index("dsn = require_disposable()") < main.index("asyncio.run(exercise(dsn))")
    exercise = source.split("async def exercise", 1)[1].split("\ndef main()", 1)[0]
    assert "import asyncpg" in exercise and "import psycopg" in exercise
    assert 'SHOW server_version_num' in exercise
    for marker in (
        "fr_m40700_disposable_ci",
        "55439",
        "CI_M41150_DISPOSABLE",
        "CI_M41150_DATABASE_URL",
        "ORIGINAL_DATABASE=NOT_ACCESSED",
        "MIGRATIONS=NONE",
        "PIX_REAL=OFF",
        "PAGAMENTOS_REAIS=OFF",
        "ATIVACAO_REAL=OFF",
        "PRODUCTION=BLOCKED",
        "M41150_FASTAPI_LEDGER_DIRECTORY=PASS",
        "M41150_FORGED_LEGACY_GUC_DENIED=PASS",
        "M41160_FORGED_LEGACY_GUC_DENIED=PASS",
        "M41150_TICKET_REPLAY_DENIED=PASS",
        "M41150_REVOKED_CAPABILITY_DENIED=PASS",
        "M41160_FASTAPI_LEDGER_READ_ROUTES=6_OF_6_PASS",
        "M41160_TENANT_ROLE_NEGATIVE=PASS",
        "M41160_CONCURRENT_READS=PASS",
        "M41160_RLS_TENANT_ISOLATION=PASS",
    ):
        assert marker in source
    for forbidden in ("127.0.0.1:5433", "backend/migrations/", "pg_ctl",
                      "PIX_REAL=ON", "PAGAMENTOS_REAIS=ON", "ATIVACAO_REAL=ON"):
        assert forbidden not in source


def test_ci_workflow_uses_pg18_service_and_only_fixture_database():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    for marker in (
        "postgres:18",
        "55439:5432",
        "fr_m40700_disposable_ci",
        "CI_M41150_DISPOSABLE: '1'",
        "CI_M41160_DISPOSABLE: '1'",
        "CI_M41150_DATABASE_URL:",
        "CI_M41160_DATABASE_URL:",
        "PIX_REAL: 'OFF'",
        "PAGAMENTOS_REAIS: 'OFF'",
        "ATIVACAO_REAL: 'OFF'",
        "backend/tests/m41050_sql_sealed_context_pg18_disposable.py",
        "backend/tests/m41150_fastapi_rls_context_pg18_disposable.py",
        "backend/requirements.txt",
        "contents: read",
    ):
        assert marker in workflow
    for forbidden in ("127.0.0.1:5433", "backend/migrations/", "pg_ctl", "ssh "):
        assert forbidden not in workflow


def test_document_keeps_external_evidence_and_production_gates_open():
    doc = DOC.read_text(encoding="utf-8")
    for marker in (
        "CP26-0061", "CP26-0062", "CTM-07", "CTM-08",
        "PENDING_INDEPENDENT_EVIDENCE", "Issue #5",
        "M41150_AUTHENTICATION=OVERRIDDEN_SYNTHETIC",
        "M41150_PROVIDER=CUSTODY_NOT_CONFIGURED",
        "ORIGINAL_DATABASE=NOT_ACCESSED", "MIGRATIONS=NONE",
        "PIX_REAL=OFF", "PAGAMENTOS_REAIS=OFF", "ATIVACAO_REAL=OFF",
        "PRODUCTION=BLOCKED",
    ):
        assert marker in doc
    assert "PRODUCTION=GO" not in doc
