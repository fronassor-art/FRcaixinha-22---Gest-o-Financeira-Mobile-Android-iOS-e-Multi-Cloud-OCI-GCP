"""M401+ — 250+ cenários de rateio anual, principais e encargos separados."""
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID
from zoneinfo import ZoneInfo
import pytest

from app.member_cycle_rules import MemberCycleReview
from app.closing_contract_oracle import (
    FinancialEvidence, simulate_contract_closing
)

T=UUID("00000000-0000-4000-8000-0000000000a1")
X=UUID("00000000-0000-4000-8000-0000000000b1")
A=UUID(int=1)
B=UUID(int=2)
C=UUID(int=3)
D=UUID(int=4)
LOCAL=ZoneInfo("America/Belem")


def event(kind, cents, ident=1, *, tenant=T,
          when=None, reconciled=True):
    return FinancialEvidence(tenant,UUID(int=ident),kind,cents,
        when or datetime(2027,6,15,12,tzinfo=LOCAL),
        reconciled,f"CI-CONTRACT-EVIDENCE-{ident}")


def member(mid,weight,*,eligible=True,tenant=T,
           status="NO_CONTRACT_TRIGGER_FOUND",exit_status="NO_EXIT_REQUEST"):
    return MemberCycleReview(tenant,mid,date(2027,12,31),0,0,None,
        eligible,status,0,Decimal(str(weight)),exit_status)


def run(*,income=1000000,cost=0,loss=0,capital=0,
        admin=Decimal("15.00"),member_pct=Decimal("85.00"),
        reviews=None,evidence=None,compliant=True,tenant=T):
    if reviews is None: reviews=(member(A,"10.00"),member(B,"10.00"),member(C,"10.00"))
    if evidence is None:
        evidence=(event("REALIZED_REVENUE",income,1,tenant=tenant),
                  event("ELIGIBLE_EXPENSE",cost,2,tenant=tenant),
                  event("ADMISSIBLE_LOSS",loss,3,tenant=tenant),
                  event("CAPITAL_PRINCIPAL",capital,4,tenant=tenant))
    return simulate_contract_closing(tenant_id=tenant,cycle_year=2027,
        admin_percent=admin,member_percent=member_pct,
        fixed_cycle_policy_version="2027-owner-policy-version-approved",
        evidence=evidence,reviews=reviews,contract_compliant=compliant)


@pytest.mark.parametrize("profit",range(121))
def test_121_profit_cent_cases_conserve_all_cents(profit):
    result=run(income=profit,cost=0)
    expected=int((Decimal(profit)*Decimal(".15")).quantize(
        Decimal("1"),rounding=ROUND_HALF_UP))
    assert result.distributable_profit_cents==profit
    assert result.admin_remuneration_cents==expected
    assert result.member_pool_cents==profit-expected
    assert sum(v.final_cents for v in result.member_shares)==profit-expected
    assert result.technical_wallet_after_allocation_cents==0
    assert result.status=="SIMULATED_NOT_AUTHORIZED"
    assert not result.financial_closing_authorized
    assert not result.pix_enabled


@pytest.mark.parametrize("profit",range(0,120,2))
def test_60_tiny_rounding_ties_and_membership_id_determinism(profit):
    first=run(income=profit)
    reordered=run(income=profit,
        reviews=(member(C,"10.00"),member(A,"10.00"),member(B,"10.00")))
    assert first.member_shares==reordered.member_shares
    amounts={x.member_id:x.final_cents for x in first.member_shares}
    assert amounts[A]>=amounts[B]>=amounts[C]
    assert max(amounts.values())-min(amounts.values()) <= 1
    assert sum(amounts.values())==first.member_pool_cents


@pytest.mark.parametrize("percentage",range(0,101,5))
def test_21_cycle_versioned_admin_ratios(percentage):
    pct=Decimal(percentage)
    result=run(income=10000,admin=pct,member_pct=Decimal(100)-pct)
    assert result.admin_remuneration_cents==percentage*100
    assert result.member_pool_cents==(100-percentage)*100
    assert sum(x.final_cents for x in result.member_shares)==result.member_pool_cents


@pytest.mark.parametrize("principal",[
    0,1,100,15000,20000,50000,100000,1000000,987654321,999999999
])
def test_10_capital_principal_values_never_count_as_profit(principal):
    result=run(income=10000,capital=principal)
    assert result.distributable_profit_cents==10000
    assert result.admin_remuneration_cents==1500
    assert result.member_pool_cents==8500


@pytest.mark.parametrize("cost",range(0,1001,47))
def test_22_expense_values_reduce_result_exactly(cost):
    r=run(income=1000,cost=cost)
    assert r.net_result_cents==1000-cost
    assert r.distributable_profit_cents==max(0,1000-cost)
    if cost>1000:
        assert r.admin_remuneration_cents==0
        assert r.member_pool_cents==0


def test_10000_reais_case_administrator_vs_member_amounts():
    r=run(income=1_000_000,cost=0,loss=0)
    assert r.admin_remuneration_cents==150_000
    assert r.member_pool_cents==850_000
    assert [x.final_cents for x in r.member_shares]==[283334,283333,283333]
    assert r.technical_wallet_before_allocation_cents==1
    assert r.technical_wallet_after_allocation_cents==0
    assert sum(x.final_cents for x in r.member_shares)+r.admin_remuneration_cents==1000000


def test_confirmed_expense_loss_reversal_vs_principal():
    r=run(income=250000,cost=15000,loss=3500,capital=500000)
    assert r.realized_revenue_cents==250000
    assert r.eligible_costs_cents==18500
    assert r.net_result_cents==231500
    assert r.distributable_profit_cents==231500


def test_no_eligible_members_pool_is_reserved_not_gifted_to_admin():
    r=run(income=10000,reviews=(member(A,"0.00",eligible=False),))
    assert r.admin_remuneration_cents==1500
    assert r.reserved_undistributed_cents==8500
    assert sum(x.final_cents for x in r.member_shares)==0
    assert r.status=="NO_ELIGIBLE_MEMBERS_RESERVE_PENDING"


def test_excluded_owner_member_weight_zero_others_get_full_pool():
    r=run(income=100000,reviews=(
        member(A,"0.00",eligible=False,status="OWNER_CYCLE_PROFIT_EXCLUDED"),
        member(B,"5.00"),member(C,"5.00")))
    amounts={x.member_id:x.final_cents for x in r.member_shares}
    assert amounts[A]==0
    assert amounts[B]+amounts[C]==85000
    assert r.admin_remuneration_cents==15000


def test_disallow_false_cycle_eligibility_positive_weight():
    with pytest.raises(ValueError):
        run(reviews=(member(A,"10.00",eligible=False),))


def test_exit_request_awaiting_review_blocks_close():
    r=run(reviews=(member(A,"10",eligible=None,
            status="VOLUNTARY_EXIT_UNRESOLVED",
            exit_status="REQUESTED_AWAITING_REVIEW"),))
    assert r.status=="PENDING_REVIEW_OR_RECONCILIATION"
    assert not r.member_shares and r.reserved_undistributed_cents==1000000
    assert not r.financial_closing_authorized


def test_unverified_owner_legal_review_blocks_close():
    r=run(reviews=(member(A,"10",eligible=None,
            status="OWNER_EXCLUSION_WAITING_LEGAL_REVIEW"),))
    assert r.status=="PENDING_REVIEW_OR_RECONCILIATION"


def test_unreconciled_income_is_not_paid_money():
    r=run(evidence=(event("REALIZED_REVENUE",100000,1,reconciled=False),))
    assert r.distributable_profit_cents==0
    assert r.status=="PENDING_REVIEW_OR_RECONCILIATION"
    assert r.admin_remuneration_cents==0


def test_dec31_local_timezone_cutoff_requires_review_for_january_event():
    at_2028=datetime(2028,1,1,2,59,59,tzinfo=timezone.utc)
    event_last=event("REALIZED_REVENUE",10000,1,when=at_2028)
    assert run(evidence=(event_last,)).distributable_profit_cents==10000
    after=datetime(2028,1,1,3,0,tzinfo=timezone.utc)
    r=run(evidence=(event("REALIZED_REVENUE",10000,1,when=after),))
    assert r.status=="PENDING_REVIEW_OR_RECONCILIATION"
    assert r.distributable_profit_cents==0


def test_negative_net_result_is_not_capital_distribution():
    r=run(income=1000,cost=2500)
    assert r.net_result_cents==-1500
    assert r.distributable_profit_cents==0
    assert r.admin_remuneration_cents==0
    assert r.member_pool_cents==0


def test_duplicate_posting_rejected():
    e=event("REALIZED_REVENUE",10000)
    with pytest.raises(ValueError):
        run(evidence=(e,e))


def test_cross_tenant_event_or_member_rejected():
    with pytest.raises(ValueError):
        run(evidence=(event("REALIZED_REVENUE",10000,tenant=X),))
    with pytest.raises(ValueError):
        run(reviews=(member(A,"100",tenant=X),))


def test_duplicate_membership_rejected_even_with_two_roles():
    with pytest.raises(ValueError):
        run(reviews=(member(A,"100"),member(A,"200")))


def test_currency_and_percent_validation_fail_closed():
    for a,b in [(Decimal("15.001"),Decimal("84.999")),
                (Decimal("15.00"),Decimal("84.00")),
                (Decimal("110.00"),Decimal("-10.00")),
                (15.0,85.0),(Decimal("NaN"),Decimal("85.00"))]:
        with pytest.raises(ValueError):
            run(admin=a,member_pct=b)


def test_unapproved_contract_freezes_calculation():
    r=run(compliant=False)
    assert r.status=="PENDING_REVIEW_OR_RECONCILIATION"
    assert r.member_shares==()
    assert r.reserved_undistributed_cents==1000000


def test_unconfirmed_reversal_blocks_snapshot():
    r=run(evidence=(event("REALIZED_REVENUE",10000,1),
                    event("APPROVED_ADJUSTMENT",500,2,reconciled=False)))
    assert r.status=="PENDING_REVIEW_OR_RECONCILIATION"
    assert not r.member_shares


def test_cannot_forge_proof_or_unknown_type():
    with pytest.raises(ValueError):
        event("FAKE_CASH",1000,1)
    with pytest.raises(ValueError):
        event("REALIZED_REVENUE",True,1)
    with pytest.raises(ValueError):
        event("REALIZED_REVENUE",-1,1)
