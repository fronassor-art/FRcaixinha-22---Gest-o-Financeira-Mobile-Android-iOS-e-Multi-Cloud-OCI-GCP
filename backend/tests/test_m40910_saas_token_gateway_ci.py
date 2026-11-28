"""M40910: fail-closed checks for the disconnected token-only broker fixture."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import pytest

ROOT=Path(__file__).resolve().parents[2]
SCRIPT=ROOT/"backend/tests/m40910_saas_token_gateway_disposable.py"
WORKFLOW=ROOT/".github/workflows/frfinance-m40910-saas-token-gateway-pg18-ci.yml"
DOC=ROOT/"docs/FR_FINANCE_M40910_TOKEN_SAAS_GATEWAY_DISPOSABLE_NO_GO.md"
SRC=SCRIPT.read_text(encoding="utf-8")


def test_runner_fails_closed_without_exact_github_disposable_env():
    p=subprocess.run([sys.executable,"-B",str(SCRIPT)],capture_output=True,
                     text=True,env={"PATH":os.environ.get("PATH","")},timeout=15)
    assert p.returncode==2
    assert "M40910_STATUS=BLOCKED_RuntimeError" in p.stdout
    assert "M40910_ORIGINAL_TERMUX_PG_5433=NOT_ACCESSED" in p.stdout


def test_disposable_gates_before_driver_import():
    for marker in ("CI_M40910_DISPOSABLE","CI_M40900_DISPOSABLE",
                   "CI_M40560_DISPOSABLE","FRCAIXINHA_CI_ISOLATED",
                   "GITHUB_ACTIONS","55433","fr_m39067_disposable_ci",
                   "CI_PROMOTIONS_DATABASE_URL"):
        assert marker in SRC
    assert SRC.index("require_disposable()\n        from m40900")<SRC.index(
        "from m39067_postgres18_disposable_runtime import restricted_connection")


def test_no_sql_guc_authority_in_new_definer():
    f=SRC.split("CREATE FUNCTION m40910.read_new_admin_offers",1)[1]
    f=f.split("$body$",2)[1]
    assert "SECURITY DEFINER" in SRC
    assert "SET search_path=pg_catalog,pg_temp" in SRC
    assert "pg_catalog.sha256(pg_catalog.convert_to(p_token,'UTF8'))" in f
    assert "s.active_role='TENANT_ADMIN'" in f
    assert "s.expires_at>pg_catalog.clock_timestamp()" in f
    assert "s.revoked_at IS NULL" in f
    assert "t.admin_user_id=s.user_id" in f
    assert "current_setting" not in f
    assert "app.current_" not in f


def test_app_table_and_owner_role_are_denied_independently():
    for marker in (
        "CREATE ROLE m40910_broker_owner NOLOGIN NOINHERIT NOBYPASSRLS",
        "CREATE ROLE m40910_ci_login LOGIN NOINHERIT NOBYPASSRLS",
        "REVOKE ALL ON m40910.sessions FROM PUBLIC,frcaixinha_app_role",
        "CREATE POLICY m40910_broker_read",
        "FOR SELECT TO m40910_broker_owner USING (true)",
        "REVOKE ALL ON FUNCTION",
        "GRANT EXECUTE ON FUNCTION",
        "SET ROLE m40910_broker_owner",
        "M40910_DIRECT_PROMOTION_TABLE",
        "M40910_DIRECT_TOKEN_DIGESTS",
    ):
        assert marker.replace("M40910_DIRECT_PROMOTION_TABLE","DIRECT_PROMOTION_TABLE").replace(
            "M40910_DIRECT_TOKEN_DIGESTS","DIRECT_TOKEN_DIGESTS") in SRC


def test_legitimate_admin_and_adversarial_session_scenarios():
    for marker in ("M40910_ADMIN_LEGITIMATE_OFFER=RESTORED_VIA_TOKEN_ONLY",
                   "M40910_EXPIRED_REVOKED_MEMBER_CROSS_TENANT=DENIED",
                   "M40910_SQL_GUC_SPOOF_CANNOT_WIDEN_BROKER=PASS",
                   "M40910_EXISTING_ADMIN_ELIGIBILITY=ENFORCED",
                   "M40910_LIVE_REVOCATION=ENFORCED",
                   "M40910_STOLEN_VALID_BEARER=NOT_MITIGATED_NO_GO",
                   "M40910_HTTP_RUNTIME_INTEGRATION=NOT_IMPLEMENTED"):
        assert marker in SRC


@pytest.mark.parametrize("forbidden",[
    "pg_ctl", "pg_restore", "pg_dump", "subprocess.Popen",
    "os.system(", "backend/migrations/114",
    "CREATE DATABASE frcaixinha", "127.0.0.1:5433",
])
def test_runner_never_targets_original_or_restarts(forbidden):
    assert forbidden not in SRC


def test_ci_and_document_keep_production_off():
    y=WORKFLOW.read_text(encoding="utf-8")
    doc=DOC.read_text(encoding="utf-8")
    for marker in ("postgres:18","55433:5432","CI_M40910_DISPOSABLE: '1'",
                   "CI_M40900_DISPOSABLE: '1'","PIX_REAL: 'OFF'",
                   "PAGAMENTOS_REAIS: 'OFF'","ATIVACAO_REAL: 'OFF'",
                   "contents: read","m40910_saas_token_gateway_disposable.py"):
        assert marker in y
    for marker in ("M40570","M40730","M40900","NO-GO",
                   "PRODUCTION=BLOCKED","MIGRATIONS=NONE"):
        assert marker in doc
