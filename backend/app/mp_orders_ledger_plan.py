"""M6000–M6100: exact Orders Pix ledger and reversal previews, NO I/O.

This module never posts ledger rows or confirms financial events. An
authenticated Orders GET, independent settlement and tenant obligation
must be validated before producing a posting specification. A future
trusted PostgreSQL worker must independently recheck the proof, ownership,
single-use IDs, double-entry constraints, balance effects, and rollback.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from hashlib import sha256
from uuid import UUID

from .mp_orders_api import OrdersReadReport
from .mp_orders_settlement import (
    AuthenticatedSettlementRow,correlate_three_source,
)
from .mp_orders_workflow import validate_orders_independent_settlement
from .pix_automation_contract import (
    FinancialOperationBlocked,LoanAllocation,
    ObligationKind,PixPaymentCommand,
)

CONTRACT="AI_STUDIO_M6000_ORDERS_BALANCED_LEDGER_PLAN_V1"
REVERSAL_CONTRACT="AI_STUDIO_M6100_NONDESTRUCTIVE_REVERSAL_PLAN_V1"


class Role(str,Enum):
    CASH="TENANT_CASH_RECONCILED"
    CAPITAL="TENANT_MEMBER_CAPITAL"
    PSP_FEE="TENANT_PSP_FEE_EXPENSE"
    LOAN_PRINCIPAL="TENANT_LOAN_RECEIVABLE"
    INTEREST="TENANT_LOAN_INTEREST_REVENUE"
    MORA="TENANT_LOAN_MORA_REVENUE"
    FINE="TENANT_LOAN_FINE_REVENUE"


@dataclass(frozen=True)
class JournalLine:
    purpose:Role
    side:str
    cents:int
    def __post_init__(self):
        if (type(self.purpose) is not Role
                or self.side not in ("DR","CR")
                or type(self.cents) is not int or not 1<=self.cents<=999999999999):
            raise FinancialOperationBlocked("Lançamento contábil sem valor seguro")


@dataclass(frozen=True)
class OrdersJournalPlan:
    tenant_id:UUID
    obligation_id:UUID
    operation_id:str
    order_id:str
    payment_id:str
    bank_statement_reference:str
    source_hash:str
    journal_reference:str
    kind:str
    gross_cents:int
    fee_cents:int
    net_cents:int
    lines:tuple[JournalLine,...]
    source:str="THREE_SOURCE_READ_ONLY_PREVIEW"
    ready_for_database_commit:bool=False
    bank_reconciled:bool=False
    ledger_written:bool=False
    financial_effect_applied:bool=False

    @property
    def debits(self)->int:
        return sum(x.cents for x in self.lines if x.side=="DR")

    @property
    def credits(self)->int:
        return sum(x.cents for x in self.lines if x.side=="CR")


def _balanced(lines:tuple[JournalLine,...],gross:int)->None:
    if type(lines) is not tuple or not 2<=len(lines)<=8:
        raise FinancialOperationBlocked("Partidas dobradas incompletas")
    dr=sum(x.cents for x in lines if x.side=="DR")
    cr=sum(x.cents for x in lines if x.side=="CR")
    if dr!=cr or dr!=gross or cr!=gross:
        raise FinancialOperationBlocked("Lançamento contábil não balanceado")


def build_orders_ledger_plan(
    *,command:PixPaymentCommand,verified_order:OrdersReadReport,
    statement:AuthenticatedSettlementRow,
    loan_allocation:LoanAllocation|None=None,
)->OrdersJournalPlan:
    if type(command) is not PixPaymentCommand:
        raise FinancialOperationBlocked("Obrigação não comprovada")
    evidence=correlate_three_source(
        command=command,authenticated_order=verified_order,
        statement=statement,
    )
    validate_orders_independent_settlement(command,verified_order,evidence)
    gross=statement.gross_cents
    fee=statement.fee_cents
    net=statement.net_cents
    lines=[]
    if net:
        lines.append(JournalLine(Role.CASH,"DR",net))
    if fee:
        lines.append(JournalLine(Role.PSP_FEE,"DR",fee))
    if command.obligation.kind is ObligationKind.CONTRIBUTION:
        if loan_allocation is not None:
            raise FinancialOperationBlocked("Contribuição não contém rateio de empréstimo")
        lines.append(JournalLine(Role.CAPITAL,"CR",gross))
    elif command.obligation.kind is ObligationKind.LOAN_INSTALLMENT:
        alloc=loan_allocation
        if (type(alloc) is not LoanAllocation
                or command.obligation.loan_id is None
                or alloc.applied_cents!=gross):
            raise FinancialOperationBlocked("Imputação de prestação não validada")
        for purpose,amount in (
            (Role.LOAN_PRINCIPAL,alloc.paid_principal),
            (Role.INTEREST,alloc.paid_interest),
            (Role.MORA,alloc.paid_mora),
            (Role.FINE,alloc.paid_fine),
        ):
            if amount:
                lines.append(JournalLine(purpose,"CR",amount))
    else:
        raise FinancialOperationBlocked("Categoria financeira inválida")
    result=tuple(lines)
    _balanced(result,gross)
    if (command.obligation.kind is ObligationKind.CONTRIBUTION
            and not any(line.purpose is Role.CAPITAL for line in result)):
        raise FinancialOperationBlocked("Capital de contribuição ausente")
    if (command.obligation.kind is ObligationKind.LOAN_INSTALLMENT
            and not any(line.purpose in (
                Role.LOAN_PRINCIPAL,Role.INTEREST,Role.MORA,Role.FINE
            ) for line in result)):
        raise FinancialOperationBlocked("Prestação sem imputação")
    ref=sha256("|".join((
        "ORDERS_JOURNAL_V1",str(command.obligation.tenant_id),
        command.operation_id,verified_order.order_id,
        verified_order.payment_id,statement.statement_reference,
        statement.statement_source_hash,
        str(gross),str(fee),
        ";".join(f"{x.purpose.value}:{x.side}:{x.cents}" for x in result),
    )).encode("ascii")).hexdigest()
    return OrdersJournalPlan(
        tenant_id=command.obligation.tenant_id,
        obligation_id=command.obligation.obligation_id,
        operation_id=command.operation_id,
        order_id=verified_order.order_id,
        payment_id=verified_order.payment_id,
        bank_statement_reference=statement.statement_reference,
        source_hash=statement.statement_source_hash,
        journal_reference="OJR_"+ref[:40],
        kind=command.obligation.kind.value,
        gross_cents=gross,fee_cents=fee,net_cents=net,
        lines=result,
    )


@dataclass(frozen=True)
class AuthenticatedReversal:
    tenant_id:UUID
    order_id:str
    payment_id:str
    prior_journal_reference:str
    reversal_reference:str
    reversal_evidence_hash:str
    amount_cents:int
    fee_returned_cents:int
    net_cash_reversed_cents:int
    final_state:str
    occurred_at:datetime
    authenticated_origin:bool
    independently_verified:bool


@dataclass(frozen=True)
class ReversalPlan:
    original_journal_reference:str
    reversal_journal_reference:str
    tenant_id:UUID
    lines:tuple[JournalLine,...]
    reason:str
    requires_ledger_commit:bool=True
    original_history_preserved:bool=True
    reversal_applied:bool=False
    financial_effect_applied:bool=False


def build_full_reversal_preview(
    *,original:OrdersJournalPlan,proof:AuthenticatedReversal,
)->ReversalPlan:
    if (type(original) is not OrdersJournalPlan
            or type(proof) is not AuthenticatedReversal
            or proof.tenant_id!=original.tenant_id
            or proof.order_id!=original.order_id
            or proof.payment_id!=original.payment_id
            or proof.prior_journal_reference!=original.journal_reference
            or proof.reversal_reference==original.bank_statement_reference
            or not 8<=len(proof.reversal_reference)<=128
            or len(proof.reversal_evidence_hash)!=64
            or any(x not in "0123456789abcdef"
                   for x in proof.reversal_evidence_hash)
            or type(proof.amount_cents) is not int
            or proof.amount_cents!=original.gross_cents
            or type(proof.fee_returned_cents) is not int
            or proof.fee_returned_cents!=original.fee_cents
            or type(proof.net_cash_reversed_cents) is not int
            or proof.net_cash_reversed_cents!=original.net_cents
            or proof.final_state!="FULL_REFUND_FEE_RETURNED_SETTLED"
            or type(proof.occurred_at) is not datetime
            or proof.occurred_at.tzinfo is None
            or proof.occurred_at.utcoffset() is None
            or proof.authenticated_origin is not True
            or proof.independently_verified is not True):
        raise FinancialOperationBlocked("Estorno não comprovado por extrato")
    lines=tuple(JournalLine(x.purpose,
        "CR" if x.side=="DR" else "DR",x.cents) for x in original.lines)
    _balanced(lines,original.gross_cents)
    fingerprint=sha256("|".join((
        "ORDERS_REVERSAL_V1",str(original.tenant_id),
        original.journal_reference,proof.reversal_reference,
        proof.reversal_evidence_hash,proof.final_state,
        str(proof.fee_returned_cents),str(proof.net_cash_reversed_cents),
    )).encode("ascii")).hexdigest()
    return ReversalPlan(
        original_journal_reference=original.journal_reference,
        reversal_journal_reference="REV_"+fingerprint[:40],
        tenant_id=original.tenant_id,lines=lines,
        reason=proof.final_state,
    )
