"""FR Finance M39033 — fluxo FastAPI administração/membro 100% sintético.

CI only: FastAPI TestClient, conexão RLS simulada, sem PG18 original,
sem SMTP, FCM, WhatsApp, SMS, PIX, reservas ou desembolso.
A integração SQL real é testada separadamente em PostgreSQL 18 descartável.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.dependencies import AuthenticatedSession
from backend.app.routers import special_credit as router

TENANT = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
OTHER_TENANT = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
ADMIN = UUID("11111111-1111-4111-8111-111111111111")
MEMBER_USER = UUID("22222222-2222-4222-8222-222222222222")
MEMBERSHIP = UUID("aaaaeeee-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
CYCLE = UUID("aaaacccc-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
GRANT = UUID("a1111111-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
CAMPAIGN = UUID("a2222222-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
RECIPIENT = UUID("a3333333-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
PATH = f"/api/v1/tenants/{TENANT}/special-credit"


class SyntheticRlsDb:
    """O teste deve falhar se as rotas executarem SQL inesperada."""

    def __init__(self):
        self.grant = None
        self.campaign = None
        self.recipient = None
        self.prefs = {}
        self.outbox = []
        self.audit = []
        self.statements = []

    def _record(self, query):
        self.statements.append(query)
        for forbidden in (
            "public.loans", "public.loan_payments", "public.pix_payment_intents",
            "pg_sleep", "http", "pg_notify"
        ):
            assert forbidden not in query.lower(), f"Operação inesperada: {forbidden}"

    async def fetchval(self, query, *args):
        self._record(query)
        if "SELECT admin_user_id FROM public.tenants" in query:
            return ADMIN
        if "SELECT EXISTS(SELECT 1 FROM public.memberships" in query:
            return args == (TENANT, MEMBER_USER)
        if "SELECT count(*) FROM public.special_credit_recipients" in query:
            return 0
        raise AssertionError("fetchval SQL inesperado: " + query)

    async def fetchrow(self, query, *args):
        self._record(query)
        if "SELECT id,end_date FROM public.cycles" in query:
            return {"id": CYCLE,
                    "end_date": (datetime.now(timezone.utc) + timedelta(days=90)).date()}
        if "SELECT id,tenant_id,status,role FROM public.memberships" in query:
            return ({"id": MEMBERSHIP, "tenant_id": TENANT,
                     "status": "ATIVA", "role": "TENANT_MEMBER"}
                    if args == (MEMBERSHIP, TENANT) else None)
        if "INSERT INTO public.special_credit_grants" in query:
            if self.grant is not None:
                return None
            self.grant = {
                "id": GRANT, "tenant_id": args[0], "cycle_id": args[1],
                "member_id": args[2], "created_by": args[3],
                "ceiling_brl": args[4], "reason": args[5], "expires_at": args[6],
                "request_id": args[7], "status": "ACTIVE",
            }
            return self.grant
        if "FROM public.special_credit_grants" in query and "request_id=$3" in query:
            return self.grant if self.grant and (
                self.grant["tenant_id"], self.grant["created_by"],
                self.grant["request_id"], self.grant["member_id"]
            ) == args else None
        if "INSERT INTO public.special_credit_campaigns" in query:
            if self.campaign is not None:
                return None
            self.campaign = {
                "id": CAMPAIGN, "tenant_id": args[0], "cycle_id": args[1],
                "created_by": args[2], "title": args[3], "body": args[4],
                "expires_at": args[5], "request_id": args[6], "status": "DRAFT",
            }
            return {"id": CAMPAIGN}
        if "FROM public.special_credit_campaigns" in query and "request_id=$3" in query:
            return self.campaign
        if "FROM public.special_credit_campaigns" in query and "FOR UPDATE" in query:
            return self.campaign if self.campaign and args==(CAMPAIGN,TENANT) else None
        if "UPDATE public.special_credit_recipients r" in query:
            if (self.recipient and self.recipient["response_status"] == "PENDING"
                    and args[1:] == (RECIPIENT, TENANT, MEMBER_USER)
                    and self.campaign and self.campaign["status"]=="PUBLISHED"
                    and self.grant and self.grant["status"]=="ACTIVE"):
                self.recipient["response_status"] = args[0]
                return {"id": RECIPIENT}
            return None
        raise AssertionError("fetchrow SQL inesperado: " + query)

    async def fetch(self, query, *args):
        self._record(query)
        if "SELECT g.id,g.member_id,m.user_id,g.expires_at,g.status" in query:
            if self.grant and args==(TENANT,CYCLE,[GRANT]):
                return [{"id":GRANT,"member_id":MEMBERSHIP,"user_id":MEMBER_USER,
                         "expires_at":self.grant["expires_at"],
                         "status":self.grant["status"]}]
            return []
        if "SELECT grant_id FROM public.special_credit_recipients" in query:
            return [{"grant_id":GRANT}] if self.recipient else []
        if "SELECT r.id AS recipient_id,r.response_status,c.id AS campaign_id" in query:
            if self.campaign and self.campaign["status"]=="PUBLISHED" and (
                args==(TENANT,MEMBER_USER)) and self.grant["status"]=="ACTIVE":
                return [{
                    "recipient_id": RECIPIENT,
                    "response_status": self.recipient["response_status"],
                    "campaign_id": CAMPAIGN, "title":self.campaign["title"],
                    "body":self.campaign["body"], "expires_at":self.campaign["expires_at"],
                    "grant_id":GRANT, "ceiling_brl":self.grant["ceiling_brl"],
                }]
            return []
        if "SELECT channel,opted_in FROM public.special_credit_preferences" in query:
            return [{"channel":c,"opted_in":b} for c,b in self.prefs.items()]
        raise AssertionError("fetch SQL inesperado: " + query)

    async def execute(self, query, *args):
        self._record(query)
        if "INSERT INTO public.special_credit_audit" in query:
            self.audit.append(tuple(args))
            return "INSERT 0 1"
        if "INSERT INTO public.special_credit_recipients" in query:
            self.recipient = {
                "id": RECIPIENT, "tenant_id":args[0], "campaign_id":args[1],
                "grant_id":args[2], "member_id":args[3], "user_id":args[4],
                "response_status":"PENDING",
            }
            return "INSERT 0 1"
        if "UPDATE public.special_credit_campaigns" in query:
            assert self.campaign and args==(CAMPAIGN,TENANT)
            self.campaign["status"]="PUBLISHED"
            return "UPDATE 1"
        if "INSERT INTO public.special_credit_outbox" in query:
            assert self.campaign and self.campaign["status"]=="PUBLISHED"
            self.outbox = [
                {"channel":c,"state":"BLOCKED_EXTERNAL"}
                for c,opted_in in self.prefs.items() if opted_in
            ]
            return f"INSERT 0 {len(self.outbox)}"
        if "INSERT INTO public.special_credit_preferences" in query:
            assert args[0:2] == (TENANT,MEMBER_USER)
            self.prefs[args[2]]=args[3]
            return "INSERT 0 1"
        raise AssertionError("execute SQL inesperado: " + query)


def make_client(db, role, user, tenant=TENANT):
    app=FastAPI()
    app.include_router(router.router, prefix="/api/v1")
    session=AuthenticatedSession(str(user),role,str(tenant),
                                 "synthetic@example.invalid",
                                 "Identidade CI simulada",False)
    app.dependency_overrides[router.get_current_session]=lambda:session
    app.dependency_overrides[router.get_rls_db_connection]=lambda:db
    return TestClient(app)


def test_admin_member_campaign_sandbox_happy_path(monkeypatch):
    """Roteador real + estado sintético. NÃO equivale a E2E PG18 original."""
    monkeypatch.setenv("ENVIRONMENT","development")
    monkeypatch.setenv("FRCAIXINHA_TEST_AUTH","1")
    monkeypatch.setenv("FR_FINANCE_SPECIAL_CREDIT_SANDBOX","YES")
    monkeypatch.setattr(router,"settings",SimpleNamespace(
        DATABASE_URL="postgresql://frc_ai_app@127.0.0.1:5433/frcaixinha_aistudio_dev"
    ))
    state=SyntheticRlsDb()
    admin=make_client(state,"TENANT_ADMIN",ADMIN)
    member=make_client(state,"TENANT_MEMBER",MEMBER_USER)
    member_other_tenant=make_client(state,"TENANT_MEMBER",MEMBER_USER,OTHER_TENANT)

    expiration_grant=(datetime.now(timezone.utc)+timedelta(days=7)).isoformat()
    expiration_campaign=(datetime.now(timezone.utc)+timedelta(days=2)).isoformat()
    grant_payload={
        "member_ids":[str(MEMBERSHIP)],"ceiling_brl":"5000.00",
        "expires_at":expiration_grant,
        "reason":"Justificativa de elegibilidade exclusivamente demonstrativa.",
        "request_id":"00000000-0000-4000-8000-000000000001",
    }
    assert member.post(PATH+"/grants",json=grant_payload).status_code==403
    assert member_other_tenant.get(PATH+"/opportunities").status_code==403
    assert not state.statements  # Nenhuma operação no banco para acessos proibidos.

    created=admin.post(PATH+"/grants",json=grant_payload)
    assert created.status_code==200,created.text
    assert created.json()["real_credit_enabled"] is False
    assert created.json()["grants"][0]["grant_id"]==str(GRANT)
    assert admin.post(PATH+"/grants",json=grant_payload).status_code==200
    assert len([e for e in state.audit if e[4]=="GRANT_CREATED"])==1

    campaign_payload={
        "grant_ids":[str(GRANT)],"title":"Oportunidade para simulacao",
        "body":"Nova oportunidade demonstrativa para consulta no FR Finance.",
        "expires_at":expiration_campaign,
        "request_id":"00000000-0000-4000-8000-000000000002",
    }
    created=admin.post(PATH+"/campaigns",json=campaign_payload)
    assert created.status_code==200,created.text
    assert created.json()["status"]=="DRAFT"
    assert admin.post(PATH+"/campaigns",json=campaign_payload).json()["created"] is False

    no_optin=admin.post(PATH+f"/campaigns/{CAMPAIGN}/publish")
    assert no_optin.status_code==200,no_optin.text
    assert no_optin.json()=={
        "status":"PUBLISHED","in_app":True,"external_dispatch":False
    }
    assert not state.outbox  # Sem opt-in, NENHUMA entrada de canal externo.

    opportunities=member.get(PATH+"/opportunities")
    assert opportunities.status_code==200,opportunities.text
    assert opportunities.json()[0]["response_status"]=="PENDING"
    assert opportunities.json()[0]["ceiling_brl"]=="5000.00"
    reply=member.post(PATH+f"/opportunities/{RECIPIENT}/reply",
                      json={"status":"INTERESTED"})
    assert reply.status_code==200,reply.text
    assert reply.json()=={"status":"INTERESTED","loan_created":False}
    assert member.post(PATH+f"/opportunities/{RECIPIENT}/reply",
                       json={"status":"DECLINED"}).status_code==409
    assert len([e for e in state.audit if e[4]=="OPPORTUNITY_INTERESTED"])==1

    # Preferência de marketing posterior não transmite nada retroativamente.
    consent=member.post(PATH+"/preferences",
                        json={"channel":"PUSH","opted_in":True})
    assert consent.status_code==200,consent.text
    assert consent.json()["external_dispatch"] is False
    assert state.outbox == []
    prefs=member.get(PATH+"/preferences").json()
    assert prefs["preferences"] == {
        "PUSH":True,"EMAIL":False,"WHATSAPP":False,"SMS":False
    }
    assert prefs["external_dispatch"] is False
    assert all("INSERT INTO public.loans" not in q for q in state.statements)
