"""AI Studio M9100-M9400: bounded tenant recovery scheduling previews.

All inputs are untrusted snapshots; this does not acquire distributed leases,
authorize HTTP requests, read any bank statement, or persist incident notes.
Only actions supported by BOTH recovery and circuit policies are candidates.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from uuid import UUID

from .mp_orders_incident_ops import (
    UnresolvedIncident, IncidentPriority, HoldReason,
    triage_incident, validate_incident,
)
from .mp_orders_recovery_scheduler import (
    RecoverySnapshot, SafeRecoveryAction, plan_readonly_recovery,
)
from .mp_orders_readonly_circuit import (
    ReadonlyCircuitSnapshot, ReadonlyAction, decide_readonly_circuit,
)
from .pix_automation_contract import FinancialOperationBlocked

CONTRACT = "AI_STUDIO_M9400_TENANT_QUEUE_GET_CANDIDATE_PREFLIGHT_V1"


@dataclass(frozen=True)
class RecoveryCase:
    recovery: RecoverySnapshot
    circuit: ReadonlyCircuitSnapshot


@dataclass(frozen=True)
class RecoveryQueuePreview:
    tenant_id: UUID
    provider_account_id: str
    scanned: int
    get_candidates: tuple[str, ...]
    pending_or_blocked: int
    safety_hold_active: bool = True
    tenant_authentication_performed: bool = False
    rate_limit_persisted: bool = False
    get_execution_authorized: bool = False
    money_movement_authorized: bool = False
    ledger_write_authorized: bool = False


@dataclass(frozen=True)
class ReasonCount:
    reason: HoldReason
    count: int
    priority: IncidentPriority


@dataclass(frozen=True)
class TenantIncidentSummary:
    tenant_id: UUID
    counts: tuple[ReasonCount, ...]
    total: int
    critical: int
    high: int
    review: int
    sanitized_counts_only: bool = True
    source_authenticated: bool = False
    bank_reconciled: bool = False
    financial_effect_applied: bool = False


def summary_for_tenant(
    tenant_id: UUID,
    incidents: tuple[UnresolvedIncident, ...],
) -> TenantIncidentSummary:
    """No PII, operation IDs, account IDs, hashes or receipt details."""
    if (
        type(tenant_id) is not UUID or not tenant_id.int
        or type(incidents) is not tuple or len(incidents) > 1000
    ):
        raise FinancialOperationBlocked("Lote de incidentes inválido")
    unique: dict[tuple[str, HoldReason], UnresolvedIncident] = {}
    for incident in incidents:
        validate_incident(incident)
        if incident.tenant_id != tenant_id:
            raise FinancialOperationBlocked("Resumo de caixinhas misturadas")
        key = (incident.operation_id, incident.reason)
        if key in unique and unique[key] != incident:
            raise FinancialOperationBlocked("Registro duplicado com metadados alterados")
        unique[key] = incident
    counts = {reason: 0 for reason in HoldReason}
    groups = {p: 0 for p in IncidentPriority}
    for incident in unique.values():
        priority = triage_incident(incident).priority
        counts[incident.reason] += 1
        groups[priority] += 1
    rows = tuple(ReasonCount(reason, count,
                            triage_incident(next(i for i in unique.values()
                                                 if i.reason is reason)).priority)
                 for reason, count in counts.items() if count)
    return TenantIncidentSummary(
        tenant_id=tenant_id, counts=rows, total=len(unique),
        critical=groups[IncidentPriority.CRITICAL],
        high=groups[IncidentPriority.HIGH],
        review=groups[IncidentPriority.REVIEW],
    )


def readonly_queue_preview(
    tenant_id: UUID, provider_account_id: str,
    cases: tuple[RecoveryCase, ...], *,
    max_candidates: int = 3,
) -> RecoveryQueuePreview:
    if (
        type(tenant_id) is not UUID or not tenant_id.int
        or type(provider_account_id) is not str
        or not provider_account_id.isascii()
        or not provider_account_id.isdecimal()
        or not 1 <= len(provider_account_id) <= 40
        or type(cases) is not tuple or len(cases) > 100
        or type(max_candidates) is not int
        or not 1 <= max_candidates <= 10
    ):
        raise FinancialOperationBlocked("Parâmetros de fila não homologados")
    candidates: list[tuple[str, str]] = []
    seen: dict[str, RecoveryCase] = {}
    for case in cases:
        if type(case) is not RecoveryCase:
            raise FinancialOperationBlocked("Caso de recuperação malformado")
        r, c = case.recovery, case.circuit
        if type(r) is not RecoverySnapshot or type(c) is not ReadonlyCircuitSnapshot:
            raise FinancialOperationBlocked("Snapshots de fila inválidos")
        incident = r.incident
        validate_incident(incident)
        if (
            incident.tenant_id != tenant_id
            or incident.provider_account_id != provider_account_id
            or c.tenant_id != tenant_id
            or c.provider_account_id != provider_account_id
            or c.operation_id != incident.operation_id
        ):
            raise FinancialOperationBlocked("Fila cruza caixinha, seller ou operação")
        if incident.operation_id in seen:
            if case != seen[incident.operation_id]:
                raise FinancialOperationBlocked("Replay de operação com contexto divergente")
            continue
        seen[incident.operation_id] = case
        rplan = plan_readonly_recovery(r)
        cplan = decide_readonly_circuit(c)
        # Never select an unknown/processed Order, revoked seller or a case
        # with circuit open, or allow the UI to imply execution authority.
        if (
            rplan.action is SafeRecoveryAction.READ_ORDER_ONLY
            and cplan.action is ReadonlyAction.GET_CANDIDATE_ONLY
        ):
            candidates.append((incident.operation_id, incident.operation_id))
    candidates.sort()
    return RecoveryQueuePreview(
        tenant_id=tenant_id, provider_account_id=provider_account_id,
        scanned=len(seen),
        get_candidates=tuple(op for _, op in candidates[:max_candidates]),
        pending_or_blocked=len(seen)-len(candidates[:max_candidates]),
    )
