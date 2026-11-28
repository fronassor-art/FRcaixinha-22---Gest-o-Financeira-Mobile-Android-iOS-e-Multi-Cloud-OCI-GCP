"""Read-only contractual SaaS endpoints with permission tests (no local DB)."""
import datetime
import uuid

import pytest
from fastapi.testclient import TestClient

from app.database import get_rls_db_connection
from app.dependencies import AuthenticatedSession, get_current_session, require_master
from app.main import app

TENANT_A=str(uuid.uuid4())
TENANT_B=str(uuid.uuid4())
MASTER_ID=str(uuid.uuid4())
ADMIN_ID=str(uuid.uuid4())
MEMBER_ID=str(uuid.uuid4())


class FakeGovernanceConnection:
    def __init__(self):
        self.queries=[]
    async def fetch(self,sql,*params):
        self.queries.append((sql,params))
        if "saas_subscription_preparations" in sql:
            return [{
                "id":uuid.uuid4(),"tenant_id":uuid.UUID(TENANT_A),
                "plan_tier":"ESSENCIAL","price_version_id":uuid.uuid4(),
                "billing_period":"MONTHLY","status":"PENDING_PAYMENT",
                "created_at":datetime.datetime.now(datetime.timezone.utc),
            }]
        if "contract_acceptances" in sql:
            return [{
                "id":uuid.uuid4(),"document_id":uuid.uuid4(),
                "document_kind":"TENANT_MEMBERSHIP",
                "accepted_at":datetime.datetime.now(datetime.timezone.utc),
                "version_label":"CI-v1","sha256":"f"*64,
                "source_reference":"Documento sintético somente para CI",
            }]
        return []


@pytest.fixture
def db():
    x=FakeGovernanceConnection()
    app.dependency_overrides[get_rls_db_connection]=lambda:x
    yield x
    app.dependency_overrides.clear()


def actor(user_id,role,tenant=None,master=False):
    return AuthenticatedSession(user_id,role,tenant,
                                "synthetic@example.com","Ator sintético",master)


def test_master_saas_inventory_does_not_include_tenant_finances(db):
    app.dependency_overrides[require_master]=lambda:actor(MASTER_ID,'MASTER',master=True)
    with TestClient(app) as client:
        r=client.get('/api/v1/master/subscription-preparations')
    assert r.status_code==200,r.text
    data=r.json()
    assert data["billing_status"]=="NO_PROVIDER_NO_FINANCIAL_ACTIVATION"
    assert data["preparations"][0]["status"]=="PENDING_PAYMENT"
    assert "balance" not in r.text and "pix" not in r.text.lower()
    assert all("ledger" not in q and "contributions" not in q for q,_ in db.queries)


def test_master_saas_inventory_rejects_admin(db):
    from fastapi import HTTPException
    def denied():
        raise HTTPException(status_code=403,detail="Somente Master.")
    app.dependency_overrides[require_master]=denied
    with TestClient(app) as client:
        r=client.get('/api/v1/master/subscription-preparations')
    assert r.status_code==403
    assert db.queries==[]


def test_tenant_license_is_admin_only_and_scoped(db):
    app.dependency_overrides[get_current_session]=lambda:actor(ADMIN_ID,'TENANT_ADMIN',TENANT_A)
    with TestClient(app) as client:
        good=client.get(f'/api/v1/tenants/{TENANT_A}/license-preparation')
        wrong=client.get(f'/api/v1/tenants/{TENANT_B}/license-preparation')
    assert good.status_code==200,good.text
    assert good.json()["tenant_id"]==TENANT_A
    assert good.json()["preparations"][0]["status"]=="PENDING_PAYMENT"
    assert wrong.status_code==403
    assert len(db.queries)==1
    assert db.queries[0][1]==(uuid.UUID(TENANT_A),)


def test_member_cannot_access_tenant_license_but_can_read_own_acceptances(db):
    app.dependency_overrides[get_current_session]=lambda:actor(MEMBER_ID,'TENANT_MEMBER',TENANT_A)
    with TestClient(app) as client:
        denied=client.get(f'/api/v1/tenants/{TENANT_A}/license-preparation')
        own=client.get(f'/api/v1/tenants/{TENANT_A}/my-contracts')
        elsewhere=client.get(f'/api/v1/tenants/{TENANT_B}/my-contracts')
    assert denied.status_code==403
    assert own.status_code==200,own.text
    assert own.json()['contracts'][0]['kind']=='TENANT_MEMBERSHIP'
    assert elsewhere.status_code==403
    assert len(db.queries)==1
    assert db.queries[0][1]==(uuid.UUID(MEMBER_ID),uuid.UUID(TENANT_A))


def test_master_does_not_inherit_tenant_contract_access(db):
    app.dependency_overrides[get_current_session]=lambda:actor(MASTER_ID,'MASTER',master=True)
    with TestClient(app) as client:
        r=client.get(f'/api/v1/tenants/{TENANT_A}/my-contracts')
    assert r.status_code==403
    assert db.queries==[]
