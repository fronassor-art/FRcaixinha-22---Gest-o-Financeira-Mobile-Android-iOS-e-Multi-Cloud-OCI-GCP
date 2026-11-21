"""M6000/M6100: pure accounting previews, no real ledger posting."""
from dataclasses import replace
from datetime import date,datetime,timedelta,timezone
from uuid import UUID
import pytest

from app.mp_orders_api import OrdersReadReport
from app.mp_orders_ledger_plan import (
    Role,OrdersJournalPlan,AuthenticatedReversal,
    build_orders_ledger_plan,build_full_reversal_preview,
    CONTRACT,REVERSAL_CONTRACT,
)
from app.mp_orders_settlement import AuthenticatedSettlementRow
from app.pix_automation_contract import (
    PaymentObligation,ObligationKind,build_pix_command,
    LoanAllocation,FinancialOperationBlocked,
)

T=UUID("00000000-0000-4000-8000-0000000000a1")
OTHER=UUID("00000000-0000-4000-8000-0000000000b1")
C=UUID("00000000-0000-4000-8000-0000000000a2")
M=UUID("00000000-0000-4000-8000-0000000000a3")
O=UUID("00000000-0000-4000-8000-0000000000a4")
L=UUID("00000000-0000-4000-8000-0000000000a5")
ORD="ORD01HRYFWNYRE1MR1E60MW3X0T2P"
PAY="PAY01HRYFXQ53Q3JPEC48MYWMR0TE"
AT=datetime(2027,1,10,15,tzinfo=timezone.utc)


def command(kind=ObligationKind.CONTRIBUTION):
    return build_pix_command(PaymentObligation(
        tenant_id=T,cycle_id=C,member_id=M,obligation_id=O,kind=kind,
        loan_id=L if kind is ObligationKind.LOAN_INSTALLMENT else None,
        expected_cents=15000,already_paid_cents=0,
        due_date=date(2027,1,10),terms_version="policy-2027-ci",
        provider_account_id="2002",environment="HOMOLOGACAO"))


def order():
    return OrdersReadReport(
        order_id=ORD,payment_id=PAY,
        status="processed",status_detail="accredited",
        payment_status="processed",payment_detail="accredited",
        provider_response_structure_verified=True,
        ready_for_independent_settlement_lookup=True,
    )


def statement(cmd,fee=300,**overrides):
    values=dict(
        tenant_id=T,collector_id="2002",order_id=ORD,payment_id=PAY,
        external_reference=cmd.external_reference,
        statement_reference="BANK_SETTLEMENT_A_2027",
        statement_source_hash="a"*64,
        currency="BRL",gross_cents=15000,fee_cents=fee,
        net_cents=15000-fee,settlement_state="SETTLED",
        settled_at=AT,fetched_at=AT+timedelta(minutes=5),
        authenticated_provider_identity=True,
        authenticated_statement_transport=True,
        independently_settled=True,
    )
    values.update(overrides)
    return AuthenticatedSettlementRow(**values)


def ledger(kind=ObligationKind.CONTRIBUTION,fee=300,allocation=None):
    cmd=command(kind)
    return build_orders_ledger_plan(
        command=cmd,verified_order=order(),
        statement=statement(cmd,fee=fee),
        loan_allocation=allocation,
    )


def test_contribution_posts_net_cash_plus_fee_vs_gross_capital():
    p=ledger()
    assert isinstance(p,OrdersJournalPlan)
    assert p.debits==p.credits==p.gross_cents==15000
    assert p.fee_cents==300 and p.net_cents==14700
    assert {(x.purpose,x.side,x.cents) for x in p.lines}=={
        (Role.CASH,"DR",14700),
        (Role.PSP_FEE,"DR",300),
        (Role.CAPITAL,"CR",15000),
    }
    assert p.source=="THREE_SOURCE_READ_ONLY_PREVIEW"
    assert not p.ready_for_database_commit
    assert not p.bank_reconciled
    assert not p.ledger_written
    assert not p.financial_effect_applied
    assert p.journal_reference.startswith("OJR_")
    assert CONTRACT=="AI_STUDIO_M6000_ORDERS_BALANCED_LEDGER_PLAN_V1"


@pytest.mark.parametrize("fee",list(range(0,15001,499)))
def test_many_fee_bands_still_balanced(fee):
    p=ledger(fee=fee)
    assert p.net_cents+p.fee_cents==15000
    assert p.debits==p.credits==15000
    assert all(x.cents>0 for x in p.lines)


def test_full_fee_no_zero_cash_line():
    p=ledger(fee=15000)
    assert p.debits==p.credits==15000
    assert all(x.purpose is not Role.CASH for x in p.lines)


def test_loan_principal_interest_mora_fine_credit_split():
    alloc=LoanAllocation(
        paid_interest=2000,paid_mora=1000,paid_fine=1000,
        paid_principal=11000,remaining_interest=0,remaining_mora=0,
        remaining_fine=0,remaining_principal=0,
    )
    p=ledger(ObligationKind.LOAN_INSTALLMENT,fee=300,allocation=alloc)
    credits={(x.purpose,x.cents) for x in p.lines if x.side=="CR"}
    assert credits=={
        (Role.INTEREST,2000),(Role.MORA,1000),
        (Role.FINE,1000),(Role.LOAN_PRINCIPAL,11000),
    }
    assert Role.CAPITAL not in {x.purpose for x in p.lines}
    assert p.debits==p.credits==15000


def test_partial_interest_only_repayment_still_valid():
    alloc=LoanAllocation(
        paid_interest=15000,paid_mora=0,paid_fine=0,
        paid_principal=0,remaining_interest=500,
        remaining_mora=0,remaining_fine=0,remaining_principal=10000,
    )
    p=ledger(ObligationKind.LOAN_INSTALLMENT,fee=100,allocation=alloc)
    assert p.credits==15000
    assert any(x.purpose is Role.INTEREST for x in p.lines)
    assert not any(x.purpose is Role.LOAN_PRINCIPAL for x in p.lines)


@pytest.mark.parametrize("bad",[
    None,
    LoanAllocation(0,0,0,14999,0,0,0,0),
    LoanAllocation(0,0,0,15001,0,0,0,0),
])
def test_loan_without_exact_allocation_rejected(bad):
    with pytest.raises(FinancialOperationBlocked):
        ledger(ObligationKind.LOAN_INSTALLMENT,allocation=bad)


def test_contribution_cannot_take_loan_allocation():
    alloc=LoanAllocation(3000,0,0,12000,0,0,0,0)
    with pytest.raises(FinancialOperationBlocked):
        ledger(allocation=alloc)


@pytest.mark.parametrize("bad",[
    {"tenant_id":OTHER},
    {"collector_id":"3003"},
    {"external_reference":"CROSS-TENANT"},
    {"gross_cents":14999},
    {"net_cents":14699},
    {"fee_cents":-1},
    {"statement_source_hash":"wrong"},
    {"independently_settled":False},
])
def test_untrusted_payment_does_not_produce_journal(bad):
    cmd=command()
    with pytest.raises(FinancialOperationBlocked):
        build_orders_ledger_plan(
            command=cmd,verified_order=order(),
            statement=statement(cmd,**bad),
        )


def proof(original,**changes):
    values=dict(
        tenant_id=original.tenant_id,
        order_id=original.order_id,payment_id=original.payment_id,
        prior_journal_reference=original.journal_reference,
        reversal_reference="BANK_REVERSAL_FULL_2027",
        reversal_evidence_hash="f"*64,
        amount_cents=original.gross_cents,
        fee_returned_cents=original.fee_cents,
        net_cash_reversed_cents=original.net_cents,
        final_state="FULL_REFUND_FEE_RETURNED_SETTLED",
        occurred_at=AT+timedelta(days=3),
        authenticated_origin=True,
        independently_verified=True,
    )
    values.update(changes)
    return AuthenticatedReversal(**values)


def test_full_refund_with_fee_returned_inverts_all_lines_only_as_preview():
    original=ledger()
    inverse=build_full_reversal_preview(original=original,proof=proof(original))
    assert inverse.original_journal_reference==original.journal_reference
    assert inverse.reversal_journal_reference.startswith("REV_")
    assert inverse.tenant_id==original.tenant_id
    assert inverse.original_history_preserved
    assert inverse.requires_ledger_commit
    assert not inverse.reversal_applied
    assert not inverse.financial_effect_applied
    assert sum(x.cents for x in inverse.lines if x.side=="DR")==15000
    assert sum(x.cents for x in inverse.lines if x.side=="CR")==15000
    assert [(x.purpose,x.side,x.cents) for x in inverse.lines]==[
        (x.purpose,"CR" if x.side=="DR" else "DR",x.cents)
        for x in original.lines
    ]
    assert REVERSAL_CONTRACT=="AI_STUDIO_M6100_NONDESTRUCTIVE_REVERSAL_PLAN_V1"


@pytest.mark.parametrize("bad",[
    {"tenant_id":OTHER},
    {"order_id":"ORD01ANOTHERORDER00000000000"},
    {"payment_id":"PAY01ANOTHERPAYMENT0000000000"},
    {"prior_journal_reference":"WRONG"},
    {"reversal_reference":"BANK_SETTLEMENT_A_2027"},
    {"reversal_evidence_hash":"a"*63},
    {"amount_cents":14999},
    {"fee_returned_cents":0},
    {"net_cash_reversed_cents":0},
    {"final_state":"CHARGEBACK_SETTLED"},
    {"final_state":"REFUND_PENDING"},
    {"occurred_at":datetime(2027,1,13)},
    {"authenticated_origin":False},
    {"independently_verified":False},
])
def test_missing_proof_partial_refund_or_retained_fee_denied(bad):
    original=ledger()
    with pytest.raises(FinancialOperationBlocked):
        build_full_reversal_preview(original=original,proof=proof(original,**bad))


def test_reversal_idempotency_fingerprint_deterministic():
    a=ledger()
    x=build_full_reversal_preview(original=a,proof=proof(a))
    y=build_full_reversal_preview(original=a,proof=proof(a))
    assert x.reversal_journal_reference==y.reversal_journal_reference
    altered=build_full_reversal_preview(
        original=a,proof=proof(a,reversal_reference="BANK_REVERSAL_FULL_2028"))
    assert altered.reversal_journal_reference!=x.reversal_journal_reference
