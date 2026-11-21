"""M40560: fail-closed guards for disposable Postgres role data-plane test."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import os
import subprocess
import sys

import pytest

ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/"backend/tests/m40560_saas_role_dataplane_disposable.py"
CI=ROOT/".github/workflows/frfinance-m40560-saas-role-rls-disposable.yml"
M39067=ROOT/"backend/tests/m39067_postgres18_disposable_runtime.py"


def test_forbidden_without_ci_environment():
    p=subprocess.run([sys.executable,"-B",str(SOURCE)],capture_output=True,
                     text=True,env={"PATH":os.environ.get("PATH","")},
                     timeout=10)
    assert p.returncode == 2
    assert "M40560_STATUS=BLOCKED_RuntimeError" in p.stdout
    assert "M40560_ORIGINAL_TERMUX_PG_5433=NOT_ACCESSED" in p.stdout


def test_strict_disposable_connection_target_and_two_layers():
    s=SOURCE.read_text()
    for marker in ("GITHUB_ACTIONS","CI_M40560_DISPOSABLE","FRCAIXINHA_CI_ISOLATED",
                   "CI_PROMOTIONS_DATABASE_URL","fr_m39067_disposable_ci",
                   "55433","127.0.0.1","restricted_connection()",
                   "isolate_only_identity_do(mig112","isolate_only_identity_do(mig113"):
        assert marker in s
    assert "NEVER_CONNECT_NON_DISPOSABLE_POSTGRES" in M39067.read_text()


def test_role_enforcement_and_real_disposable_sql112_113():
    s=SOURCE.read_text()
    for marker in ("SET ROLE frcaixinha_app_role","SET ROLE frcaixinha_auth_role",
                   "TENANT_MEMBER","TENANT_ADMIN","MASTER",
                   "MEMBER_INSERT","FAKE_MASTER_INSERT",
                   "APP_PROMO_UPDATE","APP_PROMO_DELETE",
                   "APP_PRICE_UPDATE","APP_PRICE_DELETE",
                   "AUTH_ROLE_OFFER_READER","AUTH_ROLE_PROMO_TABLE",
                   "ADMIN_CROSS_TENANT_OFFER_DENIED"):
        assert marker in s
    assert "exc.sqlstate != \"42501\"" in s


def test_synthetic_fixture_only_and_no_app_api_calls():
    s=SOURCE.read_text()
    assert "m40560_ci_master_allowlist" in s
    assert "set_config('app.current_role'" in s
    assert "GITHUB_ACTIONS" in s
    for forbidden in ("api.env","pg_ctl","pg_dump",
                      "DATABASE_URL","requests.post(","asyncpg.connect(",
                      "subprocess.Popen(","os.kill("):
        if forbidden=="DATABASE_URL":
            assert "DATABASE_URL" not in s.replace("CI_PROMOTIONS_DATABASE_URL","")
        else:
            assert forbidden not in s


def test_workflow_uses_isolated_container_only():
    s=CI.read_text()
    for marker in ("postgres:18","55433:5432",
                   "fr_m39067_disposable_ci","CI_M40560_DISPOSABLE: '1'",
                   "FRCAIXINHA_CI_ISOLATED: '1'",
                   "PIX_REAL: 'OFF'","PAGAMENTOS_REAIS: 'OFF'",
                   "ATIVACAO_REAL: 'OFF'",
                   "m40560_saas_role_dataplane_disposable.py"):
        assert marker in s
    for forbidden in ("pg_ctl restart","termux","ssh ","oci session","--apply"):
        assert forbidden not in s.lower()


def test_no_false_real_auth_claims():
    s=SOURCE.read_text()
    for marker in ("M40560_REAL_SESSIONS=NONE",
                   "M40560_PRODUCTION=BLOCKED",
                   "M40560_ORIGINAL_TERMUX_PG_5433=NOT_ACCESSED",
                   "M40560_ROLE_DATA_PLANE=PASS_DISPOSABLE_ONLY_NOT_PRODUCTION"):
        assert marker in s
