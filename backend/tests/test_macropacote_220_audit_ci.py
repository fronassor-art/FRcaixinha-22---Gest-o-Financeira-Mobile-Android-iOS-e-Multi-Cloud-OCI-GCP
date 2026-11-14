"""FRcaixinha AI Studio M220: auditoria sem atribuir autenticidade; somente CI sintético."""
from datetime import datetime,timezone
from decimal import Decimal
from uuid import uuid4,UUID
import pytest
from fastapi import HTTPException
from app.dependencies import AuthenticatedSession
from app.routers.audit import get_audit_readiness_preview,create_tenant_audit_event
from app.models import AuditEventCreatePayload
from app.annual_allocation_preview import annual_allocation_preview
T=str(uuid4())
U=str(uuid4())
O=str(uuid4())

def session(role="TENANT_ADMIN",tenant=T):
    return AuthenticatedSession(U,role,tenant,"ci@example.invalid","Sintética",role=="MASTER")

def event(**changes):
    row={"id":uuid4(),"actor_id":uuid4(),"actor_role":"TENANT_ADMIN",
        "action":"CI_ONLY","object_type":"POLICY","object_id":"synthetic",
        "reason":"CI synthetic","evidence_ref":"CI:reference",
        "created_at":datetime(2027,1,1,tzinfo=timezone.utc)}
    return {**row,**changes}

class ReadOnly:
    def __init__(self,rows=None):
        self.rows=[event()] if rows is None else rows
        self.calls=[]
    async def fetch(self,sql,*args):
        self.calls.append((sql,args))
        return self.rows
    async def execute(self,*_):
        raise AssertionError("NEVER write")
    async def fetchrow(self,*_):
        raise AssertionError("Only one SELECT allowed")

@pytest.mark.asyncio
async def test_readiness_is_bounded_without_authorization_claim():
    db=ReadOnly([event(),event()])
    r=await get_audit_readiness_preview(T,session(),db)
    assert r.source=="POSTGRESQL_RLS"
    assert r.scope=="TENANT_ADMIN_READ_ONLY"
    assert r.checked_events==r.fields_present_events==2
    assert r.review_required_events==0 and r.status=="FIELDS_PRESENT_ONLY"
    assert r.provenance_verified is False
    assert r.append_only_verified is False
    assert r.financial_audit_approved is False
    assert len(db.calls)==1
    sql,args=db.calls[0]
    assert sql.lstrip().startswith("SELECT")
    assert "WHERE tenant_id=$1" in sql and "LIMIT 501" in sql
    assert args==(UUID(T),)

@pytest.mark.asyncio
async def test_master_member_other_tenant_rejected_without_sql():
    for role,tenant in (("MASTER",None),("TENANT_MEMBER",T),("TENANT_ADMIN",O)):
        db=ReadOnly()
        with pytest.raises(HTTPException) as e:
            await get_audit_readiness_preview(T,session(role,tenant),db)
        assert e.value.status_code==403 and db.calls==[]

@pytest.mark.asyncio
async def test_empty_audit_does_not_claim_approval():
    r=await get_audit_readiness_preview(T,session(),ReadOnly([]))
    assert r.status=="NO_EVENTS" and r.checked_events==0
    assert not r.provenance_verified

@pytest.mark.asyncio
async def test_missing_evidence_fields_flag_review():
    for name in ("actor_role","action","object_type","object_id","reason","evidence_ref"):
        r=await get_audit_readiness_preview(T,session(),ReadOnly([event(**{name:""})]))
        assert r.status=="REVIEW_REQUIRED"
        assert r.review_required_events==1
        assert not r.financial_audit_approved

@pytest.mark.asyncio
async def test_invalid_identifiers_and_large_audit_fail_closed():
    duplicate=event(id="11111111-1111-1111-1111-111111111111")
    for rows in ([event(id="bad")],[event(actor_id="invalid")],
                 [event(id=None)],[duplicate,duplicate],
                 [event() for _ in range(501)]):
        with pytest.raises(HTTPException) as e:
            await get_audit_readiness_preview(T,session(),ReadOnly(rows))
        assert e.value.status_code==503

@pytest.mark.asyncio
async def test_bad_uuid_rejected_with_no_sql():
    db=ReadOnly()
    with pytest.raises(HTTPException) as e:
        await get_audit_readiness_preview("not-a-uuid",session("TENANT_ADMIN","not-a-uuid"),db)
    assert e.value.status_code==422 and db.calls==[]

@pytest.mark.asyncio
async def test_manual_audit_mutation_remains_blocked():
    payload=AuditEventCreatePayload(action="RECONCILED",object_type="PAYMENT",
        object_id="fake",reason="Client claim",evidence_ref="CI_ONLY")
    db=ReadOnly()
    with pytest.raises(HTTPException) as e:
        await create_tenant_audit_event(T,payload,session(),db)
    assert e.value.status_code==503 and db.calls==[]

def test_financial_rateio_remains_simulated_only():
    p=annual_allocation_preview(Decimal("100.01"),{
        "m3":Decimal("100"),"m1":Decimal("100"),"m2":Decimal("100")})
    assert p["state"]=="PREVIEW_NOT_SETTLED"
    assert p["admin_provisional_cents"]+p["member_pool_cents"]==10001
    assert sum(p["member_shares_cents"].values())==p["member_pool_cents"]
    assert p["segregated_undistributed_cents"]==0

def test_undistributed_weights_remain_segregated():
    p=annual_allocation_preview("15.00",{"m1":0,"m2":0})
    assert p["state"]=="PREVIEW_NOT_SETTLED"
    assert p["segregated_undistributed_cents"]==p["member_pool_cents"]
    assert not any(p["member_shares_cents"].values())
