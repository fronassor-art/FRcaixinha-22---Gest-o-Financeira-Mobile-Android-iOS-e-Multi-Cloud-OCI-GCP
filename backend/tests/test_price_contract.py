from datetime import date
from decimal import Decimal, ROUND_HALF_UP

import pytest

from app.routers.loans import compute_price_schedule


def test_regular_price_500_20_percent_five_installments():
    result = compute_price_schedule(Decimal('500.00'), 5, Decimal('0.20'))
    assert result.uniform_payment == Decimal('167.19')
    assert result.last_payment == Decimal('167.20')
    assert result.total_payable == Decimal('835.96')
    assert result.total_interest == Decimal('335.96')
    assert sum(row.amortization_portion for row in result.schedule) == Decimal('500.00')
    assert result.schedule[-1].closing_balance == 0


def test_irregular_first_period_uses_discount_equivalence_and_tenth_calendar():
    start = date(2027, 1, 28)
    result = compute_price_schedule(Decimal('500.00'), 5, Decimal('0.20'), start)
    rates = [Decimal('0.20') * Decimal(13) / Decimal(30)] + [Decimal('0.20')] * 4
    cumulative = Decimal(1)
    divisor = Decimal(0)
    for rate in rates:
        cumulative /= 1 + rate
        divisor += cumulative
    expected = (Decimal('500.00') / divisor).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    assert result.uniform_payment == expected
    assert result.first_period_days == 13
    assert [row.due_date for row in result.schedule] == [
        '2027-02-10', '2027-03-10', '2027-04-10', '2027-05-10', '2027-06-10']
    assert sum(row.amortization_portion for row in result.schedule) == Decimal('500.00')
    assert result.schedule[-1].closing_balance == 0


@pytest.mark.parametrize('start,due', [
    (date(2027, 1, 28), date(2027, 2, 11)),
    (date(2027, 12, 28), date(2028, 1, 10)),
])
def test_invalid_first_due_or_next_cycle_is_rejected(start, due):
    with pytest.raises(ValueError):
        compute_price_schedule(Decimal('500.00'), 5, Decimal('0.20'), start, due)


def test_zero_rate_and_negative_amortization_guards():
    zero = compute_price_schedule(Decimal('500.00'), 5, Decimal('0'))
    assert zero.uniform_payment == Decimal('100.00')
    with pytest.raises(ValueError):
        compute_price_schedule(Decimal('500.00'), 5, Decimal('-0.01'))
