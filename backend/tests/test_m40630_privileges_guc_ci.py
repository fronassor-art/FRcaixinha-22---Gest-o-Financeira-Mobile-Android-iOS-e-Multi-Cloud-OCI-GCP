"""M40630: fail-closed source/CI guard for privilege and GUC risk audit."""
from pathlib import Path
import os
import subprocess
import sys
from urllib.parse import urlsplit
import importlib.util

import pytest

ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "backend/tests/m40630_privileges_guc_disposable.py"
WORKFLOW = ROOT / ".github/workflows/frfinance-m40630-privilege-guc-ci.yml"
SOURCE = RUNNER.read_text(encoding="utf-8")
WF = WORKFLOW.read_text(encoding="utf-8")


def load():
    spec = importlib.util.spec_from_file_location("frfinance_m40630", RUNNER)
    m = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(m)
    return m


def test_fail_closed_without_disposable_flags_or_psycopg():
    r = subprocess.run(
        [sys.executable, "-B", str(RUNNER)], capture_output=True,
        text=True, timeout=10, check=False,
        env={"PATH": os.environ.get("PATH","")},
    )
    assert r.returncode == 2
    assert "M40630_STATUS=BLOCKED_RuntimeError" in r.stdout
    assert "M40630_TERMUX_PG_5433=NOT_ACCESSED" in r.stdout


@pytest.mark.parametrize("invalid", (
    "postgresql://postgres:synthetic@127.0.0.1:5433/fr_m39067_disposable_ci",
    "postgresql://postgres:synthetic@127.0.0.1:55433/frcaixinha_aistudio_dev",
    "postgresql://postgres:synthetic@localhost:55433/fr_m39067_disposable_ci",
    "postgresql://frc_ai_owner:synthetic@127.0.0.1:55433/fr_m39067_disposable_ci",
    "postgresql://postgres:synthetic@127.0.0.1:55433/fr_m39067_disposable_ci?sslmode=disable",
))
def test_wrong_database_identity_rejected(monkeypatch,invalid):
    m = load()
    for k,v in {
        "GITHUB_ACTIONS":"true",
        "CI_M40630_DISPOSABLE":"1",
        "CI_M40560_DISPOSABLE":"1",
        "FRCAIXINHA_CI_ISOLATED":"1",
        "PIX_REAL":"OFF",
        "PAGAMENTOS_REAIS":"OFF",
        "ATIVACAO_REAL":"OFF",
        "CI_PROMOTIONS_DATABASE_URL":invalid,
    }.items():
        monkeypatch.setenv(k,v)
    with pytest.raises(RuntimeError):
        m.require_disposable()


def test_guard_enforced_before_connection_import():
    assert SOURCE.index("require_disposable()\n        # Import") < SOURCE.index(
        "from m39067_postgres18_disposable_runtime import restricted_connection"
    )
    assert "if os.environ.get(k) != v:" in SOURCE
    assert "EXPECTED_PORT = 55433" in SOURCE


def test_privileges_and_rls_checked_using_pg_catalog():
    for value in (
        "pg_catalog.pg_roles", "rolsuper", "rolbypassrls", "rolcreaterole",
        "rolcreatedb", "relrowsecurity", "relforcerowsecurity",
        "has_table_privilege", "has_function_privilege",
        "frcaixinha_app_role", "frcaixinha_auth_role",
        "SET ROLE frcaixinha_app_role",
    ):
        assert value in SOURCE


def test_exposure_must_remain_no_go_not_secure():
    for value in (
        "EXPOSURE_REPRODUCED", "NOT_REMEDIATED",
        "M40630_SQL_ROLE_ACL_NOT_SESSION_ATTESTATION=CONFIRMED",
        "M40630_HTTP_AUTH_BYPASS=NOT_TESTED",
        "M40630_PRODUCTION=BLOCKED",
    ):
        assert value in SOURCE


def test_ci_uses_only_synthetic_postgres_and_no_live_provider():
    for value in (
        "postgres:18", "55433:5432", "fr_m39067_disposable_ci",
        "CI_M40630_DISPOSABLE: '1'", "CI_M40560_DISPOSABLE: '1'",
        "FRCAIXINHA_CI_ISOLATED: '1'", "PIX_REAL: 'OFF'",
        "PAGAMENTOS_REAIS: 'OFF'", "ATIVACAO_REAL: 'OFF'",
    ):
        assert value in WF
    assert "ssh " not in WF
    assert "pg_ctl" not in WF
    assert "kubectl" not in WF

def test_autocommit_guc_spoof_uses_session_scope_not_transaction_local():
    assert "set_config('app.current_role','MASTER',false)" in SOURCE
    assert "set_config('app.current_user_id',%s,false)" in SOURCE
    assert "set_config('app.current_role','MASTER',true)" not in SOURCE
