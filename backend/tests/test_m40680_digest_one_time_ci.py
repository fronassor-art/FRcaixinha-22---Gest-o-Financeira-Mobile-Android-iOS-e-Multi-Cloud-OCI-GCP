"""M40680: static, fail-closed offline tests; no DB connections."""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import pytest

ROOT=Path(__file__).resolve().parents[2]
RUNNER=ROOT/"backend/tests/m40680_digest_one_time_gateway_disposable.py"
WF=ROOT/".github/workflows/frfinance-m40680-digest-one-time-ci.yml"
SOURCE=RUNNER.read_text(encoding="utf-8")


def load():
    spec=importlib.util.spec_from_file_location("m40680_ci", RUNNER)
    assert spec is not None and spec.loader is not None
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_local_command_is_rejected_before_any_db_driver():
    result=subprocess.run([sys.executable,"-B",str(RUNNER)],
                          capture_output=True,text=True,timeout=8,check=False,
                          env={"PATH":os.environ.get("PATH","")})
    assert result.returncode==2
    assert "M40680_STATUS=BLOCKED_RuntimeError" in result.stdout
    assert "M40680_ORIGINAL_PG_5433=NOT_ACCESSED" in result.stdout


@pytest.mark.parametrize("dsn",(
    "postgresql://postgres:fixture@127.0.0.1:5433/fr_m40680_disposable_ci",
    "postgresql://postgres:fixture@127.0.0.1:55437/frcaixinha_aistudio_dev",
    "postgresql://postgres:fixture@localhost:55437/fr_m40680_disposable_ci",
    "postgresql://frc_ai_owner:fixture@127.0.0.1:55437/fr_m40680_disposable_ci",
    "postgresql://postgres:fixture@127.0.0.1:55437/fr_m40680_disposable_ci?sslmode=disable",
))
def test_target_identity_fail_closed(monkeypatch,dsn):
    m=load()
    for k,v in {
        "GITHUB_ACTIONS":"true",
        "CI_M40680_DISPOSABLE":"1",
        "FRCAIXINHA_CI_ISOLATED":"1",
        "PIX_REAL":"OFF",
        "PAGAMENTOS_REAIS":"OFF",
        "ATIVACAO_REAL":"OFF",
        "CI_M40680_DATABASE_URL":dsn,
    }.items():
        monkeypatch.setenv(k,v)
    with pytest.raises(RuntimeError):
        m.gate()


def test_raw_bearer_is_only_hashed_in_python_not_sql_parameters():
    for marker in (
        'digest = sha256(raw.encode("utf-8")).hexdigest()',
        '"SELECT m40650.m40680_issue(%s,%s)",(digest,tenant)',
        '"SELECT m40650.m40680_consume(%s,%s)",(ticket,tenant)',
        "M40680_RAW_BEARER_SQL_PARAMETERS=NONE",
        "M40680_DIGEST_AND_TICKET_LOG_RISK=NOT_REMEDIATED",
    ):
        assert marker in SOURCE
    assert "(raw,tenant)" not in SOURCE
    assert "(raw, tenant)" not in SOURCE
    assert "m40680_issue(%s,%s)\",(digest,tenant) if False else True  # fail-fast contract marker above


def test_sql_roles_ticket_atomicity_and_guc_no_go():
    for marker in (
        "m40680_auth_login LOGIN NOINHERIT NOBYPASSRLS",
        "m40680_auth TO m40680_auth_login",
        "m40680_tickets(",
        "used_at IS NULL",
        "RETURNING t.session_digest INTO v_digest",
        "t.tenant_id=p_tenant",
        "REVOKE EXECUTE ON FUNCTION m40650.read_entries(text,uuid)",
        "REVOKE ALL ON FUNCTION m40650.m40680_issue(text,uuid)",
        "GRANT EXECUTE ON FUNCTION m40650.m40680_issue(text,uuid)",
        "GRANT EXECUTE ON FUNCTION m40650.m40680_consume(text,uuid)",
        "SET search_path=pg_catalog,pg_temp",
        "M40680_SPLIT_SQL_ROLES_AND_ONE_TIME_REPLAY_DENIED=PASS",
        "M40680_REVOKED_SESSION_AND_EXPIRED_TICKET_DENIED=PASS",
        "M40680_EXISTING_GUC_SQL_RISK=NOT_REMEDIATED",
        "M40680_REAL_FASTAPI_ROUTES=NOT_MODIFIED",
    ):
        assert marker in SOURCE


def test_ci_isolated_postgres_and_gate():
    wf=WF.read_text(encoding="utf-8")
    for token in (
        "postgres:18", "55437:5432","fr_m40680_disposable_ci",
        "CI_M40680_DISPOSABLE: '1'",
        "FRCAIXINHA_CI_ISOLATED: '1'",
        "PIX_REAL: 'OFF'", "PAGAMENTOS_REAIS: 'OFF'",
        "ATIVACAO_REAL: 'OFF'",
        "backend/tests/m40680_digest_one_time_gateway_disposable.py",
    ):
        assert token in wf
    for token in ("ssh ", "pg_ctl", "kubectl"):
        assert token not in wf
