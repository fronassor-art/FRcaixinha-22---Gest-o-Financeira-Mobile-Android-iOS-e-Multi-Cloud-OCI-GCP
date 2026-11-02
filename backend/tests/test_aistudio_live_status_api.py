"""Status operacional SaaS é somente leitura, com papéis e RLS."""
from datetime import datetime,timezone
from uuid import uuid4,UUID

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import app
from app.dependencies import require_master,get_current_session,AuthenticatedSession
from app.database import get_rls_db_connection


A=str(uuid4());B=str(uuid4());M=str(uuid4());ADM=str(uuid4());MEM=str(uuid4())
NOW=datetime(2026,11,1,tzinfo=timezone.utc)


class FakeSaasConnection:
    def __init__(self):self.queries=[]
    async def fetch(self,sql,*args):
        self.queries.append((sql,args))
        if "saas_payment_intents" in sql:
            return [dict(id=uuid4(),tenant_id=UUID(A),status="PENDING",
                         expected_amount_cents=8990,currency="BRL",created_at=NOW)]
        if "saas_license_entitlements" in sql:
            return [dict(id=uuid4(),tenant_id=UUID(A),plan_tier="ESSENCIAL",
                         status="ACTIVE",valid_from=NOW,valid_until=NOW)]
        raise AssertionError("Unexpected query")


def actor(user,role,tenant=None,master=False):
    return AuthenticatedSession(user,role,tenant,"ci@example.com","Pessoa CI",master)


@pytest.fixture
def db():
    fake=FakeSaasConnection()
    app.dependency_overrides[get_rls_db_connection]=lambda:fake
    yield fake
    app.dependency_overrides.clear()


def test_master_reads_only_license_status_not_tenant_ledger(db):
    app.dependency_overrides[require_master]=lambda:actor(M,"MASTER",master=True)
    with TestClient(app) as client:
        r=client.get("/api/v1/master/saas-payment-status")
        ready=client.get("/api/v1/master/integration-readiness")
    assert r.status_code==200,r.text
    assert r.json()["payments"][0]["expected_amount_cents"]==8990
    assert r.json()["licenses"][0]["status"]=="ACTIVE"
    assert ready.status_code==200
    assert ready.json()["saas_platform_payment"]=="BLOCKED_BY_GOVERNANCE"
    assert "access_token" not in ready.text
    assert "balance" not in r.text and "ledger" not in str(db.queries)


def test_master_rejects_tenant_admin_without_reading_db(db):
    def denied():
        raise HTTPException(status_code=403,detail="Somente Master")
    app.dependency_overrides[require_master]=denied
    with TestClient(app) as client:
        r=client.get("/api/v1/master/saas-payment-status")
        ready=client.get("/api/v1/master/integration-readiness")
    assert r.status_code==403 and ready.status_code==403
    assert db.queries==[]


def test_admin_status_scoped_to_tenant_and_member_denied(db):
    app.dependency_overrides[get_current_session]=lambda:actor(ADM,"TENANT_ADMIN",A)
    with TestClient(app) as client:
        allowed=client.get(f"/api/v1/tenants/{A}/saas-payment-status")
        cross=client.get(f"/api/v1/tenants/{B}/saas-payment-status")
    assert allowed.status_code==200,allowed.text
    assert cross.status_code==403
    assert allowed.json()["tenant_id"]==A
    assert len(db.queries)==2
    assert all(q[1]==(UUID(A),) for q in db.queries)
    app.dependency_overrides[get_current_session]=lambda:actor(MEM,"TENANT_MEMBER",A)
    with TestClient(app) as client:
        member=client.get(f"/api/v1/tenants/{A}/saas-payment-status")
    assert member.status_code==403
    assert len(db.queries)==2


def test_master_cannot_impersonate_tenant_admin(db):
    app.dependency_overrides[get_current_session]=lambda:actor(M,"MASTER",master=True)
    with TestClient(app) as client:
        r=client.get(f"/api/v1/tenants/{A}/saas-payment-status")
    assert r.status_code==403 and db.queries==[]
