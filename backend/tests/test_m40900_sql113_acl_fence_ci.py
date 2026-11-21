"""M40900 local static/fail-closed checks; no PostgreSQL or network access."""
from __future__ import annotations
import os
from pathlib import Path
import subprocess
import sys

from app.m40840_financial_sql_release_no_go import (
    FinancialSQLReleaseBlocked, require_nonproduction_financial_sql,
)
import pytest

ROOT=Path(__file__).resolve().parents[2]
RUNNER=ROOT/"backend/tests/m40900_sql113_acl_fence_disposable.py"
CI=ROOT/".github/workflows/frfinance-m40900-sql113-acl-fence-disposable.yml"
DOC=ROOT/"docs/FR_FINANCE_M40900_DISPOSABLE_SQL113_ACL_FENCE_NO_GO.md"

def test_runner_never_opens_pg_without_disposable_ci_environment():
    proc=subprocess.run(
      [sys.executable,"-B",str(RUNNER)],capture_output=True,text=True,
      env={"PATH":os.environ.get("PATH","")},
      timeout=12,
    )
    assert proc.returncode==2
    assert "M40900_STATUS=BLOCKED_RuntimeError" in proc.stdout
    assert "M40900_ORIGINAL_TERMUX_PG_5433=NOT_ACCESSED" in proc.stdout

def test_runner_checks_target_before_importing_real_driver():
    text=RUNNER.read_text()
    assert text.index("require_disposable()")<text.index(
        "from m39067_postgres18_disposable_runtime import restricted_connection"
    )
    for item in ("CI_M40900_DISPOSABLE", "GITHUB_ACTIONS",
                 "FRCAIXINHA_CI_ISOLATED", "55433",
                 "fr_m39067_disposable_ci", "CI_PROMOTIONS_DATABASE_URL"):
        assert item in text

def test_column_level_insert_acl_must_be_revoked_explicitly():
    from importlib.util import spec_from_file_location,module_from_spec
    spec=spec_from_file_location("m40900_sql113_acl_fence_disposable",RUNNER)
    assert spec is not None and spec.loader is not None
    # No code execution beyond module imports; psycopg imported in run only.
    # Verify all column grants in historical SQL113 are represented.
    sql=(ROOT/"backend/migrations/113_frfinance_saas_new_admin_promotions.sql").read_text()
    assert "GRANT INSERT(campaign_id,revision,plan_tier,billing_period" in sql
    source=RUNNER.read_text()
    assert "REVOKE INSERT (" in source
    assert "has_column_privilege" in source
    assert '"FORGED_MASTER_INSERT"' in source
    assert "has_table_privilege" in source
    assert "has_function_privilege" in source
    assert "BASELINE_SQL_GUC_SPOOF=EXPOSURE_CONFIRMED" in source

def test_privileged_acl_fence_must_not_run_on_original():
    content=RUNNER.read_text()
    for word in ("pg_ctl","pg_dump","pg_restore","subprocess.Popen","os.system",
                 "ssh ", "oci ", "127.0.0.1:5433"):
        assert word not in content
    assert "M40900_REAL_POSTGRES_PRIVILEGES=NOT_ATTESTED" in content
    assert "M40900_LEGACY_SAAS_ENDPOINTS=UNAVAILABLE_AFTER_FENCE" in content

def test_existing_real_production_sql_gate_still_blocks():
    with pytest.raises(FinancialSQLReleaseBlocked):
        require_nonproduction_financial_sql({
            "ENVIRONMENT":"production","PIX_REAL":"OFF",
            "PAGAMENTOS_REAIS":"OFF","ATIVACAO_REAL":"OFF",
        })

def test_doc_ci_pinned_disposable_and_release_no_go():
    ci=CI.read_text()
    doc=DOC.read_text()
    for value in ("postgres:18","55433:5432",
                  "CI_M40900_DISPOSABLE: '1'","CI_M40560_DISPOSABLE: '1'",
                  "FRCAIXINHA_CI_ISOLATED: '1'","PIX_REAL: 'OFF'",
                  "PAGAMENTOS_REAIS: 'OFF'", "ATIVACAO_REAL: 'OFF'",
                  "contents: read", "m40900_sql113_acl_fence_disposable.py"):
        assert value in ci
    for value in ("M40570","M40730","M40870","GUC","NO-GO",
                  "PRODUCTION=BLOCKED","MIGRATIONS=NONE"):
        assert value in doc
