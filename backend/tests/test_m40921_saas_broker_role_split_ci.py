"""M40921 offline guardrails for split SaaS broker, no original DB access."""
from pathlib import Path
import os
import subprocess
import sys
import pytest

ROOT=Path(__file__).resolve().parents[2]
SCRIPT=ROOT/"backend/tests/m40921_saas_broker_role_split_disposable.py"
WORKFLOW=ROOT/".github/workflows/frfinance-m40921-saas-broker-role-split-pg18-ci.yml"
DOC=ROOT/"docs/FR_FINANCE_M40921_SAAS_BROKER_ROLE_SPLIT_NO_GO.md"
SOURCE=SCRIPT.read_text(encoding="utf-8")

def test_fail_closed_without_exact_runner_identity():
    proc=subprocess.run([sys.executable,"-B",str(SCRIPT)],
          text=True,capture_output=True,
          env={"PATH":os.environ.get("PATH","")},timeout=15)
    assert proc.returncode==2
    assert "M40921_STATUS=BLOCKED_RuntimeError" in proc.stdout
    assert "M40921_ORIGINAL_TERMUX_PG_5433=NOT_ACCESSED" in proc.stdout

@pytest.mark.parametrize("required",[
    "CI_M40921_DISPOSABLE","from m40920_master_token_writes_disposable",
    "CREATE ROLE m40921_writer_owner NOLOGIN NOINHERIT NOBYPASSRLS",
    "CREATE POLICY m40921_writer_read",
    "CREATE POLICY m40921_writer_append",
    "ALTER TABLE m40920.audit OWNER TO m40921_writer_owner",
    "ALTER FUNCTION ","DROP POLICY m40920_broker_append",
    "REVOKE INSERT (","FROM m40910_broker_owner",
    "M40921_READ_OWNER_WRITE_PRIVILEGES=REVOKED",
    "M40921_READ_GATEWAY_SURVIVES_ROLE_SPLIT=PASS",
    "M40921_MASTER_WRITES_AND_ATOMIC_AUDIT=PASS",
    "M40921_REVOKED_AND_FORGED_MASTER=DENIED",
])
def test_separation_and_proofs_explicit(required):
    assert required in SOURCE

def test_no_public_role_membership_or_old_guc_authority():
    assert "GRANT m40921_writer_owner TO frcaixinha_app_role" not in SOURCE
    assert "CREATE ROLE m40921_writer_owner LOGIN" not in SOURCE
    assert "current_setting('app.current_" not in SOURCE
    assert "SET ROLE m40921_writer_owner" in SOURCE # negative test only

@pytest.mark.parametrize("forbidden",[
    "pg_ctl","pg_restore","pg_dump","subprocess.Popen","os.system(",
    "127.0.0.1:5433","backend/migrations/114",
    "ALTER ROLE frc_ai_owner","INSERT INTO public.audit_events"
])
def test_never_operates_original_or_production(forbidden):
    assert forbidden not in SOURCE

def test_disposable_ci_and_no_go_doc():
    y=WORKFLOW.read_text(encoding="utf-8")
    doc=DOC.read_text(encoding="utf-8")
    for marker in ("postgres:18","55433:5432",
        "CI_M40921_DISPOSABLE: '1'","CI_M40920_DISPOSABLE: '1'",
        "PIX_REAL: 'OFF'","PAGAMENTOS_REAIS: 'OFF'",
        "ATIVACAO_REAL: 'OFF'","contents: read"):
        assert marker in y
    for marker in ("M40570","M40730","M40920",
        "NO-GO","PRODUCTION=BLOCKED","MIGRATIONS=NONE"):
        assert marker in doc
