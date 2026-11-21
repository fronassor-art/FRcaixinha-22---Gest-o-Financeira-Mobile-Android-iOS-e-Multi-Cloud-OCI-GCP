"""M8400-M8600: pure per-tenant read-only circuit policy.

This module does not enforce a distributed rate limit: counters, signed
tenant bindings and probe leases still require a durable trusted worker.
It NEVER creates an Order, settles a Pix, posts ledger or issues payout.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from re import fullmatch
from uuid import UUID

from .pix_automation_contract import FinancialOperationBlocked

CONTRACT = "AI_STUDIO_M8600_READONLY_RECOVERY_CIRCUIT_POLICY_V1"


class ReadonlyAction(str, Enum):
    GET_CANDIDATE_ONLY = "GET_CANDIDATE_ONLY"
    WAIT_COOLDOWN = "WAIT_COOLDOWN"
    CIRCUIT_OPEN = "CIRCUIT_OPEN"
    HUMAN_PROVIDER_REVIEW = "HUMAN_PROVIDER_REVIEW"
    SELLER_BLOCKED = "SELLER_BLOCKED"


@dataclass(frozen=True)
class ReadonlyCircuitSnapshot:
    tenant_id: UUID
    provider_account_id: str
    operation_id: str
    observed_at: datetime
    failure_window_opened_at: datetime
    failures_in_window: int
    last_failure_at: datetime | None
    recovery_attempts: int
    seller_approved: bool
    tenant_binding_verified: bool


@dataclass(frozen=True)
class ReadonlyCircuitDecision:
    tenant_id: UUID
    operation_id: str
    action: ReadonlyAction
    retry_not_before: datetime | None
    can_execute_get: bool = False
    can_post_order: bool = False
    can_mark_paid: bool = False
    can_release_hold: bool = False
    can_write_ledger: bool = False
    can_issue_payout: bool = False


def _aware(value: datetime) -> bool:
    return (
        type(value) is datetime and value.tzinfo is not None
        and value.utcoffset() is not None
    )


def decide_readonly_circuit(s: ReadonlyCircuitSnapshot) -> ReadonlyCircuitDecision:
    if (
        type(s) is not ReadonlyCircuitSnapshot
        or type(s.tenant_id) is not UUID or not s.tenant_id.int
        or type(s.provider_account_id) is not str
        or fullmatch(r"[0-9]{1,40}", s.provider_account_id) is None
        or type(s.operation_id) is not str
        or fullmatch(r"P_[a-f0-9]{32}", s.operation_id) is None
        or not _aware(s.observed_at)
        or not _aware(s.failure_window_opened_at)
        or s.failure_window_opened_at > s.observed_at
        or type(s.failures_in_window) is not int
        or not 0 <= s.failures_in_window <= 100000
        or type(s.recovery_attempts) is not int
        or not 0 <= s.recovery_attempts <= 10000
        or type(s.seller_approved) is not bool
        or type(s.tenant_binding_verified) is not bool
        or s.last_failure_at is not None and (
            not _aware(s.last_failure_at)
            or s.last_failure_at > s.observed_at
            or s.last_failure_at < s.failure_window_opened_at
        )
        or (s.failures_in_window == 0) != (s.last_failure_at is None)
    ):
        raise FinancialOperationBlocked("Circuito read-only sem contexto válido")
    action = ReadonlyAction.GET_CANDIDATE_ONLY
    next_at = None
    if not s.seller_approved or not s.tenant_binding_verified:
        action = ReadonlyAction.SELLER_BLOCKED
    elif s.recovery_attempts >= 6:
        action = ReadonlyAction.HUMAN_PROVIDER_REVIEW
    elif (
        s.failures_in_window >= 5
        and s.observed_at - s.failure_window_opened_at <= timedelta(minutes=15)
    ):
        action = ReadonlyAction.CIRCUIT_OPEN
        next_at = s.failure_window_opened_at + timedelta(minutes=15)
    elif s.failures_in_window >= 5:
        # No automatic half-open / tokenless probe. The server must
        # authenticate a new window and acquire a distributed probe lease.
        action = ReadonlyAction.HUMAN_PROVIDER_REVIEW
    elif s.last_failure_at is not None:
        cooldown = min(300, 15 * 2 ** min(s.failures_in_window - 1, 4))
        next_at = s.last_failure_at + timedelta(seconds=cooldown)
        if s.observed_at < next_at:
            action = ReadonlyAction.WAIT_COOLDOWN
        else:
            next_at = None
    return ReadonlyCircuitDecision(
        tenant_id=s.tenant_id, operation_id=s.operation_id,
        action=action, retry_not_before=next_at,
    )
