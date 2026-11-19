"""M40650: offline safety/structure tests; no PostgreSQL or external connections."""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "backend/tests/m40650_token_bound_gateway_disposable.py"
WORKFLOW = ROOT / ".github/workflows/frfinance-m40650-token-gateway-ci.yml"
SOURCE = RUNNER.read_text(encoding="utf-8")


def load():
    spec = importlib.util.spec_from_file_location("frfinance_m40650", RUNNER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_disposable_runner_fails_closed_without_flags_or_driver():
    result = subprocess.run(
        [sys.executable, "-B", str(RUNNER)],
        env={"PATH": os.environ.get("PATH", "")},
        text=True, capture_output=True, check=False, timeout=8,
    )
    assert result.returncode == 2
    assert "M40650_STATUS=BLOCKED_RuntimeError" in result.stdout
    assert "M40650_ORIGINAL_PG_5433=NOT_ACCESSED" in result.stdout


@pytest.mark.parametrize("dsn", (
    "postgresql://postgres:test@127.0.0.1:5433/fr_m40650_disposable_ci",
    "postgresql://postgres:test@127.0.0.1:55435/frcaixinha_aistudio_dev",
    "postgresql://postgres:test@localhost:55435/fr_m40650_disposable_ci",
    "postgresql://frc_ai_owner:test@127.0.0.1:55435/fr_m40650_disposable_ci",
    "postgresql://postgres:test@127.0.0.1:55435/fr_m40650_disposable_ci?sslmode=disable",
    "postgresql://postgres@127.0.0.1:55435/fr_m40650_disposable_ci",
))
def test_wrong_database_identity_blocked(monkeypatch, dsn):
    mod = load()
    for key, value in {
        "GITHUB_ACTIONS": "true",
        "CI_M40650_DISPOSABLE": "1",
        "FRCAIXINHA_CI_ISOLATED": "1",
        "PIX_REAL": "OFF",
        "PAGAMENTOS_REAIS": "OFF",
        "ATIVACAO_REAL": "OFF",
        "CI_M40650_DATABASE_URL": dsn,
    }.items():
        monkeypatch.setenv(key, value)
    with pytest.raises(RuntimeError):
        mod.require_disposable()


def test_connection_happens_only_after_disposable_gate():
    assert SOURCE.index("require_disposable()\n        # Strict CI") < SOURCE.index(
        "import psycopg\n        with psycopg.connect"
    )
    assert 'PORT = 55435' in SOURCE
    assert 'DB = "fr_m40650_disposable_ci"' in SOURCE
    assert "M40650_PRODUCTION=BLOCKED" in SOURCE


def test_sql_function_makes_token_the_only_identity_authority():
    for marker in (
        "LANGUAGE plpgsql SECURITY DEFINER",
        "SET search_path = pg_catalog, pg_temp",
        "m40650.sessions",
        "m40650.memberships",
        "m40650.entries",
        "pg_catalog.sha256(pg_catalog.convert_to(p_token, 'UTF8'))",
        "s.revoked_at IS NULL",
        "m.status = 'ATIVA'",
        "s.active_tenant_id = p_tenant",
        "s.active_role IN ('TENANT_MEMBER', 'TENANT_ADMIN')",
        "v_role = 'TENANT_ADMIN' OR e.user_id = v_user",
        "REVOKE ALL ON FUNCTION m40650.read_entries(text,uuid) FROM PUBLIC",
        "GRANT EXECUTE ON FUNCTION m40650.read_entries(text,uuid) TO m40650_app",
    ):
        assert marker in SOURCE


def test_adversary_has_independent_non_superuser_session():
    for marker in (
        "m40650_ci_login LOGIN NOINHERIT NOBYPASSRLS",
        "GRANT m40650_app TO m40650_ci_login",
        "with psycopg.connect(app_dsn, autocommit=True) as conn:",
        'assert conn.execute("SELECT session_user").fetchone()[0] == "m40650_ci_login"',
        'expect_denied(conn, "SET ROLE m40650_owner")',
    ):
        assert marker in SOURCE


def test_adversarial_proof_is_explicit_and_not_a_false_prod_go():
    for marker in (
        "M40650_DIRECT_TABLE_AND_OWNER_ESCALATION=DENIED",
        "M40650_TOKEN_ROLE_MEMBERSHIP_TENANT_DENIAL=PASS",
        "M40650_SYNTHETIC_GUC_SPOOF_CANNOT_WIDEN_GATEWAY=PASS",
        "M40650_SEARCH_PATH_TEMP_SHADOW=DENIED",
        "M40650_REVOKED_MEMBERSHIP_ACCESS=DENIED",
        "M40650_EXISTING_APPLICATION_RLS=NOT_REMEDIATED",
        "M40650_HTTP_BEARER_INTEGRATION=NOT_TESTED",
        "M40650_PROPOSED_GATEWAY=ISOLATED_PROTOTYPE_ONLY",
    ):
        assert marker in SOURCE


def test_m40660_account_status_dual_tenant_and_session_context():
    for marker in (
        "CREATE TABLE m40650.users",
        "JOIN m40650.users AS u",
        "u.status = 'ACTIVE'",
        "(member_a, tenant_b, \"TENANT_MEMBER\", \"ATIVA\")",
        '"master_member", master, "TENANT_MEMBER", tenant_a',
        'UPDATE m40650.users SET status=\'SUSPENDED\' WHERE id=%s',
        "UPDATE m40650.sessions SET active_role='TENANT_ADMIN'",
        "UPDATE m40650.sessions SET revoked_at=%s",
        "M40660_DUAL_TENANT_MEMBERSHIP_LOCK=PASS",
        "M40660_MASTER_ACCOUNT_MEMBER_SESSION=PASS",
        "M40660_DISABLED_ACCOUNT_DENIED=PASS",
        "M40660_UNAUTHORIZED_ROLE_SWITCH_DENIED=PASS",
        "M40660_LIVE_SESSION_REVOCATION_DENIED=PASS",
        "M40650_EXISTING_APPLICATION_RLS=NOT_REMEDIATED",
    ):
        assert marker in SOURCE


def test_workflow_disposable_only_no_local_execution():
    yaml = WORKFLOW.read_text(encoding="utf-8")
    for marker in (
        "postgres:18", "55435:5432",
        "fr_m40650_disposable_ci",
        "CI_M40650_DISPOSABLE: '1'",
        "FRCAIXINHA_CI_ISOLATED: '1'",
        "PIX_REAL: 'OFF'",
        "PAGAMENTOS_REAIS: 'OFF'",
        "ATIVACAO_REAL: 'OFF'",
        "backend/tests/m40650_token_bound_gateway_disposable.py",
    ):
        assert marker in yaml
    assert "ssh " not in yaml
    assert "pg_ctl" not in yaml
    assert "kubectl" not in yaml
