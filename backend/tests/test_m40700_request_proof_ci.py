"""M40700: fail-closed static tests only; no database access."""
from __future__ import annotations

import ast
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import pytest

ROOT = Path(__file__).resolve().parents[2]
SOURCE_PATH = ROOT / "backend/tests/m40700_request_proof_disposable.py"
WF_PATH = ROOT / ".github/workflows/frfinance-m40700-request-proof-ci.yml"
SOURCE = SOURCE_PATH.read_text(encoding="utf-8")


def load():
    spec = importlib.util.spec_from_file_location("m40700_only_fixture", SOURCE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_syntax_and_gate_before_driver():
    ast.parse(SOURCE)
    assert SOURCE.index("require_disposable_ci()\n        import psycopg") < SOURCE.index(
        "with psycopg.connect(os.environ"
    )


def test_local_execution_is_fail_closed():
    r = subprocess.run(
        [sys.executable, "-B", str(SOURCE_PATH)], capture_output=True, text=True,
        env={"PATH": os.environ.get("PATH", "")}, check=False, timeout=8,
    )
    assert r.returncode == 2
    assert "M40700_STATUS=BLOCKED_RuntimeError" in r.stdout
    assert "M40700_ORIGINAL_PG_5433=NOT_ACCESSED" in r.stdout


@pytest.mark.parametrize("dsn", (
    "postgresql://postgres:fixture@127.0.0.1:5433/fr_m40700_disposable_ci",
    "postgresql://postgres:fixture@127.0.0.1:55439/frcaixinha_aistudio_dev",
    "postgresql://postgres:fixture@localhost:55439/fr_m40700_disposable_ci",
    "postgresql://frc_ai_owner:fixture@127.0.0.1:55439/fr_m40700_disposable_ci",
    "postgresql://postgres:fixture@127.0.0.1:55439/fr_m40700_disposable_ci?sslmode=disable",
    "postgresql://postgres@127.0.0.1:55439/fr_m40700_disposable_ci",
))
def test_disposable_identity_is_required(monkeypatch, dsn):
    m = load()
    for k, v in {
        "GITHUB_ACTIONS": "true",
        "CI_M40700_DISPOSABLE": "1",
        "FRCAIXINHA_CI_ISOLATED": "1",
        "PIX_REAL": "OFF",
        "PAGAMENTOS_REAIS": "OFF",
        "ATIVACAO_REAL": "OFF",
        "CI_M40700_DATABASE_URL": dsn,
    }.items():
        monkeypatch.setenv(k, v)
    with pytest.raises(RuntimeError):
        m.require_disposable_ci()


def test_signed_claim_binds_session_tenant_nonce_expiry_and_scope():
    for marker in (
        "FRF-M40700|v1|{digest}|{tenant}|{nonce}|{expiry}|{scope}",
        "hmac.new(secret, message(digest, tenant, nonce, expiry, scope)",
        "CREATE EXTENSION pgcrypto WITH SCHEMA m40700",
        "m40700.hmac(",
        "p_scope IS DISTINCT FROM 'READ_ENTRIES'",
        "p_scope IS DISTINCT FROM 'WRITE_TEST_ENTRY'",
        "WRITE_SCOPE = \"WRITE_TEST_ENTRY\"",
        "INSERT INTO m40700.ticket_scopes(ticket_digest,scope_name)",
        "p_expiry>pg_catalog.floor(",
        "p_proof<>v_expected",
        "ON CONFLICT(nonce) DO NOTHING RETURNING nonce INTO v_nonce",
        "M40700_DIGEST_ALONE_AND_TAMPERED_ATTESTATION_DENIED=PASS",
        "M40700_NONCE_REPLAY_AND_TICKET_REPLAY_DENIED=PASS",
        "M40700_SESSION_REVOCATION_AFTER_SIGNING_DENIED=PASS",
    ):
        assert marker in SOURCE


def test_low_privilege_sql_cannot_bypass_claim_check_with_legacy_issuer():
    for marker in (
        "REVOKE EXECUTE ON FUNCTION m40650.m40680_issue(text,uuid)",
        "FROM m40680_auth",
        "REVOKE ALL ON m40700.verifier_secret",
        "REVOKE ALL ON m40700.used_nonces",
        "REVOKE ALL ON FUNCTION",
        "GRANT EXECUTE ON FUNCTION",
        "M40700_SIGNING_SECRET_AND_ROLE_ACL_DENIED=PASS",
        "M40700_SIGNER_KEY_COMPROMISE=NO_GO",
        "M40700_SIGNATURE_DB_PARAMETER_LOGGING=NOT_REMEDIATED",
        "M40700_HMAC_VERIFY_TIMING=NOT_ATTESTED",
        "M40700_EXISTING_GUC_SPOOF=NOT_REMEDIATED",
        "M40700_PRODUCTION_INTEGRATION=NOT_ACTIVATED",
        "M40700_PRODUCTION=BLOCKED",
    ):
        assert marker in SOURCE


def test_workflow_is_pg18_ephemeral_only():
    wf = WF_PATH.read_text(encoding="utf-8")
    for marker in (
        "postgres:18", "55439:5432", "fr_m40700_disposable_ci",
        "CI_M40700_DISPOSABLE: '1'",
        "FRCAIXINHA_CI_ISOLATED: '1'",
        "PIX_REAL: 'OFF'", "PAGAMENTOS_REAIS: 'OFF'",
        "ATIVACAO_REAL: 'OFF'",
        "backend/tests/m40700_request_proof_disposable.py",
    ):
        assert marker in wf
    for forbidden in ("ssh ", "pg_ctl", "kubectl", "backend/migrations/"):
        assert forbidden not in wf
