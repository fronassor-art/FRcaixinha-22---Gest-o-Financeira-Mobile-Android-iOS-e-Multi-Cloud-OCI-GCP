"""M40920 offline safety checks; never contacts the original PostgreSQL."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT=Path(__file__).resolve().parents[2]
SCRIPT=ROOT/"backend/tests/m40920_master_token_writes_disposable.py"
WORKFLOW=ROOT/".github/workflows/frfinance-m40920-master-token-writes-pg18-ci.yml"
DOC=ROOT/"docs/FR_FINANCE_M40920_MASTER_TOKEN_WRITES_DISPOSABLE_NO_GO.md"
SRC=SCRIPT.read_text(encoding="utf-8")


def test_fail_closed_without_github_disposable_identity():
    result=subprocess.run(
        [sys.executable,"-B",str(SCRIPT)],env={"PATH":os.environ.get("PATH","")},
        text=True,capture_output=True,timeout=15,
    )
    assert result.returncode==2
    assert "M40920_STATUS=BLOCKED_RuntimeError" in result.stdout


def test_master_authentication_independent_from_guc():
    functions=SRC.split("CREATE FUNCTION m40920.create_draft",1)[1]
    functions=functions.split('    """)\n    for name in (',1)[0]
    assert functions.count("SECURITY DEFINER") == 2
    assert functions.count("SET search_path=pg_catalog,pg_temp") == 2
    assert functions.count("s.active_role='MASTER'") == 2
    assert functions.count("s.revoked_at IS NULL") == 2
    assert functions.count("m40910.sessions") >= 2
    assert "current_setting" not in functions
    assert "app.current_" not in functions


@pytest.mark.parametrize("marker",[
    "CI_M40920_DISPOSABLE", "CREATE POLICY m40920_broker_append",
    "REVOKE ALL ON m40920.audit FROM PUBLIC,frcaixinha_app_role",
    "REVOKE ALL ON FUNCTION", "m40910_broker_owner",
    "M40920_MASTER_DRAFT_AND_ATOMIC_AUDIT=PASS",
    "M40920_AUDIT_FAILURE_ROLLS_BACK_DRAFT=PASS",
    "M40920_DRAFT_PUBLISH_CANCEL_APPEND_ONLY=PASS",
    "M40920_REVOCATION_AND_GUC_SPOOF=PASS",
    "M40920_VALID_STOLEN_MASTER_BEARER=NOT_MITIGATED_NO_GO",
    "M40920_HTTP_AND_REAL_ISSUER=NOT_INTEGRATED",
])
def test_static_security_contract(marker):
    assert marker in SRC


@pytest.mark.parametrize("forbidden",[
    "pg_ctl","pg_restore","pg_dump","subprocess.Popen","os.system(",
    "backend/migrations/114","127.0.0.1:5433","httpx.post(",
])
def test_runner_cannot_target_real_local_database(forbidden):
    assert forbidden not in SRC


def test_workflow_and_document_no_go():
    flow=WORKFLOW.read_text(encoding="utf-8")
    doc=DOC.read_text(encoding="utf-8")
    for phrase in (
        "postgres:18","55433:5432","CI_M40920_DISPOSABLE: '1'",
        "CI_M40910_DISPOSABLE: '1'","PIX_REAL: 'OFF'",
        "PAGAMENTOS_REAIS: 'OFF'","ATIVACAO_REAL: 'OFF'",
        "contents: read","m40920_master_token_writes_disposable.py",
    ):
        assert phrase in flow
    for phrase in (
        "M40570","M40730","M40912","NO-GO","PRODUCTION=BLOCKED",
        "MIGRATIONS=NONE","PostgreSQL","Master",
    ):
        assert phrase in doc
