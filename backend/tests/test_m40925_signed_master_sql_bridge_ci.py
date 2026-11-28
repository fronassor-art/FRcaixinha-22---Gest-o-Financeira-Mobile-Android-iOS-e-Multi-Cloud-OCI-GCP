"""M40925 synthetic ASGI/SQL issuer bridging contract, no live DB."""
from pathlib import Path
import os
import subprocess
import sys
import pytest

ROOT=Path(__file__).resolve().parents[2]
SCRIPT=ROOT/"backend/tests/m40925_signed_master_sql_bridge_disposable.py"
WORKFLOW=ROOT/".github/workflows/frfinance-m40925-signed-master-sql-bridge-pg18-ci.yml"
DOC=ROOT/"docs/FR_FINANCE_M40925_SIGNED_MASTER_SQL_BRIDGE_NO_GO.md"
SRC=SCRIPT.read_text(encoding="utf-8")

def test_requires_ci_disposable_before_importing_database():
    result=subprocess.run(
        [sys.executable,"-B",str(SCRIPT)],capture_output=True,text=True,
        env={"PATH":os.environ.get("PATH","")},timeout=15,
    )
    assert result.returncode==2
    assert "M40925_STATUS=BLOCKED_RuntimeError" in result.stdout
    assert "M40925_ORIGINAL_TERMUX_PG_5433=NOT_ACCESSED" in result.stdout

@pytest.mark.parametrize("required",[
    "CI_M40925_DISPOSABLE",
    "m40924_master_one_time_sql_gate_disposable import require_disposable",
    "CREATE ROLE m40925_issuer_role NOLOGIN NOINHERIT NOBYPASSRLS",
    "CREATE ROLE m40925_issuer_login LOGIN NOINHERIT NOBYPASSRLS",
    "CREATE POLICY m40925_issuer_insert",
    "m40923_offdb_master_action_gate import",
    "verifier.authorize(",
    "body_digest(payload)",
    "command[\"session_digest\"]!=sha256(token.encode",
    "m40924.draft_digest(",
    "m40924.transition_digest(",
    "m40924.gated_draft(",
    "m40924.gated_transition(",
    "M40925_SQL_ISSUER_APP_AND_WRITER_ROLES=DISJOINT",
    "M40925_STOLEN_APP_SQL_PLUS_MASTER_NO_APPROVAL=DENIED",
    "M40925_ASGI_ED25519_CONTEXT_TAMPER_REPLAY=DENIED",
    "M40925_END_TO_END_DRAFT_PUBLISH_CANCEL=PASS_SYNTHETIC",
    "M40925_ASGI_CONCURRENT_SIGNED_NONCE_ONE_OF_SIX=PASS",
    "M40925_REVOKED_MASTER_SIGNED_COMMAND=DENIED",
    "M40925_STOLEN_ISSUER_PLUS_APP_SQL_PLUS_BEARER=NO_GO_BYPASS",
    "M40925_KEYS_AND_SIGNATURES_NEVER_PASSED_TO_SQL=PASS_SYNTHETIC",
])
def test_expected_gateway_and_negative_proofs(required):
    assert required in SRC

@pytest.mark.parametrize("forbidden",[
    "pg_ctl","pg_dump","pg_restore","subprocess.Popen","os.system(",
    "127.0.0.1:5433","backend/migrations/114",
    "ALTER ROLE frc_ai_owner","CREATE EXTENSION dblink",
])
def test_no_original_or_service_access(forbidden):
    assert forbidden not in SRC

def test_workflow_and_documented_no_go():
    y=WORKFLOW.read_text(encoding="utf-8")
    doc=DOC.read_text(encoding="utf-8")
    for mark in (
        "postgres:18","55433:5432",
        "CI_M40925_DISPOSABLE: '1'","CI_M40924_DISPOSABLE: '1'",
        "CI_M40923_DISPOSABLE: '1'","PIX_REAL: 'OFF'",
        "PAGAMENTOS_REAIS: 'OFF'","ATIVACAO_REAL: 'OFF'",
        "contents: read","fastapi==0.115.12",
        "httpx==0.28.1","cryptography==45.0.7",
    ):
        assert mark in y
    for mark in (
        "M40570","M40730","M40924","NO-GO","SQL","Ed25519",
        "MIGRATIONS=NONE","PRODUCTION=BLOCKED","FastAPI",
    ):
        assert mark in doc
