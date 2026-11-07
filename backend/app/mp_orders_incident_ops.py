"""M7300-M7600 — offline incident triage and immutable review preflight.

Not an HTTP endpoint, payment worker, or bank reconciliation service.
Only opaque evidence digests enter the decision engine. A human review
can document an unresolved divergence, NEVER release a financial hold.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from hashlib import sha256
import re
from uuid import UUID

from .mp_orders_holds import HoldReason
from .pix_automation_contract import FinancialOperationBlocked

CONTRACT = "AI_STUDIO_M7600_ORDERS_INCIDENT_AUDIT_PREFLIGHT_V1"
_OPERATION = re.compile(r"P_[a-f0-9]{32}\Z")
_SELLER = re.compile(r"[0-9]{1,40}\Z")
_SHA256 = re.compile(r"[a-f0-9]{64}\Z")


class IncidentPriority(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    REVIEW = "REVIEW"


class IncidentNextStep(str, Enum):
    PROVIDER_SUPPORT_ONLY = "PROVIDER_SUPPORT_ONLY"
    READ_PROVIDER_ONLY = "READ_PROVIDER_ONLY"
    CHECK_INDEPENDENT_STATEMENT = "CHECK_INDEPENDENT_STATEMENT"
    ESCALATE_SECURITY = "ESCALATE_SECURITY"


@dataclass(frozen=True)
class UnresolvedIncident:
    tenant_id: UUID
    operation_id: str
    provider_account_id: str
    reason: HoldReason
    evidence_sha256: str
    opened_at: datetime
    reported_by: UUID


@dataclass(frozen=True)
class IncidentTriage:
    tenant_id: UUID
    operation_id: str
    priority: IncidentPriority
    next_step: IncidentNextStep
    hold_active: bool = True
    bank_reconciled: bool = False
    mark_paid_authorized: bool = False
    ledger_write_authorized: bool = False
    payout_authorized: bool = False
    financial_closing_authorized: bool = False


@dataclass(frozen=True)
class ReviewRecord:
    tenant_id: UUID
    operation_id: str
    reason: HoldReason
    reviewer_one: UUID
    reviewer_two: UUID
    reviewed_at: datetime
    evidence_sha256: str
    previous_audit_sha256: str
    audit_sha256: str
    outcome: str = "REVIEW_RECORDED_HOLD_REMAINS"
    can_release_hold: bool = False
    can_mark_paid: bool = False
    can_post_ledger: bool = False
    can_payout: bool = False


def _aware(value: datetime) -> bool:
    return (
        type(value) is datetime
        and value.tzinfo is not None
        and value.utcoffset() is not None
    )


def validate_incident(incident: UnresolvedIncident) -> None:
    if (
        type(incident) is not UnresolvedIncident
        or type(incident.tenant_id) is not UUID
        or incident.tenant_id.int == 0
        or type(incident.operation_id) is not str
        or _OPERATION.fullmatch(incident.operation_id) is None
        or type(incident.provider_account_id) is not str
        or _SELLER.fullmatch(incident.provider_account_id) is None
        or type(incident.reason) is not HoldReason
        or type(incident.evidence_sha256) is not str
        or _SHA256.fullmatch(incident.evidence_sha256) is None
        or not _aware(incident.opened_at)
        or type(incident.reported_by) is not UUID
        or incident.reported_by.int == 0
    ):
        raise FinancialOperationBlocked("Incidente sem identidade/evidência válida")


def triage_incident(incident: UnresolvedIncident) -> IncidentTriage:
    validate_incident(incident)
    if incident.reason in (
        HoldReason.SELLER_REVOKED,
        HoldReason.ORDER_REPLAY,
        HoldReason.STATEMENT_DUPLICATE,
    ):
        priority, next_step = (
            IncidentPriority.CRITICAL, IncidentNextStep.ESCALATE_SECURITY
        )
    elif incident.reason in (
        HoldReason.TIMEOUT_UNKNOWN,
        HoldReason.STATUS_CONFLICT,
        HoldReason.PROVIDER_MISMATCH,
    ):
        priority, next_step = (
            IncidentPriority.HIGH, IncidentNextStep.PROVIDER_SUPPORT_ONLY
        )
    elif incident.reason in (
        HoldReason.BANK_MISSING,
        HoldReason.FEE_MISMATCH,
        HoldReason.REVERSAL_PENDING,
    ):
        priority, next_step = (
            IncidentPriority.REVIEW,
            IncidentNextStep.CHECK_INDEPENDENT_STATEMENT,
        )
    else:
        raise FinancialOperationBlocked("Motivo de retenção não homologado")
    return IncidentTriage(
        tenant_id=incident.tenant_id, operation_id=incident.operation_id,
        priority=priority, next_step=next_step,
    )


def review_incident(
    incident: UnresolvedIncident, *,
    reviewer_one: UUID, reviewer_two: UUID,
    reviewed_at: datetime, previous_audit_sha256: str,
) -> ReviewRecord:
    """Hash-chain preview; not a DB insert, signature, or bank attestation."""
    validate_incident(incident)
    if (
        type(reviewer_one) is not UUID
        or type(reviewer_two) is not UUID
        or not reviewer_one.int or not reviewer_two.int
        or len({reviewer_one, reviewer_two, incident.reported_by}) != 3
        or not _aware(reviewed_at)
        or reviewed_at < incident.opened_at
        or type(previous_audit_sha256) is not str
        or _SHA256.fullmatch(previous_audit_sha256) is None
    ):
        raise FinancialOperationBlocked("Revisão sem segregação ou encadeamento")
    content = "|".join((
        "FRCAIXINHA_AI_STUDIO_M7600_REVIEW",
        previous_audit_sha256, str(incident.tenant_id),
        incident.operation_id, incident.provider_account_id,
        incident.reason.value, incident.evidence_sha256,
        incident.opened_at.isoformat(), str(incident.reported_by),
        str(reviewer_one), str(reviewer_two), reviewed_at.isoformat(),
        "REVIEW_RECORDED_HOLD_REMAINS",
    ))
    return ReviewRecord(
        tenant_id=incident.tenant_id, operation_id=incident.operation_id,
        reason=incident.reason, reviewer_one=reviewer_one,
        reviewer_two=reviewer_two, reviewed_at=reviewed_at,
        evidence_sha256=incident.evidence_sha256,
        previous_audit_sha256=previous_audit_sha256,
        audit_sha256=sha256(content.encode("ascii")).hexdigest(),
    )


def triage_tenant_page(
    tenant_id: UUID, incidents: tuple[UnresolvedIncident, ...], *,
    offset: int = 0, limit: int = 50,
) -> tuple[IncidentTriage, ...]:
    """In-memory staging preview; real cursor authorization remains P0."""
    if (
        type(tenant_id) is not UUID or not tenant_id.int
        or type(incidents) is not tuple or len(incidents) > 1000
        or type(offset) is not int or offset < 0
        or type(limit) is not int or not 1 <= limit <= 100
    ):
        raise FinancialOperationBlocked("Consulta operacional inválida")
    seen: dict[tuple[str, HoldReason], UnresolvedIncident] = {}
    rows: list[tuple[UnresolvedIncident, IncidentTriage]] = []
    for incident in incidents:
        validate_incident(incident)
        if incident.tenant_id != tenant_id:
            raise FinancialOperationBlocked("Consulta de incidentes cruza caixinhas")
        key = (incident.operation_id, incident.reason)
        if key in seen:
            # Replays must match the complete original tenant/seller/reporter/time
            # binding, not merely a copied evidence fingerprint.
            if seen[key] != incident:
                raise FinancialOperationBlocked("Contexto de retenção divergente")
            continue
        seen[key] = incident
        rows.append((incident, triage_incident(incident)))
    rank = {IncidentPriority.CRITICAL: 0,
            IncidentPriority.HIGH: 1, IncidentPriority.REVIEW: 2}
    rows.sort(key=lambda pair: (
        rank[pair[1].priority], pair[0].opened_at,
        pair[0].operation_id, pair[0].reason.value,
    ))
    return tuple(pair[1] for pair in rows[offset:offset + limit])
