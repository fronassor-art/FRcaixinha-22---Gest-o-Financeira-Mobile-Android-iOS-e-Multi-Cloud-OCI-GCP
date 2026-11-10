"""M37465: CI-only HTTP policy -> atomic SQL adapter, adversarial offline tests."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime,timedelta,timezone
from pathlib import Path
from uuid import UUID
import pytest

from app.dependencies import AuthenticatedSession
from app.saas_acceptance_api_contract_ci import CIPrincipal,CIPublishedOffer
from app.saas_atomic_api_adapter_ci import (
    CIAtomicSQLExecutor,CIAtomicServerBinding,
    derive_server_binding_ci,evaluate_atomic_api_ci,ci_environment,
)

N=datetime(2026,11,10,17,0,tzinfo=timezone.utc)
S=UUID("daba0000-0000-4000-8000-000000000664")
A=UUID("daba0000-0000-4000-8000-000000000001")
T=UUID("daba0000-0000-4000-8000-000000000010")
C=UUID("daba0000-0000-4000-8000-000000000674")
R=UUID("daba0000-0000-4000-8000-000000000675")
D=UUID("daba0000-0000-4000-8000-000000000030")
P=UUID("daba0000-0000-4000-8000-000000000060")
X=UUID("daba0000-0000-4000-8000-000000000099")
BEARER="m37464-ci-only-lock-session-NEVER-REAL-01"
ENV=dict(GITHUB_ACTIONS="true",FRCAIXINHA_CI_ISOLATED="1",
         ENVIRONMENT="ci",FR_FINANCE_SAAS_REAL="OFF",
         FR_FINANCE_PIX_REAL="OFF")
STATES={"ISSUE":"CHALLENGE_ISSUED_CI",
        "ACCEPT":"CONSENT_RECORDED_CI_NO_LEGAL_PROOF",
        "PREPARE":"DRAFT_PREPARED_CI_NO_PAYMENT"}


def auth(**overrides):
    data=dict(
        user_id=str(A),role="TENANT_ADMIN",tenant_id=str(T),
        email="ci@example.invalid",name="CI",is_master=False,
        verified_session_id=str(S),
        verified_session_at=N-timedelta(seconds=5),
        verified_session_expires_at=N+timedelta(minutes=10),
        verification_source="POSTGRES_TOKEN_HASH_REFRESH",
    )
    data.update(overrides)
    return AuthenticatedSession(**data)


def binding(principal=None,token=BEARER,now=N):
    return derive_server_binding_ci(principal or auth(),token,now=now)


def offer(**overrides):
    data=dict(
        tenant_id=T,document_id=D,document_sha256="a"*64,
        price_version_id=P,billing_period="MONTHLY",price_cents=19937,
        published_at=N-timedelta(days=1),state="ACTIVE",
    )
    data.update(overrides)
    return CIPublishedOffer(**data)


def principal(**overrides):
    data=dict(
        user_id=A,tenant_id=T,session_id=S,
        active_role="TENANT_ADMIN",active=True,email_verified=True,
        server_checked_at=N-timedelta(seconds=5),
        expires_at=N+timedelta(minutes=10),
    )
    data.update(overrides)
    return CIPrincipal(**data)


class FakeConn:
    def __init__(self,meta=None,states=None):
        self.meta=meta if meta is not None else (
            "frcaixinha_staging","frcaixinha_saas_preprep_ci","off","1","1",5432)
        self.states=states or STATES
        self.calls=[]
        self.next_state=None

    def execute(self,sql,values=None):
        self.calls.append((sql,values))
        if "current_database()" in sql:
            self.next_state=self.meta
        else:
            assert sql.startswith("SELECT public.m37464_atomic_consent_ci(")
            assert values and len(values)==11
            self.next_state=(self.states[values[0]],)
        return self

    def fetchone(self):
        return self.next_state


def worker(*,connection=None,session=None,claim=None,off=None,env=None):
    c=connection or FakeConn()
    s=session or auth()
    b=claim if claim is not None else binding(s)
    o=off or offer()
    e=CIAtomicSQLExecutor(
        worker_conn=c,binding=b,authenticated_session=s,
        offer=o,env=env or ENV,now=N,
    )
    return e,c


def request_body(action):
    b=dict(action=action,request_id=str(R))
    if action!="ISSUE":
        b["challenge_id"]=str(C)
    if action=="ACCEPT":
        b["confirmation"]="ACEITO_CONTRATO_DE_LICENCA_FR_FINANCE"
    return b


def decision(executor,action="ISSUE",p=None,o=None,body=None,env=None):
    return evaluate_atomic_api_ci(
        body=body if body is not None else request_body(action),
        principal=p or principal(),offer=o or offer(),
        request_id_server=R,challenge_id_server=C,
        executor=executor,env=env or ENV,now=N,
    )


@pytest.mark.parametrize("action,expected",[
    ("ISSUE","CI_CHALLENGE_ISSUED_CI"),
    ("ACCEPT","CI_CONSENT_RECORDED_CI_NO_LEGAL_PROOF"),
    ("PREPARE","CI_DRAFT_PREPARED_CI_NO_PAYMENT"),
])
def test_http_contract_drives_atomic_token_scoped_db_function(action,expected):
    e,c=worker()
    result=decision(e,action)
    assert result.status_code==202 and result.state==expected
    assert result.hypothetical_consistency_only
    assert not any((
        result.real_identity_verified,result.legal_consent_verified,
        result.payment_authorized,result.license_authorized,
        result.pix_authorized,result.real_activation_authorized,
        result.production_authorized,result.real_writes_performed,
    ))
    calls=[x for x in c.calls if "m37464_atomic_consent_ci" in x[0]]
    assert len(calls)==1
    q=calls[0][1]
    assert q[0]==action and q[2]==S and q[3]==C and q[4]==R
    assert q[5]==T and q[6]==A and q[7]==D and q[8]==P
    assert q[9]=="MONTHLY"
    assert len(q[1])==64 and BEARER not in repr(c.calls)


def test_binding_is_derived_from_actual_server_verified_session():
    b=binding()
    assert b.verified_session_id==S
    assert b.administrator_id==A and b.tenant_id==T
    assert len(b.token_sha256)==64
    assert BEARER not in repr(b)


@pytest.mark.parametrize("field,value",[
    ("verification_source","CLIENT_ASSERTED"),
    ("verification_source","LEGACY_NO_SESSION_BINDING"),
    ("verified_session_id",str(X)),
    ("verified_session_id","not-a-uuid"),
    ("verified_session_id",None),
    ("user_id",str(X)),
    ("tenant_id",str(X)),
    ("is_master",True),
    ("role","MASTER"),
    ("role","TENANT_MEMBER"),
    ("verified_session_at",N-timedelta(minutes=6)),
    ("verified_session_at",N+timedelta(seconds=30)),
    ("verified_session_at",N.replace(tzinfo=None)),
    ("verified_session_expires_at",N-timedelta(seconds=1)),
    ("verified_session_expires_at",N.replace(tzinfo=None)),
])
def test_unverified_or_expired_principal_cannot_create_binding(field,value):
    assert derive_server_binding_ci(auth(**{field:value}),BEARER,now=N) is None


@pytest.mark.parametrize("bad",[
    "", "short", "has whitespace in bearer token", "x"*513,
    123,None,"ótimo","A"*23,
])
def test_malformed_raw_bearer_never_produces_server_digest(bad):
    assert derive_server_binding_ci(auth(),bad,now=N) is None


@pytest.mark.parametrize("change",[
    {"verified_session_id":X},
    {"administrator_id":X},
    {"tenant_id":X},
    {"verified_at":N+timedelta(seconds=1)},
    {"verified_at":N-timedelta(minutes=6)},
    {"expires_at":N-timedelta(minutes=1)},
    {"token_sha256":"A"*64},
    {"token_sha256":"bad"},
    {"source":"CLIENT_ASSERTED"},
])
def test_forged_or_stale_token_binding_denied(change):
    b=binding()
    assert b is not None
    with pytest.raises(ValueError):
        worker(claim=replace(b,**change))


@pytest.mark.parametrize("field,value",[
    ("role","MASTER"),
    ("is_master",True),
    ("tenant_id",str(X)),
    ("user_id",str(X)),
    ("verified_session_id",str(X)),
    ("verified_session_at",N-timedelta(minutes=6)),
    ("verified_session_expires_at",N+timedelta(minutes=11)),
])
def test_worker_rejects_auth_identity_after_binding(field,value):
    s=auth()
    b=binding(s)
    with pytest.raises(ValueError):
        worker(session=auth(**{field:value}),claim=b)


@pytest.mark.parametrize("change",[
    {"tenant_id":X},
    {"document_id":UUID(int=0)},
    {"price_version_id":UUID(int=0)},
    {"state":"REVOKED"},
    {"billing_period":"WEEKLY"},
    {"published_at":N+timedelta(days=1)},
    {"published_at":N.replace(tzinfo=None)},
    {"price_cents":0},
    {"price_cents":True},
    {"source":"CLIENT_SUBMITTED_OFFER"},
])
def test_constructor_rejects_forged_client_offer(change):
    with pytest.raises(ValueError):
        worker(off=offer(**change))


@pytest.mark.parametrize("meta",[
    ("frcaixinha_aistudio_dev","frcaixinha_saas_preprep_ci","off","1","1",5433),
    ("frcaixinha_staging","postgres","on","1","1",5432),
    ("frcaixinha_staging","frcaixinha_app_role","off","1","1",5432),
    ("frcaixinha_staging","frcaixinha_saas_preprep_ci","off","0","1",5432),
    ("frcaixinha_staging","frcaixinha_saas_preprep_ci","off","1","0",5432),
])
def test_wrong_db_or_role_fails_before_financial_sql(meta):
    c=FakeConn(meta=meta)
    with pytest.raises(ValueError):
        worker(connection=c)
    assert len(c.calls)==1


@pytest.mark.parametrize("changes",[
    {"GITHUB_ACTIONS":"false"},
    {"FRCAIXINHA_CI_ISOLATED":"0"},
    {"ENVIRONMENT":"production"},
    {"FR_FINANCE_SAAS_REAL":"ON"},
    {"FR_FINANCE_PIX_REAL":"ON"},
    {"FRCAIXINHA_TERMUX_LOCAL_API":"1"},
])
def test_feature_gates_cannot_turn_on_ci_adapter(changes):
    env={**ENV,**changes}
    assert not ci_environment(env)
    with pytest.raises(ValueError):
        worker(env=env)


@pytest.mark.parametrize("change",[
    {"user_id":X},
    {"tenant_id":X},
    {"session_id":X},
    {"active_role":"MASTER"},
    {"active":False},
    {"email_verified":False},
    {"source":"CLIENT_CLAIM"},
    {"server_checked_at":N-timedelta(minutes=6)},
    {"expires_at":N-timedelta(minutes=1)},
])
def test_transition_rejects_untrusted_principal_without_sql(change):
    w,c=worker()
    res=decision(w,p=principal(**change))
    assert res.status_code!=202
    assert not any("m37464_atomic_consent_ci" in x[0] for x in c.calls)


@pytest.mark.parametrize("change",[
    {"price_version_id":X},
    {"document_id":X},
    {"tenant_id":X},
    {"price_cents":123},
    {"billing_period":"ANNUAL"},
    {"source":"CLIENT"},
])
def test_transition_rejects_offer_substitution_without_sql(change):
    w,c=worker()
    res=decision(w,o=offer(**change))
    assert res.status_code!=202
    assert not any("m37464_atomic_consent_ci" in x[0] for x in c.calls)


def test_client_cannot_override_price_or_identity_fields():
    w,c=worker()
    b=request_body("ACCEPT")
    b.update(tenant_id=str(X),administrator_id=str(X),
             price_cents=1,legal_consent_verified=True)
    result=decision(w,"ACCEPT",body=b)
    assert result.status_code==400
    assert not any("m37464_atomic_consent_ci" in x[0] for x in c.calls)


def test_missing_executor_stays_503():
    result=decision(None)
    assert result.status_code==503
    assert not result.production_authorized


def test_denied_database_transition_is_not_positive_http_result():
    w,c=worker(connection=FakeConn(states={x:"DENIED_CI" for x in STATES}))
    result=decision(w)
    assert result.status_code==409
    assert not result.production_authorized


def test_server_does_not_persist_confirmation_in_token_binding():
    w,c=worker()
    result=decision(w,"ACCEPT")
    assert result.status_code==202
    assert "ACEITO_CONTRATO_DE_LICENCA_FR_FINANCE" not in repr(w._binding)


def test_sql_is_exact_stored_procedure_no_network_or_production_route():
    p=Path(__file__).resolve().parents[1]/"app"/"saas_atomic_api_adapter_ci.py"
    s=p.read_text()
    assert "public.m37464_atomic_consent_ci(" in s
    assert "get_current_session" not in s  # caller must authenticate first
    assert "APIRouter(" not in s and "include_router" not in s
    assert "INSERT INTO" not in s and "UPDATE public." not in s
    assert "requests.post(" not in s and "httpx.post(" not in s
    assert "production_authorized=True" not in s


def test_disposable_integration_script_uses_actual_get_current_session():
    root=Path(__file__).resolve().parents[2]
    s=(root/"backend/scripts/aistudio_m37464_atomic_consent_ci.py").read_text()
    for marker in (
        "get_current_session(request)",
        "derive_server_binding_ci(authenticated,TOKEN",
        "CIAtomicSQLExecutor(",
        "evaluate_atomic_api_ci(",
        "M37465_HTTP_CONTRACT_TO_ATOMIC_SQL=PASS",
        "M37465_NO_PRODUCTION_WRITES=PASS",
        "M37464_FINANCIAL_TABLES_UNCHANGED=PASS",
    ):
        assert marker in s
