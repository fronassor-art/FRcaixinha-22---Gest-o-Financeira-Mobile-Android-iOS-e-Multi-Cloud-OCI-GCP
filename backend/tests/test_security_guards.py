from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.dependencies import AuthenticatedSession, require_master, require_tenant_access
from app.routers.closings import capital_days_weight, close_cycle
from app.routers.loans import disburse_loan, repay_loan_installment, settle_loan_early
from app.routers.contributions import pay_contribution
from app.main import app


def test_loans_get_route_is_unique_and_uses_financial_router():
    routes = [route for route in app.routes if route.path == '/api/v1/tenants/{tenant_id}/loans' and 'GET' in (route.methods or set())]
    assert len(routes) == 1
    assert routes[0].endpoint.__module__ == 'app.routers.loans'


def session(role="TENANT_ADMIN", is_master=False):
    return AuthenticatedSession("user", role, "tenant", "test@example.invalid", "Teste", is_master)


def test_only_master_context_can_manage_master():
    assert require_master(session("MASTER", True)).role == "MASTER"
    for candidate in (session("MASTER", False), session("TENANT_ADMIN", True)):
        with pytest.raises(HTTPException) as exc:
            require_master(candidate)
        assert exc.value.status_code == 403


def test_unknown_or_master_role_cannot_access_tenant():
    for candidate in (session("UNKNOWN"), session("MASTER", True), session("TENANT_MEMBER", True)):
        with pytest.raises(HTTPException) as exc:
            require_tenant_access("tenant", candidate)
        assert exc.value.status_code == 403
    assert require_tenant_access("tenant", session("TENANT_MEMBER"))
    with pytest.raises(HTTPException):
        require_tenant_access("another", session("TENANT_ADMIN"))


def test_capital_days_uses_december_end_not_january_settlement():
    end = date(2027, 12, 31)
    assert capital_days_weight(Decimal("100"), date(2027, 1, 10), end) == Decimal("35500.0000")
    assert capital_days_weight(Decimal("100"), date(2028, 1, 1), end) == Decimal("0.0000")


@pytest.mark.asyncio
async def test_financial_completion_is_blocked_without_bank_reconciliation():
    # A None connection makes any accidental database operation fail the test.
    calls = [
        close_cycle("tenant", None, session(), None),
        disburse_loan("tenant", "loan", session(), None),
        repay_loan_installment("tenant", "loan", None, session(), None),
        settle_loan_early("tenant", "loan", session(), None),
        pay_contribution("tenant", "contribution", None, session(), None),
    ]
    for call in calls:
        with pytest.raises(HTTPException) as exc:
            await call
        assert exc.value.status_code == 503
