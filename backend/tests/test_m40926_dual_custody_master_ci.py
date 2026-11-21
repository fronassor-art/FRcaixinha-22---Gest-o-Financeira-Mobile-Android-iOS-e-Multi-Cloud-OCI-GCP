"""M40926 offline guard tests; never connects to a user database."""
from pathlib import Path
import os
import subprocess
import sys
import pytest

ROOT=Path(__file__).resolve().parents[2]
SCRIPT=ROOT/"backend/tests/m40926_dual_custody_master_disposable.py"
WORKFLOW=ROOT/".github/workflows/frfinance-m40926-dual-custody-master-pg18-ci.yml"
DOC=ROOT/"docs/FR_FINANCE_M40926_DUAL_CUSTODY_MASTER_NO_GO.md"
SRC=SCRIPT.read_text(encoding="utf-8")

def test_disposable_identity_required_before_import_and_connect():
    result=subprocess.run(
        [sys.executable,"-B",str(SCRIPT)],
        capture_output=True,text=True,
        env={"PATH":os.environ.get("PATH","")},timeout=15,
    )
    assert result.returncode==2
    assert "M40926_STATUS=BLOCKED_RuntimeError" in result.stdout
    assert "M40926_ORIGINAL_TERMUX_PG_5433=NOT_ACCESSED" in result.stdout

@pytest.mark.parametrize("needle",[
    "CI_M40926_DISPOSABLE",
    "m40925_signed_master_sql_bridge_disposable import require_disposable",
    "CREATE ROLE m40926_guardian_writer NOLOGIN NOINHERIT NOBYPASSRLS",
    "CREATE ROLE m40926_guardian_login LOGIN NOINHERIT NOBYPASSRLS",
    "CREATE ROLE m40926_seal_checker NOLOGIN NOINHERIT NOBYPASSRLS",
    "ALTER TABLE m40926.seals FORCE ROW LEVEL SECURITY",
    "GRANT INSERT (",
    "GRANT SELECT,UPDATE(consumed_at) ON m40926.seals",
    "CREATE TRIGGER m40926_guardian_fence",
    "BEFORE UPDATE OF consumed_at ON m40924.approvals",
    "SECURITY DEFINER",
    "s.approval_digest=NEW.approval_digest",
    "s.session_digest=NEW.session_digest",
    "s.body_digest=NEW.body_digest",
    "s.expires_at>=NEW.expires_at",
    "s.consumed_at IS NULL",
    "M40926_GUARDIAN_FENCE_TRIGGER=ENABLED",
    "M40926_STOLEN_ISSUER_APP_BEARER_WITHOUT_GUARDIAN=DENIED",
    "M40926_STOLEN_GUARDIAN_APP_BEARER_NO_ISSUER=DENIED",
    "M40926_ED25519_GUARDIAN_ASGI_DRAFT=PASS",
    "M40926_DRAFT_PUBLISH_CANCEL_WITH_TWO_SEALS=PASS",
    "M40926_AUDIT_FAILURE_ROLLS_BACK_BOTH_CONSUMPTIONS=PASS",
    "M40926_CONCURRENT_DUAL_APPROVAL_ONE_OF_SIX=PASS",
    "M40926_REVOKED_MASTER_DUAL_APPROVAL=DENIED",
    "M40926_ALL_SQL_CREDENTIALS_AND_BEARER=NO_GO_BYPASS",
    "M40926_CUSTODY_BOTH_SQL_LOGINS_IN_ONE_PROCESS=NOT_REMEDIATED",
])
def test_guardian_sql_and_adversarial_proof_is_explicit(needle):
    assert needle in SRC

@pytest.mark.parametrize("bad",[
    "pg_ctl","pg_dump","pg_restore","subprocess.Popen",
    "os.system(","127.0.0.1:5433",
    "ALTER ROLE frc_ai_owner","backend/migrations/114",
])
def test_fixture_never_targets_original_database_or_services(bad):
    assert bad not in SRC

def test_ci_and_documented_no_go():
    y=WORKFLOW.read_text()
    doc=DOC.read_text()
    for needle in (
        "postgres:18","55433:5432",
        "CI_M40926_DISPOSABLE: '1'",
        "CI_M40925_DISPOSABLE: '1'",
        "CI_M40924_DISPOSABLE: '1'",
        "CI_M40923_DISPOSABLE: '1'",
        "fastapi==0.115.12","httpx==0.28.1",
        "cryptography==45.0.7",
        "PIX_REAL: 'OFF'","PAGAMENTOS_REAIS: 'OFF'",
        "ATIVACAO_REAL: 'OFF'","contents: read",
    ):
        assert needle in y
    for needle in (
        "NO-GO","M40570","M40730","M40925","M40926",
        "Ed25519","FastAPI","Vault","MIGRATIONS=NONE",
        "PRODUCTION=BLOCKED",
    ):
        assert needle in doc
