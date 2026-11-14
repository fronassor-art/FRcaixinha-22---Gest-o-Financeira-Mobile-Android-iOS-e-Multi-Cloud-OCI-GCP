"""M37460: HTTP tests for isolated SaaS contract acceptance boundary.

Tests override dependencies only in an isolated FastAPI test client. They do
not represent real authentication, legal consent or operational onboarding.
"""
from dataclasses import replace
from datetime import datetime, timezone, timedelta
from pathlib import Path
from uuid import UUID
import os

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from app.dependencies import AuthenticatedSession, get_current_session
from app.routers.saas_authenticated_contract_ci import (
    CITrustedServerContext, ci_endpoint_allowed,
    get_ci_trusted_server_context, get_ci_disposable_executor,
    check_server_identity_binding, router,
)
from app.saas_acceptance_api_contract_ci import (
    CIPublishedOffer, CITransition,
)

NOW=datetime.now(timezone.utc)
T=UUID("daba0000-0000-4000-8000-000000000010")
A=UUID("daba0000-0000-4000-8000-000000000001")
S=UUID("daba0000-0000-4000-8000-000000000581")
C=UUID("daba0000-0000-4000-8000-000000000596")
R=UUID("daba0000-0000-4000-8000-000000000597")
D=UUID("daba0000-0000-4000-8000-000000000030")
P=UUID("daba0000-0000-4000-8000-000000000060")
OTHER=UUID("daba0000-0000-4000-8000-000000000099")
CONFIRM="ACEITO_CONTRATO_DE_LICENCA_FR_FINANCE"
ENV={
    "GITHUB_ACTIONS":"true",
    "FRCAIXINHA_CI_ISOLATED":"1",
    "ENVIRONMENT":"ci",
    "FR_FINANCE_SAAS_REAL":"OFF",
    "FR_FINANCE_PIX_REAL":"OFF",
    "FR_FINANCE_M37460_ROUTE":"CI_DISPOSABLE_ONLY",
}


def session(*,role="TENANT_ADMIN",tenant=T,user=A,is_master=False):
    return AuthenticatedSession(
        user_id=str(user),role=role,
        tenant_id=str(tenant) if tenant is not None else None,
        email="ci-admin@example.invalid",name="CI only",is_master=is_master,
        verified_session_id=str(S),
        verified_session_at=datetime.now(timezone.utc)-timedelta(seconds=10),
        verified_session_expires_at=datetime.now(timezone.utc)+timedelta(minutes=60),
        verification_source="POSTGRES_TOKEN_HASH_REFRESH",
    )


def context():
    return CITrustedServerContext(
        tenant_id=T,administrator_id=A,session_id=S,
        session_role="TENANT_ADMIN",session_active=True,
        email_verified=True,
        session_checked_at=datetime.now(timezone.utc)-timedelta(seconds=5),
        session_expires_at=datetime.now(timezone.utc)+timedelta(minutes=15),
        request_id=R,challenge_id=C,
        offer=CIPublishedOffer(
            tenant_id=T,document_id=D,document_sha256="a"*64,
            price_version_id=P,billing_period="MONTHLY",
            price_cents=19937,published_at=NOW-timedelta(days=1),
            state="ACTIVE",
        ),
    )


class FakeExecutor:
    def __init__(self,response="CHALLENGE_ISSUED_CI"):
        self.response=response
        self.called=[]
    def transition(self,**kwargs):
        self.called.append(kwargs)
        return CITransition(self.response)


def payload(action="ISSUE"):
    x={"action":action,"request_id":str(R)}
    if action!="ISSUE":
        x["challenge_id"]=str(C)
    if action=="ACCEPT":
        x["confirmation"]=CONFIRM
    return x


@pytest.fixture
def test_client(monkeypatch):
    for k,v in ENV.items():
        monkeypatch.setenv(k,v)
    monkeypatch.delenv("FRCAIXINHA_TERMUX_LOCAL_API",raising=False)
    app=FastAPI()
    app.include_router(router,prefix="/api/v1")
    fake=FakeExecutor()
    app.dependency_overrides[get_current_session]=lambda:session()
    app.dependency_overrides[get_ci_trusted_server_context]=lambda:context()
    app.dependency_overrides[get_ci_disposable_executor]=lambda:fake
    with TestClient(app) as client:
        yield client,app,fake


def no_real(result):
    assert result["ci_only"] is True
    for key in (
        "real_identity_verified","legal_consent_verified",
        "payment_authorized","license_authorized","pix_authorized",
        "activation_authorized","production_authorized",
    ):
        assert result[key] is False


@pytest.mark.parametrize("action,expected",[
    ("ISSUE","CI_CHALLENGE_ISSUED_CI"),
    ("ACCEPT","CI_CHALLENGE_ISSUED_CI"),
    ("PREPARE","CI_CHALLENGE_ISSUED_CI"),
])
def test_http_contract_route_synthetic_success(test_client,action,expected):
    client,app,fake=test_client
    res=client.post("/api/v1/saas/ci-contract/transition",json=payload(action))
    assert res.status_code in (202,503)
    # Only an action-consistent CI state may return 202.
    if action=="ISSUE":
        assert res.status_code==202
        assert res.json()["state"]==expected
    else:
        assert res.status_code==503
    no_real(res.json())
    assert res.headers["cache-control"]=="no-store"


@pytest.mark.parametrize("role,tenant,user,is_master",[
    ("MASTER",None,A,True),
    ("TENANT_MEMBER",T,A,False),
    ("TENANT_ADMIN",OTHER,A,False),
    ("TENANT_ADMIN",T,OTHER,False),
    ("TENANT_ADMIN",T,A,True),
    ("OTHER",T,A,False),
])
def test_http_role_tenant_user_and_master_segregated(test_client,role,tenant,user,is_master):
    client,app,fake=test_client
    app.dependency_overrides[get_current_session]=lambda:session(
        role=role,tenant=tenant,user=user,is_master=is_master)
    res=client.post("/api/v1/saas/ci-contract/transition",json=payload())
    assert res.status_code==403
    assert fake.called==[]


@pytest.mark.parametrize("change",[
    {"source":"USER_INPUT"},
    {"session_active":False},
    {"email_verified":False},
    {"session_role":"MASTER"},
    {"tenant_id":OTHER},
    {"administrator_id":OTHER},
    {"session_id":UUID(int=0)},
    {"session_checked_at":NOW-timedelta(minutes=6)},
    {"session_checked_at":NOW+timedelta(minutes=1)},
    {"session_expires_at":NOW-timedelta(minutes=1)},
])
def test_http_server_context_cannot_override_credential_scope(test_client,change):
    client,app,fake=test_client
    app.dependency_overrides[get_ci_trusted_server_context]=lambda:replace(
        context(),**change)
    res=client.post("/api/v1/saas/ci-contract/transition",json=payload())
    assert res.status_code==403
    assert fake.called==[]


@pytest.mark.parametrize("change",[
    {"GITHUB_ACTIONS":"false"},
    {"FRCAIXINHA_CI_ISOLATED":"0"},
    {"ENVIRONMENT":"production"},
    {"FR_FINANCE_SAAS_REAL":"ON"},
    {"FR_FINANCE_PIX_REAL":"ON"},
    {"FR_FINANCE_M37460_ROUTE":"TRUE"},
    {"FRCAIXINHA_TERMUX_LOCAL_API":"1"},
])
def test_http_endpoint_fail_closed_outside_ci(test_client,change,monkeypatch):
    client,app,fake=test_client
    for k,v in change.items():
        monkeypatch.setenv(k,v)
    res=client.post("/api/v1/saas/ci-contract/transition",json=payload())
    assert res.status_code==404
    assert fake.called==[]


@pytest.mark.parametrize("bad",[
    {"action":"ISSUE","request_id":str(R),"role":"TENANT_ADMIN"},
    {"action":"ISSUE","request_id":str(R),"tenant_id":str(T)},
    {"action":"ISSUE","request_id":str(R),"price_cents":19937},
    {"action":"ISSUE","request_id":str(R),"document_sha256":"a"*64},
    {"action":"ISSUE","request_id":str(OTHER)},
    {"action":"ACCEPT","request_id":str(R),"challenge_id":str(C),
     "confirmation":"ACEITO"},
    {"action":"PREPARE","request_id":str(R)},
])
def test_http_rejects_client_claims_and_malformed_payload(test_client,bad):
    client,app,fake=test_client
    res=client.post("/api/v1/saas/ci-contract/transition",json=bad)
    assert res.status_code in (400,403,422)
    no_real(res.json())
    assert fake.called==[]


def test_content_type_size_and_json_schema_fail_closed(test_client):
    client,app,fake=test_client
    path="/api/v1/saas/ci-contract/transition"
    for content_type,body,expected in (
        ("text/plain",'{"action":"ISSUE"}',415),
        ("application/json","",413),
        ("application/json","x"*2050,413),
        ("application/json","not-json",400),
    ):
        x=client.post(path,content=body,headers={"content-type":content_type})
        assert x.status_code==expected
    assert fake.called==[]


def test_no_dependency_override_is_inert_even_in_ci(test_client):
    client,app,fake=test_client
    app.dependency_overrides.pop(get_ci_trusted_server_context)
    app.dependency_overrides.pop(get_ci_disposable_executor)
    res=client.post("/api/v1/saas/ci-contract/transition",json=payload())
    assert res.status_code==503
    assert fake.called==[]


def test_real_get_current_session_is_required_without_override(test_client):
    client,app,fake=test_client
    app.dependency_overrides.pop(get_current_session)
    res=client.post("/api/v1/saas/ci-contract/transition",json=payload())
    assert res.status_code==401
    assert fake.called==[]


def test_server_binding_is_pure_and_cannot_attest_real_identity():
    principal=check_server_identity_binding(session(),context(),now=datetime.now(timezone.utc))
    assert principal is not None
    assert principal.source=="CI_SYNTHETIC_SERVER_AUTH_READBACK"
    assert principal.user_id==A and principal.tenant_id==T
    assert principal.session_id==S


def test_main_never_mounts_ci_route_by_default():
    root=Path(__file__).resolve().parents[2]
    main=(root/"backend/app/main.py").read_text()
    module=(root/"backend/app/routers/saas_authenticated_contract_ci.py").read_text()
    assert "if _saas_authenticated_contract_ci.ci_endpoint_allowed(os.environ)" in main
    assert 'app.include_router(_saas_authenticated_contract_ci.router' in main
    assert "Depends(get_current_session)" in module
    assert "CI_DISPOSABLE_ONLY" in module
    assert "get_ci_disposable_executor()" in module
    assert "get_ci_trusted_server_context()" in module
    assert "raise HTTPException(503" in module
    assert "Cache-Control" in module
    assert "real_identity_verified" in module
    assert "saas_payment_intents" not in module
    assert "saas_license_entitlements" not in module
    assert not ci_endpoint_allowed({})
    assert ci_endpoint_allowed(ENV)


def test_non_ci_real_main_routes_are_absent():
    from app.main import app as main_app
    endpoints={getattr(route,"path",None) for route in main_app.routes}
    assert "/api/v1/saas/ci-contract/transition" not in endpoints
