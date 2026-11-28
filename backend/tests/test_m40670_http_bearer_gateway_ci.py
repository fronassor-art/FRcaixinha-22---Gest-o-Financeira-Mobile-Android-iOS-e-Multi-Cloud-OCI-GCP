"""M40670: fail-closed offline checks for synthetic Bearer/SQL proof."""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "backend/tests/m40670_http_bearer_gateway_disposable.py"
WF = ROOT / ".github/workflows/frfinance-m40670-http-bearer-disposable-ci.yml"
SOURCE = RUNNER.read_text(encoding="utf-8")


def loaded():
    spec = importlib.util.spec_from_file_location("m40670", RUNNER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_without_ci_environment_denied_before_driver_import():
    proc = subprocess.run(
        [sys.executable, "-B", str(RUNNER)], capture_output=True,
        text=True, check=False, timeout=8,
        env={"PATH": os.environ.get("PATH", "")},
    )
    assert proc.returncode == 2
    assert "M40670_STATUS=BLOCKED_RuntimeError" in proc.stdout
    assert "M40670_ORIGINAL_PG_5433=NOT_ACCESSED" in proc.stdout


@pytest.mark.parametrize("dsn", (
    "postgresql://postgres:test@127.0.0.1:5433/fr_m40670_disposable_ci",
    "postgresql://postgres:test@127.0.0.1:55436/frcaixinha_aistudio_dev",
    "postgresql://postgres:test@localhost:55436/fr_m40670_disposable_ci",
    "postgresql://frc_ai_owner:test@127.0.0.1:55436/fr_m40670_disposable_ci",
    "postgresql://postgres:test@127.0.0.1:55436/fr_m40670_disposable_ci?sslmode=disable",
    "postgresql://postgres@127.0.0.1:55436/fr_m40670_disposable_ci",
))
def test_bad_disposable_identity_denied(monkeypatch, dsn):
    m = loaded()
    for key, value in {
        "GITHUB_ACTIONS": "true",
        "CI_M40670_DISPOSABLE": "1",
        "FRCAIXINHA_CI_ISOLATED": "1",
        "PIX_REAL": "OFF",
        "PAGAMENTOS_REAIS": "OFF",
        "ATIVACAO_REAL": "OFF",
        "CI_M40670_DATABASE_URL": dsn,
    }.items():
        monkeypatch.setenv(key, value)
    with pytest.raises(RuntimeError):
        m.require_disposable()


def test_boundary_is_synthetic_only_and_source_is_static():
    assert SOURCE.index("require_disposable()\n        # No DB driver") < SOURCE.index(
        "import psycopg\n        with psycopg.connect"
    )
    assert "DB = \"fr_m40670_disposable_ci\"" in SOURCE
    assert "PORT = 55436" in SOURCE
    assert "m40670/tenants/{tenant_id}/entries" in SOURCE
    assert "http_read_entries(%s,%s)" in SOURCE
    assert "LANGUAGE plpgsql SECURITY DEFINER" in SOURCE
    assert "SET search_path = pg_catalog, pg_temp" in SOURCE
    assert "REVOKE ALL ON FUNCTION m40650.http_read_entries(text,uuid) FROM PUBLIC" in SOURCE
    assert "GRANT EXECUTE ON FUNCTION m40650.http_read_entries(text,uuid) TO m40650_app" in SOURCE
    assert "JOIN m40650.memberships AS m" in SOURCE
    assert "JOIN m40650.users AS u" in SOURCE
    assert "s.active_tenant_id=p_tenant" in SOURCE
    assert "u.status='ACTIVE'" in SOURCE
    assert "m.status='ATIVA'" in SOURCE
    assert "s.revoked_at IS NULL" in SOURCE
    assert "s.active_role IN ('TENANT_MEMBER','TENANT_ADMIN')" in SOURCE


def test_auth_negative_cases_do_not_pretend_to_fix_old_rls():
    for required in (
        "X_Role=\"TENANT_ADMIN\"",
        'assert (await get(tokens["member"], tenant_b)).status_code == 401',
        'assert (await get(tokens["master"])).status_code == 401',
        'assert (await get(tokens["expired"])).status_code == 401',
        'assert (await get(tokens["revoked"])).status_code == 401',
        'assert (await get(None)).status_code == 401',
        "M40670_SQL_APP_DIRECT_READ_DENIED=PASS",
        "M40670_HTTP_REVOCATION_ACCOUNT_MEMBERSHIP=PASS",
        "M40670_BEARER_SQL_LOG_RISK=UNRESOLVED",
        "M40670_EXISTING_GUC_RISK=NOT_REMEDIATED",
        "M40670_REAL_FASTAPI_ROUTES=NOT_MODIFIED",
        "M40670_PRODUCTION=BLOCKED",
    ):
        assert required in SOURCE


def test_workflow_never_targets_real_bank_or_providers():
    wf = WF.read_text(encoding="utf-8")
    for required in (
        "postgres:18", "55436:5432", "fr_m40670_disposable_ci",
        "CI_M40670_DISPOSABLE: '1'",
        "FRCAIXINHA_CI_ISOLATED: '1'",
        "PIX_REAL: 'OFF'", "PAGAMENTOS_REAIS: 'OFF'",
        "ATIVACAO_REAL: 'OFF'",
        "backend/tests/m40670_http_bearer_gateway_disposable.py",
    ):
        assert required in wf
    assert "ssh " not in wf
    assert "pg_ctl" not in wf
    assert "kubectl" not in wf
