"""M39083: check cycle-readiness without original PostgreSQL or any writes."""
from types import SimpleNamespace

import pytest

from backend.app.routers import special_credit as module
from backend.tests.test_m39033_special_credit_route_flow_ci import (
    ADMIN, MEMBER_USER, OTHER_TENANT, PATH, TENANT, make_client,
)


class ReadOnlyCycleDb:
    def __init__(self, current):
        self.current = current
        self.queries = []

    async def fetchval(self, query, *args):
        self.queries.append(query)
        assert args == (TENANT,)
        if "SELECT admin_user_id FROM public.tenants" in query:
            return ADMIN
        assert "SELECT EXISTS (SELECT 1 FROM public.cycles" in query
        for gate in ("tenant_id=$1", "status='ABERTO'",
                     "start_date<=CURRENT_DATE", "end_date>=CURRENT_DATE"):
            assert gate in query
        return self.current


@pytest.fixture(autouse=True)
def sandbox_only(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("FRCAIXINHA_TEST_AUTH", "1")
    monkeypatch.setenv("FR_FINANCE_SPECIAL_CREDIT_SANDBOX", "YES")
    monkeypatch.setattr(module, "settings", SimpleNamespace(
        DATABASE_URL="postgresql://frc_ai_app@127.0.0.1:5433/frcaixinha_aistudio_dev"
    ))


@pytest.mark.parametrize("current", [True, False, None])
def test_admin_cycle_readiness_only_reads(current):
    db = ReadOnlyCycleDb(current)
    client = make_client(db, "TENANT_ADMIN", ADMIN)
    response = client.get(PATH + "/cycle-readiness")
    assert response.status_code == 200, response.text
    assert response.json() == {
        "current_open_cycle": current is True,
        "campaign_creation_allowed": current is True,
        "real_credit_enabled": False,
        "external_dispatch": False,
    }
    assert len(db.queries) == 2
    assert all(query.startswith("SELECT") for query in db.queries)


def test_non_admin_and_cross_tenant_rejected_before_any_db_use():
    db = ReadOnlyCycleDb(True)
    for role, user, tenant in (
        ("TENANT_MEMBER", MEMBER_USER, TENANT),
        ("TENANT_ADMIN", ADMIN, OTHER_TENANT),
        ("MASTER", ADMIN, TENANT),
    ):
        client = make_client(db, role, user, tenant)
        assert client.get(PATH + "/cycle-readiness").status_code == 403
    assert db.queries == []


def test_default_gate_denies_readiness_without_db(monkeypatch):
    monkeypatch.delenv("FR_FINANCE_SPECIAL_CREDIT_SANDBOX", raising=False)
    db = ReadOnlyCycleDb(True)
    client = make_client(db, "TENANT_ADMIN", ADMIN)
    assert client.get(PATH + "/cycle-readiness").status_code == 503
    assert db.queries == []
