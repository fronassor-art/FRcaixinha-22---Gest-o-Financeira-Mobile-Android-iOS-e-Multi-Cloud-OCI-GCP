"""Motor de catalogo SaaS do MASTER: testes API e schema sem dados reais."""
import datetime
import os
import uuid

import psycopg
import pytest
from fastapi.testclient import TestClient

from app.database import get_rls_db_connection
from app.dependencies import AuthenticatedSession, require_master
from app.main import app


class FakeCatalogDb:
    def __init__(self):
        self.events = []
        self.version_id = uuid.uuid4()

    async def fetch(self, query, *params):
        assert "platform_license_plans" in query
        return [
            {"tier":"ESSENCIAL","display_name":"Essencial","members_limit":20,
             "quotas_limit":40,"status":"ACTIVE","version_id":self.version_id,
             "monthly_price":"89.90","annual_price":"899.00",
             "created_at":datetime.datetime(2026,11,1,tzinfo=datetime.timezone.utc)}
        ]

    async def fetchval(self, query, *params):
        if "attgenerated" in query:
            return True
        if "pg_advisory_xact_lock" in query:
            return None
        if "SELECT id FROM public.platform_license_price_versions" in query:
            return self.version_id
        raise AssertionError(query)

    async def fetchrow(self, query, *params):
        if query.startswith("SELECT"):
            return {"tier":"ESSENCIAL","status":"ACTIVE"}
        assert "INSERT INTO public.platform_license_price_versions" in query
        self.events.append(("price", params))
        return {"id":uuid.uuid4(),"monthly_price":str(params[1]),
                "annual_price":str(params[2]),
                "created_at":datetime.datetime(2026,11,1,tzinfo=datetime.timezone.utc)}

    async def execute(self, query, *params):
        assert "INSERT INTO public.audit_events" in query
        self.events.append(("audit", params))


@pytest.fixture
def catalog_db():
    fake=FakeCatalogDb()
    def owner():
        return AuthenticatedSession(str(uuid.uuid4()), "MASTER", None,
                                    "master@example.invalid","Master",True)
    app.dependency_overrides[require_master] = owner
    app.dependency_overrides[get_rls_db_connection] = lambda: fake
    yield fake
    app.dependency_overrides.clear()


def test_master_reads_catalog_from_postgres(catalog_db):
    with TestClient(app) as client:
        result=client.get("/api/v1/master/licenses")
    assert result.status_code==200,result.text
    payload=result.json()
    assert payload["source"]=="POSTGRESQL_RLS"
    assert payload["plans"][0]["monthly_price"]=="89.90"
    assert payload["plans"][0]["annual_price"]=="899.00"
    assert payload["billing_status"]=="NOT_CONNECTED_TO_RECONCILED_PROVIDER"


def test_master_appends_independent_prices_and_audit_without_billing(catalog_db):
    with TestClient(app) as client:
        result=client.post("/api/v1/master/license-prices",
                           json={"tier":"ESSENCIAL","monthly_price":"99.90",
                                 "annual_price":"775.33",
                                 "expected_version_id":str(catalog_db.version_id),
                                 "reason":"Revisao comercial documentada"})
    assert result.status_code==200,result.text
    payload=result.json()
    assert payload["status"]=="VERSION_PERSISTED_NO_BILLING"
    assert payload["monthly_price"]=="99.90"
    assert payload["annual_price"]=="775.33"  # NUNCA 10 x mensal
    assert payload["billing_status"]=="OFF_NO_PROVIDER_NO_CHARGE"
    assert [e[0] for e in catalog_db.events]==["price","audit"]


def test_master_price_refuses_old_client_missing_annual(catalog_db):
    with TestClient(app) as client:
        result=client.post("/api/v1/master/license-prices",
                           json={"tier":"ESSENCIAL","monthly_price":"99.90",
                                 "reason":"Revisao comercial documentada"})
    assert result.status_code==422
    assert catalog_db.events==[]


def test_master_price_refuses_stale_version(catalog_db):
    with TestClient(app) as client:
        result=client.post("/api/v1/master/license-prices",
                           json={"tier":"ESSENCIAL","monthly_price":"99.90",
                                 "annual_price":"845.23",
                                 "expected_version_id":str(uuid.uuid4()),
                                 "reason":"Revisao comercial documentada"})
    assert result.status_code==409
    assert catalog_db.events==[]


def test_master_price_refuses_invalid_tier_and_reason(catalog_db):
    valid={"monthly_price":"99.90","annual_price":"777.19",
           "expected_version_id":str(catalog_db.version_id),
           "reason":"Revisao comercial documentada"}
    with TestClient(app) as client:
        result=client.post("/api/v1/master/license-prices",
                           json={"tier":"AMPLIADO",**valid})
        reason=client.post("/api/v1/master/license-prices",
                           json={"tier":"ESSENCIAL",**valid,"reason":"curto"})
        annual=client.post("/api/v1/master/license-prices",
                           json={"tier":"ESSENCIAL",**valid,"annual_price":"0.00"})
    assert result.status_code==422
    assert reason.status_code==422
    assert annual.status_code==422
    assert catalog_db.events==[]


@pytest.mark.skipif(os.getenv("FRCAIXINHA_CI_ISOLATED")!="1",
                    reason="Somente banco descartavel GitHub Actions")
def test_catalog_schema_in_disposable_postgres():
    with psycopg.connect(os.environ["CI_ADMIN_DATABASE_URL"]) as db:
        prices=db.execute(
            "SELECT plan_tier,monthly_price,annual_price FROM "
            "public.platform_license_price_versions ORDER BY plan_tier"
        ).fetchall()
        assert prices==[("ESSENCIAL",99.90,999.00),("INTERMEDIARIO",109.90,1099.00)] or (
            len(prices)==2 and prices[0][0]=="ESSENCIAL"
            and str(prices[0][1])=="89.90" and str(prices[0][2])=="899.00"
            and str(prices[1][1])=="109.90" and str(prices[1][2])=="1099.00"
        )
        tables=db.execute(
            "SELECT relname,relrowsecurity,relforcerowsecurity FROM pg_class "
            "WHERE relname IN ('platform_license_plans','platform_license_price_versions')"
        ).fetchall()
        assert len(tables)==2 and all(a and b for _,a,b in tables)
    with psycopg.connect(os.environ["DATABASE_URL"]) as db:
        assert db.execute("SELECT count(*) FROM public.platform_license_price_versions").fetchone()[0]==0
        assert db.execute(
            "SELECT has_table_privilege(current_user,'public.platform_license_price_versions','UPDATE')"
        ).fetchone()[0] is False
