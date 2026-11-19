"""M40730 offline-only guards and explicit residual threat assertions."""
from __future__ import annotations
import ast
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import pytest

ROOT=Path(__file__).resolve().parents[2]
RUNNER=ROOT/"backend/tests/m40730_offdb_signer_authority_disposable.py"
WORKFLOW=ROOT/".github/workflows/frfinance-m40730-offdb-issuer-ci.yml"
SOURCE=RUNNER.read_text(encoding="utf-8")


def module():
    spec=importlib.util.spec_from_file_location("m40730_test_fixture",RUNNER)
    assert spec and spec.loader
    obj=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj


def test_compile_and_gate_before_postgresql():
    ast.parse(SOURCE)
    assert SOURCE.index("gate()\n        import psycopg") < SOURCE.index(
        'psycopg.connect(os.environ["CI_M40730_DATABASE_URL"]'
    )
    assert 'if __name__=="__main__":' in SOURCE


def test_termux_and_debian_execution_fail_closed():
    p=subprocess.run(
        [sys.executable,"-B",str(RUNNER)],
        env={"PATH":os.environ.get("PATH","")},
        capture_output=True,text=True,check=False,timeout=8
    )
    assert p.returncode==2
    assert "M40730_STATUS=BLOCKED_RuntimeError" in p.stdout
    assert "M40730_ORIGINAL_PG_5433=NOT_ACCESSED" in p.stdout


@pytest.mark.parametrize("dsn",(
    "postgresql://postgres:fixture@127.0.0.1:5433/fr_m40730_disposable_ci",
    "postgresql://postgres:fixture@127.0.0.1:55442/frcaixinha_aistudio_dev",
    "postgresql://postgres:fixture@localhost:55442/fr_m40730_disposable_ci",
    "postgresql://frc_ai_owner:fixture@127.0.0.1:55442/fr_m40730_disposable_ci",
    "postgresql://postgres:fixture@127.0.0.1:55442/fr_m40730_disposable_ci?sslmode=disable",
    "postgresql://postgres@127.0.0.1:55442/fr_m40730_disposable_ci",
))
def test_reject_original_and_wrong_database_identity(monkeypatch,dsn):
    obj=module()
    for key,value in {
        "GITHUB_ACTIONS":"true",
        "FRCAIXINHA_CI_ISOLATED":"1",
        "CI_M40730_DISPOSABLE":"1",
        "PIX_REAL":"OFF",
        "PAGAMENTOS_REAIS":"OFF",
        "ATIVACAO_REAL":"OFF",
        "CI_M40730_DATABASE_URL":dsn,
    }.items():
        monkeypatch.setenv(key,value)
    with pytest.raises(RuntimeError):
        obj.gate()


def test_no_hmac_or_client_private_key_stored_in_sql():
    for marker in (
        "CREATE SCHEMA m40730 AUTHORIZATION m40650_owner",
        "CREATE TABLE m40730.nonces",
        "m40730.issue_if_unused(",
        "CREATE ROLE m40730_signer NOLOGIN NOINHERIT NOBYPASSRLS",
        "GRANT EXECUTE ON FUNCTION m40730.issue_if_unused",
        "REVOKE EXECUTE ON FUNCTION m40650.m40680_issue",
        "REVOKE ALL ON m40730.nonces",
        "M40730_NO_SIGNING_KEYS_OR_PROOFS_STORED_IN_SQL=PASS_SYNTHETIC",
        "M40730_AUTH_FINANCIAL_SIGNER_SQL_ROLE_SPLIT=PASS",
    ):
        assert marker in SOURCE
    assert "m40700.verifier_secret" not in SOURCE
    assert "m40700.issue_bound" not in SOURCE
    assert "private.sign(canonical(" in SOURCE
    assert "public.verify(sig,canonical(" in SOURCE


def test_synthetic_scenarios_include_privileged_bypass_and_capture():
    for marker in (
        "M40730_CLIENT_POP_AND_TENANT_BOUND_HTTP_GATE=PASS",
        "M40730_CONCURRENT_NONCE_SINGLE_ISSUE=PASS",
        "M40730_PREUSE_CAPTURED_HTTP_REQUEST=CONFIRMED_NO_GO",
        "M40730_SESSION_REVOCATION_AFTER_POP=PASS",
        "M40730_COMPROMISED_SIGNER_SQL_LOGIN_BYPASSES_POP=CONFIRMED_NO_GO",
        "M40730_PRIVILEGED_DB_OWNER_CAN_REGRANT_SIGNER=CONFIRMED_NO_GO",
        "M40730_SIGNER_LOGIN_AND_TICKET_LOG_LEAKAGE=NOT_REMEDIATED",
        "M40730_TLS_DEVICE_KEY_ENROLLMENT_ATTESTATION=NOT_ATTESTED",
        "M40730_ORIGINAL_GUC_SPOOF=NOT_REMEDIATED",
        "M40730_REAL_FASTAPI_SQL_APP=NOT_MODIFIED",
        "M40730_PRODUCTION=BLOCKED",
    ):
        assert marker in SOURCE
    assert "sum(r.status_code==200 for r in responses)==1" in SOURCE
    assert "sum(r.status_code==401 for r in responses)==5" in SOURCE


def test_disposable_workflow_only():
    y=WORKFLOW.read_text(encoding="utf-8")
    for marker in (
        "postgres:18","55442:5432","fr_m40730_disposable_ci",
        "CI_M40730_DISPOSABLE: '1'",
        "FRCAIXINHA_CI_ISOLATED: '1'",
        "PIX_REAL: 'OFF'","PAGAMENTOS_REAIS: 'OFF'",
        "ATIVACAO_REAL: 'OFF'",
        "backend/tests/m40730_offdb_signer_authority_disposable.py",
    ):
        assert marker in y
    for forbidden in ("ssh ","pg_ctl","kubectl","backend/migrations/"):
        assert forbidden not in y
