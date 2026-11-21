"""M40690 offline-only contract tests, no PostgreSQL connection."""
from __future__ import annotations

import ast
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import pytest

ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "backend/tests/m40690_concurrent_ticket_digest_risk_disposable.py"
WORKFLOW = ROOT / ".github/workflows/frfinance-m40690-concurrent-ticket-ci.yml"
SOURCE = RUNNER.read_text(encoding="utf-8")


def runner_module():
    spec = importlib.util.spec_from_file_location("m40690_disposable_test", RUNNER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_syntax_and_no_implicit_execution():
    ast.parse(SOURCE)
    assert 'if __name__ == "__main__":' in SOURCE
    assert SOURCE.index("require_isolated_ci()\n        # Neither") < SOURCE.index(
        "import psycopg\n        with psycopg.connect"
    )


def test_default_environment_fails_before_postgres_import():
    p = subprocess.run(
        [sys.executable, "-B", str(RUNNER)],
        env={"PATH": os.environ.get("PATH", "")},
        capture_output=True, text=True, timeout=8, check=False,
    )
    assert p.returncode == 2
    assert "M40690_STATUS=BLOCKED_RuntimeError" in p.stdout
    assert "M40690_ORIGINAL_PG_5433=NOT_ACCESSED" in p.stdout


@pytest.mark.parametrize("dsn", (
    "postgresql://postgres:ci@127.0.0.1:5433/fr_m40690_disposable_ci",
    "postgresql://postgres:ci@127.0.0.1:55438/frcaixinha_aistudio_dev",
    "postgresql://frc_ai_owner:ci@127.0.0.1:55438/fr_m40690_disposable_ci",
    "postgresql://postgres:ci@localhost:55438/fr_m40690_disposable_ci",
    "postgresql://postgres:ci@127.0.0.1:55438/fr_m40690_disposable_ci?sslmode=disable",
    "postgresql://postgres@127.0.0.1:55438/fr_m40690_disposable_ci",
))
def test_wrong_postgres_identity_is_refused(monkeypatch, dsn):
    mod = runner_module()
    for key, value in {
        "GITHUB_ACTIONS": "true",
        "CI_M40690_DISPOSABLE": "1",
        "FRCAIXINHA_CI_ISOLATED": "1",
        "PIX_REAL": "OFF",
        "PAGAMENTOS_REAIS": "OFF",
        "ATIVACAO_REAL": "OFF",
        "CI_M40690_DATABASE_URL": dsn,
    }.items():
        monkeypatch.setenv(key, value)
    with pytest.raises(RuntimeError):
        mod.require_isolated_ci()


def test_real_parallel_connections_and_single_winner():
    for token in (
        "ThreadPoolExecutor(max_workers=workers)",
        "Barrier(workers, timeout=20)",
        "workers = 8",
        "for trial in range(3):",
        "len(wins) == 1",
        "len(losses) == workers - 1",
        "M40690_EIGHT_PARALLEL_CONSUMERS_SINGLE_SUCCESS=PASS",
        "M40690_CROSS_TENANT_GUESS_NO_AUTHORIZATION=PASS",
    ):
        assert token in SOURCE


def test_digest_as_credential_risk_must_not_be_mislabeled_as_remediated():
    for token in (
        "stolen_digest = digest_b",
        "cap1 = issue(stolen_digest, tenant_a)",
        "cap2 = issue(stolen_digest, tenant_a)",
        "cap1 != cap2",
        "M40690_DIGEST_REPLAY_MINTS_MULTIPLE_TICKETS=CONFIRMED_NO_GO",
        "M40690_AUTH_DIGEST_CREDENTIAL_EQUIVALENCE=NOT_REMEDIATED",
        "M40690_SQL_LOG_LEAKAGE_AND_TELEMETRY=NOT_ATTESTED",
        "M40690_EXISTING_GUC_SPOOF=NOT_REMEDIATED",
        "M40690_HTTP_AND_REAL_SQL_ROUTES=NOT_MODIFIED",
        "M40690_PRODUCTION=BLOCKED",
    ):
        assert token in SOURCE


def test_session_and_membership_revocation_are_rechecked():
    for token in (
        "M40690_REVOKED_SESSION_CANNOT_USE_PREISSUED_TICKET=PASS",
        "M40690_DISABLED_MEMBERSHIP_CANNOT_USE_PREISSUED_TICKET=PASS",
        "M40690_AUTH_FINANCIAL_SQL_ROLE_SEPARATION=PASS",
        "SET ROLE m40680_auth",
        "SET ROLE m40650_app",
        "has_function_privilege(",
        "has_table_privilege(",
        "autocommit=True",
    ):
        assert token in SOURCE


def test_workflow_disposable_only():
    wf = WORKFLOW.read_text(encoding="utf-8")
    for token in (
        "postgres:18", "55438:5432", "fr_m40690_disposable_ci",
        "CI_M40690_DISPOSABLE: '1'",
        "FRCAIXINHA_CI_ISOLATED: '1'",
        "PIX_REAL: 'OFF'", "PAGAMENTOS_REAIS: 'OFF'",
        "ATIVACAO_REAL: 'OFF'",
        "backend/tests/m40690_concurrent_ticket_digest_risk_disposable.py",
    ):
        assert token in wf
    for forbidden in ("ssh ", "pg_ctl", "kubectl", "backend/migrations/"):
        assert forbidden not in wf
