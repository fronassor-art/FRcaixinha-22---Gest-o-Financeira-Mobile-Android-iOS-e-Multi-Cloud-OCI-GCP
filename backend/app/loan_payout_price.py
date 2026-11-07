"""M5400: definitive loan Price schedule AFTER externally proved Pix OUT.

A confirmed provider datetime must be converted into the tenant's verified
IANA timezone before determining its effective calendar day. Do not use
the webhook arrival date, the admin approval date or UTC blindly.
"""
from __future__ import annotations

from datetime import date,datetime
from decimal import Decimal,InvalidOperation
from zoneinfo import ZoneInfo,ZoneInfoNotFoundError
import re

from .pix_automation_contract import FinancialOperationBlocked

CONTRACT="AI_STUDIO_M5400_CONFIRMED_PAYOUT_PRICE_DATE_V1"

def confirmed_price_schedule(
    *, principal:str,monthly_rate:str,installments:int,
    effective_at:datetime,tenant_timezone:str,
    cycle_start:date,cycle_end:date,
    expected_payout_cents:int,
):
    if (type(effective_at) is not datetime
            or effective_at.tzinfo is None
            or effective_at.utcoffset() is None
            or type(tenant_timezone) is not str
            or not re.fullmatch(r"America/[A-Za-z_]{2,40}",tenant_timezone)
            or type(cycle_start) is not date
            or type(cycle_end) is not date
            or cycle_end<cycle_start
            or type(expected_payout_cents) is not int
            or not 1<=expected_payout_cents<=999999999999):
        raise FinancialOperationBlocked("Desembolso sem fuso ou contrato válido")
    try:
        tz=ZoneInfo(tenant_timezone)
        principal_dec=Decimal(principal)
        rate_dec=Decimal(monthly_rate)
        if (not principal_dec.is_finite() or not rate_dec.is_finite()
                or principal_dec*100!=expected_payout_cents):
            raise ValueError("Crédito não corresponde à transferência efetiva")
        local_day=effective_at.astimezone(tz).date()
        if not cycle_start<=local_day<=cycle_end:
            raise ValueError("Transferência fora do ciclo anual")
        from .routers.loans import compute_price_schedule
        schedule=compute_price_schedule(
            principal=principal_dec,term_months=installments,
            monthly_rate=rate_dec,disbursement_date=local_day,
            cycle_start_date=cycle_start,cycle_end_date=cycle_end,
        )
        if (sum(x.amortization_portion for x in schedule.schedule)
                !=principal_dec
                or any(date.fromisoformat(x.due_date)>cycle_end
                       for x in schedule.schedule)):
            raise ValueError("Cronograma Price inconsistente")
        return schedule
    except (ZoneInfoNotFoundError,InvalidOperation,ValueError,TypeError,
            OverflowError) as exc:
        raise FinancialOperationBlocked(
            "Data ou valores de desembolso incompatíveis com a política"
        ) from exc
