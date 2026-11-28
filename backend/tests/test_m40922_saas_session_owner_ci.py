"""M40922: fail-closed CI guards for detached SaaS token table owner."""
from pathlib import Path
import os
import subprocess
import sys
import pytest

ROOT=Path(__file__).resolve().parents[2]
SCRIPT=ROOT/"backend/tests/m40922_saas_session_owner_disposable.py"
WORKFLOW=ROOT/".github/workflows/frfinance-m40922-saas-session-owner-pg18-ci.yml"
DOC=ROOT/"docs/FR_FINANCE_M40922_SAAS_SESSION_OWNER_NO_GO.md"
SRC=SCRIPT.read_text(encoding="utf-8")

def test_no_runner_access_without_ci_disposable_flags():
    result=subprocess.run([sys.executable,"-B",str(SCRIPT)],
        capture_output=True,text=True,env={"PATH":os.environ.get("PATH","")},
        timeout=15)
    assert result.returncode==2
    assert "M40922_STATUS=BLOCKED_RuntimeError" in result.stdout
    assert "M40922_ORIGINAL_TERMUX_PG_5433=NOT_ACCESSED" in result.stdout

@pytest.mark.parametrize("must_exist",[
    "CI_M40922_DISPOSABLE",
    "from m40921_saas_broker_role_split_disposable import require_disposable",
    "CREATE ROLE m40922_session_owner NOLOGIN NOINHERIT NOBYPASSRLS",
    "ALTER TABLE m40910.sessions OWNER TO m40922_session_owner",
    "ALTER SCHEMA m40910 OWNER TO m40922_session_owner",
    "REVOKE ALL ON m40910.sessions",
    "GRANT SELECT ON m40910.sessions",
    "M40922_READER_WRITER_SESSION_DML=DENIED_SQLSTATE_42501",
    "M40922_READER_WITHOUT_SESSION_OWNERSHIP=PASS",
    "M40922_WRITER_WITHOUT_SESSION_OWNERSHIP=PASS",
    "M40922_SESSION_REVOCATION=ENFORCED",
])
def test_role_custody_split_and_proofs(must_exist):
    assert must_exist in SRC

def test_roles_only_read_tokens_not_issue_them():
    assert "for role in (READER,WRITER)" in SRC
    for op in ("INSERT","UPDATE","DELETE","TRUNCATE","REFERENCES","TRIGGER"):
        assert '"'+op+'"' in SRC
    assert "'MEMBER'" in SRC
    assert "CREATE ROLE m40922_session_owner LOGIN" not in SRC
    assert "GRANT m40922_session_owner TO" not in SRC
    assert "current_setting('app.current_" not in SRC

@pytest.mark.parametrize("forbidden",[
    "pg_ctl","pg_restore","pg_dump","subprocess.Popen",
    "os.system(","127.0.0.1:5433","backend/migrations/114",
    "ALTER ROLE frc_ai_owner",
])
def test_no_real_database_or_service_access(forbidden):
    assert forbidden not in SRC

def test_workflow_and_report_no_go():
    workflow=WORKFLOW.read_text(encoding="utf-8")
    doc=DOC.read_text(encoding="utf-8")
    for p in (
        "postgres:18","55433:5432","CI_M40922_DISPOSABLE: '1'",
        "CI_M40921_DISPOSABLE: '1'","CI_M40920_DISPOSABLE: '1'",
        "PIX_REAL: 'OFF'","PAGAMENTOS_REAIS: 'OFF'",
        "ATIVACAO_REAL: 'OFF'","contents: read"):
        assert p in workflow
    for p in ("M40570","M40730","M40921","NO-GO",
              "MIGRATIONS=NONE","PRODUCTION=BLOCKED"):
        assert p in doc
