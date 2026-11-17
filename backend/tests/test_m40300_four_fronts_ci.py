"""FR Finance M40300: 4-front integrated source & synthetic regression.

Uses existing FastAPI routers, existing finance oracles, existing synthetic PG
facades and existing identity context. No original PostgreSQL, no real sessions,
no OCI instance, no new database, no real messages or financial effects.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

from fastapi import HTTPException
import pytest

from app.closing_contract_oracle import FinancialEvidence, simulate_contract_closing
from app.member_cycle_rules import CapitalMovement, capital_days_v2
from app.routers.loans import compute_price_schedule
from backend.app.routers import special_credit
from backend.tests.test_m39033_special_credit_route_flow_ci import (
    ADMIN, CAMPAIGN, GRANT, MEMBER_USER, MEMBERSHIP, PATH, RECIPIENT,
    TENANT, OTHER_TENANT, make_client,
)
from backend.tests.test_m39082_special_credit_cycle_actions_ci import (
    PeriodAwareSyntheticRlsDb,
)
from backend.tests.test_annual_closing_contract_ci import (
    run as closing, event as closing_event, member as closing_member,
    A as MEMBER_A, B as MEMBER_B, T as TENANT_A,
)
from backend.tests.test_m29500_m29800_two_tenant_closing_ci import (
    pair, review_two_tenants,
)

ROOT = Path(__file__).resolve().parents[2]
ONE = UUID("00000000-0000-4000-8000-000000000061")


@pytest.fixture(autouse=True)
def sandbox_only_no_real_connections(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("FRCAIXINHA_TEST_AUTH", "1")
    monkeypatch.setenv("FR_FINANCE_SPECIAL_CREDIT_SANDBOX", "YES")
    monkeypatch.setenv("PIX_REAL", "OFF")
    monkeypatch.setenv("PAGAMENTOS_REAIS", "OFF")
    monkeypatch.setattr(special_credit, "settings", SimpleNamespace(
        DATABASE_URL="postgresql://frc_ai_app@127.0.0.1:5433/frcaixinha_aistudio_dev"
    ))
    async def forbidden(*args, **kwargs):
        pytest.fail("M40300 must not access an external or original database")
    monkeypatch.setattr("app.dependencies.asyncpg.connect", forbidden)
    monkeypatch.setattr("app.database.get_db_pool", forbidden)


def test_security_recipient_and_grant_bindings_in_original_router():
    src=(ROOT/"backend/app/routers/special_credit.py").read_text()
    start=src.index('async def member_opportunities(')
    finish=src.index('@router.post("/opportunities/{recipient_id}/reply")')
    read=src[start:finish]
    for required in (
        "g.tenant_id=r.tenant_id", "g.member_id=r.member_id",
        "m.tenant_id=r.tenant_id", "m.user_id=r.user_id",
        "m.role='TENANT_MEMBER'", "m.status='ATIVA'",
        "r.user_id=$2", "g.cycle_id=cy.id",
        "cy.start_date<=CURRENT_DATE", "cy.end_date>=CURRENT_DATE",
    ):
        assert required in read, required
    start=src.index('async def reply(')
    finish=src.index('@router.get("/preferences")')
    sql=src[start:finish]
    for required in (
        "r.response_status='PENDING'", "r.user_id=$4",
        "JOIN public.memberships m ON m.id=g.member_id",
        "g.member_id=r.member_id", "m.tenant_id=$3",
        "m.user_id=$4", "m.role='TENANT_MEMBER'",
        "m.status='ATIVA'", "g.status='ACTIVE'",
        "c.cycle_id=g.cycle_id", "c.expires_at>now()",
        "cy.end_date>=CURRENT_DATE",
        '\"loan_created\":False',
    ):
        assert required in sql, required


@pytest.mark.parametrize("invalid", ("expired", "future", "closed"))
def test_campaign_member_reply_in_inactive_cycle_denied_without_audit(invalid):
    state=PeriodAwareSyntheticRlsDb(invalid)
    client=make_client(state,"TENANT_MEMBER",MEMBER_USER)
    response=client.post(PATH+f"/opportunities/{RECIPIENT}/reply",
                         json={"status":"INTERESTED"})
    assert response.status_code==409
    assert state.recipient["response_status"]=="PENDING"
    assert not state.outbox and not state.audit


def test_revoked_member_cannot_reply_even_with_stale_existing_session():
    class RevokedMembership(PeriodAwareSyntheticRlsDb):
        async def fetchrow(self, query, *args):
            if "UPDATE public.special_credit_recipients r" in query:
                self._record(query)
                assert "m.status='ATIVA'" in query
                assert "m.user_id=$4" in query
                assert "g.member_id=r.member_id" in query
                # Synthetic DB imitates a membership marked inactive since login.
                return None
            return await super().fetchrow(query,*args)
    db=RevokedMembership("current")
    client=make_client(db,"TENANT_MEMBER",MEMBER_USER)
    response=client.post(PATH+f"/opportunities/{RECIPIENT}/reply",
                         json={"status":"INTERESTED"})
    assert response.status_code==409
    assert db.recipient["response_status"]=="PENDING"
    assert not db.audit and not db.outbox


def test_another_tenant_cannot_reply_before_any_sql():
    db=PeriodAwareSyntheticRlsDb("current")
    member=make_client(db,"TENANT_MEMBER",MEMBER_USER,OTHER_TENANT)
    response=member.post(PATH+f"/opportunities/{RECIPIENT}/reply",
                         json={"status":"DECLINED"})
    assert response.status_code==403
    assert db.statements==[]


def test_admin_cannot_replay_member_reply_before_sql():
    db=PeriodAwareSyntheticRlsDb("current")
    admin=make_client(db,"TENANT_ADMIN",ADMIN)
    response=admin.post(PATH+f"/opportunities/{RECIPIENT}/reply",
                        json={"status":"INTERESTED"})
    assert response.status_code==403
    assert db.statements==[]


def test_missing_consent_no_external_delivery_even_for_push():
    db=PeriodAwareSyntheticRlsDb("current")
    db.campaign["status"]="DRAFT"
    client=make_client(db,"TENANT_ADMIN",ADMIN)
    posted=client.post(PATH+f"/campaigns/{CAMPAIGN}/publish")
    assert posted.status_code==200
    assert posted.json()["external_dispatch"] is False
    assert db.outbox==[]
    assert all("public.loans" not in sql.lower() for sql in db.statements)


def test_duplicate_reply_rejected_no_new_financial_effects():
    db=PeriodAwareSyntheticRlsDb("current")
    client=make_client(db,"TENANT_MEMBER",MEMBER_USER)
    first=client.post(PATH+f"/opportunities/{RECIPIENT}/reply",
                      json={"status":"DECLINED"})
    second=client.post(PATH+f"/opportunities/{RECIPIENT}/reply",
                       json={"status":"INTERESTED"})
    assert first.status_code==200 and first.json()["loan_created"] is False
    assert second.status_code==409
    assert db.recipient["response_status"]=="DECLINED"
    assert db.outbox==[]
    assert len(db.audit)==1


def test_certain_future_capital_events_cannot_be_ignored_silently():
    start,end=date(2027,1,1),date(2028,1,1)
    for effective in (
        datetime(2028,1,1,3,tzinfo=timezone.utc),
        datetime(2028,5,10,12,tzinfo=timezone.utc),
    ):
        future=CapitalMovement(TENANT_A,MEMBER_A,effective,15000,ONE)
        with pytest.raises(ValueError,match="Movimento fora do ciclo"):
            capital_days_v2(TENANT_A,MEMBER_A,(future,),
                            start=start,end_exclusive=end)


@pytest.mark.parametrize("principal,monthly,term", [
    (Decimal(principal),Decimal(rate),term)
    for principal in ("500.00","150.00","1050.39","49999.00")
    for rate in ("0","0.01","0.10","0.20")
    for term in (1,2,3,4,5,6)
])
def test_price_schedule_conserves_principal_and_cents_without_money(
    principal,monthly,term
):
    result=compute_price_schedule(principal,term,monthly)
    assert result.schedule[-1].closing_balance == Decimal(0)
    assert sum((r.amortization_portion for r in result.schedule),Decimal(0)) == principal
    assert sum((r.interest_portion for r in result.schedule),Decimal(0)) == result.total_interest
    assert result.total_payable == principal+result.total_interest
    assert all(x.opening_balance>=0 and x.amortization_portion>=0
               and x.closing_balance>=0 for x in result.schedule)


@pytest.mark.parametrize("income,adjustment", [
    (101,0),(101,1),(101,57),(101,201),
    (999,0),(999,1),(999,500),(10000,9999),
])
def test_closing_replay_rounding_and_expenses_no_double_credit(income,adjustment):
    evidence=(closing_event("REALIZED_REVENUE",income,1),
              closing_event("APPROVED_ADJUSTMENT",adjustment,2),
              closing_event("CAPITAL_PRINCIPAL",5000000,3))
    members=(closing_member(MEMBER_A,"1"),closing_member(MEMBER_B,"1"))
    a=closing(evidence=evidence,reviews=members)
    b=closing(evidence=tuple(reversed(evidence)),reviews=tuple(reversed(members)))
    assert a==b
    assert a.net_result_cents==income-adjustment
    assert a.distributable_profit_cents==max(income-adjustment,0)
    assert (a.admin_remuneration_cents+
            sum(x.final_cents for x in a.member_shares)+
            a.reserved_undistributed_cents)==a.distributable_profit_cents
    assert not a.pix_enabled and not a.financial_closing_authorized
    with pytest.raises(ValueError,match="Duplicata"):
        closing(evidence=evidence+(evidence[0],))


@pytest.mark.parametrize("year_shift", (0,1,2))
def test_two_tenant_preview_replay_is_deterministic_and_non_authorizing(year_shift):
    a,b=pair()
    if year_shift:
        # Reuse existing financial oracle, change only synthetic profit evidence.
        a=replace(a,evidence=tuple(
            replace(e,amount_cents=e.amount_cents+year_shift)
            if e.kind=="REALIZED_REVENUE" else e for e in a.evidence))
    first=review_two_tenants((a,b))
    second=review_two_tenants((a,b))
    assert first==second
    assert first.status in ("OFFLINE_PREVIEW_NOT_SETTLED","REVIEW_HOLD_NO_SETTLEMENT")
    assert first.admin_cents+first.allocated_to_members_cents+first.reserved_cents==first.profit_cents
    assert first.actual_provider_reconciled is False
    assert first.pix_authorized is False


def test_no_extra_backend_migrations_or_external_effects():
    source=(ROOT/"backend/app/routers/special_credit.py").read_text()
    assert "BLOCKED_EXTERNAL" in source
    assert '"external_dispatch":False' in source
    assert 'INSERT INTO public.loans' not in source
    assert 'pg_notify(' not in source
