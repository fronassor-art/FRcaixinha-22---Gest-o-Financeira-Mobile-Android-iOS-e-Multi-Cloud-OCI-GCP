"""Inventario Master somente leitura e metadados, sem banco real."""
import datetime
import uuid

from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.database import get_rls_db_connection
from app.dependencies import AuthenticatedSession, require_master
from app.main import app

TENANT_ID=uuid.UUID("00000000-0000-4000-8000-000000000001")
ADMIN_ID=uuid.UUID("00000000-0000-4000-8000-000000000002")
CREATED=datetime.datetime(2026,11,2,tzinfo=datetime.timezone.utc)


class FakeRegistry:
    def __init__(self):
        self.queries=[]
    async def fetchval(self,query,*params):
        self.queries.append((query,params))
        assert "FROM public.tenants" in query
        assert "count(*)" in query.lower()
        return 1
    async def fetch(self,query,*params):
        self.queries.append((query,params))
        assert "FROM public.tenants" in query
        if "GROUP BY status" in query:
            return [{"status":"ATIVO","count":1}]
        return [{
            "id":TENANT_ID, "display_name":"Caixinha sintética",
            "status":"ATIVO","is_owner_box":False,
            "admin_user_id":ADMIN_ID,"created_at":CREATED,
        }]


def _master():
    return AuthenticatedSession(str(uuid.uuid4()),"MASTER",None,
                                "ci@example.invalid","Master CI",True)


def test_registry_server_filters_pagination_and_no_private_data():
    fake=FakeRegistry()
    app.dependency_overrides[get_rls_db_connection]=lambda:fake
    app.dependency_overrides[require_master]=_master
    try:
        with TestClient(app) as client:
            result=client.get("/api/v1/master/tenant-registry",
                params={"search":"Caixinha","tenant_status":"ATIVO",
                        "page":1,"page_size":5})
        assert result.status_code==200,result.text
        body=result.json()
        assert body["source"]=="POSTGRESQL_RLS"
        assert body["scope"]=="MASTER_TENANT_REGISTRY"
        assert body["total"]==1 and body["page_size"]==5
        assert body["status_counts"]["ATIVO"]==1
        assert body["status_counts"]["SUSPENSO"]==0
        assert body["has_more"] is False
        assert body["tenants"][0]["admin_user_id"]==str(ADMIN_ID)
        assert body["admin_invitation_status"]=="NOT_IMPLEMENTED"
        assert body["admin_access_changes"]=="BLOCKED_PENDING_APPROVAL"
        text=result.text.lower()
        for private in ("cpf","email","telefone","phone","balance","ledger","contribu"):
            assert private not in text
        for sql,params in fake.queries:
            assert "public.tenants" in sql
            assert not any(private in sql for private in
                           ("public.users","public.memberships","public.ledger"))
        assert fake.queries[0][1]==("Caixinha","ATIVO")
        assert fake.queries[1][1]==("Caixinha","ATIVO",5,0)
    finally:
        app.dependency_overrides.clear()


def test_registry_rejects_invalid_filters_without_db():
    fake=FakeRegistry()
    app.dependency_overrides[get_rls_db_connection]=lambda:fake
    app.dependency_overrides[require_master]=_master
    try:
        with TestClient(app) as client:
            results=[
                client.get("/api/v1/master/tenant-registry?page=0"),
                client.get("/api/v1/master/tenant-registry?page_size=999"),
                client.get("/api/v1/master/tenant-registry?tenant_status=INVENTADO"),
                client.get("/api/v1/master/tenant-registry?search="+("a"*81)),
            ]
        assert all(r.status_code==422 for r in results)
        assert fake.queries==[]
    finally:
        app.dependency_overrides.clear()


def test_registry_disallows_unprivileged_actor_and_unauthenticated():
    fake=FakeRegistry()
    app.dependency_overrides[get_rls_db_connection]=lambda:fake
    def denied():
        raise HTTPException(status_code=403,detail="Somente Master")
    app.dependency_overrides[require_master]=denied
    try:
        with TestClient(app) as client:
            denied_res=client.get("/api/v1/master/tenant-registry")
        assert denied_res.status_code==403
        assert fake.queries==[]
    finally:
        app.dependency_overrides.clear()
    with TestClient(app) as client:
        unauth=client.get("/api/v1/master/tenant-registry")
    assert unauth.status_code==401
