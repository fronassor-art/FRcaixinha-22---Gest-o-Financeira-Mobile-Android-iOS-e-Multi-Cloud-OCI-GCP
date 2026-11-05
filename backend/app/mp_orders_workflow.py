"""M4600 — Orders API application workflow and settlement journaling ports.

FR Caixinha manages payment obligations; Mercado Pago executes them.
No public callback may claim financial settlement. Real posting requires
independent source + transactional ledger repository not provided here.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from .pix_automation_contract import (
    PixPaymentCommand,LoanAllocation,FinancialOperationBlocked,
)
from .mp_orders_api import OrdersPixCheckout,OrdersReadReport

CONTRACT="AI_STUDIO_M4600_ORDERS_CONCILIATION_WORKFLOW_PORTS_V1"


class OrdersCollectionProvider(Protocol):
    async def create(self,*,command:PixPaymentCommand,
                     payer_email:str)->OrdersPixCheckout: ...
    async def get(self,*,command:PixPaymentCommand,
                  order_id:str)->OrdersReadReport: ...


@dataclass(frozen=True)
class OrdersSettlementEvidence:
    """Only trusted workers may construct this after authentic bank evidence."""
    tenant_id:UUID
    account_id:str
    operation_id:str
    external_reference:str
    order_id:str
    payment_id:str
    amount_cents:int
    bank_statement_reference:str
    bank_statement_hash:str
    bank_settled_at:datetime
    bank_settlement_attested:bool
    account_binding_attested:bool
    independent_statement_source:bool


@dataclass(frozen=True)
class OrdersPaymentReceipt:
    receipt_id:UUID
    tenant_id:UUID
    order_id:str
    payment_id:str
    operation_id:str
    obligation_id:UUID
    amount_cents:int
    ledger_transaction_id:UUID
    statement_reference:str
    bank_reconciled:bool
    status:str="CONFIRMADO_CONCILIADO"


class OrdersPaymentJournal(Protocol):
    async def reserve_idempotent(self,command:PixPaymentCommand)->str: ...
    async def lookup_checkout(self,operation_id:str)->OrdersPixCheckout|None: ...
    async def write_checkout(self,command:PixPaymentCommand,
                             checkout:OrdersPixCheckout)->None: ...
    async def mark_uncertain(self,operation_id:str)->None: ...
    async def atomic_post_once(
        self,*,command:PixPaymentCommand,
        bank:OrdersSettlementEvidence,
        loan_allocation:LoanAllocation|None,
    )->OrdersPaymentReceipt: ...


class OrdersIndependentStatementPort(Protocol):
    async def fetch_and_attest(
        self,*,command:PixPaymentCommand,
        verified_get:OrdersReadReport,
    )->OrdersSettlementEvidence|None: ...


def validate_orders_independent_settlement(
    command:PixPaymentCommand,
    provider_read:OrdersReadReport,
    bank:OrdersSettlementEvidence,
)->None:
    """Guard-only: a producer still needs a real trusted attestation."""
    if (type(command) is not PixPaymentCommand
            or type(provider_read) is not OrdersReadReport
            or type(bank) is not OrdersSettlementEvidence
            or provider_read.provider_response_structure_verified is not True
            or provider_read.ready_for_independent_settlement_lookup is not True
            or provider_read.status!="processed"
            or provider_read.status_detail!="accredited"
            or provider_read.payment_status!="processed"
            or provider_read.payment_detail!="accredited"
            or bank.tenant_id!=command.obligation.tenant_id
            or bank.account_id!=command.obligation.provider_account_id
            or bank.operation_id!=command.operation_id
            or bank.external_reference!=command.external_reference
            or bank.order_id!=provider_read.order_id
            or bank.payment_id!=provider_read.payment_id
            or bank.amount_cents!=command.amount_cents
            or type(bank.bank_statement_reference) is not str
            or not 8<=len(bank.bank_statement_reference)<=128
            or type(bank.bank_statement_hash) is not str
            or len(bank.bank_statement_hash)!=64
            or any(c not in "0123456789abcdef" for c in bank.bank_statement_hash)
            or type(bank.bank_settled_at) is not datetime
            or bank.bank_settled_at.tzinfo is None
            or bank.bank_settled_at.utcoffset() is None
            or bank.bank_settlement_attested is not True
            or bank.account_binding_attested is not True
            or bank.independent_statement_source is not True):
        raise FinancialOperationBlocked("Orders sem conciliação bancária independente")


class OrdersCollectionAutomation:
    def __init__(
        self,*,provider:OrdersCollectionProvider,
        journal:OrdersPaymentJournal,
        statements:OrdersIndependentStatementPort,
    ):
        self.provider=provider
        self.journal=journal
        self.statements=statements

    async def create(
        self,*,command:PixPaymentCommand,payer_email:str,
    )->OrdersPixCheckout:
        status=await self.journal.reserve_idempotent(command)
        if status=="EXISTS":
            old=await self.journal.lookup_checkout(command.operation_id)
            if type(old) is not OrdersPixCheckout:
                raise FinancialOperationBlocked("Order em estado incerto")
            return old
        if status!="NEW":
            raise FinancialOperationBlocked("Order não autorizada pelo journal")
        try:
            result=await self.provider.create(
                command=command,payer_email=payer_email,
            )
            if (type(result) is not OrdersPixCheckout
                    or result.operation_id!=command.operation_id
                    or result.amount_cents!=command.amount_cents
                    or result.status!="action_required"
                    or result.status_detail!="waiting_transfer"
                    or result.capital_recognized is not False
                    or result.bank_reconciled is not False
                    or result.ledger_written is not False):
                raise FinancialOperationBlocked("Order criada sem estado validado")
            await self.journal.write_checkout(command,result)
            return result
        except Exception:
            await self.journal.mark_uncertain(command.operation_id)
            raise

    async def reconcile(
        self,*,command:PixPaymentCommand,order_id:str,
        loan_allocation:LoanAllocation|None=None,
    )->OrdersPaymentReceipt|None:
        # Verify the persisted reservation BEFORE trusting GET/notification.
        # A caller-supplied Order ID is never sufficient to choose a payee.
        persisted=await self.journal.lookup_checkout(command.operation_id)
        if (type(persisted) is not OrdersPixCheckout
                or persisted.operation_id!=command.operation_id
                or persisted.order_id!=order_id
                or persisted.amount_cents!=command.amount_cents
                or persisted.bank_reconciled is not False
                or persisted.ledger_written is not False):
            raise FinancialOperationBlocked("Order sem reserva comprovada")
        report=await self.provider.get(command=command,order_id=order_id)
        if (type(report) is not OrdersReadReport
                or report.order_id!=order_id
                or report.payment_id!=persisted.payment_id):
            raise FinancialOperationBlocked("Consulta Orders inválida")
        if not report.ready_for_independent_settlement_lookup:
            return None
        proof=await self.statements.fetch_and_attest(
            command=command,verified_get=report)
        if proof is None:
            return None
        validate_orders_independent_settlement(command,report,proof)
        if command.obligation.kind.value=="LOAN_INSTALLMENT":
            if (type(loan_allocation) is not LoanAllocation
                    or loan_allocation.applied_cents!=command.amount_cents):
                raise FinancialOperationBlocked("Imputação não comprovada para empréstimo")
        elif loan_allocation is not None:
            raise FinancialOperationBlocked("Contribuição não admite juros de empréstimo")
        # Only the independently audited DB worker may implement this port.
        # It must enforce ownership, serializable transaction, two-entry
        # balance, receipt idempotency and non-destructive reversals.
        receipt=await self.journal.atomic_post_once(
            command=command,bank=proof,loan_allocation=loan_allocation)
        if (type(receipt) is not OrdersPaymentReceipt
                or receipt.operation_id!=command.operation_id
                or receipt.tenant_id!=command.obligation.tenant_id
                or receipt.obligation_id!=command.obligation.obligation_id
                or receipt.order_id!=proof.order_id
                or receipt.payment_id!=proof.payment_id
                or receipt.amount_cents!=command.amount_cents
                or receipt.bank_reconciled is not True
                or receipt.ledger_transaction_id is None):
            raise FinancialOperationBlocked("Recibo de Orders sem compromisso de ledger")
        return receipt
