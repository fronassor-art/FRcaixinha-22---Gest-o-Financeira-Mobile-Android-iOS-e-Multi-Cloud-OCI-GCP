"""M6800 partial contribution refunds, original ledger preserved, zero I/O."""
from dataclasses import replace
from datetime import datetime,timezone
from uuid import UUID
import pytest

from app.mp_orders_ledger_plan import OrdersJournalPlan,JournalLine,Role
from app.mp_orders_partial_refund import (
    CONTRACT,IndependentRefundEvidence,ContributionRefundPreview,
    build_contribution_refund_preview,
)
from app.pix_automation_contract import FinancialOperationBlocked

T=UUID("00000000-0000-4000-8000-0000000000a1")
OTHER=UUID("00000000-0000-4000-8000-0000000000b1")
OB=UUID("00000000-0000-4000-8000-0000000000a4")


def original(kind="CONTRIBUTION",fee=300):
    return OrdersJournalPlan(
        tenant_id=T,obligation_id=OB,
        operation_id="P_"+"a"*32,order_id="ORD01HRYFWNYRE1MR1E60MW3X0T2P",
        payment_id="PAY01HRYFXQ53Q3JPEC48MYWMR0TE",
        bank_statement_reference="ORIGINAL_BANK_2027_A",
        source_hash="a"*64,
        journal_reference="OJR_"+"b"*40,
        kind=kind,gross_cents=15000,fee_cents=fee,net_cents=15000-fee,
        lines=(
            JournalLine(Role.CASH,"DR",15000-fee),
            JournalLine(Role.PSP_FEE,"DR",fee),
            JournalLine(Role.CAPITAL,"CR",15000),
        ) if fee else (
            JournalLine(Role.CASH,"DR",15000),
            JournalLine(Role.CAPITAL,"CR",15000),
        ),
    )


def proof(p=None,**changes):
    p=p or original()
    kwargs=dict(
        tenant_id=T,order_id=p.order_id,payment_id=p.payment_id,
        prior_journal_reference=p.journal_reference,
        refund_id="REFUND_MP_2027_00001",
        bank_reference="BANK_REFUND_2027_0001",
        bank_evidence_hash="f"*64,
        refund_gross_cents=5000,
        psp_fee_refunded_cents=0,net_cash_debit_cents=5000,
        previously_refunded_cents=0,previously_fee_refunded_cents=0,
        final_provider_state="REFUND_SETTLED",
        settled_at=datetime(2027,2,10,tzinfo=timezone.utc),
        authenticated_origin=True,bank_settlement_independent=True,
    )
    kwargs.update(changes)
    return IndependentRefundEvidence(**kwargs)


def test_partial_contribution_fee_retained_is_balanced():
    p=original()
    out=build_contribution_refund_preview(original=p,proof=proof(p))
    assert isinstance(out,ContributionRefundPreview)
    assert out.debits==out.credits==5000
    assert {(x.purpose,x.side,x.cents) for x in out.lines}=={
        (Role.CAPITAL,"DR",5000),(Role.CASH,"CR",5000)}
    assert out.original_history_preserved
    assert not out.ready_for_database_commit
    assert not out.refund_applied
    assert not out.financial_effect_applied
    assert CONTRACT=="AI_STUDIO_M6800_PARTIAL_REFUND_PREVIEW_V1"


def test_partial_contribution_fee_repaid_by_psp_is_separately_accounted():
    p=original()
    receipt=proof(p,psp_fee_refunded_cents=100,net_cash_debit_cents=4900)
    out=build_contribution_refund_preview(original=p,proof=receipt)
    assert out.debits==out.credits==5000
    assert {(x.purpose,x.side,x.cents) for x in out.lines}=={
        (Role.CAPITAL,"DR",5000),(Role.CASH,"CR",4900),
        (Role.PSP_FEE,"CR",100)}
    assert out.fee_refunded_cents==100


def test_full_gross_refund_with_full_fee_return_is_balanced():
    p=original()
    out=build_contribution_refund_preview(
        original=p,proof=proof(p,refund_gross_cents=15000,
            psp_fee_refunded_cents=300,net_cash_debit_cents=14700))
    assert out.credits==out.debits==15000


def test_second_partial_refund_observes_authoritative_cumulative_bound():
    p=original()
    valid=proof(p,refund_gross_cents=1000,
        previously_refunded_cents=14000,net_cash_debit_cents=1000)
    out=build_contribution_refund_preview(original=p,proof=valid)
    assert out.refunded_cents==1000
    with pytest.raises(FinancialOperationBlocked):
        build_contribution_refund_preview(original=p,
            proof=replace(valid,refund_gross_cents=1001,
                          net_cash_debit_cents=1001))


@pytest.mark.parametrize("changed",[
    {"tenant_id":OTHER},
    {"order_id":"ORD_OTHER_2027"},
    {"payment_id":"PAY_OTHER_2027"},
    {"prior_journal_reference":"OJR_WRONG"},
    {"refund_id":"x"},
    {"bank_reference":"x"},
    {"bank_reference":"ORIGINAL_BANK_2027_A"},
    {"bank_evidence_hash":"g"*64},
    {"refund_gross_cents":0,"net_cash_debit_cents":0},
    {"refund_gross_cents":15001,"net_cash_debit_cents":15001},
    {"refund_gross_cents":5000,"net_cash_debit_cents":4999},
    {"psp_fee_refunded_cents":301,"net_cash_debit_cents":4699},
    {"psp_fee_refunded_cents":100,"net_cash_debit_cents":4900,
     "previously_fee_refunded_cents":300},
    {"previously_refunded_cents":14000},
    {"final_provider_state":"PENDING"},
    {"settled_at":datetime(2027,1,1)},
    {"authenticated_origin":False},
    {"bank_settlement_independent":False},
    {"refund_gross_cents":True,"net_cash_debit_cents":1},
])
def test_invalid_or_unreconciled_partial_refund_is_blocked(changed):
    p=original()
    with pytest.raises(FinancialOperationBlocked):
        build_contribution_refund_preview(original=p,proof=proof(p,**changed))


def test_loan_repayment_partial_refund_not_assumed_to_be_contribution():
    p=original(kind="LOAN_INSTALLMENT")
    with pytest.raises(FinancialOperationBlocked):
        build_contribution_refund_preview(original=p,proof=proof(p))


def test_fee_and_refund_fingerprint_deterministic_and_unique():
    p=original()
    a=build_contribution_refund_preview(original=p,proof=proof(p))
    b=build_contribution_refund_preview(original=p,proof=proof(p))
    assert a.refund_journal_reference==b.refund_journal_reference
    c=build_contribution_refund_preview(original=p,
         proof=proof(p,refund_id="REFUND_MP_2027_00002"))
    assert c.refund_journal_reference!=a.refund_journal_reference


def test_zero_fee_case_has_no_zero_value_line():
    p=original(fee=0)
    out=build_contribution_refund_preview(original=p,proof=proof(p))
    assert len(out.lines)==2
    assert out.debits==out.credits==5000
