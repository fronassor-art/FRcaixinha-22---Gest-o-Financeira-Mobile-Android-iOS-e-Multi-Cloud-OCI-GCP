"""FR Finance M39067 — contract tests no real users, DB or money."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
import uuid
import json
import subprocess

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import app
from app.database import get_rls_db_connection
from app.dependencies import require_master, get_current_session, AuthenticatedSession
from app.routers.saas_promotions import (
    SaaSPromotionDraft, SaaSPromotionTransition,
    create_master_promotion_draft, transition_master_promotion,
)

ROOT = Path(__file__).resolve().parents[2]
USER = str(uuid.uuid4())
TENANT = str(uuid.uuid4())
VERSION = uuid.uuid4()
CAMPAIGN = uuid.uuid4()
NOW = datetime.now(timezone.utc)
START = NOW + timedelta(days=2)
END = NOW + timedelta(days=12)


class FakePromotionConnection:
    def __init__(self, state="DRAFT", revision=1, version=VERSION):
        self.state=state
        self.revision=revision
        self.version=version
        self.writes=[]
        self.calls=[]
        self.current = {
            "campaign_id": CAMPAIGN, "revision": revision,
            "plan_tier": "ESSENCIAL", "billing_period": "ANNUAL",
            "base_price_version_id": version, "promotional_price": Decimal("599.97"),
            "audience": "NEW_ADMIN_ONLY",
            "title": "Campanha anual", "benefit_description": "Oferta temporária SaaS",
            "starts_at": START,"ends_at": END,"state":state,
        }

    async def fetchval(self, sql, *params):
        self.calls.append((sql,params))
        if "to_regclass" in sql: return True
        if "pg_advisory_xact_lock" in sql: return None
        if "SELECT EXISTS" in sql: return False
        raise AssertionError(sql)

    async def fetchrow(self, sql, *params):
        self.calls.append((sql,params))
        if "FROM public.platform_license_plans p" in sql:
            return {"status":"ACTIVE","version_id":self.version,
                    "plan_tier":"ESSENCIAL"}
        if "WHERE campaign_id=$1 ORDER BY revision DESC" in sql:
            return dict(self.current)
        if "INSERT INTO public.platform_saas_promotion_revisions" in sql:
            self.writes.append(("promotion",params))
            if len(params)==11: # draft fields
                return {**self.current,"campaign_id":params[0],
                        "revision":1,"promotional_price":params[4],
                        "starts_at":params[7],"ends_at":params[8],
                        "state":"DRAFT"}
            return {**self.current,"revision":params[1],"state":params[-3]}
        raise AssertionError(sql)

    async def fetch(self, sql, *params):
        self.calls.append((sql,params))
        if "frfinance_saas_new_admin_published_promotions" in sql:
            return [{k:self.current[k] for k in
                     ("campaign_id","plan_tier","billing_period","promotional_price",
                      "title","benefit_description","starts_at","ends_at","revision",
                      "base_price_version_id")}]
        if "DISTINCT ON (campaign_id)" in sql:
            return [dict(self.current)]
        raise AssertionError(sql)

    async def execute(self, sql, *params):
        self.calls.append((sql,params))
        assert "INSERT INTO public.audit_events" in sql
        self.writes.append(("audit",params))


@pytest.fixture()
def fake_db():
    fake=FakePromotionConnection()
    def master():
        return AuthenticatedSession(USER,"MASTER",None,"ci@example.invalid",
                                    "CI Master",True)
    app.dependency_overrides[require_master] = master
    app.dependency_overrides[get_rls_db_connection] = lambda: fake
    try: yield fake
    finally: app.dependency_overrides.clear()


def draft_payload():
    return {
        "plan_tier":"ESSENCIAL","billing_period":"ANNUAL",
        "base_price_version_id":str(VERSION),"promotional_price":"599.97",
        "title":"Campanha anual",
        "benefit_description":"Oferta temporária SaaS",
        "starts_at":START.isoformat(),"ends_at":END.isoformat(),
        "reason":"Campanha de boas-vindas ao administrador",
    }


def test_create_draft_master_requires_price_version_and_audit(fake_db):
    with TestClient(app) as c:
        res=c.post("/api/v1/master/saas-promotions/draft",json=draft_payload())
    assert res.status_code==201,res.text
    assert res.json()["status"]=="DRAFT_PERSISTED_NO_BILLING"
    assert res.json()["promotion"]["state"]=="DRAFT"
    assert [x[0] for x in fake_db.writes]==["promotion","audit"]
    assert len([x for x in fake_db.calls if "INSERT INTO public.saas_payment" in x[0]])==0


@pytest.mark.parametrize("changes",[
    {"promotional_price":"0"},
    {"promotional_price":"1.001"},
    {"plan_tier":"AMPLIADO"},
    {"billing_period":"WEEKLY"},
    {"reason":"curto"},
    {"benefit_description":"curto"},
    {"starts_at":END.isoformat(),"ends_at":START.isoformat()},
    {"starts_at":"2026-12-01T00:00:00","ends_at":"2026-12-31T00:00:00"},
])
def test_invalid_drafts_fail_before_db_write(fake_db,changes):
    data={**draft_payload(),**changes}
    with TestClient(app) as c:
        response=c.post("/api/v1/master/saas-promotions/draft",json=data)
    assert response.status_code==422
    assert fake_db.writes==[]


def test_stale_catalog_prevents_campaign(fake_db):
    with TestClient(app) as c:
        resp=c.post("/api/v1/master/saas-promotions/draft",
                    json={**draft_payload(),"base_price_version_id":str(uuid.uuid4())})
    assert resp.status_code==409
    assert fake_db.writes==[]


def test_publish_creates_new_revision_not_update(fake_db):
    payload={
        "campaign_id":str(CAMPAIGN),"expected_revision":1,
        "action":"PUBLISH","reason":"Publicar campanha comercial autorizada",
    }
    with TestClient(app) as c:
        resp=c.post("/api/v1/master/saas-promotions/transition",json=payload)
    assert resp.status_code==200,resp.text
    assert resp.json()["promotion"]["revision"]==2
    assert resp.json()["promotion"]["state"]=="PUBLISHED"
    assert [x[0] for x in fake_db.writes]==["promotion","audit"]
    assert not any("UPDATE public.platform_saas_promotion_revisions" in x[0]
                   for x in fake_db.calls)


def test_concurrent_stale_revision_rejected(fake_db):
    with TestClient(app) as c:
        resp=c.post("/api/v1/master/saas-promotions/transition",
                    json={"campaign_id":str(CAMPAIGN),"expected_revision":2,
                          "action":"PUBLISH","reason":"Publicação comercial documentada"})
    assert resp.status_code==409
    assert fake_db.writes==[]


def test_cancel_creates_immutable_revision(fake_db):
    fake_db.state="PUBLISHED"
    fake_db.current["state"]="PUBLISHED"
    with TestClient(app) as c:
        resp=c.post("/api/v1/master/saas-promotions/transition",
                    json={"campaign_id":str(CAMPAIGN),"expected_revision":1,
                          "action":"CANCEL","reason":"Cancelar campanha antes da vigência"})
    assert resp.status_code==200,resp.text
    assert resp.json()["promotion"]["state"]=="CANCELED"
    assert [x[0] for x in fake_db.writes]==["promotion","audit"]


def test_listing_master_and_no_pseudo_prices(fake_db):
    with TestClient(app) as c:
        resp=c.get("/api/v1/master/saas-promotions")
    assert resp.status_code==200,resp.text
    assert resp.json()["promotions"][0]["campaign_id"]==str(CAMPAIGN)
    assert resp.json()["billing"]=="OFF_NO_PROVIDER_NO_CHARGE"


def test_tenant_admin_read_only_and_mismatch_denied(fake_db):
    def admin():
        return AuthenticatedSession(USER,"TENANT_ADMIN",TENANT,
                                    "ci@example.invalid","CI Admin",False)
    app.dependency_overrides[get_current_session]=admin
    try:
        with TestClient(app) as c:
            ok=c.get(f"/api/v1/tenants/{TENANT}/saas-promotions")
            bad=c.get(f"/api/v1/tenants/{uuid.uuid4()}/saas-promotions")
        assert ok.status_code==200,ok.text
        assert ok.json()["scope"]=="ELIGIBLE_NEW_TENANT_ADMIN_ONLY"
        assert ok.json()["offers"][0]["promotional_price"]=="599.97"
        assert bad.status_code==403
        assert fake_db.writes==[]
    finally:
        app.dependency_overrides.pop(get_current_session,None)


def test_member_and_master_cannot_use_tenant_offers(fake_db):
    for role,master in (("TENANT_MEMBER",False),("MASTER",True)):
        def wrong(role=role,master=master):
            return AuthenticatedSession(USER,role,None if master else TENANT,
                                        "ci@example.invalid","CI",master)
        app.dependency_overrides[get_current_session]=wrong
        try:
            with TestClient(app) as c:
                resp=c.get(f"/api/v1/tenants/{TENANT}/saas-promotions")
            assert resp.status_code==403
            assert fake_db.writes==[]
        finally: app.dependency_overrides.pop(get_current_session,None)


def test_schema_and_docs_policy_registered():
    path=ROOT/"backend/migrations/113_frfinance_saas_new_admin_promotions.sql"
    sql=path.read_text()
    catalog=json.loads((ROOT/"backend/migration_catalog_ai_studio.json").read_text())
    item=next(x for x in catalog["entries"] if x["id"]=="migrations:113")
    assert item["source_path"]==str(path.relative_to(ROOT))
    assert item["source_blob_sha"]==subprocess.check_output(
        ["git","hash-object",str(path)],text=True).strip()
    for marker in (
        "CREATE TABLE public.platform_saas_promotion_revisions",
        "FORCE ROW LEVEL SECURITY","SECURITY DEFINER",
        "NEW_ADMIN_ONLY", "UNIQUE(campaign_id,revision)",
        "frfinance_saas_new_admin_published_promotions",
        "GRANT INSERT(", "REVOKE ALL ON",
        "CREATE TRIGGER frfinance_guard_saas_promo_append",
        "M39067_BASE_PRICE_VERSION_PLAN_MISMATCH",
        "M39067_REVISION_NOT_SEQUENTIAL",
        "M39067_REVIEW_CANNOT_REWRITE_COMMERCIAL_SNAPSHOT",
        "M39067_INVALID_CAMPAIGN_TRANSITION",
        "M39067_OVERLAPPING_PUBLISHED_PROMOTION",
        "SECURITY DEFINER SET search_path=pg_catalog,pg_temp",
    ):
        assert marker in sql
    for forbidden in ("CREATE DATABASE", "ALTER ROLE", "UPDATE public.",
                      "DELETE FROM public.", "pg_ctl", "pix_payment_intents"):
        assert forbidden not in sql
    docs=(ROOT/"docs/CONTRATO_TECNICO_MESTRE_FR_FINANCE_AI_STUDIO.md").read_text()
    notebook=(ROOT/"docs/CADERNO_MESTRE_FR_FINANCE_AI_STUDIO.md").read_text()
    assert "CTM-SAAS-01" in docs and "CTM-SAAS-09" in docs
    assert "SQL112" in notebook and "SQL113" in notebook
    assert "10 × mensal" in docs
    assert "não" in docs.lower()


def test_combined_migration_replaces_standalone_apply():
    runner=(ROOT/"backend/scripts/frfinance_m39067_apply_saas_prices_promotions_pg18.py").read_text()
    old=(ROOT/"backend/scripts/frfinance_m39066_master_prices_sql112_termux.py").read_text()
    assert "SQL113_BLOB" in runner
    assert "conn.execute(ddl112)" in runner
    assert "conn.execute(ddl113)" in runner
    assert "with conn.transaction():" in runner
    assert "SQL113_RLS_PRIVILEGES_TRIGGER_OR_FUNCTION_UNSAFE" in runner
    assert "APLICAR_SQL112_113_FR_FINANCE" in runner
    assert "BLOCKED_SUPERSEDED_USE_M39067_SQL112_113_ATOMIC" in old
    for denied in ("createdb", "dropdb", "subprocess.Popen(", "os.kill("):
        assert denied not in runner


def test_no_real_dispatch_or_payments_from_routes():
    backend=(ROOT/"backend/app/routers/saas_promotions.py").read_text()
    assert "Depends(require_master)" in backend
    assert "Depends(get_current_session)" in backend
    assert "pg_advisory_xact_lock" in backend
    assert "public.audit_events" in backend
    assert "saas_payment_intents" not in backend
    assert "mercadopago" not in backend.lower()
    assert "requests.post(" not in backend
    assert "smtplib" not in backend
    assert "update public.platform_saas_promotion_revisions" not in backend.lower()
