"""M40710: offline fail-closed checks. No PostgreSQL connection."""
from __future__ import annotations

import ast
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import pytest

ROOT = Path(__file__).resolve().parents[2]
SOURCE_PATH = ROOT / "backend/tests/m40710_signer_capture_adversarial_disposable.py"
WORKFLOW = ROOT / ".github/workflows/frfinance-m40710-signer-capture-ci.yml"
SOURCE = SOURCE_PATH.read_text(encoding="utf-8")


def fixture():
    spec = importlib.util.spec_from_file_location("m40710_fixt", SOURCE_PATH)
    assert spec is not None and spec.loader is not None
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj


def test_no_auto_start_and_gate_precedes_db_connect():
    ast.parse(SOURCE)
    assert 'if __name__ == "__main__":' in SOURCE
    assert SOURCE.index("require_disposable()\n        # No driver") < SOURCE.index(
        "import psycopg\n        with psycopg.connect"
    )


def test_termux_and_debian_execution_fail_closed():
    run = subprocess.run(
        [sys.executable, "-B", str(SOURCE_PATH)],
        capture_output=True, text=True, timeout=8, check=False,
        env={"PATH": os.environ.get("PATH", "")},
    )
    assert run.returncode == 2
    assert "M40710_STATUS=BLOCKED_RuntimeError" in run.stdout
    assert "M40710_ORIGINAL_PG_5433=NOT_ACCESSED" in run.stdout


@pytest.mark.parametrize("dsn", (
    "postgresql://postgres:ci@127.0.0.1:5433/fr_m40710_disposable_ci",
    "postgresql://postgres:ci@127.0.0.1:55440/frcaixinha_aistudio_dev",
    "postgresql://postgres:ci@localhost:55440/fr_m40710_disposable_ci",
    "postgresql://frc_ai_owner:ci@127.0.0.1:55440/fr_m40710_disposable_ci",
    "postgresql://postgres@127.0.0.1:55440/fr_m40710_disposable_ci",
    "postgresql://postgres:ci@127.0.0.1:55440/fr_m40710_disposable_ci?sslmode=disable",
))
def test_reject_non_disposable_identity(monkeypatch, dsn):
    obj = fixture()
    for key, value in {
        "GITHUB_ACTIONS": "true",
        "CI_M40710_DISPOSABLE": "1",
        "FRCAIXINHA_CI_ISOLATED": "1",
        "PIX_REAL": "OFF",
        "PAGAMENTOS_REAIS": "OFF",
        "ATIVACAO_REAL": "OFF",
        "CI_M40710_DATABASE_URL": dsn,
    }.items():
        monkeypatch.setenv(key, value)
    with pytest.raises(RuntimeError):
        obj.require_disposable()


def test_capture_and_key_extraction_are_explicit_no_go():
    for marker in (
        "M40710_PREUSE_CAPTURED_SIGNED_CLAIM_ACCEPTED=CONFIRMED_NO_GO",
        "M40710_DATABASE_OWNER_HMAC_KEY_EXTRACTION=CONFIRMED_NO_GO",
        "M40710_EXTRACTED_HMAC_KEY_CAN_FORGE_SESSION_CLAIM=CONFIRMED_NO_GO",
        "M40710_PREUSE_INTERCEPTION_RISK=NOT_REMEDIATED",
        "M40710_SIGNED_CLAIM_SQL_PARAMETER_EXPOSURE=NOT_REMEDIATED",
        "M40710_ORIGINAL_GUC_SPOOF=NOT_REMEDIATED",
        "M40710_PRODUCTION=BLOCKED",
    ):
        assert marker in SOURCE


def test_race_and_privilege_checks_are_real_sql_connections():
    for marker in (
        "Barrier(workers, timeout=20)",
        "ThreadPoolExecutor(max_workers=workers)",
        "workers = 6",
        "len(tickets) == 1",
        "for _ in range(2):",
        "m40700.issue_bound(%s,%s,%s,%s,%s,%s)",
        "SELECT key FROM m40700.verifier_secret WHERE singleton=true",
        "m40700.verifier_secret",
        "has_table_privilege",
        "has_function_privilege",
        "has_schema_privilege",
        "SET ROLE m40680_auth",
        "SET ROLE m40650_app",
        "M40710_DIGEST_PLUS_AUTH_ROLE_WITHOUT_SIGNER_KEY=DENIED",
        "M40710_CONCURRENT_SIGNED_CLAIM_SINGLE_REDEEM=PASS",
    ):
        assert marker in SOURCE


def test_workflow_is_strictly_disposable():
    text = WORKFLOW.read_text(encoding="utf-8")
    for marker in (
        "postgres:18", "55440:5432", "fr_m40710_disposable_ci",
        "CI_M40710_DISPOSABLE: '1'", "FRCAIXINHA_CI_ISOLATED: '1'",
        "PIX_REAL: 'OFF'", "PAGAMENTOS_REAIS: 'OFF'",
        "ATIVACAO_REAL: 'OFF'",
        "backend/tests/m40710_signer_capture_adversarial_disposable.py",
    ):
        assert marker in text
    for forbidden in ("ssh ", "pg_ctl", "kubectl", "backend/migrations/"):
        assert forbidden not in text
