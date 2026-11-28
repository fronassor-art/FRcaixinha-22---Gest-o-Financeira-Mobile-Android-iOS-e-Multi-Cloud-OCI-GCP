"""M33400-M33800: authenticated RLS admission preflight, no activation."""
from pathlib import Path
from uuid import uuid4
import pytest
from fastapi import HTTPException

from app.dependencies import AuthenticatedSession
from app.models import InvitationContractReadinessRequest
from app.saas_member_admission_readiness import member_admission_readiness
from app.routers.invitations import preview_saas_member_capacity

ROOT=Path(__file__).resolve().parents[2]

def actor(role,tenant=None,master=False):
    return AuthenticatedSession(str(uuid4()),role,str(tenant) if tenant else None,
        "ci@example.invalid","CI only",master)

def request(tenant,role="TENANT_MEMBER"):
    return InvitationContractReadinessRequest(target_role=role,tenant_id=tenant,
        required_document_id=uuid4())

class FakeRLS:
    def __init__(self,active=True,published=True,row=None,members=0,quotas=0):
        self.active=active
        self.published=published
        self.row=row
        self.members=members
        self.quotas=quotas
        self.queries=[]
    async def fetchval(self,q,*args):
        assert q.startswith("SELECT ")
        assert not any(x in q.upper() for x in ("INSERT INTO ","UPDATE PUBLIC.","DELETE FROM "))
        self.queries.append(("val",q,args))
        if "FROM public.tenants" in q:
            return self.active
        if "FROM public.contract_documents" in q:
            return self.published
        if "FROM public.memberships" in q:
            return self.members
        if "FROM public.quotas" in q:
            return self.quotas
        raise AssertionError("Unexpected SQL "+q)
    async def fetchrow(self,q,*args):
        assert q.startswith("SELECT ")
        assert "public.saas_license_entitlements" in q
        assert "public.platform_license_plans" in q
        assert "public.saas_payment_intents" in q
        assert "public.saas_subscription_preparations" in q
        assert "$1::uuid" in q and "$2::uuid" in q
        self.queries.append(("row",q,args))
        return self.row

def offer(**extra):
    data=dict(members_limit=20,quotas_limit=40,entitlement_status="ACTIVE",
        within_term=True,plan_status="ACTIVE",payment_status="APPROVED",
        locally_reconciled=True,payment_live_mode=False)
    data.update(extra)
    return data

@pytest.mark.asyncio
async def test_available_plan_stays_blocked_and_snapshot_does_not_authorize():
    tenant=uuid4()
    session=actor("TENANT_ADMIN",tenant)
    db=FakeRLS(row=offer(),members=19,quotas=40)
    out=await preview_saas_member_capacity(request(tenant),session,db)
    assert out["capacity_candidate_only"] is True
    assert out["active_member_count_snapshot"] == 19
    assert out["member_limit_snapshot"] == 20
    assert out["status"]=="BLOCKED"
    assert out["provider_verified_live"] is False
    assert out["final_capacity_reserved"] is False
    assert out["writes_performed"] is False
    assert out["activation_authorized"] is False
    assert out["invitation_created"] is False
    assert all("example.invalid" not in str(out) for _ in range(1))
    assert db.queries[2][2] == (tenant, session_uuid(session))

def session_uuid(session):
    from uuid import UUID
    return UUID(session.user_id)

@pytest.mark.asyncio
@pytest.mark.parametrize("row,members,quotas,expected",[
 (offer(),20,0,"PLAN_CAPACITY_EXCEEDED"),
 (offer(),0,41,"PLAN_CAPACITY_EXCEEDED"),
 (offer(members_limit=None),0,0,"PLAN_LIMITS_NOT_APPROVED"),
 (offer(plan_status="BLOCKED_PENDING_CEILING"),0,0,"PLAN_LIMITS_NOT_APPROVED"),
 (offer(entitlement_status="EXPIRED"),0,0,"LICENSE_EXPIRED_OR_INACTIVE"),
 (offer(within_term=False),0,0,"LICENSE_EXPIRED_OR_INACTIVE"),
 (offer(payment_status="REFUNDED"),0,0,"PAYMENT_RECORD_NOT_RECONCILED"),
 (offer(locally_reconciled=False),0,0,"PAYMENT_RECORD_NOT_RECONCILED"),
 (None,0,0,"LICENSE_PLAN_OR_PAYMENT_NOT_VISIBLE"),
])
async def test_negative_cases(row,members,quotas,expected):
    tenant=uuid4()
    out=await member_admission_readiness(
        session=actor("TENANT_ADMIN",tenant),
        payload=request(tenant),conn=FakeRLS(row=row,members=members,quotas=quotas))
    assert expected in out["blocking_gates"]
    assert out["capacity_candidate_only"] is False
    assert out["activation_authorized"] is False
    assert out["writes_performed"] is False

@pytest.mark.asyncio
@pytest.mark.parametrize("active,published,expected",[
 (False,True,"ACTIVE_TENANT_NOT_ATTESTED"),
 (True,False,"PUBLISHED_MEMBERSHIP_CONTRACT_NOT_ATTESTED"),
 (False,False,"PUBLISHED_MEMBERSHIP_CONTRACT_NOT_ATTESTED"),
])
async def test_missing_tenant_or_contract_never_queries_license(active,published,expected):
    tenant=uuid4()
    db=FakeRLS(active=active,published=published,row=offer())
    out=await member_admission_readiness(session=actor("TENANT_ADMIN",tenant),
        payload=request(tenant),conn=db)
    assert expected in out["blocking_gates"]
    assert len(db.queries)==2

@pytest.mark.asyncio
async def test_cross_tenant_or_role_denied_before_any_sql():
    tenant,other=uuid4(),uuid4()
    for session,payload in (
        (actor("TENANT_ADMIN",tenant),request(other)),
        (actor("TENANT_MEMBER",tenant),request(tenant)),
        (actor("MASTER",master=True),request(tenant,"TENANT_ADMIN")),
        (actor("TENANT_ADMIN",tenant),request(tenant,"TENANT_ADMIN")),
    ):
        db=FakeRLS(row=offer())
        with pytest.raises(HTTPException) as exc:
            await member_admission_readiness(session=session,payload=payload,conn=db)
        assert exc.value.status_code==403
        assert db.queries==[]

def test_read_only_router_and_migration_policy():
    router=(ROOT/"backend/app/routers/invitations.py").read_text()
    policy=(ROOT/"backend/local_migrations/045_saas_member_plan_visibility.sql").read_text()
    service=(ROOT/"backend/app/saas_member_admission_readiness.py").read_text()
    assert '@router.post("/preflight/saas-capacity")' in router
    assert "Depends(get_current_session)" in router
    assert "Depends(get_rls_db_connection)" in router
    assert "M33400_LOCAL_MIGRATION_NOT_AUTHORIZED" in policy
    assert "CREATE POLICY platform_license_plans_admin_licensed_read" in policy
    assert "public.rls_is_tenant_admin" in policy
    assert "public.saas_license_entitlements" in policy
    assert "public.saas_payment_intents" in service
    for bad in ("INSERT INTO ","UPDATE public.","DELETE FROM ","asyncpg.connect(","psycopg.connect("):
        assert bad not in service
    assert "Convites ainda não implementados" in router
