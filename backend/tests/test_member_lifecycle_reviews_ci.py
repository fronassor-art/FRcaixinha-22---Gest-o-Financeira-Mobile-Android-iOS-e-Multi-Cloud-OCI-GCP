"""M1081–M1240: revisão documental em sandbox, RBAC e histórico sem efeitos."""
from datetime import datetime, timezone
from uuid import UUID
import asyncpg
import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.dependencies import AuthenticatedSession
from app.routers.member_lifecycle_reviews import (
    ReviewEventPayload, lifecycle_review_capabilities,
    list_member_review_events, submit_member_review_event_sandbox,
)

T=UUID(int=31001)
B=UUID(int=31002)
C=UUID(int=31003)
Q=UUID(int=31004)
M=UUID(int=31005)
U=UUID(int=31006)
EV=UUID(int=31007)
NOW=datetime(2027,6,12,12,tzinfo=timezone.utc)
KINDS=(
 "ADMIN_DOCUMENTS_REQUESTED",
 "ADMIN_REVIEW_ACCEPTED_SANDBOX",
 "ADMIN_REVIEW_REJECTED_SANDBOX",
 "MEMBER_CONTESTED",
)

def actor(role="TENANT_ADMIN",tenant=T):
    return AuthenticatedSession(str(U),role,
       str(tenant) if tenant else None,"ci@example.invalid",
       "Pessoa de Testes",role=="MASTER")

def body(kind="ADMIN_DOCUMENTS_REQUESTED",idempotency=EV):
    return ReviewEventPayload(idempotency_key=idempotency,
        event_kind=kind,evidence_reference="CI-EVIDENCE-REVIEW-2027")

def event(kind="ADMIN_DOCUMENTS_REQUESTED",seq=1):
    return dict(
      event_id=EV,event_seq=seq,tenant_id=T,request_id=Q,
      membership_id=M,actor_user_id=U,event_kind=kind,
      evidence_reference="CI-EVIDENCE-REVIEW-2027",recorded_at=NOW,
    )

class FakeReviewDB:
    def __init__(self,rows=None,ready=True):
        self.rows=[] if rows is None else rows
        self.ready=ready
        self.calls=[]
    async def fetchrow(self,sql,*params):
        self.calls.append(("fetchrow",sql,params))
        if "FROM public.cycles" in sql:
            return {"id":C,"status":"ABERTO"}
        if "FROM public.member_lifecycle_requests" in sql:
            return {"id":Q,"tenant_id":T,"cycle_id":C,
                    "membership_id":M,"request_kind":"DELINQUENCY_REVIEW"}
        if "FROM public.member_lifecycle_review_events" in sql:
            return event()
        raise AssertionError(sql)
    async def fetch(self,sql,*params):
        self.calls.append(("fetch",sql,params))
        assert "FROM public.member_lifecycle_review_events" in sql
        return self.rows
    async def fetchval(self,sql,*params):
        self.calls.append(("fetchval",sql,params))
        if "to_regclass" in sql:
            return self.ready
        assert "lifecycle_append_review_event_sandbox" in sql
        assert params[0]==T and params[1]==Q
        return EV
    async def execute(self,*args):
        raise AssertionError("Não é permitido gravar eventos por SQL comum")

@pytest.mark.asyncio
async def test_read_events_is_audited_no_financial_rights():
    db=FakeReviewDB([event("ADMIN_DOCUMENTS_REQUESTED",1),
                     event("MEMBER_CONTESTED",2)])
    result=await list_member_review_events(
        T,2027,Q,actor(),db,
    )
    assert len(result.items)==2
    assert result.latest_event_kind=="MEMBER_CONTESTED"
    assert result.pending_technical_review
    assert result.request_kind=="DELINQUENCY_REVIEW"
    assert not result.financial_effect_applied
    assert not result.closing_authorized
    assert not result.payout_authorized
    assert not result.membership_status_changed
    assert all(not x.financial_effect_applied and not x.bank_reconciled
               for x in result.items)

@pytest.mark.asyncio
@pytest.mark.parametrize("kind,pending",[
    (None,True),
    ("ADMIN_DOCUMENTS_REQUESTED",True),
    ("MEMBER_CONTESTED",True),
    ("ADMIN_REVIEW_ACCEPTED_SANDBOX",False),
    ("ADMIN_REVIEW_REJECTED_SANDBOX",False),
])
async def test_review_state_derived_from_latest_event(kind,pending):
    db=FakeReviewDB([] if kind is None else [event(kind)])
    r=await list_member_review_events(T,2027,Q,actor(),db)
    assert r.pending_technical_review==pending
    assert r.latest_event_kind==kind
    assert not r.financial_effect_applied
    assert not r.payout_authorized

@pytest.mark.asyncio
async def test_master_and_cross_tenant_rejected_before_sql():
    for bad in (actor("MASTER",None),actor("TENANT_ADMIN",B),
                actor("TENANT_MEMBER",B)):
        db=FakeReviewDB()
        with pytest.raises(HTTPException) as err:
            await list_member_review_events(T,2027,Q,bad,db)
        assert err.value.status_code==403
        assert db.calls==[]

@pytest.mark.asyncio
async def test_missing_request_is_404_without_leaking_other_tenant_data():
    class NoRequest(FakeReviewDB):
        async def fetchrow(self,sql,*params):
            if "FROM public.member_lifecycle_requests" in sql:
                return None
            return await super().fetchrow(sql,*params)
    with pytest.raises(HTTPException) as exc:
        await list_member_review_events(T,2027,Q,actor(),NoRequest())
    assert exc.value.status_code==404

@pytest.mark.asyncio
async def test_unmigrated_029_returns_503_for_history():
    class Missing(FakeReviewDB):
        async def fetch(self,sql,*params):
            raise asyncpg.UndefinedTableError("relation missing")
    with pytest.raises(HTTPException) as exc:
        await list_member_review_events(T,2027,Q,actor(),Missing())
    assert exc.value.status_code==503
    assert "029" in str(exc.value.detail)

@pytest.mark.asyncio
async def test_more_than_100_events_are_not_truncated_to_false_complete():
    with pytest.raises(HTTPException) as err:
        await list_member_review_events(
            T,2027,Q,actor(),FakeReviewDB([event() for _ in range(101)])
        )
    assert err.value.status_code==503

@pytest.mark.asyncio
async def test_sandbox_write_is_disabled_by_default(monkeypatch):
    monkeypatch.delenv("FRCAIXINHA_LIFECYCLE_SANDBOX",raising=False)
    db=FakeReviewDB()
    with pytest.raises(HTTPException) as err:
        await submit_member_review_event_sandbox(
            T,2027,Q,body(),actor(),db
        )
    assert err.value.status_code==503
    assert db.calls==[]

@pytest.mark.asyncio
async def test_sandbox_write_disabled_in_production_even_if_flag_set(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT","production")
    monkeypatch.setenv("FRCAIXINHA_LIFECYCLE_SANDBOX","1")
    db=FakeReviewDB()
    with pytest.raises(HTTPException) as exc:
        await submit_member_review_event_sandbox(
            T,2027,Q,body(),actor(),db)
    assert exc.value.status_code==503
    assert db.calls==[]

@pytest.mark.asyncio
@pytest.mark.parametrize("kind",KINDS)
async def test_review_kind_enforced_by_actor_role(monkeypatch,kind):
    monkeypatch.setenv("ENVIRONMENT","development")
    monkeypatch.setenv("FRCAIXINHA_LIFECYCLE_SANDBOX","1")
    for role in ("TENANT_ADMIN","TENANT_MEMBER"):
        expected=role=="TENANT_MEMBER" if kind=="MEMBER_CONTESTED" else role=="TENANT_ADMIN"
        db=FakeReviewDB()
        if expected:
            r=await submit_member_review_event_sandbox(
                T,2027,Q,body(kind),actor(role),db)
            assert r.event_id==str(EV)
            assert r.event_kind=="ADMIN_DOCUMENTS_REQUESTED" # fake mock response
            assert not r.financial_effect_applied
        else:
            with pytest.raises(HTTPException) as exc:
                await submit_member_review_event_sandbox(
                    T,2027,Q,body(kind),actor(role),db)
            assert exc.value.status_code==403

@pytest.mark.asyncio
async def test_missing_sql_function_returns_503(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT","development")
    monkeypatch.setenv("FRCAIXINHA_LIFECYCLE_SANDBOX","1")
    class Missing(FakeReviewDB):
        async def fetchval(self,sql,*params):
            raise asyncpg.UndefinedFunctionError("missing")
    with pytest.raises(HTTPException) as exc:
        await submit_member_review_event_sandbox(
            T,2027,Q,body(),actor(),Missing()
        )
    assert exc.value.status_code==503

@pytest.mark.asyncio
async def test_conflicting_decision_returns_409(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT","homologation")
    monkeypatch.setenv("FRCAIXINHA_LIFECYCLE_SANDBOX","1")
    class Conflict(FakeReviewDB):
        async def fetchval(self,sql,*params):
            raise asyncpg.UniqueViolationError("self-approval prohibited")
    with pytest.raises(HTTPException) as exc:
        await submit_member_review_event_sandbox(
            T,2027,Q,body(),actor(),Conflict()
        )
    assert exc.value.status_code==409

@pytest.mark.asyncio
async def test_capabilities_respect_production_and_role(monkeypatch):
    for role in ("TENANT_MEMBER","TENANT_ADMIN"):
        for env,flag,ready in (
            ("development","1",True),
            ("staging","1",True),
            ("production","1",True),
            ("development","0",True),
            ("development","1",False),
        ):
            monkeypatch.setenv("ENVIRONMENT",env)
            monkeypatch.setenv("FRCAIXINHA_LIFECYCLE_SANDBOX",flag)
            r=await lifecycle_review_capabilities(
                T,2027,actor(role),FakeReviewDB(ready=ready))
            enabled=env!="production" and flag=="1" and ready
            assert r.can_submit_contestation==(enabled and role=="TENANT_MEMBER")
            assert r.can_review_independently==(enabled and role=="TENANT_ADMIN")
            assert not r.financial_effects_enabled
            assert not r.real_payout_enabled

@pytest.mark.asyncio
@pytest.mark.parametrize("n",range(170))
async def test_170_capability_variations_without_money(monkeypatch,n):
    monkeypatch.setenv("ENVIRONMENT","production" if n%5==0 else "homologation")
    monkeypatch.setenv("FRCAIXINHA_LIFECYCLE_SANDBOX","1" if n%3 else "0")
    role="TENANT_MEMBER" if n%2 else "TENANT_ADMIN"
    db=FakeReviewDB(ready=n%7!=0)
    result=await lifecycle_review_capabilities(T,2027,actor(role),db)
    enabled=n%5!=0 and n%3!=0 and n%7!=0
    assert result.can_submit_contestation==(enabled and role=="TENANT_MEMBER")
    assert result.can_review_independently==(enabled and role=="TENANT_ADMIN")
    assert not result.financial_effects_enabled

@pytest.mark.parametrize("invalid",[
    {"evidence_reference":"short"},
    {"evidence_reference":"contains spaces"},
    {"evidence_reference":"a"*121},
    {"evidence_reference":"../forbidden/path"},
    {"event_kind":"IMMEDIATE_PAYOUT"},
    {"event_kind":"CLOSE_CYCLE"},
    {"event_kind":"MEMBER_BANNED"},
    {"event_kind":"CONTRIBUTION_CONFISCATED"},
    {"event_kind":"TRANSFER_REAL"},
    {"idempotency_key":"not-a-uuid"},
])
def test_malformed_review_payload_fails_closed(invalid):
    payload=dict(idempotency_key=str(EV),
                 event_kind="ADMIN_DOCUMENTS_REQUESTED",
                 evidence_reference="CI-VALID-DOCUMENT-2027")
    payload.update(invalid)
    with pytest.raises(ValidationError):
        ReviewEventPayload(**payload)

def test_route_methods_are_get_post_only_without_financial_payout():
    from app.main import app
    paths=[r for r in app.routes
           if "/member-lifecycle/" in getattr(r,"path","")]
    review=[r for r in paths if "review-events" in r.path]
    assert len(review)==2
    assert {frozenset(r.methods) for r in review}=={
       frozenset(("GET",)),frozenset(("POST",))
    }
    assert not any(any(v in r.methods for v in ("PATCH","PUT","DELETE"))
                   for r in paths)
