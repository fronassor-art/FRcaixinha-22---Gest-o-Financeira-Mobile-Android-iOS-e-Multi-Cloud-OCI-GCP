"""AI Studio M9500-M9900: cross-component case consistency preflight.

This is PURE, OFFLINE and UNAUTHENTICATED. Inputs are claims, not bank
proof. Digest consistency is NOT a signature or an immutable audit log.
No provider I/O, SQL, payments, ledger, settlement, payout or hold release.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from uuid import UUID

from .mp_orders_evidence_discrepancy import (
    DiscrepancyContext, ReviewOutcome, review_claimed_three_source,
)
from .mp_orders_incident_ops import (
    IncidentPriority, UnresolvedIncident, triage_incident, validate_incident,
)
from .mp_orders_incident_timeline import TimelineEvent, verify_timeline
from .mp_orders_readonly_circuit import (
    ReadonlyAction, ReadonlyCircuitSnapshot, decide_readonly_circuit,
)
from .mp_orders_recovery_scheduler import (
    RecoverySnapshot, SafeRecoveryAction, plan_readonly_recovery,
)
from .pix_automation_contract import FinancialOperationBlocked

CONTRACT = "AI_STUDIO_M9900_INTEGRATED_UNVERIFIED_CASE_PREFLIGHT_V1"


@dataclass(frozen=True)
class IntegratedCaseSnapshot:
    incident: UnresolvedIncident
    timeline: tuple[TimelineEvent, ...]
    claimed_evidence: DiscrepancyContext
    recovery: RecoverySnapshot
    circuit: ReadonlyCircuitSnapshot


@dataclass(frozen=True)
class IntegratedCaseDecision:
    tenant_id: UUID
    operation_id: str
    priority: IncidentPriority
    evidence_outcome: ReviewOutcome
    recovery_action: SafeRecoveryAction
    circuit_action: ReadonlyAction
    case_fingerprint: str
    read_candidate_policy_only: bool
    hold_active: bool = True
    verified_bank_source: bool = False
    authenticated_operator_identity: bool = False
    persisted_audit_trail: bool = False
    get_execution_authorized: bool = False
    mark_paid_authorized: bool = False
    ledger_write_authorized: bool = False
    hold_release_authorized: bool = False
    payout_authorized: bool = False
    financial_closing_authorized: bool = False


@dataclass(frozen=True)
class TenantCaseCount:
    tenant_id: UUID
    total_cases: int
    critical_cases: int
    high_cases: int
    review_cases: int
    get_candidates_policy_only: int
    blocked_or_manual_cases: int
    contains_case_ids: bool = False
    authenticated_source: bool = False
    bank_reconciled: bool = False
    financial_effect_applied: bool = False


def inspect_integrated_case(case: IntegratedCaseSnapshot) -> IntegratedCaseDecision:
    """All component identities and observation times must agree exactly."""
    if type(case) is not IntegratedCaseSnapshot:
        raise FinancialOperationBlocked("Pacote de caso não reconhecido")
    incident = case.incident
    validate_incident(incident)
    if (
        type(case.timeline) is not tuple
        or type(case.claimed_evidence) is not DiscrepancyContext
        or type(case.recovery) is not RecoverySnapshot
        or type(case.circuit) is not ReadonlyCircuitSnapshot
    ):
        raise FinancialOperationBlocked("Componentes incompletos ou não validados")

    timeline = verify_timeline(incident, case.timeline)
    evidence = review_claimed_three_source(case.claimed_evidence)
    recovery = plan_readonly_recovery(case.recovery)
    circuit = decide_readonly_circuit(case.circuit)
    p = case.claimed_evidence.provider
    r = case.recovery
    c = case.circuit
    if (
        r.incident != incident
        or evidence.tenant_id != incident.tenant_id
        or p.tenant_id != incident.tenant_id
        or p.operation_id != incident.operation_id
        or p.provider_account_id != incident.provider_account_id
        or c.tenant_id != incident.tenant_id
        or c.operation_id != incident.operation_id
        or c.provider_account_id != incident.provider_account_id
        or (r.order_id is not None and r.order_id != p.order_id)
        or c.observed_at != r.now
        or c.seller_approved != r.seller_approved
        or c.tenant_binding_verified != r.tenant_binding_verified
        or case.timeline[-1].recorded_at > r.now
        or any(source.observed_at > r.now for source in (
            case.claimed_evidence.provider,
            case.claimed_evidence.settlement,
            case.claimed_evidence.bank,
        ))
    ):
        raise FinancialOperationBlocked(
            "Caso com divergência entre caixinha, conta, fontes ou horários"
        )

    priority = triage_incident(incident).priority
    read_candidate = (
        r.order_id is not None
        and evidence.outcome in (
            ReviewOutcome.UNVERIFIED_SOURCE,
            ReviewOutcome.AMOUNT_MISMATCH,
            ReviewOutcome.SETTLEMENT_DATE_REVIEW,
        )
        and recovery.action is SafeRecoveryAction.READ_ORDER_ONLY
        and circuit.action is ReadonlyAction.GET_CANDIDATE_ONLY
    )
    payload = "|".join((
        "AI_STUDIO_M9900_UNVERIFIED_BUNDLE",
        str(incident.tenant_id), incident.operation_id,
        incident.provider_account_id, incident.reason.value,
        incident.evidence_sha256, timeline.head_digest,
        evidence.case_fingerprint, priority.value,
        evidence.outcome.value, recovery.action.value,
        circuit.action.value, str(r.order_id or "-"),
        r.now.isoformat(),
        "HOLD_UNRESOLVED_NO_AUTHORITY",
    ))
    return IntegratedCaseDecision(
        tenant_id=incident.tenant_id,
        operation_id=incident.operation_id,
        priority=priority,
        evidence_outcome=evidence.outcome,
        recovery_action=recovery.action,
        circuit_action=circuit.action,
        case_fingerprint=sha256(payload.encode("ascii")).hexdigest(),
        read_candidate_policy_only=read_candidate,
    )


def count_integrated_cases_for_tenant(
    tenant_id: UUID, cases: tuple[IntegratedCaseSnapshot, ...],
) -> TenantCaseCount:
    """Count only; never expose operation, account or evidence digests."""
    if (
        type(tenant_id) is not UUID or tenant_id.int == 0
        or type(cases) is not tuple or len(cases) > 100
    ):
        raise FinancialOperationBlocked("Contador de casos sem escopo permitido")
    unique: dict[str, IntegratedCaseSnapshot] = {}
    for case in cases:
        decision = inspect_integrated_case(case)
        if decision.tenant_id != tenant_id:
            raise FinancialOperationBlocked("Contador cruzou caixinhas")
        key = decision.operation_id
        if key in unique:
            if case != unique[key]:
                raise FinancialOperationBlocked("Replay de caso com histórico diferente")
            continue
        unique[key] = case
    priorities = {p: 0 for p in IncidentPriority}
    get_candidates = 0
    for case in unique.values():
        decision = inspect_integrated_case(case)
        priorities[decision.priority] += 1
        get_candidates += int(decision.read_candidate_policy_only)
    return TenantCaseCount(
        tenant_id=tenant_id,
        total_cases=len(unique),
        critical_cases=priorities[IncidentPriority.CRITICAL],
        high_cases=priorities[IncidentPriority.HIGH],
        review_cases=priorities[IncidentPriority.REVIEW],
        get_candidates_policy_only=get_candidates,
        blocked_or_manual_cases=len(unique)-get_candidates,
    )
