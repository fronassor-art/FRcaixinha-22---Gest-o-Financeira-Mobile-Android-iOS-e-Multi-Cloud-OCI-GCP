"""M6200: verified tenant cash, no phantom capacity and no real payout."""
from dataclasses import replace
from datetime import datetime,timedelta,timezone
from uuid import UUID
import pytest
from app.loan_credit_liquidity import (
    CONTRACT,AuthenticatedCashSnapshot,LoanReservationRequest,
    LoanLiquidityPreview,credit_liquidity_preflight,
)
from app.pix_automation_contract import FinancialOperationBlocked

T=UUID("00000000-0000-4000-8000-0000000000a1")
OTHER=UUID("00000000-0000-4000-8000-0000000000b1")
C=UUID("00000000-0000-4000-8000-0000000000a2")
L=UUID("00000000-0000-4000-8000-0000000000a3")
M=UUID("00000000-0000-4000-8000-0000000000a4")
NOW=datetime(2027,1,10,18,tzinfo=timezone.utc)


def request(**override):
    fields=dict(tenant_id=T,cycle_id=C,loan_id=L,member_id=M,
        provider_account_id="2002",principal_cents=500000,
        loan_status="APROVADO",cycle_status="ABERTO",
        admin_review_verified=True,active_member_verified=True,
        beneficiary_ownership_verified=True,recipient_consent_current=True,
        is_admin_self_loan=False,collective_self_loan_consent_verified=False,
        existing_payout_attempts=0)
    fields.update(override)
    return LoanReservationRequest(**fields)


def snapshot(**override):
    fields=dict(tenant_id=T,cycle_id=C,provider_account_id="2002",
        balance_cents=1000000,existing_credit_reservations_cents=200000,
        pending_payouts_cents=100000,mandatory_liabilities_cents=100000,
        snapshot_hash="a"*64,verified_at=NOW-timedelta(minutes=1),
        authenticated_provider=True,independent_bank_source=True)
    fields.update(override)
    return AuthenticatedCashSnapshot(**fields)


def preflight(r=None,b=None,t=NOW):
    return credit_liquidity_preflight(
        request=r or request(),snapshot=b or snapshot(),checked_at=t)


def test_only_free_authenticated_cash_can_support_reservation_preview():
    outcome=preflight()
    assert isinstance(outcome,LoanLiquidityPreview)
    assert outcome.free_cash_cents==600000
    assert outcome.requested_cents==500000
    assert outcome.eligible_for_atomic_reservation_attempt
    assert outcome.bank_balance_is_authenticated
    assert not outcome.reserve_written
    assert not outcome.payout_authorized
    assert not outcome.money_transferred
    assert not outcome.ledger_written
    assert CONTRACT=="AI_STUDIO_M6200_TENANT_LOAN_LIQUIDITY_PREFLIGHT_V1"


@pytest.mark.parametrize("principal",range(1,600001,11111))
def test_many_principals_do_not_exceed_free_cash(principal):
    outcome=preflight(r=request(principal_cents=principal))
    assert outcome.free_cash_cents==600000


@pytest.mark.parametrize("bad",[
    {"tenant_id":OTHER},{"cycle_id":OTHER},
    {"provider_account_id":"3003"},
    {"snapshot_hash":"wrong"},
    {"verified_at":NOW-timedelta(minutes=6)},
    {"verified_at":NOW+timedelta(minutes=1)},
    {"authenticated_provider":False},
    {"independent_bank_source":False},
    {"source_kind":"CLIENT_UPLOADED_CSV"},
    {"balance_cents":200000},
    {"existing_credit_reservations_cents":1000000},
    {"pending_payouts_cents":999999999999},
])
def test_wrong_tenant_stale_bank_balance_or_provider_denied(bad):
    with pytest.raises(FinancialOperationBlocked):
        preflight(b=snapshot(**bad))


@pytest.mark.parametrize("bad",[
    {"tenant_id":OTHER},{"cycle_id":OTHER},
    {"provider_account_id":"9999"},
    {"principal_cents":0},
    {"principal_cents":700000},
    {"loan_status":"SOLICITADO"},
    {"loan_status":"DESEMBOLSADO"},
    {"cycle_status":"LIQUIDADO"},
    {"admin_review_verified":False},
    {"active_member_verified":False},
    {"beneficiary_ownership_verified":False},
    {"recipient_consent_current":False},
    {"existing_payout_attempts":1},
])
def test_wrong_credit_or_reused_loan_denied(bad):
    with pytest.raises(FinancialOperationBlocked):
        preflight(r=request(**bad))


def test_admin_self_loan_requires_distinct_collective_approval():
    with pytest.raises(FinancialOperationBlocked):
        preflight(r=request(is_admin_self_loan=True))
    p=preflight(r=request(is_admin_self_loan=True,
        collective_self_loan_consent_verified=True))
    assert p.eligible_for_atomic_reservation_attempt
    assert not p.reserve_written


def test_verified_bank_snapshot_at_exact_five_minutes_is_allowed():
    p=preflight(b=snapshot(verified_at=NOW-timedelta(minutes=5)))
    assert p.free_cash_cents==600000


def test_no_float_or_boolean_cash_values():
    for amount in (500000.00,True,-1,9999999999999):
        with pytest.raises(FinancialOperationBlocked):
            preflight(r=request(principal_cents=amount))


def test_preview_is_not_a_statement_of_funds_held_by_app():
    p=preflight()
    assert not p.money_transferred
    assert not p.ledger_written
