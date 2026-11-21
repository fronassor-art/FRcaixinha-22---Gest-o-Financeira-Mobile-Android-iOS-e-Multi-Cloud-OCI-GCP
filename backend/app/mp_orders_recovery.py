"""M5300: deterministic Orders recovery after failures/replay, no re-POST.

A provider timeout is economically ambiguous. Neither frontend retries
nor signed webhooks are grounds to create a second charge or mark one paid.
The recovery worker may only do read-only GET if the Order ID is known;
otherwise it must request human/provider-assisted tracing.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from uuid import UUID
import re

CONTRACT="AI_STUDIO_M5300_ORDERS_RECOVERY_REPLAY_V1"
_ORD=re.compile(r"ORD[A-Z0-9]{12,77}\Z")
_OPERATION=re.compile(r"P_[0-9a-f]{32}\Z")
_MP=re.compile(r"[0-9]{1,40}\Z")


class RecoveryAction(str,Enum):
    NO_ACTION="NO_ACTION"
    READ_ORDER_ONLY="READ_ORDER_ONLY"
    CHECK_BANK_ONLY="CHECK_BANK_ONLY"
    PROVIDER_SUPPORT_REVIEW="PROVIDER_SUPPORT_REVIEW"
    BLOCKED="BLOCKED"


@dataclass(frozen=True)
class OrdersRecoveryState:
    tenant_id:UUID
    merchant_account_id:str
    operation_id:str
    status:str
    order_id:str|None
    receipt_exists:bool
    provider_get_processed:bool
    bank_settlement_confirmed:bool
    merchant_binding_valid:bool
    tenant_context_valid:bool
    signed_webhook_seen:bool


@dataclass(frozen=True)
class OrdersRecoveryDecision:
    action:RecoveryAction
    requires_human_review:bool
    can_repost_to_provider:bool=False
    can_mark_paid:bool=False
    can_write_ledger:bool=False
    can_issue_payout:bool=False


def decide_orders_recovery(state:OrdersRecoveryState)->OrdersRecoveryDecision:
    if (type(state) is not OrdersRecoveryState
            or type(state.tenant_id) is not UUID
            or type(state.merchant_account_id) is not str
            or not _MP.fullmatch(state.merchant_account_id)
            or type(state.operation_id) is not str
            or not _OPERATION.fullmatch(state.operation_id)
            or state.status not in (
              "PENDENTE","AGUARDANDO_PROVEDOR",
              "PENDENTE_CONCILIACAO","LIQUIDADO_CONCILIADO",
              "FALHOU","REVERTIDO"
            )
            or state.order_id is not None and (
              type(state.order_id) is not str or not _ORD.fullmatch(state.order_id)
            )
            or any(type(v) is not bool for v in (
                state.receipt_exists,state.provider_get_processed,
                state.bank_settlement_confirmed,state.merchant_binding_valid,
                state.tenant_context_valid,state.signed_webhook_seen
            ))):
        raise ValueError("Orders recovery context invalid")
    if state.merchant_binding_valid is False or state.tenant_context_valid is False:
        return OrdersRecoveryDecision(RecoveryAction.BLOCKED,True)
    if state.status in ("LIQUIDADO_CONCILIADO","REVERTIDO","FALHOU"):
        return OrdersRecoveryDecision(RecoveryAction.NO_ACTION,False)
    if state.receipt_exists:
        # Inconsistent states require manual investigation; do not re-post
        # and do not mutate an existing receipt via this worker.
        return OrdersRecoveryDecision(RecoveryAction.PROVIDER_SUPPORT_REVIEW,True)
    if state.order_id is None:
        # Unknown network timeout: an Order MAY already exist remotely.
        return OrdersRecoveryDecision(RecoveryAction.PROVIDER_SUPPORT_REVIEW,True)
    if state.provider_get_processed:
        # Even signed webhook + GET processed is not verified bank settlement.
        # Bank evidence must be fetched from an independent authenticated rail.
        return OrdersRecoveryDecision(RecoveryAction.CHECK_BANK_ONLY,False)
    return OrdersRecoveryDecision(RecoveryAction.READ_ORDER_ONLY,False)
