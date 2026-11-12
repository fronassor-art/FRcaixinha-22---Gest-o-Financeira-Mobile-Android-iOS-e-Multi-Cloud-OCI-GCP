"""M39020 — FastAPI RBAC / fail-closed contract, no original PostgreSQL.

Only TestClient with overridden dependencies; no credentials or external dispatch.
"""
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.dependencies import AuthenticatedSession
from backend.app.routers import special_credit as module

TENANT_A = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
TENANT_B = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
ROOT = "/api/v1/tenants/" + TENANT_A + "/special-credit"


def client(role: str, session_tenant: str | None) -> TestClient:
    app = FastAPI()
    app.include_router(module.router, prefix="/api/v1")
    session = AuthenticatedSession(
        str(uuid4()),role,session_tenant,"nobody@example.invalid",
        "Usuário de teste",role=="MASTER")
    app.dependency_overrides[module.get_current_session] = lambda: session
    # Dummy dependency asserts no original database will be touched.
    app.dependency_overrides[module.get_rls_db_connection] = lambda: None
    return TestClient(app)


@pytest.mark.parametrize("path", ["/members","/grants","/campaigns","/opportunities","/preferences"])
def test_master_cannot_read_tenant_credit(path):
    assert client("MASTER",None).get(ROOT+path).status_code==403


@pytest.mark.parametrize("path", ["/members","/grants","/campaigns","/opportunities","/preferences"])
def test_admin_other_tenant_is_blocked(path):
    assert client("TENANT_ADMIN",TENANT_B).get(ROOT+path).status_code==403


@pytest.mark.parametrize("path,payload", [
    ("/grants",{"member_ids":[str(uuid4())],"ceiling_brl":"5000.00",
                "expires_at":"2027-01-10T00:00:00+00:00",
                "reason":"Justificativa demonstrativa de risco.","request_id":str(uuid4())}),
    ("/campaigns",{"grant_ids":[str(uuid4())],"title":"Campanha",
                   "body":"Convite para simulação, sem aprovação real.",
                   "expires_at":"2027-01-10T00:00:00+00:00","request_id":str(uuid4())}),
])
def test_member_cannot_create_admin_credit(path,payload):
    assert client("TENANT_MEMBER",TENANT_A).post(ROOT+path,json=payload).status_code==403


def test_admin_cannot_write_when_sandbox_off(monkeypatch):
    monkeypatch.delenv("FR_FINANCE_SPECIAL_CREDIT_SANDBOX",raising=False)
    response=client("TENANT_ADMIN",TENANT_A).post(ROOT+"/grants",
        json={"member_ids":[str(uuid4())],"ceiling_brl":"5000.00",
              "expires_at":"2027-01-10T00:00:00+00:00",
              "reason":"Justificativa de risco acima de vinte caracteres.",
              "request_id":str(uuid4())})
    assert response.status_code==503


def test_amount_cannot_exceed_current_price_engine():
    response=client("TENANT_ADMIN",TENANT_A).post(ROOT+"/grants",
        json={"member_ids":[str(uuid4())],"ceiling_brl":"50000.01",
              "expires_at":"2027-01-10T00:00:00+00:00",
              "reason":"Justificativa demonstrativa de risco.",
              "request_id":str(uuid4())})
    assert response.status_code==422


def test_capabilities_never_claim_delivery_or_pix(monkeypatch):
    monkeypatch.delenv("FR_FINANCE_SPECIAL_CREDIT_SANDBOX",raising=False)
    data=client("TENANT_MEMBER",TENANT_A).get(ROOT+"/capabilities").json()
    assert data["sandbox_enabled"] is False
    assert data["pix_real_enabled"] is False
    assert data["real_credit_enabled"] is False
    assert data["grants_allow_request_only"] is True
    for channel in ("PUSH","EMAIL","WHATSAPP","SMS"):
        assert data["channels"][channel]["real_delivery_enabled"] is False


def test_route_map_has_no_bank_or_provider_dispatch():
    paths={r.path for r in module.router.routes}
    assert not any("disburse" in p or "payout" in p or "dispatch" in p for p in paths)
    assert not any("send" in p or "pix" in p for p in paths)


def test_environment_gate_requires_exclusive_local_pg18(monkeypatch):
    from types import SimpleNamespace
    monkeypatch.setattr(module,"settings",SimpleNamespace(
        DATABASE_URL="postgresql://frc_ai_app@127.0.0.1:5433/frcaixinha_aistudio_dev"))
    monkeypatch.setenv("FRCAIXINHA_TEST_AUTH","1")
    monkeypatch.setenv("FR_FINANCE_SPECIAL_CREDIT_SANDBOX","YES")
    monkeypatch.setenv("ENVIRONMENT","development")
    assert module._enabled() is True
    monkeypatch.setenv("ENVIRONMENT","production")
    assert module._enabled() is False
    monkeypatch.setenv("ENVIRONMENT","development")
    monkeypatch.setattr(module,"settings",SimpleNamespace(
        DATABASE_URL="postgresql://frc_ai_app@127.0.0.1:5432/another_db"))
    assert module._enabled() is False
