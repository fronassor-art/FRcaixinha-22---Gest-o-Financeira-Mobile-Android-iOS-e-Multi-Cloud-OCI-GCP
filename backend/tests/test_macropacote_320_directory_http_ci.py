"""M320: rotas HTTP em FastAPI, somente dados sinteticos e conexao fake read-only."""
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.database import get_rls_db_connection
from app.dependencies import AuthenticatedSession, get_current_session
from app.main import app

T=str(uuid4())
OTHER=str(uuid4())
U=str(uuid4())
ACCOUNT=str(uuid4())
URL=f"/api/v1/tenants/{T}/ledger/accounts/directory"


def identity(role,tenant=T):
    return AuthenticatedSession(U,role,tenant,"ci@example.invalid","CI",role=="MASTER")


class Fake:
    def __init__(self):
        self.calls=[]

    async def fetch(self, sql, *args):
        assert sql.lstrip().startswith("SELECT")
        self.calls.append((sql,args))
        return [{
            "id":ACCOUNT,"tenant_id":T,"account_code":"1.1.1",
            "account_name":"Conta sintética","account_type":"ASSET",
        }]

    async def execute(self, *_):
        raise AssertionError("Escrita nao autorizada")


@pytest.fixture(autouse=True)
def clean_overrides():
    yield
    app.dependency_overrides.pop(get_current_session,None)
    app.dependency_overrides.pop(get_rls_db_connection,None)


def test_http_directory_only_admin_receives_no_balance():
    db=Fake()
    app.dependency_overrides[get_current_session]=lambda:identity("TENANT_ADMIN")
    app.dependency_overrides[get_rls_db_connection]=lambda:db
    with TestClient(app) as client:
        response=client.get(URL)
    assert response.status_code==200,response.text
    body=response.json()
    assert body["accounts"]==[{
        "id":ACCOUNT,"account_code":"1.1.1",
        "account_name":"Conta sintética","account_type":"ASSET",
    }]
    assert body["source"]=="POSTGRESQL_RLS"
    assert body["balance_values_hidden"] is True
    assert body["complete_ledger_verified"] is False
    assert body["bank_reconciled"] is False
    assert body["financial_closing_authorized"] is False
    assert len(db.calls)==1
    assert "balance" not in str(body["accounts"]).lower()
    assert response.headers.get("cache-control")=="no-store"


def test_http_roles_master_member_and_other_tenant_forbidden_before_sql():
    for role,tenant in (("MASTER",None),("TENANT_MEMBER",T),
                        ("TENANT_ADMIN",OTHER)):
        db=Fake()
        app.dependency_overrides[get_current_session]=lambda r=role,t=tenant:identity(r,t)
        app.dependency_overrides[get_rls_db_connection]=lambda:db
        with TestClient(app) as client:
            response=client.get(URL)
        assert response.status_code==403,response.text
        assert db.calls==[]


def test_http_no_auth_stays_blocked_without_db_connection():
    db=Fake()
    app.dependency_overrides[get_rls_db_connection]=lambda:db
    with TestClient(app) as client:
        response=client.get(URL)
    assert response.status_code==401
    assert db.calls==[]
