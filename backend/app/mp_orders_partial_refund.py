"""M6800: partial contribution Pix refund with PSP fee retained/refunded.

Only a zero-effect accounting preview. It does not send Pix, read a
bank, re-open a reconciled obligation, or post a ledger entry.
Partial loan repayment reversal requires authoritative allocation snapshots
and remains blocked. Cumulative refund state MUST come from the trusted DB
under an eventual serializable transaction, never a frontend counter.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from re import fullmatch
from uuid import UUID

from .mp_orders_ledger_plan import (
    Role,JournalLine,OrdersJournalPlan,_balanced,
)
from .pix_automation_contract import FinancialOperationBlocked,ObligationKind

CONTRACT="AI_STUDIO_M6800_PARTIAL_REFUND_PREVIEW_V1"


@dataclass(frozen=True)
class IndependentRefundEvidence:
    tenant_id:UUID
    order_id:str
    payment_id:str
    prior_journal_reference:str
    refund_id:str
    bank_reference:str
    bank_evidence_hash:str
    refund_gross_cents:int
    psp_fee_refunded_cents:int
    net_cash_debit_cents:int
    previously_refunded_cents:int
    previously_fee_refunded_cents:int
    final_provider_state:str
    settled_at:datetime
    authenticated_origin:bool
    bank_settlement_independent:bool


@dataclass(frozen=True)
class ContributionRefundPreview:
    tenant_id:UUID
    original_journal_reference:str
    refund_journal_reference:str
    refunded_cents:int
    fee_refunded_cents:int
    net_cash_debit_cents:int
    lines:tuple[JournalLine,...]
    original_history_preserved:bool=True
    ready_for_database_commit:bool=False
    refund_applied:bool=False
    financial_effect_applied:bool=False

    @property
    def debits(self)->int:
        return sum(x.cents for x in self.lines if x.side=="DR")
    @property
    def credits(self)->int:
        return sum(x.cents for x in self.lines if x.side=="CR")


def build_contribution_refund_preview(
    *,original:OrdersJournalPlan,
    proof:IndependentRefundEvidence,
)->ContributionRefundPreview:
    if (type(original) is not OrdersJournalPlan
        or type(proof) is not IndependentRefundEvidence
        or original.kind!=ObligationKind.CONTRIBUTION.value
        or original.tenant_id!=proof.tenant_id
        or original.order_id!=proof.order_id
        or original.payment_id!=proof.payment_id
        or original.journal_reference!=proof.prior_journal_reference
        or type(proof.refund_id) is not str
        or fullmatch(r"[A-Za-z0-9._:-]{8,100}",proof.refund_id) is None
        or type(proof.bank_reference) is not str
        or fullmatch(r"[A-Za-z0-9._:/-]{8,128}",proof.bank_reference) is None
        or proof.bank_reference==original.bank_statement_reference
        or type(proof.bank_evidence_hash) is not str
        or fullmatch(r"[a-f0-9]{64}",proof.bank_evidence_hash) is None
        or proof.final_provider_state!="REFUND_SETTLED"
        or type(proof.settled_at) is not datetime
        or proof.settled_at.tzinfo is None
        or proof.settled_at.utcoffset() is None
        or proof.authenticated_origin is not True
        or proof.bank_settlement_independent is not True):
        raise FinancialOperationBlocked("Estorno parcial sem prova independente")
    monetary=(
        proof.refund_gross_cents,proof.psp_fee_refunded_cents,
        proof.net_cash_debit_cents,proof.previously_refunded_cents,
        proof.previously_fee_refunded_cents,
    )
    if (any(type(n) is not int or n<0 or n>999999999999 for n in monetary)
        or proof.refund_gross_cents==0
        or proof.previously_refunded_cents+proof.refund_gross_cents>original.gross_cents
        or proof.previously_fee_refunded_cents+proof.psp_fee_refunded_cents>original.fee_cents
        or proof.psp_fee_refunded_cents>proof.refund_gross_cents
        or proof.net_cash_debit_cents!=(
            proof.refund_gross_cents-proof.psp_fee_refunded_cents
        )):
        raise FinancialOperationBlocked("Valor ou cumulativo de estorno inconsistente")

    # Contributions only. Reverses capital pro-rata on full gross and
    # credits cash out less any independently proven PSP fee refund.
    lines=[JournalLine(Role.CAPITAL,"DR",proof.refund_gross_cents)]
    if proof.net_cash_debit_cents:
        lines.append(JournalLine(Role.CASH,"CR",proof.net_cash_debit_cents))
    if proof.psp_fee_refunded_cents:
        lines.append(JournalLine(Role.PSP_FEE,"CR",
                                 proof.psp_fee_refunded_cents))
    outcome=tuple(lines)
    _balanced(outcome,proof.refund_gross_cents)
    identity="|".join((
        "ORDERS_PARTIAL_REFUND_V1",str(original.tenant_id),
        original.journal_reference,proof.refund_id,
        proof.bank_reference,proof.bank_evidence_hash,
        str(proof.refund_gross_cents),
        str(proof.psp_fee_refunded_cents),
        str(proof.previously_refunded_cents),
        str(proof.previously_fee_refunded_cents),
    ))
    ref="REF_"+sha256(identity.encode("ascii")).hexdigest()[:40]
    return ContributionRefundPreview(
        tenant_id=original.tenant_id,
        original_journal_reference=original.journal_reference,
        refund_journal_reference=ref,
        refunded_cents=proof.refund_gross_cents,
        fee_refunded_cents=proof.psp_fee_refunded_cents,
        net_cash_debit_cents=proof.net_cash_debit_cents,
        lines=outcome,
    )
