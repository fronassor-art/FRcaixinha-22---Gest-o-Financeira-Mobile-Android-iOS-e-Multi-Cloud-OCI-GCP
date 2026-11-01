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


@pytest.mark.asyncio
async def test_loan_write_returns_only_selected_record_or_fails_closed(monkeypatch):
    from datetime import datetime, timezone
    from fastapi import HTTPException
    from app.dependencies import AuthenticatedSession
    from app.models import LoanResponse
    from app.routers import loans

    one = LoanResponse(
        id='one', tenant_id='tenant', cycle_id='cycle', borrower_membership_id='member',
        is_admin_loan=False, principal=Decimal('100.00'), monthly_rate=Decimal('0.20'),
        term_months=1, monthly_payment=Decimal('120.00'), last_payment=Decimal('120.00'),
        total_interest=Decimal('20.00'), status='SOLICITADO',
        created_at=datetime(2027, 1, 1, tzinfo=timezone.utc),
    )
    other = one.model_copy(update={'id': 'other'})
    async def listed(_tenant, _session, _conn):
        return [other, one]
    monkeypatch.setattr(loans, 'list_tenant_loans', listed)
    session = AuthenticatedSession('user', 'TENANT_MEMBER', 'tenant',
                                   'synthetic@example.invalid', 'Sintético', False)
    assert await loans._read_loan_result('tenant', 'one', session, None) == one
    with pytest.raises(HTTPException) as error:
        await loans._read_loan_result('tenant', 'missing', session, None)
    assert error.value.status_code == 500
