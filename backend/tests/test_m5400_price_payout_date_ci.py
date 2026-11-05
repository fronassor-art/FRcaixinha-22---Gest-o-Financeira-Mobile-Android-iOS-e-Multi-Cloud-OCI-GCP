"""M5400: Price after payout exact time zone/cycle; no approval-date parcels."""
from datetime import date,datetime,timezone,timedelta
from decimal import Decimal
import pytest

from app.loan_payout_price import CONTRACT,confirmed_price_schedule
from app.pix_automation_contract import FinancialOperationBlocked

START=date(2027,1,1)
END=date(2027,12,31)


def schedule(moment,zone="America/Belem",**kw):
    args=dict(principal="500.00",monthly_rate="0.20",installments=5,
        effective_at=moment,tenant_timezone=zone,
        cycle_start=START,cycle_end=END,expected_payout_cents=50000)
    args.update(kw)
    return confirmed_price_schedule(**args)


def test_same_utc_instant_may_belong_to_prior_local_calendar_day():
    instant=datetime(2027,1,15,3,30,tzinfo=timezone.utc)
    belem=schedule(instant,"America/Belem")
    manaus=schedule(instant,"America/Manaus")
    assert belem.first_period_days==26  # Jan 15 -> Feb 10
    assert manaus.first_period_days==27  # Jan 14 -> Feb 10
    assert belem.schedule[0].due_date=="2027-02-10"
    assert manaus.schedule[0].due_date=="2027-02-10"
    assert belem.total_interest!=manaus.total_interest


def test_schedules_balanced_and_date_not_from_approval():
    result=schedule(datetime(2027,1,28,12,tzinfo=timezone.utc))
    assert result.first_period_days==13
    assert result.schedule[0].due_date=="2027-02-10"
    assert sum(x.amortization_portion for x in result.schedule)==Decimal("500.00")
    assert result.schedule[-1].closing_balance==Decimal("0.00")
    assert result.schedule[-1].due_date=="2027-06-10"
    assert CONTRACT=="AI_STUDIO_M5400_CONFIRMED_PAYOUT_PRICE_DATE_V1"


@pytest.mark.parametrize("changes",[
    {"effective_at":datetime(2027,1,28)},
    {"effective_at":datetime(2026,12,31,23,tzinfo=timezone.utc)},
    {"effective_at":datetime(2028,1,1,tzinfo=timezone.utc)},
    {"tenant_timezone":"UTC"},
    {"tenant_timezone":"America/UnknownCity"},
    {"principal":"501.00"},
    {"principal":"499.99"},
    {"principal":"NaN"},
    {"monthly_rate":"NaN"},
    {"expected_payout_cents":49999},
    {"installments":0},
    {"installments":7},
    {"cycle_end":date(2027,1,31)},
])
def test_invalid_effective_date_amount_or_policy_fails_closed(changes):
    instant=datetime(2027,1,28,tzinfo=timezone.utc)
    with pytest.raises((FinancialOperationBlocked,ValueError)):
        schedule(instant,**changes)


def test_cycle_end_blocks_last_due_not_only_disbursement():
    instant=datetime(2027,11,1,tzinfo=timezone.utc)
    with pytest.raises(FinancialOperationBlocked):
        schedule(instant,installments=4)


def test_other_tenant_timezone_is_explicit_not_derived_from_server():
    instant=datetime(2027,1,15,3,30,tzinfo=timezone.utc)
    a=schedule(instant,"America/Belem")
    b=schedule(instant,"America/Manaus")
    assert a.first_period_days!=b.first_period_days
