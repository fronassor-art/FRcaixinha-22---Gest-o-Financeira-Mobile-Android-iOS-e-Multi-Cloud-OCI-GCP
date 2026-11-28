"""Inventario administrativo Master: API restrita sem banco real."""
import uuid
from fastapi import HTTPException
from fastapi.testclient import TestClient
from app.database import get_rls_db_connection
from app.dependencies import AuthenticatedSession, require_master
from app.main import app

ADMIN_ID=uuid.UUID("00000000-0000-4000-8000-000000000002")


class FakeAdminRegistry:
    def __init__(self):
        self.queries=[]
    async def fetchval(self,sql,*args):
        self.queries.append((sql,args))
        assert "count(DISTINCT admin_user_id)" in sql
        assert "FROM public.tenants" in sql
        return 1
    async def fetch(self,sql,*args):
        self.queries.append((sql,args))
        assert "GROUP BY admin_user_id" in sql
        assert "FROM public.tenants" in sql
        return [{
            "admin_user_id":ADMIN_ID,"tenant_count":3,"active_count":1,
            "suspended_count":1,"draft_count":1,"closed_count":0,
        }]


def owner():
    return AuthenticatedSession(str(uuid.uuid4()),"MASTER",None,
                                "ci@example.invalid","Owner CI",True)


def test_admin_registry_aggregates_only_tenant_metadata():
    fake=FakeAdminRegistry()
    app.dependency_overrides[get_rls_db_connection]=lambda:fake
    app.dependency_overrides[require_master]=owner
    try:
        with TestClient(app) as client:
            response=client.get("/api/v1/master/admin-registry",
                params={"search":"00000000","page":2,"page_size":5})
        assert response.status_code==200,response.text
        data=response.json()
        assert data["source"]=="POSTGRESQL_RLS"
        assert data["scope"]=="MASTER_PRIMARY_ADMIN_REGISTRY"
        assert data["total"]==1 and data["page"]==2
        assert data["administrators"][0]["tenant_count"]==3
        assert data["administrators"][0]["admin_user_id"]==str(ADMIN_ID)
        assert data["identity_status"]=="UNVERIFIED_REFERENCE_ONLY"
        assert data["invitation_status"]=="NOT_IMPLEMENTED"
        assert data["access_changes"]=="BLOCKED_PENDING_APPROVAL"
        assert fake.queries[0][1]==("00000000",)
        assert fake.queries[1][1]==("00000000",5,5)
        for sql,_ in fake.queries:
            for prohibited in ("public.users","public.memberships",
                               "public.credentials","public.ledger",
                               "contributions","loans"):
                assert prohibited not in sql
        for field in ("email","cpf","phone","password_hash","balance"):
            assert field not in response.text.lower()
    finally:
        app.dependency_overrides.clear()


def test_admin_registry_rejects_invalid_filters():
    fake=FakeAdminRegistry()
    app.dependency_overrides[get_rls_db_connection]=lambda:fake
    app.dependency_overrides[require_master]=owner
    try:
        with TestClient(app) as client:
            checks=[
                client.get("/api/v1/master/admin-registry?page=0"),
                client.get("/api/v1/master/admin-registry?page_size=100"),
                client.get("/api/v1/master/admin-registry?search="+("a"*37)),
            ]
        assert all(response.status_code==422 for response in checks)
        assert fake.queries==[]
    finally:
        app.dependency_overrides.clear()


def test_admin_registry_denies_nonmaster_and_unauthenticated():
    fake=FakeAdminRegistry()
    app.dependency_overrides[get_rls_db_connection]=lambda:fake
    def forbidden():
        raise HTTPException(status_code=403,detail="Somente Master")
    app.dependency_overrides[require_master]=forbidden
    try:
        with TestClient(app) as client:
            result=client.get("/api/v1/master/admin-registry")
        assert result.status_code==403
        assert fake.queries==[]
    finally:
        app.dependency_overrides.clear()
    with TestClient(app) as client:
        result=client.get("/api/v1/master/admin-registry")
    assert result.status_code==401
