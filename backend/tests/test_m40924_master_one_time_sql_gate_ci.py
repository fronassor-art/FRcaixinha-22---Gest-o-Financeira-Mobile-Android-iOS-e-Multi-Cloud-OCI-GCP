"""M40924 offline verification of synthetic SQL authorization fence."""
from pathlib import Path
import os
import subprocess
import sys
import pytest

ROOT=Path(__file__).resolve().parents[2]
SCRIPT=ROOT/"backend/tests/m40924_master_one_time_sql_gate_disposable.py"
WORKFLOW=ROOT/".github/workflows/frfinance-m40924-master-one-time-sql-gate-pg18-ci.yml"
DOC=ROOT/"docs/FR_FINANCE_M40924_MASTER_ONE_TIME_SQL_GATE_NO_GO.md"
SRC=SCRIPT.read_text(encoding="utf-8")

def test_script_fails_closed_without_exact_ci_identity():
    out=subprocess.run([sys.executable,"-B",str(SCRIPT)],
        capture_output=True,text=True,
        env={"PATH":os.environ.get("PATH","")},timeout=15)
    assert out.returncode==2
    assert "M40924_STATUS=BLOCKED_RuntimeError" in out.stdout
    assert "M40924_ORIGINAL_TERMUX_PG_5433=NOT_ACCESSED" in out.stdout

@pytest.mark.parametrize("marker",[
    "CI_M40924_DISPOSABLE",
    "from m40923_offdb_master_sql_issuer_disposable import require_disposable",
    "CREATE ROLE m40924_approval_owner NOLOGIN NOINHERIT NOBYPASSRLS",
    "CREATE ROLE m40924_gate_owner NOLOGIN NOINHERIT NOBYPASSRLS",
    "ALTER TABLE m40924.approvals FORCE ROW LEVEL SECURITY",
    "GRANT SELECT,UPDATE(consumed_at)",
    "M40924_LEGACY_SQL_WRITER_APP_EXECUTE=REVOKED",
    "M40924_APPROVAL_TABLE_APP_ACCESS=ZERO",
    "M40924_GATE_OWNER_UPDATE_ONLY_CONSUMED_AT=PASS",
    "M40924_STOLEN_SQL_PLUS_MASTER_BEARER_WITHOUT_APPROVAL=DENIED",
    "M40924_AUDIT_FAILURE_ROLLS_BACK_APPROVAL=PASS",
    "M40924_CONCURRENT_APPROVAL_ONE_OF_SIX=PASS",
    "M40924_SESSION_REVOKED_APPROVAL_DENIED=PASS",
    "M40924_REAL_OFFDB_APPROVER_OR_ED25519_LINK=NOT_INTEGRATED_NO_GO",
])
def test_sql_gate_and_known_limits_are_explicit(marker):
    assert marker in SRC

def test_sql_gate_consumption_matches_real_parameters():
    assert "m40924.draft_digest(" in SRC
    assert "m40924.transition_digest(" in SRC
    assert "a.body_digest=m40924.draft_digest(" in SRC
    assert "a.body_digest=m40924.transition_digest(" in SRC
    assert "AND a.consumed_at IS NULL" in SRC
    assert "AND a.expires_at>pg_catalog.clock_timestamp()" in SRC
    assert "a.actor_id=v_actor" in SRC
    assert "a.tenant_id=v_tenant" in SRC
    assert "a.session_digest=v_session_digest" in SRC
    assert "RETURN QUERY" in SRC

@pytest.mark.parametrize("forbidden",[
    "pg_ctl","pg_restore","pg_dump","subprocess.Popen","os.system(",
    "127.0.0.1:5433","ALTER ROLE frc_ai_owner",
    "backend/migrations/114",
])
def test_no_original_database_or_service_access(forbidden):
    assert forbidden not in SRC

def test_workflow_and_security_no_go():
    y=WORKFLOW.read_text(encoding="utf-8")
    doc=DOC.read_text(encoding="utf-8")
    for marker in ("postgres:18","55433:5432",
        "CI_M40924_DISPOSABLE: '1'","CI_M40923_DISPOSABLE: '1'",
        "CI_M40922_DISPOSABLE: '1'","PIX_REAL: 'OFF'",
        "PAGAMENTOS_REAIS: 'OFF'","ATIVACAO_REAL: 'OFF'",
        "contents: read"):
        assert marker in y
    for marker in ("M40570","M40730","M40923","NO-GO",
        "MIGRATIONS=NONE","PRODUCTION=BLOCKED",
        "SQL app","Ed25519","FastAPI"):
        assert marker in doc
