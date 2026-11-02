"""Contrato dos painéis reais do AI Studio. Testes sem banco local nem segredos."""
import datetime
import uuid

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.database import get_rls_db_connection
from app.dependencies import AuthenticatedSession, get_current_session, require_master
from app.main import app


class FakeConnection:
    def __init__(self):
        self.queries = []

    async def fetchval(self, sql, *params):
        self.queries.append((sql, params))
        if "public.tenants" in sql:
            return 1
        if "public.memberships" in sql and "m.role='TENANT_MEMBER'" in sql:
            # Na consulta individual do membro, o join com memberships
            # nao significa contagem de membros de toda a caixinha.
            return 0
        if "public.memberships" in sql:
            return 2
        return 0

    async def fetch(self, sql, *params):
        self.queries.append((sql, params))
        if "public.tenants" in sql:
            return [{"id": uuid.uuid4(), "display_name": "Caixinha teste",
                     "status": "ATIVO", "is_owner_box": False}]
        if "public.memberships" in sql:
            return [{"id": uuid.uuid4(), "role": "TENANT_MEMBER",
                     "status": "ATIVA", "joined_at": datetime.date(2027, 1, 10),
                     "full_name": "Membro ficticio"}]
        return []


@pytest.fixture
def fake_db():
    connection = FakeConnection()
    def get_db():
        return connection
    app.dependency_overrides[get_rls_db_connection] = get_db
    yield connection
    app.dependency_overrides.clear()


def fake_session(user_role, tenant=None, is_master=False):
    return AuthenticatedSession(str(uuid.uuid4()), user_role, tenant,
                                "pessoa@example.invalid", "Pessoa", is_master)


def test_master_overview_uses_postgres_without_financial_data(fake_db):
    app.dependency_overrides[require_master] = lambda: fake_session("MASTER", is_master=True)
    with TestClient(app) as client:
        response = client.get("/api/v1/master/overview")
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["source"] == "POSTGRESQL_RLS"
    assert data["total_tenants"] == 1
    assert len(data["tenants"]) == 1
    assert data["saas_revenue_status"] == "NOT_CONNECTED_TO_RECONCILED_BILLING"
    assert not any("ledger" in sql or "contributions" in sql for sql, _ in fake_db.queries)


def test_master_endpoint_rejects_non_master(fake_db):
    def denied():
        return require_master(fake_session("TENANT_ADMIN", tenant=str(uuid.uuid4())))
    app.dependency_overrides[require_master] = denied
    with TestClient(app) as client:
        response = client.get("/api/v1/master/overview")
    assert response.status_code == 403


def test_tenant_dashboard_is_scoped_by_role_and_members_are_admin_only(fake_db):
    tenant_id = str(uuid.uuid4())
    app.dependency_overrides[get_current_session] = lambda: fake_session("TENANT_MEMBER", tenant_id)
    with TestClient(app) as client:
        response = client.get(f"/api/v1/tenants/{tenant_id}/dashboard")
        denied = client.get(f"/api/v1/tenants/{tenant_id}/members")
    assert response.status_code == 200, response.text
    assert response.json()["source"] == "POSTGRESQL_RLS"
    assert response.json()["quota_count_visible"] == 0
    # As tres contagens devem obrigatoriamente filtrar o membership MEMBER
    # ate quando a identidade tenha tambem vinculo ADMIN.
    assert len(fake_db.queries) == 3
    assert all("m.role='TENANT_MEMBER'" in sql for sql, _ in fake_db.queries)
    assert "member_count_visible" not in response.json()
    assert denied.status_code == 403

    app.dependency_overrides[get_current_session] = lambda: fake_session("TENANT_ADMIN", tenant_id)
    with TestClient(app) as client:
        admin = client.get(f"/api/v1/tenants/{tenant_id}/members")
        dashboard = client.get(f"/api/v1/tenants/{tenant_id}/dashboard")
    assert admin.status_code == 200, admin.text
    assert admin.json()["members"][0]["name"] == "Membro ficticio"
    assert "cpf" not in admin.text.lower() and "phone" not in admin.text.lower()
    assert dashboard.status_code == 200
    assert dashboard.json()["member_count_visible"] == 2


def test_cross_tenant_is_denied_before_query(fake_db):
    active = str(uuid.uuid4())
    target = str(uuid.uuid4())
    app.dependency_overrides[get_current_session] = lambda: fake_session("TENANT_ADMIN", active)
    with TestClient(app) as client:
        result = client.get(f"/api/v1/tenants/{target}/dashboard")
        members = client.get(f"/api/v1/tenants/{target}/members")
    assert result.status_code == 403
    assert members.status_code == 403
    assert fake_db.queries == []


def test_master_cannot_use_tenant_dashboard(fake_db):
    target = str(uuid.uuid4())
    app.dependency_overrides[get_current_session] = lambda: fake_session("MASTER", is_master=True)
    with TestClient(app) as client:
        response = client.get(f"/api/v1/tenants/{target}/dashboard")
    assert response.status_code == 403
    assert fake_db.queries == []
