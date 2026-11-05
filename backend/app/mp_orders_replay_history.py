"""M11100-M12000: offline rollback/replay detection for unresolved Orders.

In-memory reconstruction ONLY. The chain hashes UNTRUSTED claims, and
does not establish authenticity, durability, signature, operator identity,
bank settlement, real GET permissions, or a distributed idempotency lock.
Never transfers funds, settles payments or authorizes ledger entries.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from uuid import UUID

from .mp_orders_case_integrity import (
    IntegratedCaseSnapshot, inspect_integrated_case,
)
from .mp_orders_recovery_scheduler import RecoverySignal
from .pix_automation_contract import FinancialOperationBlocked

CONTRACT = "AI_STUDIO_M12000_ORDERS_REPLAY_ROLLBACK_PREFLIGHT_V1"
_GENESIS = "0" * 64
_MAX_SNAPSHOTS = 64
_TERMINAL_AUTH = frozenset((
    RecoverySignal.GET_401, RecoverySignal.GET_403,
))
_PROCESSED = RecoverySignal.ORDER_PROCESSED


@dataclass(frozen=True)
class ReplayStep:
    sequence: int
    observed_at: datetime
    attempts: int
    case_fingerprint: str
    previous_digest: str
    audit_digest: str
    read_candidate_policy_only: bool
    hold_active: bool = True
    bank_origin_verified: bool = False
    network_get_executed: bool = False
    paid_authorized: bool = False


@dataclass(frozen=True)
class ReplayHistory:
    tenant_id: UUID
    provider_account_id: str
    operation_id: str
    order_id: str | None
    payment_id: str
    steps: tuple[ReplayStep, ...]
    last_digest: str
    unique_snapshots: int
    exact_replays_suppressed: int
    hold_active: bool = True
    history_persisted: bool = False
    signature_verified: bool = False
    operator_identity_authenticated: bool = False
    distributed_lease_held: bool = False
    get_execution_authorized: bool = False
    mark_paid_authorized: bool = False
    ledger_write_authorized: bool = False
    payout_authorized: bool = False
    financial_closing_authorized: bool = False


@dataclass(frozen=True)
class TenantReplaySummary:
    tenant_id: UUID
    histories: int
    unique_snapshots: int
    exact_replays_suppressed: int
    cases_needing_independent_bank_proof: int
    contains_operation_ids: bool = False
    history_persisted: bool = False
    independent_bank_proof: bool = False
    all_financial_effects_blocked: bool = True


def _utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _case_identifiers(snapshot: IntegratedCaseSnapshot) -> tuple[str, str, str, str]:
    i = snapshot.incident
    p = snapshot.claimed_evidence.provider
    return (str(i.tenant_id), i.provider_account_id, p.order_id, p.payment_id)


def replay_unresolved_history(
    snapshots: tuple[IntegratedCaseSnapshot, ...],
) -> ReplayHistory:
    """Reconstruct monotonic snapshots; never claim they survived a reboot.

    A complete history must be independently loaded from an authenticated,
    durable source in future. This function cannot detect omitted history.
    """
    if (
        type(snapshots) is not tuple
        or not 1 <= len(snapshots) <= _MAX_SNAPSHOTS
    ):
        raise FinancialOperationBlocked("Histórico vazio, excedido ou não confiável")

    first = snapshots[0]
    first_decision = inspect_integrated_case(first)
    base = first.incident
    first_ids = _case_identifiers(first)
    previous = None
    previous_stamp: datetime | None = None
    previous_fingerprint: str | None = None
    previous_attempts: int | None = None
    previous_window: datetime | None = None
    previous_failure_count: int | None = None
    previous_timeline: tuple = ()
    seller_revoked_seen = False
    binding_invalid_seen = False
    terminal_auth_seen = False
    processed_seen = False
    steps: list[ReplayStep] = []
    suppressed = 0
    digest = _GENESIS

    for snapshot in snapshots:
        decision = inspect_integrated_case(snapshot)
        i, r, c = snapshot.incident, snapshot.recovery, snapshot.circuit
        if (
            i != base or decision.tenant_id != base.tenant_id
            or decision.operation_id != base.operation_id
            or _case_identifiers(snapshot) != first_ids
            or r.order_id != first.recovery.order_id
        ):
            raise FinancialOperationBlocked(
                "Histórico com troca de tenant, incidente, Order ou Payment"
            )
        # A later revision may only append authenticated-identity PREVIEW
        # events. The actual operators are not authenticated here.
        if (
            len(snapshot.timeline) < len(previous_timeline)
            or snapshot.timeline[:len(previous_timeline)] != previous_timeline
        ):
            raise FinancialOperationBlocked(
                "Histórico de revisão alterado ou retrocedido"
            )
        stamp = r.now
        fingerprint = decision.case_fingerprint
        if previous_stamp is not None:
            if stamp < previous_stamp:
                raise FinancialOperationBlocked(
                    "Rollback de relógio ou snapshot mais antigo"
                )
            if stamp == previous_stamp:
                if fingerprint != previous_fingerprint or snapshot != previous:
                    raise FinancialOperationBlocked(
                        "Replay com mesmo horário e conteúdo divergente"
                    )
                suppressed += 1
                continue
            # A retry counter can stay equal while waiting, or advance by
            # exactly one; skipped retries hide unverified network effects.
            if r.attempts < previous_attempts or (
                r.attempts > previous_attempts + 1
            ):
                raise FinancialOperationBlocked(
                    "Tentativas retrocedidas ou saltadas"
                )
            if c.failure_window_opened_at < previous_window:
                raise FinancialOperationBlocked("Janela do circuito retrocedeu")
            if (
                c.failure_window_opened_at == previous_window
                and c.failures_in_window < previous_failure_count
            ):
                raise FinancialOperationBlocked(
                    "Falhas apagadas sem nova janela de circuito"
                )
            if previous.recovery.order_id is None and r.order_id is not None:
                raise FinancialOperationBlocked(
                    "Order introduzida sem prova autenticada"
                )
            if terminal_auth_seen and r.signal not in _TERMINAL_AUTH:
                raise FinancialOperationBlocked(
                    "Recuperação de credencial revogada sem novo incidente"
                )
            if processed_seen and r.signal is not _PROCESSED:
                raise FinancialOperationBlocked(
                    "Status processado retrocedido sem evidência de estorno"
                )
            if (
                (seller_revoked_seen and r.seller_approved)
                or (binding_invalid_seen and r.tenant_binding_verified)
            ):
                raise FinancialOperationBlocked(
                    "Vínculo de seller/tenant restaurado sem nova autenticação"
                )
        previous = snapshot
        previous_stamp = stamp
        previous_fingerprint = fingerprint
        previous_attempts = r.attempts
        previous_window = c.failure_window_opened_at
        previous_failure_count = c.failures_in_window
        previous_timeline = snapshot.timeline
        seller_revoked_seen = seller_revoked_seen or not r.seller_approved
        binding_invalid_seen = (
            binding_invalid_seen or not r.tenant_binding_verified
        )
        terminal_auth_seen = terminal_auth_seen or r.signal in _TERMINAL_AUTH
        processed_seen = processed_seen or r.signal is _PROCESSED
        sequence = len(steps) + 1
        payload = json.dumps({
            "domain": "AI_STUDIO_M12000_NO_AUTHENTICATED_HISTORY_V1",
            "sequence": sequence,
            "tenant_id": str(i.tenant_id),
            "seller": i.provider_account_id,
            "operation_id": i.operation_id,
            "order_id": r.order_id,
            "payment_id": first_ids[3],
            "observed_at": _utc(stamp),
            "attempts": r.attempts,
            "case_fingerprint": fingerprint,
            "prev": digest,
            "hold": True,
            "authorized_money_effects": False,
        }, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        next_digest = sha256(payload.encode("ascii")).hexdigest()
        steps.append(ReplayStep(
            sequence=sequence,
            observed_at=stamp,
            attempts=r.attempts,
            case_fingerprint=fingerprint,
            previous_digest=digest,
            audit_digest=next_digest,
            read_candidate_policy_only=decision.read_candidate_policy_only,
        ))
        digest = next_digest
    return ReplayHistory(
        tenant_id=first_decision.tenant_id,
        provider_account_id=base.provider_account_id,
        operation_id=base.operation_id,
        order_id=first.recovery.order_id,
        payment_id=first_ids[3],
        steps=tuple(steps), last_digest=digest,
        unique_snapshots=len(steps), exact_replays_suppressed=suppressed,
    )


def verify_replayed_history(
    snapshots: tuple[IntegratedCaseSnapshot, ...],
    exported: ReplayHistory,
) -> ReplayHistory:
    """Checksum comparison against the full supplied inputs, NOT a signature."""
    actual = replay_unresolved_history(snapshots)
    if type(exported) is not ReplayHistory or exported != actual:
        raise FinancialOperationBlocked(
            "Prévia de histórico ou sua cadeia foi adulterada"
        )
    return actual


def summarize_tenant_replay_histories(
    tenant_id: UUID,
    histories: tuple[tuple[IntegratedCaseSnapshot, ...], ...],
) -> TenantReplaySummary:
    """Only aggregate counts, with duplicate Order/Payment detection in batch."""
    if (
        type(tenant_id) is not UUID or tenant_id.int == 0
        or type(histories) is not tuple or len(histories) > 100
    ):
        raise FinancialOperationBlocked(
            "Lote de históricos de caixinha malformado"
        )
    by_operation: dict[str, tuple[IntegratedCaseSnapshot, ...]] = {}
    orders: dict[tuple[str, str], str] = {}
    payments: dict[tuple[str, str], str] = {}
    total_steps = 0
    suppressed = 0
    for snapshots in histories:
        history = replay_unresolved_history(snapshots)
        if history.tenant_id != tenant_id:
            raise FinancialOperationBlocked(
                "Histórico agregado cruza caixinhas"
            )
        if history.operation_id in by_operation:
            if by_operation[history.operation_id] != snapshots:
                raise FinancialOperationBlocked(
                    "Operação repetida com histórico divergente"
                )
            continue
        for ownership, reference in (
            (orders, history.order_id), (payments, history.payment_id),
        ):
            if reference is not None:
                key = (history.provider_account_id, reference)
                prev = ownership.setdefault(key, history.operation_id)
                if prev != history.operation_id:
                    raise FinancialOperationBlocked(
                        "Order ou Payment reutilizado entre operações"
                    )
        by_operation[history.operation_id] = snapshots
        total_steps += history.unique_snapshots
        suppressed += history.exact_replays_suppressed
    return TenantReplaySummary(
        tenant_id=tenant_id, histories=len(by_operation),
        unique_snapshots=total_steps,
        exact_replays_suppressed=suppressed,
        cases_needing_independent_bank_proof=len(by_operation),
    )
