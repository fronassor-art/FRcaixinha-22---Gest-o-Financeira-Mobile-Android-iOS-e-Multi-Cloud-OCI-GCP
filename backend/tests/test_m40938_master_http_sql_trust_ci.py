"""M40938: real FastAPI HTTP route, fake sessions, zero original database I/O.

Do not override require_master or the M40930 write guard: exercise actual
FastAPI RBAC graph for Master, admin, member and inconsistent Master claims.
The ONLY override is the upstream token lookup to supply synthetic sessions.
This does not attest real bearer, runtime SQL roles or provider deployment.
"""
from __future__ import annotations

import os
from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.dependencies import AuthenticatedSession, get_current_session
from app.m40840_financial_sql_release_no_go import (
    FinancialSQLReleaseBlocked, require_nonproduction_financial_sql,
)

PATH = "/api/v1/master/launch-readiness"
MUTATION = "/api/v1/master/license-prices"


def fake_session(role: str, *, is_master: bool, tenant_id: str | None = None):
    return AuthenticatedSession(
        str(uuid4()),role,tenant_id,"ci-only@example.invalid",
        "CI synthetic actor",is_master,
    )


def _request(session, method: str, path: str, *, json=None):
    assert get_current_session not in app.dependency_overrides
    app.dependency_overrides[get_current_session] = lambda: session
    try:
        # If this endpoint ever attempts to touch SQL, the CI must fail. It
        # cannot "pass" with real PostgreSQL or auth credentials.
        with (
            patch.dict(os.environ,{
                "ENVIRONMENT":"ci",
                "FR_FINANCE_ACCESS_MAIL_ENABLE":"OFF",
                "FR_FINANCE_ACCESS_MAIL_WORKER":"OFF",
                "AUTH_SECRET":"M40938_NO_LEAK_PRIVATE",
                "DATABASE_URL":"postgresql://fakeuser:FAKE_ONLY_NO_IO@never.invalid:5432/fake_db",
                "PIX_REAL":"OFF",
                "PAGAMENTOS_REAIS":"OFF",
                "ATIVACAO_REAL":"OFF",
            },clear=True),
            patch("asyncpg.connect",side_effect=AssertionError("M40938_DB_ACCESS_FORBIDDEN")),
            patch("app.database.get_db_pool",side_effect=AssertionError("M40938_POOL_ACCESS_FORBIDDEN")),
        ):
            with TestClient(app) as client:
                return client.request(method,path,json=json)
    finally:
        app.dependency_overrides.pop(get_current_session,None)


def test_master_http_report_is_real_rbac_and_fail_closed():
    result = _request(fake_session("MASTER",is_master=True),"GET",PATH)
    assert result.status_code==200,result.text
    report = result.json()
    assert report["mode"]=="READ_ONLY_NO_ACTIVATION"
    assert report["status"]=="BLOCKED"
    assert report["unverified_gates"]==report["total_gates"]==20
    assert report["sql_trust"]["status"]=="NO_GO"
    assert report["sql_trust"]["evidence"]=="SOURCE_ONLY_NOT_RUNTIME_ATTESTED"
    assert report["sql_trust"]["master_write_operations_enabled"] is False
    assert {"M40570","M40730","M40936"} == {
        row["code"] for row in report["sql_trust"]["blockers"]
    }
    assert report["writes_performed"] is False
    assert report["real_pix_active"] is False
    assert "FAKE_ONLY_NO_IO" not in result.text
    assert "M40938_NO_LEAK_PRIVATE" not in result.text
    assert "never.invalid" not in result.text
    assert result.headers.get("cache-control")=="no-store"


@pytest.mark.parametrize("role,is_master,tenant",[
    ("TENANT_ADMIN",False,True),
    ("TENANT_MEMBER",False,True),
    ("MASTER",False,False),
    ("MASTER",True,True),
])
def test_master_http_report_denied_for_inconsistent_or_non_master_session(
    role,is_master,tenant
):
    session=fake_session(
        role,is_master=is_master,
        tenant_id=str(uuid4()) if tenant else None,
    )
    result=_request(session,"GET",PATH)
    assert result.status_code==403,result.text
    assert "sql_trust" not in result.text


def test_commercial_master_mutation_remains_unconditionally_denied():
    # Real dependency require_unreleased_master_write is NOT overridden.
    result=_request(
        fake_session("MASTER",is_master=True),"POST",MUTATION,
        json={
            "tier":"ESSENCIAL",
            "monthly_price":"90.00",
            "annual_price":"780.00",
            "expected_version_id":str(uuid4()),
            "reason":"CI 40938 only no server financial write",
        },
    )
    assert result.status_code==503,result.text
    assert "Gravacoes Master indisponiveis" in result.text


def test_sql_production_guard_still_denies_everything():
    with pytest.raises(FinancialSQLReleaseBlocked):
        require_nonproduction_financial_sql({
            "ENVIRONMENT":"production",
            "PIX_REAL":"OFF",
            "PAGAMENTOS_REAIS":"OFF",
            "ATIVACAO_REAL":"OFF",
        })
