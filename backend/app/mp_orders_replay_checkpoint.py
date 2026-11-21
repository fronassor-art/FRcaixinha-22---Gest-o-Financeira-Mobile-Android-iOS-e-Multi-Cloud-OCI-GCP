"""AI Studio M12100-M12600: offline restart checkpoint comparison.

The caller supplies ALL snapshots and the claimed prior checkpoint. This
module NEVER reads a durable database, authenticates an operator, signs a
record, acquires a lease or schedules GET/settlement. A malicious caller
can replace both the snapshots and checkpoint; no trust root is established.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from uuid import UUID

from .mp_orders_case_integrity import IntegratedCaseSnapshot
from .mp_orders_replay_history import replay_unresolved_history
from .pix_automation_contract import FinancialOperationBlocked

CONTRACT = "AI_STUDIO_M12600_RESTART_CHECKPOINT_OFFLINE_V1"
_MAX_SNAPSHOTS = 64


@dataclass(frozen=True)
class OfflineCheckpoint:
    tenant_id: UUID
    provider_account_id: str
    operation_id: str
    claimed_order_id: str | None
    claimed_payment_id: str
    snapshot_count: int
    unique_steps: int
    exact_replays: int
    history_head_digest: str
    last_attempts: int
    last_observed_utc: str
    checksum: str
    hold_active: bool = True
    trust_anchor_authenticated: bool = False
    checkpoint_persisted: bool = False
    operator_authenticated: bool = False
    externally_signed: bool = False
    get_execution_authorized: bool = False
    financial_effect_authorized: bool = False
    ledger_write_authorized: bool = False
    payout_authorized: bool = False


@dataclass(frozen=True)
class RestartReview:
    tenant_id: UUID
    operation_id: str
    prefix_verified_against_supplied_claim: bool
    new_unique_steps: int
    new_exact_replays: int
    resumed_history_digest: str
    hold_active: bool = True
    trusted_checkpoint_source_verified: bool = False
    crash_consistency_proven: bool = False
    durable_store_updated: bool = False
    operator_authenticated: bool = False
    get_execution_authorized: bool = False
    ledger_write_authorized: bool = False
    financial_effect_authorized: bool = False
    payout_authorized: bool = False


def _canonical(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def make_offline_checkpoint(
    snapshots: tuple[IntegratedCaseSnapshot, ...],
) -> OfflineCheckpoint:
    """This is a test fixture/checksum, not a persisted high watermark."""
    if type(snapshots) is not tuple or not 1 <= len(snapshots) <= _MAX_SNAPSHOTS:
        raise FinancialOperationBlocked("Checkpoint sem histórico completo permitido")
    history = replay_unresolved_history(snapshots)
    last = history.steps[-1]
    payload = {
        "domain": "AI_STUDIO_M12600_UNAUTHENTICATED_CHECKPOINT_V1",
        "tenant_id": str(history.tenant_id),
        "seller": history.provider_account_id,
        "operation_id": history.operation_id,
        "order": history.order_id,
        "payment": history.payment_id,
        "snapshot_count": len(snapshots),
        "unique_steps": history.unique_snapshots,
        "exact_replays": history.exact_replays_suppressed,
        "history_digest": history.last_digest,
        "last_attempts": last.attempts,
        "last_observed_utc": _canonical(last.observed_at),
        "hold_active": True,
        "money_effects_authorized": False,
    }
    raw = json.dumps(payload, ensure_ascii=True, sort_keys=True,
                     separators=(",", ":")).encode("ascii")
    return OfflineCheckpoint(
        tenant_id=history.tenant_id,
        provider_account_id=history.provider_account_id,
        operation_id=history.operation_id,
        claimed_order_id=history.order_id,
        claimed_payment_id=history.payment_id,
        snapshot_count=len(snapshots),
        unique_steps=history.unique_snapshots,
        exact_replays=history.exact_replays_suppressed,
        history_head_digest=history.last_digest,
        last_attempts=last.attempts,
        last_observed_utc=_canonical(last.observed_at),
        checksum=sha256(raw).hexdigest(),
    )


def validate_offline_restart(
    claimed_checkpoint: OfflineCheckpoint,
    prior_snapshots: tuple[IntegratedCaseSnapshot, ...],
    resumed_snapshots: tuple[IntegratedCaseSnapshot, ...],
) -> RestartReview:
    """All supplied history must preserve an exact previously observed prefix.

    This cannot detect a forged prior checkpoint, excluded events, or data
    omitted both before and after a crash. Only authenticated durable high
    watermarks can prove those properties in a future implementation.
    """
    if (
        type(claimed_checkpoint) is not OfflineCheckpoint
        or type(prior_snapshots) is not tuple
        or type(resumed_snapshots) is not tuple
        or not 1 <= len(prior_snapshots) <= _MAX_SNAPSHOTS
        or not len(prior_snapshots) <= len(resumed_snapshots) <= _MAX_SNAPSHOTS
    ):
        raise FinancialOperationBlocked("Retomada sem checkpoint ou limites válidos")
    rebuilt = make_offline_checkpoint(prior_snapshots)
    if rebuilt != claimed_checkpoint:
        raise FinancialOperationBlocked(
            "Checkpoint fornecido não confere com o prefixo completo"
        )
    if resumed_snapshots[:len(prior_snapshots)] != prior_snapshots:
        raise FinancialOperationBlocked(
            "Reinicialização com rollback ou alteração do prefixo"
        )
    newer = replay_unresolved_history(resumed_snapshots)
    if (
        newer.tenant_id != rebuilt.tenant_id
        or newer.operation_id != rebuilt.operation_id
        or newer.provider_account_id != rebuilt.provider_account_id
        or newer.order_id != rebuilt.claimed_order_id
        or newer.payment_id != rebuilt.claimed_payment_id
        or newer.unique_snapshots < rebuilt.unique_steps
        or newer.exact_replays_suppressed < rebuilt.exact_replays
    ):
        raise FinancialOperationBlocked("Retomada cruzou conta ou perdeu sequência")
    return RestartReview(
        tenant_id=newer.tenant_id,
        operation_id=newer.operation_id,
        prefix_verified_against_supplied_claim=True,
        new_unique_steps=newer.unique_snapshots-rebuilt.unique_steps,
        new_exact_replays=newer.exact_replays_suppressed-rebuilt.exact_replays,
        resumed_history_digest=newer.last_digest,
    )
