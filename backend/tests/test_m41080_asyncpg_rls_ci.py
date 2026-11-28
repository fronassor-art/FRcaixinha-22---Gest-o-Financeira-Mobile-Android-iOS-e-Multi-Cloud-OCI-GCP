"""M41080 offline guards for asyncpg transaction capability and RLS proof."""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "backend" / "tests" / "m41050_sql_sealed_context_pg18_disposable.py"
M41050_WORKFLOW = ROOT / ".github" / "workflows" / "frfinance-m41050-signed-session-context-pg18-ci.yml"
M41060_WORKFLOW = ROOT / ".github" / "workflows" / "frfinance-m41060-write-rls-pg18-ci.yml"
DOC = ROOT / "docs" / "FR_FINANCE_M41080_ASYNCPG_RLS_INTEGRATION_NO_GO.md"
DOC90 = ROOT / "docs" / "FR_FINANCE_M41090_ASYNCPG_POOL_REUSE_NO_GO.md"
DOC100 = ROOT / "docs" / "FR_FINANCE_M41100_ASYNCPG_REVOKED_SESSION_POOL_NO_GO.md"
DOC41140 = ROOT / "docs" / "FR_FINANCE_M41140_REVOKE_WRITE_RACE_NO_GO.md"
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
        "M41080_ASYNCPG_TRANSACTION_LOCAL_RESET=",
        "M41080_ASYNCPG_CONTEXT=",
        "M41080_ASYNCPG_M41060_PRIOR_MEMBER_ROW_ACCOUNTED=PASS",
        "M41080_DIAGNOSTIC=",
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
            "docs/FR_FINANCE_M41090_ASYNCPG_POOL_REUSE_NO_GO.md",
            "CI_M41090_DISPOSABLE",
            "CI_M41090_DATABASE_URL",
            "docs/FR_FINANCE_M41100_ASYNCPG_REVOKED_SESSION_POOL_NO_GO.md",
            "CI_M41100_DISPOSABLE",
            "CI_M41100_DATABASE_URL",
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


def test_asyncpg_pool_reuse_resets_capability_role_and_legacy_context():
    for marker in (
        "async def _m41090_create_asyncpg_pool",
        "max_size=1",
        "async def _m41090_assert_pool_clean",
        "async def _m41090_exercise_asyncpg_pool",
        "M41090_ASYNCPG_POOL_COMMIT_TRANSACTION_RESET=PASS",
        "M41090_ASYNCPG_POOL_COMMIT_REACQUIRE_RESET=PASS",
        "M41090_ASYNCPG_POOL_ROLLBACK_TRANSACTION_RESET=PASS",
        "M41090_ASYNCPG_POOL_ROLLBACK_REACQUIRE_RESET=PASS",
        "M41090_ASYNCPG_POOL_REUSED_SAME_BACKEND=PASS",
        "M41090_ASYNCPG_POOL_CONTEXT_LEAK",
        "M41090_DIAGNOSTIC=",
        "M41090_ASYNCPG_POOL_STALE_CLAIMS",
        "CI_M41090_DISPOSABLE",
        "CI_M41090_DATABASE_URL",
    ):
        assert marker in SOURCE

    doc = DOC90.read_text(encoding="utf-8")
    for marker in (
        "CP26-0061", "CP26-0062", "CTM-07", "CTM-08",
        "COMMIT", "ROLLBACK", "REACQUIRE", "SAME_BACKEND",
        "ORIGINAL_DATABASE=NOT_ACCESSED", "MIGRATIONS=NONE",
        "PIX_REAL=OFF", "PAGAMENTOS_REAIS=OFF", "ATIVACAO_REAL=OFF",
        "PRODUCTION=BLOCKED", "PENDING_INDEPENDENT_EVIDENCE",
    ):
        assert marker in doc
    assert "PRODUCTION=GO" not in doc


def test_asyncpg_pool_rechecks_revocation_between_borrows():
    for marker in (
        "async def _m41100_exercise_revoke_between_pool_borrows",
        "_m41100_exercise_revoke_between_pool_borrows(",
        "M41100_ASYNCPG_ACTIVE_BEFORE_REVOKE=PASS",
        "M41100_ASYNCPG_FIXTURE_SESSION_REVOKED=PASS",
        "M41100_ASYNCPG_REVOKED_REBORROW=DENIED",
        "M41100_ASYNCPG_REVOKED_SAME_BACKEND=PASS",
        "M41100_ASYNCPG_REVOKED_CLAIMS_REMAIN",
        "M41100_ASYNCPG_REVOKED_RLS_ROWS_REMAIN",
        "M41100_DIAGNOSTIC=",
        "CI_M41100_DISPOSABLE",
        "CI_M41100_DATABASE_URL",
    ):
        assert marker in SOURCE

    doc = DOC100.read_text(encoding="utf-8")
    for marker in (
        "CP26-0061", "CP26-0062", "CTM-07", "CTM-08",
        "ACTIVE_BEFORE_REVOKE", "REVOKED_REBORROW",
        "SAME_BACKEND", "ORIGINAL_DATABASE=NOT_ACCESSED",
        "MIGRATIONS=NONE", "PIX_REAL=OFF", "PAGAMENTOS_REAIS=OFF",
        "ATIVACAO_REAL=OFF", "PRODUCTION=BLOCKED",
        "PENDING_INDEPENDENT_EVIDENCE",
    ):
        assert marker in doc
    assert "PRODUCTION=GO" not in doc


def test_m41110_capability_seals_subject_and_role_and_invalidates_switches():
    for marker in (
        "bound_user_id uuid NOT NULL",
        "bound_role text NOT NULL",
        "FOR SHARE OF s",
        "s.user_id=c.bound_user_id",
        "s.active_role=c.bound_role",
        "OLD.active_role IS DISTINCT FROM NEW.active_role",
        "CREATE TRIGGER m41110_invalidate_changed_session_caps",
        "WHERE session_digest=OLD.token_digest AND revoked_at IS NULL",
        "M41110_INVALIDATION_ACL=PASS",
        "M41110_ASYNCPG_ROLE_SWITCH_OPEN_TRANSACTION=DENIED",
        "M41110_ASYNCPG_ROLE_SWITCH_REBORROW=DENIED",
        "M41110_MEMBER_OLD_WRITE_AFTER_PROMOTION=DENIED",
        "M41110_FRESH_ADMIN_SCOPES=PASS",
        "M41110_RETURN_TO_MEMBER_OLD_CAPS=DENIED",
        "M41110_RETURN_TO_ADMIN_OLD_CAPS=DENIED",
        "M41110_FRESH_MEMBER_SCOPE=PASS",
        "M41110_STATUS=PASS_DISPOSABLE_ROLE_BINDING_ONLY",
    ):
        assert marker in SOURCE
    doc = (ROOT / "docs" / "FR_FINANCE_M41110_ROLE_BOUND_CAPABILITY_NO_GO.md").read_text(encoding="utf-8")
    for marker in ("CP26-0061", "CP26-0062", "PRODUCTION=BLOCKED",
                   "MIGRATIONS=NONE", "PENDING_INDEPENDENT_EVIDENCE"):
        assert marker in doc


def test_m41120_signed_ticket_context_and_generation():
    for marker in (
        "FRF-M41120|v2|", "CREATE FUNCTION m40700.issue_bound_v2",
        "s.context_generation=p_generation", "s.context_generation=v_generation",
        "s.context_generation=c.context_generation",
        "CREATE TRIGGER m41120_context_generation",
        "NEW.context_generation:=OLD.context_generation+1",
        "REVOKE EXECUTE ON FUNCTION m40700.issue_bound(text,uuid,uuid,bigint,text,text)",
        "REVOKE EXECUTE ON FUNCTION m40650.m40680_consume",
        "M41120_LEGACY_PATH_AND_CONTEXT_ACL=PASS",
        "M41120_SIGNED_CONTEXT_TAMPER_AND_NONCE=PASS",
        "M41120_ISSUED_MEMBER_TICKET_AFTER_SWITCH=DENIED",
        "M41120_RETURN_TO_ORIGINAL_ROLE_OLD_TICKET=DENIED",
        "M41120_FRESH_CONTEXT=PASS",
        "M41120_STATUS=PASS_DISPOSABLE_TICKET_CONTEXT_ONLY",
    ):
        assert marker in SOURCE


def test_m41130_lifecycle_invalidation_is_scoped_and_transactional():
    for marker in (
        "CREATE TRIGGER m41130_account_context",
        "CREATE TRIGGER m41130_membership_context",
        "OLD.context_generation IS DISTINCT FROM NEW.context_generation",
        "SET context_generation=context_generation+1",
        "active_tenant_id=OLD.tenant_id",
        "active_role=OLD.role",
        "M41130_LIFECYCLE_ACL=PASS",
        "M41130_LIFECYCLE_ROLLBACK=PASS",
        "M41130_MEMBERSHIP_SUSPENSION_ISOLATED=PASS",
        "M41130_MEMBERSHIP_REACTIVATION_OLD_CAP=DENIED",
        "M41130_MEMBERSHIP_RECREATE_OLD_PROOFS=DENIED",
        "M41130_ACCOUNT_REACTIVATION_OLD_PROOFS=DENIED",
        "M41130_ADMIN_OLD_WRITE_DENIED_FRESH_WRITE=PASS",
        "M41130_STATUS=PASS_DISPOSABLE_LIFECYCLE_ONLY",
    ):
        assert marker in SOURCE


def test_m41140_serializes_disposable_revocation_and_financial_write_races():
    for marker in (
        "RETURNS boolean LANGUAGE plpgsql VOLATILE SECURITY DEFINER",
        "ORDER BY u.id",
        "ORDER BY m.user_id,m.tenant_id,m.role",
        "FROM m40650.sessions AS s",
        "FROM m41050.session_caps AS c",
        "FOR SHARE;",
        "pg_catalog.pg_blocking_pids",
        "_m41140_revoke_first(",
        "_m41140_write_first(",
        'print("M41140_"+kind.upper()+"_REVOKE_FIRST=PASS")',
        'print("M41140_"+kind.upper()+"_WRITE_FIRST=PASS")',
        "CI_M41140_DISPOSABLE",
        "CI_M41140_DATABASE_URL",
        "M41140_STATUS=PASS_DISPOSABLE_REVOCATION_WRITE_RACES_ONLY",
    ):
        assert marker in SOURCE

    doc = DOC41140.read_text(encoding="utf-8")
    for marker in (
        "CP26-0061", "CP26-0062", "CTM-07", "CTM-08",
        "330 IDs", "2.310 etapas",
        "ACCOUNT_REVOKE_FIRST", "ACCOUNT_WRITE_FIRST",
        "ADMIN_MEMBERSHIP_REVOKE_FIRST", "ADMIN_MEMBERSHIP_WRITE_FIRST",
        "MEMBER_MEMBERSHIP_REVOKE_FIRST", "MEMBER_MEMBERSHIP_WRITE_FIRST",
        "pg_blocking_pids", "MIGRATIONS=NONE",
        "ORIGINAL_DATABASE=NOT_ACCESSED",
        "PIX_REAL=OFF", "PAGAMENTOS_REAIS=OFF",
        "ATIVACAO_REAL=OFF", "PRODUCTION=BLOCKED",
        "PENDING_INDEPENDENT_EVIDENCE",
    ):
        assert marker in doc
    assert "PRODUCTION=GO" not in doc


def test_m41140_workflow_guards_the_disposable_database_and_paths():
    for workflow_path in (M41050_WORKFLOW, M41060_WORKFLOW):
        workflow = workflow_path.read_text(encoding="utf-8")
        for marker in (
            "CI_M41140_DISPOSABLE: '1'",
            "CI_M41140_DATABASE_URL: postgresql://postgres:only_m41050_disposable_ci@127.0.0.1:55439/fr_m40700_disposable_ci",
            "docs/FR_FINANCE_M41140_REVOKE_WRITE_RACE_NO_GO.md",
            "PIX_REAL: 'OFF'",
            "PAGAMENTOS_REAIS: 'OFF'",
            "ATIVACAO_REAL: 'OFF'",
            "postgres:18",
            "contents: read",
        ):
            assert marker in workflow
        assert workflow.count("docs/FR_FINANCE_M41140_REVOKE_WRITE_RACE_NO_GO.md") == 2
        for forbidden in (
            "127.0.0.1:5433",
            "backend/migrations/",
            "pg_ctl",
            "PIX_REAL: 'ON'",
            "PAGAMENTOS_REAIS: 'ON'",
            "ATIVACAO_REAL: 'ON'",
        ):
            assert forbidden not in workflow
