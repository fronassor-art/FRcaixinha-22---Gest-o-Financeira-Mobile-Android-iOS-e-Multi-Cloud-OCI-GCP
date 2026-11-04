"""AI Studio M3400: Pix mensalidade, amortizacao Price, payout e recibos."""
from dataclasses import replace
from datetime import date,datetime,timezone
from uuid import UUID,uuid4
import pytest

from app.pix_automation_contract import (
    CONTRACT, ObligationKind, PaymentObligation, FinancialOperationBlocked,
    LoanDueComponents, RegisteredPixDestination, LoanDisbursement,
    PayoutState, ConfirmedCollection,
    build_pix_command, apply_loan_installment, build_disbursement_order,
    payout_state_after_provider, eligible_for_atomic_posting,make_receipt,
    amount_cents,decimal_brl,
)

T=UUID("00000000-0000-4000-8000-0000000000a1")
C=UUID("00000000-0000-4000-8000-0000000000a2")
M=UUID("00000000-0000-4000-8000-0000000000a3")
O=UUID("00000000-0000-4000-8000-0000000000a4")
L=UUID("00000000-0000-4000-8000-0000000000a5")
D=UUID("00000000-0000-4000-8000-0000000000a6")


def obligation(kind=ObligationKind.CONTRIBUTION,**kwargs):
    data=dict(tenant_id=T,cycle_id=C,member_id=M,obligation_id=O,
        kind=kind,expected_cents=15000,already_paid_cents=0,
        due_date=date(2027,1,10),terms_version="2027-policy-v1",
        provider_account_id="2002",environment="HOMOLOGACAO",
        loan_id=L if kind is ObligationKind.LOAN_INSTALLMENT else None)
    data.update(kwargs)
    return PaymentObligation(**data)


def test_member_150_reais_january_pix_is_stable_without_pii():
    b=build_pix_command(obligation())
    assert b.amount_cents==15000
    assert decimal_brl(b.amount_cents)=="150.00"
    assert b==build_pix_command(obligation())
    assert b.operation_id.startswith("P_")
    assert b.external_reference.startswith("FRC_")
    assert len(b.external_reference)<=64
    assert str(M) not in b.external_reference
    assert str(O) not in b.external_reference
    assert "@" not in b.external_reference


def test_installment_and_months_have_different_business_reference():
    contribution=build_pix_command(obligation())
    installment=build_pix_command(obligation(ObligationKind.LOAN_INSTALLMENT))
    february=build_pix_command(obligation(obligation_id=uuid4(),due_date=date(2027,2,10)))
    assert len({contribution.idempotency_key,installment.idempotency_key,
                february.idempotency_key})==3


def test_partial_pix_is_stable_but_overpay_is_blocked():
    partial=build_pix_command(obligation(already_paid_cents=3000),
                              requested_cents=5000)
    assert partial.amount_cents==5000
    with pytest.raises(FinancialOperationBlocked):
        build_pix_command(obligation(already_paid_cents=3000),requested_cents=12001)
    with pytest.raises(FinancialOperationBlocked):
        build_pix_command(obligation(already_paid_cents=15000))


@pytest.mark.parametrize("invalid",[-1,0,True,1.5,"15000"])
def test_cents_no_float_bool_negative_zero(invalid):
    with pytest.raises(FinancialOperationBlocked):
        build_pix_command(obligation(),requested_cents=invalid)


def test_cents_are_decimal_without_locale_or_float_guessing():
    assert amount_cents("150.00")==15000
    assert amount_cents("200.00")==20000
    for bad in ("150","150,00","150.001","-1.00","0.00","1e2",True):
        with pytest.raises(FinancialOperationBlocked):
            amount_cents(bad)


def test_contractual_200_payment_amortizes_only_principal():
    due=LoanDueComponents(O,T,L,4000,0,0,16000)
    a=apply_loan_installment(due,confirmed_cents=20000)
    assert a.paid_interest==4000
    assert a.paid_principal==16000
    assert a.revenue_cents==4000
    assert a.remaining_principal==0
    assert a.applied_cents==20000
    assert a.is_fully_paid


def test_overdue_partial_imputation_no_capital_until_all_charges_paid():
    due=LoanDueComponents(O,T,L,4000,1000,1000,16000)
    a=apply_loan_installment(due,confirmed_cents=5000)
    assert (a.paid_interest,a.paid_mora,a.paid_fine,a.paid_principal)==(4000,1000,0,0)
    assert a.remaining_principal==16000
    assert a.revenue_cents==5000
    assert not a.is_fully_paid
    b=apply_loan_installment(due,confirmed_cents=7000)
    assert b.paid_principal==1000
    with pytest.raises(FinancialOperationBlocked):
        apply_loan_installment(due,confirmed_cents=22001)


def destination(**updates):
    p=dict(tenant_id=T,member_id=M,destination_id=D,
           masked_key="***-***-1234",fingerprint="a"*64,
           verified_owner=True,consent_active=True,revoked=False)
    p.update(updates)
    return RegisteredPixDestination(**p)


def loan(**updates):
    p=dict(tenant_id=T,cycle_id=C,loan_id=L,member_id=M,
           principal_cents=50000,destination=destination(),approved=True,
           reservation_confirmed=True,adequate_reconciled_cash=True,
           consent_valid=True,environment="HOMOLOGACAO",
           financial_role="TENANT_ADMIN",provider_out_capability=True)
    p.update(updates)
    return LoanDisbursement(**p)


def test_payout_business_operation_is_stable_and_never_confirms_transferred():
    order=build_disbursement_order(loan())
    assert order==build_disbursement_order(loan())
    assert order.status is PayoutState.RESERVED
    assert order.money_transferred is False
    assert order.destination_id==D
    assert order.business_operation_id.startswith("L_")
    assert "redacted" in repr(destination())


@pytest.mark.parametrize("changed",[
    {"approved":False},{"reservation_confirmed":False},
    {"adequate_reconciled_cash":False},{"consent_valid":False},
    {"financial_role":"MASTER"},{"financial_role":"TENANT_MEMBER"},
    {"provider_out_capability":False},
    {"destination":destination(member_id=uuid4())},
    {"destination":destination(tenant_id=uuid4())},
    {"destination":destination(revoked=True)},
    {"destination":destination(consent_active=False)},
    {"destination":destination(verified_owner=False)},
])
def test_payout_denies_noncompliant_loan_destination_and_capability(changed):
    with pytest.raises(FinancialOperationBlocked):
        build_disbursement_order(loan(**changed))


def test_provider_approved_payout_is_not_a_confirmed_transfer():
    assert payout_state_after_provider(
        state=PayoutState.SENT,external_status="approved",
        authentic_final_evidence=True,
    ) is PayoutState.PENDING_RECONCILIATION
    assert payout_state_after_provider(
        state=PayoutState.SENT,external_status=None,
        authentic_final_evidence=False,
    ) is PayoutState.PENDING_RECONCILIATION
    assert payout_state_after_provider(
        state=PayoutState.PENDING_RECONCILIATION,
        external_status="processed",authentic_final_evidence=True,
    ) is PayoutState.CONFIRMED
    with pytest.raises(FinancialOperationBlocked):
        payout_state_after_provider(
            state=PayoutState.SENT,external_status="processed",
            authentic_final_evidence=False,
        )


def evidence(b,**updates):
    obj=dict(tenant_id=T,operation_id=b.operation_id,
        provider_payment_id="900001",provider_account_id="2002",
        external_reference=b.external_reference,paid_cents=b.amount_cents,
        bank_statement_ref="SETTLEMENT_001",provider_get_verified=True,
        settlement_record_verified=True,currency="BRL",live_mode=False,
        obligation=b.obligation)
    obj.update(updates)
    return ConfirmedCollection(**obj)


def test_receipt_requires_matching_provider_settlement_and_committed_ledger():
    b=build_pix_command(obligation())
    e=evidence(b)
    assert eligible_for_atomic_posting(b,e)
    r=make_receipt(
        command=b,evidence=e,receipt_id=uuid4(),
        committed_ledger_transaction_id=uuid4(),
        committed_at=datetime(2027,1,10,tzinfo=timezone.utc),
    )
    assert r.amount_cents==15000
    assert r.status=="CONFIRMADO_CONCILIADO"
    assert r.payment_id=="900001"
    assert r.ledger_transaction_id


@pytest.mark.parametrize("changed",[
    {"tenant_id":uuid4()},
    {"operation_id":"wrong-op"},
    {"provider_account_id":"3003"},
    {"paid_cents":14999},
    {"external_reference":"wrong-ref"},
    {"bank_statement_ref":""},
    {"provider_get_verified":False},
    {"settlement_record_verified":False},
    {"currency":"USD"},
    {"live_mode":True},
    {"obligation":obligation(obligation_id=uuid4())},
])
def test_spoofed_receipt_or_provider_mismatch_is_rejected(changed):
    b=build_pix_command(obligation())
    with pytest.raises(FinancialOperationBlocked):
        eligible_for_atomic_posting(b,evidence(b,**changed))


def test_no_client_supplied_receipt_without_verified_commit():
    b=build_pix_command(obligation())
    with pytest.raises(FinancialOperationBlocked):
        make_receipt(command=b,evidence=evidence(b),receipt_id=uuid4(),
                     committed_ledger_transaction_id=None,
                     committed_at=datetime.now(timezone.utc))
