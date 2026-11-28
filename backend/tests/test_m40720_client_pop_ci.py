"""M40720 offline-only security contracts, no DB connections."""
from __future__ import annotations

import ast
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import pytest

ROOT=Path(__file__).resolve().parents[2]
RUNNER=ROOT/"backend/tests/m40720_client_pop_gateway_disposable.py"
WF=ROOT/".github/workflows/frfinance-m40720-client-pop-ci.yml"
SOURCE=RUNNER.read_text(encoding="utf-8")


def load():
    spec=importlib.util.spec_from_file_location("m40720_fixture",RUNNER)
    assert spec and spec.loader
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_import_syntax_and_db_only_after_gate():
    ast.parse(SOURCE)
    assert SOURCE.index("gate()\n        import asyncio") < SOURCE.index(
        "import psycopg\n        with psycopg.connect("
    )
    assert 'if __name__=="__main__":' in SOURCE


def test_local_execution_fails_before_db_connect():
    p=subprocess.run(
        [sys.executable,"-B",str(RUNNER)],
        capture_output=True,text=True,check=False,timeout=8,
        env={"PATH":os.environ.get("PATH","")},
    )
    assert p.returncode==2
    assert "M40720_STATUS=BLOCKED_RuntimeError" in p.stdout
    assert "M40720_ORIGINAL_PG_5433=NOT_ACCESSED" in p.stdout


@pytest.mark.parametrize("dsn",(
    "postgresql://postgres:fixture@127.0.0.1:5433/fr_m40720_disposable_ci",
    "postgresql://postgres:fixture@127.0.0.1:55441/frcaixinha_aistudio_dev",
    "postgresql://frc_ai_owner:fixture@127.0.0.1:55441/fr_m40720_disposable_ci",
    "postgresql://postgres:fixture@localhost:55441/fr_m40720_disposable_ci",
    "postgresql://postgres:fixture@127.0.0.1:55441/fr_m40720_disposable_ci?sslmode=disable",
    "postgresql://postgres@127.0.0.1:55441/fr_m40720_disposable_ci",
))
def test_production_identity_refused(monkeypatch,dsn):
    m=load()
    for k,v in {
        "GITHUB_ACTIONS":"true",
        "CI_M40720_DISPOSABLE":"1",
        "FRCAIXINHA_CI_ISOLATED":"1",
        "PIX_REAL":"OFF",
        "PAGAMENTOS_REAIS":"OFF",
        "ATIVACAO_REAL":"OFF",
        "CI_M40720_DATABASE_URL":dsn,
    }.items():
        monkeypatch.setenv(k,v)
    with pytest.raises(RuntimeError):
        m.gate()


def test_pop_is_method_path_session_tenant_nonce_expiry_bound():
    for marker in (
        "FRF-M40720|v1|GET|{path}|{digest}|{tenant}|{nonce}|{expiry}|{SCOPE}",
        "client_private_a = Ed25519PrivateKey.generate()",
        "verifier.verify(signature, message(digest, tenant, nonce, expiry))",
        "sha256(raw.encode(\"ascii\")).hexdigest()",
        "X-FR-Pop",
        "Cache-Control",
        "m40700.issue_bound(%s,%s,%s,%s,%s,%s)",
        "m40680_consume(%s,%s)",
        "M40720_VALID_ED25519_CLIENT_BOUND_HTTP_TO_SQL=PASS",
        "M40720_BEARER_ONLY_TAMPERED_PROOF_AND_CROSS_TENANT_DENIED=PASS",
        "M40720_SQL_AUTH_ROLE_WITHOUT_SIGNER_CANNOT_MINT=PASS",
        "M40720_REVOKED_SESSION_WITH_VALID_POP_DENIED=PASS",
    ):
        assert marker in SOURCE


def test_no_go_remains_and_no_sql_client_private_key():
    for marker in (
        "M40720_STOLEN_BEARER_PLUS_PREUSE_POP_PROOF=CONFIRMED_NO_GO",
        "M40720_CONCURRENT_SIGNED_REQUEST_ONE_TIME=PASS",
        "M40720_ED25519_PRIVATE_KEY_SENT_TO_SQL=NONE",
        "M40720_SQL_HMAC_KEY_EXTRACTABLE_BY_DB_OWNER=CONFIRMED_NO_GO",
        "M40720_IN_MEMORY_PUBLIC_KEY_REGISTRY=NOT_PRODUCTION",
        "M40720_REQUEST_CAPTURE_REPLAY_BEFORE_USE=NOT_REMEDIATED",
        "M40720_REAL_FASTAPI_AND_PROD_ROUTES=NOT_MODIFIED",
        "M40720_EXISTING_GUC_SPOOF=NOT_REMEDIATED",
        "M40720_PRODUCTION=BLOCKED",
    ):
        assert marker in SOURCE


def test_workflow_is_disposable_only():
    w=WF.read_text(encoding="utf-8")
    for marker in (
        "postgres:18", "55441:5432", "fr_m40720_disposable_ci",
        "CI_M40720_DISPOSABLE: '1'",
        "FRCAIXINHA_CI_ISOLATED: '1'",
        "PIX_REAL: 'OFF'", "PAGAMENTOS_REAIS: 'OFF'",
        "ATIVACAO_REAL: 'OFF'",
        "backend/tests/m40720_client_pop_gateway_disposable.py",
        "cryptography==45.0.7",
    ):
        assert marker in w
    for forbidden in ("ssh ", "pg_ctl", "kubectl", "backend/migrations/"):
        assert forbidden not in w
