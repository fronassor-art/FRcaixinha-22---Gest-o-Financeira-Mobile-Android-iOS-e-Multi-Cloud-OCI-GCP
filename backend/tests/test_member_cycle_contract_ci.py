"""M401+ — Mais de 150 testes de fatos, bloqueio condicionado e saída.

NÃO grava PostgreSQL, NÃO habilita rota, NÃO cria penalidade de contribuição.
Fonte AI Studio: Caderno Mestre 6.2–6.6, 8.6, 10.1–10.6.
"""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID
from zoneinfo import ZoneInfo
import pytest

from app.member_cycle_rules import (
    MonthlyDueProof, CapitalMovement, ExitRequest, first_three_unpaid_trigger,
    capital_days_v2, review_member_cycle,
)

T = UUID("00000000-0000-4000-8000-0000000000a1")
M = UUID("00000000-0000-4000-8000-0000000000a2")
X = UUID("00000000-0000-4000-8000-0000000000b1")
Y = UUID("00000000-0000-4000-8000-0000000000b2")
START, END = date(2027,1,1), date(2028,1,1)
LOCAL=ZoneInfo("America/Belem")


def due(m, *, settled=None, paid=0, tenant=T, member=M):
    value=15000
    return MonthlyDueProof(
        tenant,member,f"2027-{m:02d}",date(2027,m,10),
        value, paid, settled,f"CI-PROOF-MONTH-{m:02d}"
    )


def stamp(day, hour=12):
    return datetime(day.year,day.month,day.day,hour,tzinfo=LOCAL)


def flow(day, cents, ident=1, tenant=T, member=M):
    return CapitalMovement(tenant,member,stamp(day),cents,UUID(int=ident))


def run_review(*, as_of=date(2027,3,11), dues=None, movements=(),
               owner=True, legal=False, history=True, exit=None, tenant=T, member=M):
    return review_member_cycle(
        tenant,member,as_of=as_of,
        dues=(due(1),due(2),due(3)) if dues is None else dues,
        movements=movements,
        cycle_start=START,cycle_end_exclusive=END,
        owner_box=owner,legal_gate_approved=legal,
        history_attested=history,exit_request=exit,
    )


# 124 independently executed dates: three consecutive obligations are past due
# from 11 March; passage of "90 days" is NOT equivalent to three installments.
@pytest.mark.parametrize("age",range(-3,121))
def test_124_calendar_boundaries_for_unpaid_trigger(age):
    d=date(2027,3,10)+timedelta(days=age)
    trigger=first_three_unpaid_trigger(T,M,(due(1),due(2),due(3)),d)
    assert trigger==(date(2027,3,11) if age>=1 else None)


@pytest.mark.parametrize("first_paid_day",[
    date(2027,1,10)+timedelta(days=n) for n in range(0,70,3)
])
def test_24_variations_of_first_obligation_regularized_before_triad(first_paid_day):
    settled_first=due(1,settled=first_paid_day,paid=15000)
    result=first_three_unpaid_trigger(
        T,M,(settled_first,due(2),due(3)),date(2027,3,11))
    assert (result is None)==(first_paid_day<=date(2027,3,10))


@pytest.mark.parametrize("third_payment_offset",range(-8,9))
def test_17_payment_dates_at_third_due( third_payment_offset):
    settled=date(2027,3,10)+timedelta(days=third_payment_offset)
    result=first_three_unpaid_trigger(
        T,M,(due(1),due(2),due(3,paid=15000,settled=settled)),
        date(2027,4,30))
    assert (result is not None)==(third_payment_offset>0)


def test_90_overdue_days_alone_does_not_invent_three_consecutive_months():
    # 91 days on January's obligation is a different fact from 3 months.
    review=run_review(as_of=date(2027,4,11),dues=(due(1),),legal=True)
    assert review.longest_overdue_days>=90
    assert review.historic_three_unpaid_on is None
    assert review.profit_eligible is True


def test_three_months_trigger_before_ninety_days_for_oldest_obligation():
    review=run_review(legal=True)
    assert review.historic_three_unpaid_on==date(2027,3,11)
    assert review.longest_overdue_days<90
    assert review.current_consecutive_unpaid==3
    assert review.profit_eligible is False
    assert review.status=="OWNER_CYCLE_PROFIT_EXCLUDED"
    assert review.capital_days_weight==0
    assert not review.may_close_cycle and not review.may_pay_real_money


def test_owner_special_clause_without_legal_gate_does_not_auto_confiscate():
    r=run_review(legal=False,movements=(flow(date(2027,1,10),15000),))
    assert r.historic_three_unpaid_on==date(2027,3,11)
    assert r.status=="OWNER_EXCLUSION_WAITING_LEGAL_REVIEW"
    assert r.profit_eligible is None
    assert r.principal_preserved_cents==15000
    assert r.capital_days_weight>0
    assert not r.may_close_cycle


def test_non_owner_tenant_does_not_inherit_owner_exclusion():
    r=run_review(owner=False,legal=True)
    assert r.profit_eligible is None
    assert r.status=="TENANT_POLICY_REVIEW_REQUIRED"


def test_late_settlement_never_erases_verified_historic_trigger():
    dues=tuple(due(n,settled=date(2027,4,10),paid=15000) for n in (1,2,3))
    r=run_review(as_of=date(2027,5,1),dues=dues,legal=True,
                 movements=(flow(date(2027,4,10),45000),))
    assert r.historic_three_unpaid_on==date(2027,3,11)
    assert r.current_consecutive_unpaid==0
    assert r.profit_eligible is False
    assert r.principal_preserved_cents==45000
    assert r.capital_days_weight==0


def test_gap_in_contributions_prevents_false_consecutive_streak():
    r=run_review(dues=(due(1),due(3),due(4)),legal=True,
                 as_of=date(2027,4,11))
    assert r.historic_three_unpaid_on is None


def test_missing_historical_attestation_blocks_distribution():
    r=run_review(legal=True,history=False)
    assert r.status=="HISTORY_NOT_ATTESTED"
    assert r.profit_eligible is None


def test_end_of_local_day_and_principal_preservation():
    principal,weight=capital_days_v2(
        T,M,(flow(date(2027,1,1),15000),),start=START,end_exclusive=END)
    assert principal==15000 and weight==Decimal("54750.00") # R$150 × 365 dias


@pytest.mark.parametrize("day_index",range(0,61))
def test_61_restitution_dates_weight_is_not_retroactive(day_index):
    paid_day=date(2027,1,1)
    reversed_day=paid_day+timedelta(days=day_index+1)
    _,weight=capital_days_v2(
        T,M,(flow(paid_day,15000,1),flow(reversed_day,-15000,2)),
        start=START,end_exclusive=END)
    assert weight==Decimal(150*(day_index+1))


def test_civil_local_timezone_is_not_utc_day():
    first=datetime(2027,1,1,3,0,tzinfo=timezone.utc) # Belem Jan 1 midnight
    event=CapitalMovement(T,M,first,100,UUID(int=10))
    p,w=capital_days_v2(T,M,(event,),start=START,end_exclusive=END)
    assert p==100 and w==Decimal("365.00")
    before=datetime(2027,1,1,2,59,tzinfo=timezone.utc) # Dec 31, 2026 Belem
    with pytest.raises(ValueError):
        capital_days_v2(T,M,(CapitalMovement(T,M,before,100,UUID(int=11)),),
                        start=START,end_exclusive=END)


def test_cannot_reverse_more_than_reconciled_principal():
    with pytest.raises(ValueError):
        capital_days_v2(
            T,M,(flow(date(2027,1,1),100,1),flow(date(2027,1,2),-101,2)),
            start=START,end_exclusive=END)


def test_duplicate_capital_event_rejected():
    event=flow(date(2027,1,1),100,1)
    with pytest.raises(ValueError):
        capital_days_v2(T,M,(event,event),start=START,end_exclusive=END)


def test_cross_tenant_or_cross_member_capital_event_rejected():
    for bad in (flow(START,100,tenant=X),flow(START,100,member=Y)):
        with pytest.raises(ValueError):
            capital_days_v2(T,M,(bad,),start=START,end_exclusive=END)


def test_voluntary_exit_request_is_audit_event_not_confiscation():
    exit=ExitRequest(T,M,date(2027,6,10),UUID(int=77))
    r=run_review(as_of=date(2027,6,11),dues=(due(1,paid=15000,settled=date(2027,1,10)),),
                 movements=(flow(date(2027,1,10),15000),),
                 exit=exit,legal=True)
    assert r.exit_status=="REQUESTED_AWAITING_REVIEW"
    assert r.status=="VOLUNTARY_EXIT_UNRESOLVED"
    assert r.profit_eligible is None
    assert r.principal_preserved_cents==15000
    assert r.capital_days_weight>0


def test_verified_regular_exit_preserves_capital_days_before_restitution():
    exit=ExitRequest(T,M,date(2027,6,10),UUID(int=77),
                     accepted_contract_evidence="clause6.5+signed-acceptance",
                     authorized_exit_on=date(2027,6,10),
                     obligations_reviewed=True,capital_restitution_reconciled=True)
    r=run_review(as_of=date(2027,7,1),dues=(due(1,paid=15000,settled=date(2027,1,10)),),
                 movements=(flow(date(2027,1,10),15000,1),
                            flow(date(2027,6,10),-15000,2)),
                 exit=exit,legal=True)
    assert r.exit_status=="EXIT_DOCUMENTED_RIGHTS_PRESERVED"
    assert r.status=="NO_CONTRACT_TRIGGER_FOUND"
    assert r.profit_eligible is True
    assert r.principal_preserved_cents==0  # restituição comprovada, não confisco
    assert r.capital_days_weight==Decimal(150*(date(2027,6,10)-date(2027,1,10)).days)


def test_exit_claim_cannot_erase_outstanding_obligations_or_gain_auto_approval():
    exit=ExitRequest(T,M,date(2027,6,10),UUID(int=77),
                     accepted_contract_evidence="clause6.5",
                     authorized_exit_on=date(2027,6,12),
                     obligations_reviewed=False,capital_restitution_reconciled=True)
    r=run_review(as_of=date(2027,7,1),dues=(due(1),),exit=exit)
    assert r.exit_status=="APPROVED_BUT_SETTLEMENT_UNVERIFIED"
    assert r.profit_eligible is None


@pytest.mark.parametrize("invalid",["False",0,None])
def test_exit_evidence_must_be_explicit_boolean(invalid):
    with pytest.raises(ValueError):
        ExitRequest(T,M,START,UUID(int=3),obligations_reviewed=invalid)


def test_invalid_exit_backdate_rejected():
    with pytest.raises(ValueError):
        ExitRequest(T,M,date(2027,6,2),UUID(int=10),
                    authorized_exit_on=date(2027,6,1))


def test_unreconciled_paid_100_percent_is_not_confirmed_capital():
    with pytest.raises(ValueError):
        due(1,paid=15000,settled=None)


@pytest.mark.parametrize("bad",[-1,True,1.1,15001])
def test_invalid_reconciled_paid_cents(bad):
    with pytest.raises(ValueError):
        due(1,paid=bad)


def test_duplicate_month_or_proof_rejected():
    with pytest.raises(ValueError):
        run_review(dues=(due(1),due(1)))
    with pytest.raises(ValueError):
        run_review(dues=(due(1),due(2),due(3),due(4),due(4)))


def test_all_snapshots_are_read_only_and_distinct_per_tenant_member_cycle():
    r=run_review(dues=(),legal=True,history=True)
    assert r.profit_eligible is True and r.principal_preserved_cents==0
    assert not r.may_close_cycle and not r.may_pay_real_money
    for wrong in (due(1,tenant=X),due(1,member=Y)):
        with pytest.raises(ValueError):
            run_review(dues=(wrong,),legal=True)
