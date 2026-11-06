"""M5200 — three-source Mercado Pago Orders Pix settlement contract.

Do not treat signed webhook, Orders GET or CSV uploaded by the member as
final bank settlement. Source must be an independent authenticated read
through an operator-controlled connector, and must match all immutable
obligation identifiers before a transactional journal may even be attempted.

These are pure validators: no real bank connection, no receipt creation.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime,timezone
from typing import Protocol
from uuid import UUID
import re

from .pix_automation_contract import PixPaymentCommand,FinancialOperationBlocked
from .mp_orders_api import OrdersReadReport
from .mp_orders_workflow import OrdersSettlementEvidence

CONTRACT="AI_STUDIO_M5200_ORDERS_THREE_SOURCE_SETTLEMENT_V1"

_STMT=re.compile(r"[A-Za-z0-9._:/-]{8,128}\Z")
_HEX=re.compile(r"[a-f0-9]{64}\Z")
_PROVIDER=re.compile(r"[0-9]{1,40}\Z")
_MAX_CENTS=999999999999


@dataclass(frozen=True)
class AuthenticatedSettlementRow:
    tenant_id: UUID
    collector_id: str
    order_id: str
    payment_id: str
    external_reference: str
    statement_reference: str
    statement_source_hash: str
    currency: str
    gross_cents: int
    fee_cents: int
    net_cents: int
    settlement_state: str
    settled_at: datetime
    fetched_at: datetime
    authenticated_provider_identity: bool
    authenticated_statement_transport: bool
    independently_settled: bool
    source_kind: str = "PROVIDER_AUTHENTICATED_STATEMENT_API"


class TrustedSettlementReader(Protocol):
    async def fetch(
        self, *, tenant_id:UUID,provider_account_id:str,
        order_id:str,payment_id:str,
    )->AuthenticatedSettlementRow|None: ...


def correlate_three_source(
    *,command:PixPaymentCommand,
    authenticated_order:OrdersReadReport,
    statement:AuthenticatedSettlementRow,
)->OrdersSettlementEvidence:
    """Fail-closed accounting preflight; not evidence of a ledger commit."""
    if (type(command) is not PixPaymentCommand
            or type(authenticated_order) is not OrdersReadReport
            or type(statement) is not AuthenticatedSettlementRow
            or authenticated_order.provider_response_structure_verified is not True
            or authenticated_order.ready_for_independent_settlement_lookup is not True
            or authenticated_order.bank_reconciled is not False
            or authenticated_order.ledger_written is not False
            or authenticated_order.financial_effect_applied is not False
            or authenticated_order.status!="processed"
            or authenticated_order.status_detail!="accredited"
            or authenticated_order.payment_status!="processed"
            or authenticated_order.payment_detail!="accredited"
            or statement.source_kind!="PROVIDER_AUTHENTICATED_STATEMENT_API"
            or statement.tenant_id!=command.obligation.tenant_id
            or statement.collector_id!=command.obligation.provider_account_id
            or not _PROVIDER.fullmatch(statement.collector_id)
            or statement.order_id!=authenticated_order.order_id
            or statement.payment_id!=authenticated_order.payment_id
            or statement.external_reference!=command.external_reference
            or not _STMT.fullmatch(statement.statement_reference)
            or not _HEX.fullmatch(statement.statement_source_hash)
            or statement.currency!="BRL"
            or type(statement.gross_cents) is not int
            or type(statement.fee_cents) is not int
            or type(statement.net_cents) is not int
            or not 0<statement.gross_cents<=_MAX_CENTS
            or statement.gross_cents!=command.amount_cents
            or not 0<=statement.fee_cents<=statement.gross_cents
            or statement.net_cents!=statement.gross_cents-statement.fee_cents
            or statement.settlement_state!="SETTLED"
            or type(statement.settled_at) is not datetime
            or type(statement.fetched_at) is not datetime
            or statement.settled_at.tzinfo is None
            or statement.fetched_at.tzinfo is None
            or statement.settled_at.utcoffset() is None
            or statement.fetched_at.utcoffset() is None
            or statement.settled_at>statement.fetched_at
            or statement.authenticated_provider_identity is not True
            or statement.authenticated_statement_transport is not True
            or statement.independently_settled is not True):
        raise FinancialOperationBlocked("Conciliação Orders sem 3 fontes independentes")
    return OrdersSettlementEvidence(
        tenant_id=statement.tenant_id,
        account_id=statement.collector_id,
        operation_id=command.operation_id,
        external_reference=statement.external_reference,
        order_id=statement.order_id,
        payment_id=statement.payment_id,
        amount_cents=statement.gross_cents,
        bank_statement_reference=statement.statement_reference,
        bank_statement_hash=statement.statement_source_hash,
        bank_settled_at=statement.settled_at,
        bank_settlement_attested=True,
        account_binding_attested=True,
        independent_statement_source=True,
    )


class IndependentOrdersSettlementService:
    """Server-only unprivileged worker needs authenticated statement reader."""

    def __init__(self,reader:TrustedSettlementReader):
        self.reader=reader

    async def verify(
        self,*,command:PixPaymentCommand,
        authenticated_order:OrdersReadReport,
    )->OrdersSettlementEvidence|None:
        if (type(command) is not PixPaymentCommand
                or type(authenticated_order) is not OrdersReadReport
                or not authenticated_order.ready_for_independent_settlement_lookup
                or authenticated_order.bank_reconciled is not False
                or authenticated_order.ledger_written is not False
                or authenticated_order.financial_effect_applied is not False):
            return None
        stmt=await self.reader.fetch(
            tenant_id=command.obligation.tenant_id,
            provider_account_id=command.obligation.provider_account_id,
            order_id=authenticated_order.order_id,
            payment_id=authenticated_order.payment_id,
        )
        if stmt is None:return None
        return correlate_three_source(
            command=command,authenticated_order=authenticated_order,
            statement=stmt,
        )
