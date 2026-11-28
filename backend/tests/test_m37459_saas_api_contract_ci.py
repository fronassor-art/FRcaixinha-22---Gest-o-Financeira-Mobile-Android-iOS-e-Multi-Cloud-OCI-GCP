"""M37459 API contract: never mount an unverified SaaS endpoint."""
from dataclasses import replace
from datetime import datetime, timezone, timedelta
from pathlib import Path
from uuid import UUID

import pytest

from app.saas_acceptance_api_contract_ci import (
    CIPrincipal,CIPublishedOffer,CITransition,
    evaluate_api_contract_ci,environment_allowed,
)

NOW=datetime(2026,11,10,16,0,tzinfo=timezone.utc)
T=UUID("daba0000-0000-4000-8000-000000000010")
A=UUID("daba0000-0000-4000-8000-000000000001")
S=UUID("daba0000-0000-4000-8000-000000000581")
C=UUID("daba0000-0000-4000-8000-000000000592")
R=UUID("daba0000-0000-4000-8000-000000000593")
D=UUID("daba0000-0000-4000-8000-000000000030")
P=UUID("daba0000-0000-4000-8000-000000000060")
OTHER=UUID("daba0000-0000-4000-8000-000000000099")
CONFIRM="ACEITO_CONTRATO_DE_LICENCA_FR_FINANCE"
ENV={"GITHUB_ACTIONS":"true","FRCAIXINHA_CI_ISOLATED":"1",
     "ENVIRONMENT":"ci","FR_FINANCE_SAAS_REAL":"OFF",
     "FR_FINANCE_PIX_REAL":"OFF"}


class FakeExecutor:
    def __init__(self,state="CHALLENGE_ISSUED_CI",raises=False):
        self.state=state
        self.raises=raises
        self.calls=[]
    def transition(self,**kwargs):
        self.calls.append(kwargs)
        if self.raises:
            raise RuntimeError("CI DB unavailable")
        return CITransition(self.state)


def principal():
    return CIPrincipal(
        user_id=A,tenant_id=T,session_id=S,active_role="TENANT_ADMIN",
        active=True,email_verified=True,
        server_checked_at=NOW-timedelta(minutes=1),
        expires_at=NOW+timedelta(minutes=30),
    )


def offer():
    return CIPublishedOffer(
        tenant_id=T,document_id=D,document_sha256="a"*64,
        price_version_id=P,billing_period="MONTHLY",price_cents=19937,
        published_at=NOW-timedelta(days=1),state="ACTIVE",
    )


def command(action="ISSUE"):
    basic={"action":action,"request_id":str(R)}
    if action in ("ACCEPT","PREPARE"):
        basic["challenge_id"]=str(C)
    if action=="ACCEPT":
        basic["confirmation"]=CONFIRM
    return basic


def evaluate(*,action="ISSUE",body=None,user=None,listed=None,
             executor=None,env=None,now=NOW,
             request_id_server=R,challenge_id_server=C):
    fake=executor if executor is not None else FakeExecutor({
        "ISSUE":"CHALLENGE_ISSUED_CI",
        "ACCEPT":"CONSENT_RECORDED_CI_NO_LEGAL_PROOF",
        "PREPARE":"DRAFT_PREPARED_CI_NO_PAYMENT",
    }.get(action,"DENIED_CI"))
    return evaluate_api_contract_ci(
        body=command(action) if body is None else body,
        principal=principal() if user is None else user,
        offer=offer() if listed is None else listed,
        request_id_server=request_id_server,
        challenge_id_server=challenge_id_server,
        executor=fake,
        env=ENV if env is None else env,
        now=now,
    )


def check_no_real_permissions(result):
    assert result.real_identity_verified is False
    assert result.legal_consent_verified is False
    assert result.payment_authorized is False
    assert result.license_authorized is False
    assert result.pix_authorized is False
    assert result.real_activation_authorized is False
    assert result.production_authorized is False
    assert result.real_writes_performed is False


@pytest.mark.parametrize("action,state",[
    ("ISSUE","CI_CHALLENGE_ISSUED_CI"),
    ("ACCEPT","CI_CONSENT_RECORDED_CI_NO_LEGAL_PROOF"),
    ("PREPARE","CI_DRAFT_PREPARED_CI_NO_PAYMENT"),
])
def test_valid_ci_contract_only_is_not_an_api_endpoint(action,state):
    fake=FakeExecutor(state[3:])
    result=evaluate(action=action,executor=fake)
    assert result.status_code==202
    assert result.state==state
    assert result.hypothetical_consistency_only is True
    assert len(fake.calls)==1
    args=fake.calls[0]
    assert args["principal"].user_id==A
    assert args["offer"].price_version_id==P
    assert args["challenge_id"]==C
    assert args["confirmation"]==(CONFIRM if action=="ACCEPT" else None)
    check_no_real_permissions(result)


@pytest.mark.parametrize("change",[
    {"GITHUB_ACTIONS":"false"},
    {"FRCAIXINHA_CI_ISOLATED":"0"},
    {"ENVIRONMENT":"production"},
    {"FR_FINANCE_SAAS_REAL":"ON"},
    {"FR_FINANCE_PIX_REAL":"ON"},
])
def test_never_enable_outside_exact_ci_contract(change):
    fake=FakeExecutor()
    result=evaluate(env={**ENV,**change},executor=fake)
    assert result.status_code==503
    assert result.state=="CI_CONTRACT_NOT_AVAILABLE"
    assert fake.calls==[]
    check_no_real_permissions(result)


def test_empty_environment_and_termux_blocked():
    assert not environment_allowed({})
    assert not environment_allowed({"ENVIRONMENT":"production"})
    assert evaluate(env={}).status_code==503


@pytest.mark.parametrize("action,payload,expected",[
    ("ISSUE",{"tenant_id":str(T)},"UNEXPECTED_OR_MISSING_CLIENT_FIELD"),
    ("ISSUE",{"user_id":str(A)},"UNEXPECTED_OR_MISSING_CLIENT_FIELD"),
    ("ISSUE",{"role":"TENANT_ADMIN"},"UNEXPECTED_OR_MISSING_CLIENT_FIELD"),
    ("ISSUE",{"price_cents":19937},"UNEXPECTED_OR_MISSING_CLIENT_FIELD"),
    ("ISSUE",{"document_sha256":"a"*64},"UNEXPECTED_OR_MISSING_CLIENT_FIELD"),
    ("ISSUE",{"session_active":True},"UNEXPECTED_OR_MISSING_CLIENT_FIELD"),
    ("ISSUE",{"challenge_id":str(C)},"UNEXPECTED_OR_MISSING_CLIENT_FIELD"),
    ("ISSUE",{"confirmation":CONFIRM},"UNEXPECTED_OR_MISSING_CLIENT_FIELD"),
    ("ACCEPT",{"tenant_id":str(T)},"UNEXPECTED_OR_MISSING_CLIENT_FIELD"),
    ("ACCEPT",{"payment_authorized":True},"UNEXPECTED_OR_MISSING_CLIENT_FIELD"),
    ("PREPARE",{"confirmation":CONFIRM},"UNEXPECTED_OR_MISSING_CLIENT_FIELD"),
    ("PREPARE",{"licence_authorized":True},"UNEXPECTED_OR_MISSING_CLIENT_FIELD"),
])
def test_never_trust_client_role_tenant_price_consent_metadata(action,payload,expected):
    fake=FakeExecutor()
    body=command(action)
    body.update(payload)
    result=evaluate(action=action,body=body,executor=fake)
    assert result.state==expected
    assert fake.calls==[]
    check_no_real_permissions(result)


@pytest.mark.parametrize("action,body",[
    ("ISSUE",{"action":"ISSUE"}),
    ("ISSUE",{"action":"ISSUE","request_id":"not-uuid"}),
    ("ISSUE",{"action":"ISSUE","request_id":str(UUID(int=0))}),
    ("ISSUE",{"action":"ISSUE","request_id":R}),
    ("ACCEPT",{"action":"ACCEPT","request_id":str(R)}),
    ("PREPARE",{"action":"PREPARE","request_id":str(R)}),
    ("ACCEPT",{"action":"ACCEPT","request_id":str(R),"challenge_id":str(OTHER),"confirmation":CONFIRM}),
    ("PREPARE",{"action":"PREPARE","request_id":str(R),"challenge_id":"bad"}),
])
def test_malformed_identifiers_and_schema_fail_closed(action,body):
    fake=FakeExecutor()
    result=evaluate(action=action,body=body,executor=fake)
    assert result.status_code in (400,403)
    assert fake.calls==[]
    check_no_real_permissions(result)


@pytest.mark.parametrize("value",["ACEITO","",None,False,1,{"text":CONFIRM}])
def test_consent_requires_exact_affirmative_text(value):
    fake=FakeExecutor()
    bad=command("ACCEPT")
    bad["confirmation"]=value
    out=evaluate(action="ACCEPT",body=bad,executor=fake)
    assert out.status_code==422
    assert fake.calls==[]
    check_no_real_permissions(out)


@pytest.mark.parametrize("diff,status",[
    ({"active_role":"MASTER"},403),
    ({"active_role":"TENANT_MEMBER"},403),
    ({"email_verified":False},403),
    ({"active":False},403),
    ({"active":1},403),
    ({"tenant_id":OTHER},403),
    ({"session_id":UUID(int=0)},403),
    ({"server_checked_at":NOW-timedelta(minutes=6)},401),
    ({"server_checked_at":NOW+timedelta(seconds=1)},401),
    ({"expires_at":NOW},401),
    ({"server_checked_at":NOW.replace(tzinfo=None)},403),
    ({"source":"CLIENT_SUPPLIED_ROLE"},403),
])
def test_admin_auth_readback_must_be_current_and_server_built(diff,status):
    fake=FakeExecutor()
    out=evaluate(user=replace(principal(),**diff),executor=fake)
    assert out.status_code==status
    assert fake.calls==[]
    check_no_real_permissions(out)


@pytest.mark.parametrize("diff",[
    {"tenant_id":OTHER},
    {"document_sha256":"invalid"},
    {"price_cents":0},
    {"price_cents":True},
    {"price_version_id":UUID(int=0)},
    {"published_at":NOW+timedelta(days=1)},
    {"billing_period":"WEEKLY"},
    {"state":"BLOCKED"},
    {"source":"BROWSER"},
])
def test_offer_is_not_accepted_from_client_or_inactive_catalog(diff):
    fake=FakeExecutor()
    out=evaluate(listed=replace(offer(),**diff),executor=fake)
    assert out.status_code in (403,409)
    assert fake.calls==[]
    check_no_real_permissions(out)


@pytest.mark.parametrize("action,answer",[
    ("ISSUE","DENIED_CI"),
    ("ISSUE","CHALLENGE_COLLISION_CI_DENIED"),
    ("ACCEPT","DENIED_CI"),
    ("ACCEPT","CONSENT_COLLISION_CI_DENIED"),
    ("PREPARE","CONSENT_BEFORE_PREPARATION_REQUIRED"),
    ("PREPARE","DRAFT_COLLISION_CI_DENIED"),
    ("PREPARE","ACTIVE_LICENSE"),
    ("ISSUE",""),
])
def test_fail_closed_db_denials_and_unexpected_state(action,answer):
    fake=FakeExecutor(answer)
    result=evaluate(action=action,executor=fake)
    assert result.status_code in (409,503)
    check_no_real_permissions(result)


def test_missing_or_broken_executor_never_authorizes():
    assert evaluate_api_contract_ci(
        body=command(),principal=principal(),offer=offer(),
        challenge_id_server=C,request_id_server=R,
        executor=None,env=ENV,now=NOW).status_code==503
    x=evaluate(executor=FakeExecutor(raises=True))
    assert x.state=="CI_EXECUTOR_FAILED_CLOSED"
    check_no_real_permissions(x)


def test_wrong_challenge_or_request_fail_without_executor_call():
    f=FakeExecutor()
    assert evaluate(challenge_id_server=OTHER,executor=f).status_code==202  # server-generated ISSUE
    assert evaluate(request_id_server=OTHER,executor=f).status_code==403
    assert evaluate(action="ACCEPT",challenge_id_server=OTHER,executor=f).status_code==403


def test_no_backend_route_is_registered_or_imported():
    root=Path(__file__).resolve().parents[2]
    source=(root/"backend/app/saas_acceptance_api_contract_ci.py").read_text()
    main=(root/"backend/app/main.py").read_text()
    assert "APIRouter" not in source
    assert "include_router" not in source
    assert "saas_acceptance_api_contract_ci" not in main
    for bad in ("import psycopg","import asyncpg","import httpx",
                "INSERT INTO ","UPDATE public.","DELETE FROM "):
        assert bad not in source
