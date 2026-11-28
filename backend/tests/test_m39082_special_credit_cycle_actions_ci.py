"""M39082: closed/future/expired cycles cannot publish, reply, or simulate.

No original PostgreSQL, no provider, no external send. A synthetic DB strictly
checks the SQL date/status clauses and imitates PostgreSQL filtering.
"""
from datetime import datetime, timedelta, timezone

import pytest

from backend.app.routers import special_credit as module
from backend.tests.test_m39033_special_credit_route_flow_ci import (
    ADMIN, CAMPAIGN, CYCLE, GRANT, MEMBER_USER, MEMBERSHIP, PATH, RECIPIENT,
    TENANT, SyntheticRlsDb, make_client,
)


class PeriodAwareSyntheticRlsDb(SyntheticRlsDb):
    def __init__(self, period: str):
        super().__init__()
        self.period = period
        expires_at = datetime.now(timezone.utc) + timedelta(days=10)
        self.grant = {
            "id": GRANT, "tenant_id": TENANT, "cycle_id": CYCLE,
            "member_id": MEMBERSHIP, "status": "ACTIVE",
            "ceiling_brl": "5000.00", "expires_at": expires_at,
        }
        self.campaign = {
            "id": CAMPAIGN, "tenant_id": TENANT, "cycle_id": CYCLE,
            "status": "PUBLISHED", "title": "Oportunidade de teste",
            "body": "Mensagem interna para testes seguros.",
            "expires_at": expires_at,
        }
        self.recipient = {
            "id": RECIPIENT, "tenant_id": TENANT,
            "user_id": MEMBER_USER, "campaign_id": CAMPAIGN,
            "grant_id": GRANT, "member_id": MEMBERSHIP,
            "response_status": "PENDING",
        }

    @staticmethod
    def _assert_date_gate(query: str, alias: str) -> None:
        for condition in (
            f"{alias}.status='ABERTO'",
            f"{alias}.start_date<=CURRENT_DATE",
            f"{alias}.end_date>=CURRENT_DATE",
        ):
            assert condition in query, f"Missing cycle guard: {condition}"

    async def fetchrow(self, query, *args):
        if "FROM public.special_credit_campaigns c" in query and "FOR UPDATE OF c" in query:
            self._record(query)
            self._assert_date_gate(query, "cy")
            assert "cy.id=c.cycle_id" in query
            return self.campaign if self.period == "current" else None
        if "UPDATE public.special_credit_recipients r" in query:
            self._assert_date_gate(query, "cy")
            assert "cy.id=c.cycle_id" in query
            if self.period != "current":
                self._record(query)
                return None
        if "SELECT g.id,g.status,g.expires_at,g.ceiling_brl" in query:
            self._record(query)
            self._assert_date_gate(query, "c")
            assert "JOIN public.cycles c ON c.id=g.cycle_id" in query
            return None  # Never run pricing on a synthetic grant.
        return await super().fetchrow(query, *args)

    async def fetch(self, query, *args):
        if "SELECT r.id AS recipient_id,r.response_status,c.id AS campaign_id" in query:
            self._assert_date_gate(query, "cy")
            assert "cy.id=c.cycle_id" in query
            assert "g.cycle_id=cy.id" in query
            if self.period != "current":
                self._record(query)
                return []
        return await super().fetch(query, *args)


@pytest.fixture(autouse=True)
def offline_only(monkeypatch):
    from types import SimpleNamespace
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("FRCAIXINHA_TEST_AUTH", "1")
    monkeypatch.setenv("FR_FINANCE_SPECIAL_CREDIT_SANDBOX", "YES")
    monkeypatch.setattr(module, "settings", SimpleNamespace(
        DATABASE_URL="postgresql://frc_ai_app@127.0.0.1:5433/frcaixinha_aistudio_dev"
    ))


@pytest.mark.parametrize("period", ["closed", "future", "expired"])
def test_inactive_cycle_blocks_all_existing_campaign_actions(period):
    db = PeriodAwareSyntheticRlsDb(period)
    admin = make_client(db, "TENANT_ADMIN", ADMIN)
    member = make_client(db, "TENANT_MEMBER", MEMBER_USER)

    assert admin.post(PATH + f"/campaigns/{CAMPAIGN}/publish").status_code == 409
    response = member.get(PATH + "/opportunities")
    assert response.status_code == 200
    assert response.json() == []
    response = member.post(PATH + f"/opportunities/{RECIPIENT}/reply",
                           json={"status": "INTERESTED"})
    assert response.status_code == 409
    response = member.post(PATH + "/simulate",
                           json={"grant_id": str(GRANT),
                                 "principal": "1000.00", "term_months": 2})
    assert response.status_code == 403
    assert db.recipient["response_status"] == "PENDING"
    assert db.campaign["status"] == "PUBLISHED"
    assert not db.audit and not db.outbox


def test_current_cycle_still_allows_internal_view_and_opt_in_reply():
    db = PeriodAwareSyntheticRlsDb("current")
    member = make_client(db, "TENANT_MEMBER", MEMBER_USER)
    opportunities = member.get(PATH + "/opportunities")
    assert opportunities.status_code == 200
    assert opportunities.json()[0]["response_status"] == "PENDING"
    reply = member.post(PATH + f"/opportunities/{RECIPIENT}/reply",
                        json={"status": "DECLINED"})
    assert reply.status_code == 200
    assert reply.json() == {"status": "DECLINED", "loan_created": False}
    assert not db.outbox
    assert all("public.loans" not in sql.lower() for sql in db.statements)
