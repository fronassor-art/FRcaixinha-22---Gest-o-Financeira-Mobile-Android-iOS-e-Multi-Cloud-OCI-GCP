from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.dependencies import AuthenticatedSession, require_master, require_tenant_access
from app.routers.closings import capital_days_weight, close_cycle
from app.routers.loans import disburse_loan, repay_loan_installment, settle_loan_early, approve_loan
from app.routers.contributions import pay_contribution
from app.routers.invitations import create_invitation
from app.models import InvitationCreateRequest
from app.config import settings
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
    for candidate in (session("UNKNOWN"), session("MASTER", True)):
        with pytest.raises(HTTPException) as exc:
            require_tenant_access("tenant", candidate)
        assert exc.value.status_code == 403
    assert require_tenant_access("tenant", session("TENANT_MEMBER"))
    assert require_tenant_access("tenant", session("TENANT_MEMBER", True))
    with pytest.raises(HTTPException):
        require_tenant_access("another", session("TENANT_ADMIN"))


def test_capital_days_uses_december_end_not_january_settlement():
    end = date(2027, 12, 31)
    assert capital_days_weight(Decimal("100"), date(2027, 1, 10), end) == Decimal("35500.0000")
    assert capital_days_weight(Decimal("100"), date(2028, 1, 1), end) == Decimal("0.0000")


def test_invitation_does_not_claim_success_with_only_database_url(monkeypatch):
    monkeypatch.setattr(settings, 'DATABASE_URL', 'postgresql://127.0.0.1/frcaixinha_ci')
    with pytest.raises(HTTPException) as exc:
        create_invitation(InvitationCreateRequest(target_email='teste@example.com', target_role='TENANT_MEMBER'), session())
    assert exc.value.status_code == 503


@pytest.mark.asyncio
async def test_admin_self_loan_cannot_be_approved_without_annual_consent():
    from uuid import uuid4
    tenant, loan_id = str(uuid4()), str(uuid4())
    admin = AuthenticatedSession(str(uuid4()), 'TENANT_ADMIN', tenant, 'test@example.com', 'Teste', False)
    class FakeConn:
        async def fetchrow(self, *_args):
            return {'status': 'SOLICITADO', 'is_admin_loan': True, 'borrower_membership_id': uuid4()}
        async def fetchval(self, *_args):
            return False
    with pytest.raises(HTTPException) as exc:
        await approve_loan(tenant, loan_id, admin, FakeConn())
    assert exc.value.status_code == 503


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
