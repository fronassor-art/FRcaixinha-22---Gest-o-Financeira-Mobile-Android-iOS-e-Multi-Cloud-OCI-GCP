"""M7700-M7900 — read-only Orders recovery scheduler (no network I/O).

A signed webhook, 200 from Orders, or an operator action never produces
a paid receipt. The policy only advises GET/independent investigation.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from hashlib import sha256
import re

from .mp_orders_incident_ops import (
    UnresolvedIncident, validate_incident, _aware,
)
from .pix_automation_contract import FinancialOperationBlocked

CONTRACT = "AI_STUDIO_M7900_ORDERS_GET_ONLY_RECOVERY_POLICY_V1"
_ORDER = re.compile(r"ORD[A-Z0-9]{12,77}\Z")


class RecoverySignal(str, Enum):
    NOT_ATTEMPTED = "NOT_ATTEMPTED"
    GET_TIMEOUT = "GET_TIMEOUT"
    GET_429 = "GET_429"
    GET_503 = "GET_503"
    GET_401 = "GET_401"
    GET_403 = "GET_403"
    ORDER_PROCESSED = "ORDER_PROCESSED"
    ORDER_PENDING = "ORDER_PENDING"
    UNKNOWN_REMOTE = "UNKNOWN_REMOTE"


class SafeRecoveryAction(str, Enum):
    READ_ORDER_ONLY = "READ_ORDER_ONLY"
    RETRY_GET_LATER = "RETRY_GET_LATER"
    VERIFY_BANK_INDEPENDENTLY = "VERIFY_BANK_INDEPENDENTLY"
    ESCALATE_HUMAN_PROVIDER = "ESCALATE_HUMAN_PROVIDER"
    BLOCK_SELLER = "BLOCK_SELLER"


@dataclass(frozen=True)
class RecoverySnapshot:
    incident: UnresolvedIncident
    order_id: str | None
    signal: RecoverySignal
    attempts: int
    now: datetime
    seller_approved: bool
    tenant_binding_verified: bool
    retry_after_seconds: int | None = None


@dataclass(frozen=True)
class RecoveryPlan:
    tenant_id: str
    operation_id: str
    action: SafeRecoveryAction
    next_get_at: datetime | None
    can_post_order: bool = False
    can_mark_paid: bool = False
    can_write_ledger: bool = False
    can_release_hold: bool = False
    can_payout: bool = False
    can_close_financial_cycle: bool = False


def plan_readonly_recovery(snapshot: RecoverySnapshot) -> RecoveryPlan:
    if type(snapshot) is not RecoverySnapshot:
        raise FinancialOperationBlocked("Contexto de recuperação não validado")
    i = snapshot.incident
    validate_incident(i)
    if (
        snapshot.order_id is not None and (
            type(snapshot.order_id) is not str
            or _ORDER.fullmatch(snapshot.order_id) is None
        )
        or type(snapshot.signal) is not RecoverySignal
        or type(snapshot.attempts) is not int
        or not 0 <= snapshot.attempts <= 1000
        or not _aware(snapshot.now)
        or snapshot.now < i.opened_at
        or type(snapshot.seller_approved) is not bool
        or type(snapshot.tenant_binding_verified) is not bool
        or snapshot.retry_after_seconds is not None and (
            type(snapshot.retry_after_seconds) is not int
            or not 0 <= snapshot.retry_after_seconds <= 600
        )
    ):
        raise FinancialOperationBlocked("Tentativa GET sem contexto íntegro")
    result = SafeRecoveryAction.ESCALATE_HUMAN_PROVIDER
    next_at = None
    if not snapshot.seller_approved or not snapshot.tenant_binding_verified:
        result = SafeRecoveryAction.BLOCK_SELLER
    elif snapshot.signal in (RecoverySignal.GET_401, RecoverySignal.GET_403):
        result = SafeRecoveryAction.BLOCK_SELLER
    elif snapshot.order_id is None:
        # The PSP may have created an Order despite an unknown POST timeout.
        result = SafeRecoveryAction.ESCALATE_HUMAN_PROVIDER
    elif snapshot.signal == RecoverySignal.ORDER_PROCESSED:
        # Orders processed is not a bank statement, even with signed webhook.
        result = SafeRecoveryAction.VERIFY_BANK_INDEPENDENTLY
    elif snapshot.signal == RecoverySignal.ORDER_PENDING:
        result = SafeRecoveryAction.READ_ORDER_ONLY
    elif snapshot.signal == RecoverySignal.NOT_ATTEMPTED:
        result = SafeRecoveryAction.READ_ORDER_ONLY
    elif (
        snapshot.signal in (
            RecoverySignal.GET_TIMEOUT, RecoverySignal.GET_429,
            RecoverySignal.GET_503,
        )
        and snapshot.attempts < 6
        and snapshot.now - i.opened_at <= timedelta(hours=2)
    ):
        # Deterministic bounded jitter avoids a synchronized tenant herd.
        seed = f"{i.tenant_id}|{i.operation_id}|{snapshot.attempts}"
        jitter = int(sha256(seed.encode("ascii")).hexdigest()[:4], 16) % 11
        delay = min(300, 15 * (2 ** min(snapshot.attempts, 5)) + jitter)
        if snapshot.retry_after_seconds is not None:
            delay = max(delay, snapshot.retry_after_seconds)
        next_at = snapshot.now + timedelta(seconds=delay)
        result = SafeRecoveryAction.RETRY_GET_LATER
    return RecoveryPlan(
        tenant_id=str(i.tenant_id), operation_id=i.operation_id,
        action=result, next_get_at=next_at,
    )
