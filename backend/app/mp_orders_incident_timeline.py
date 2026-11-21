"""AI Studio M8700-M9000: deterministic incident timeline verification.

Only pure in-memory review PREVIEWS. Digests detect accidental mutations but
are not digital signatures, independently authenticated identities, immutable
database events, or bank reconciliation. No finance authority or I/O.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
from hmac import compare_digest
from re import fullmatch
from uuid import UUID

from .mp_orders_incident_ops import (
    UnresolvedIncident, validate_incident, triage_incident,
)
from .pix_automation_contract import FinancialOperationBlocked

CONTRACT = "AI_STUDIO_M9000_INCIDENT_TIMELINE_VERIFICATION_PREVIEW_V1"
_GENESIS = "0" * 64
_SHA = r"[a-f0-9]{64}"


class TimelineAction(str, Enum):
    OPENED = "OPENED"
    PROVIDER_TRACE_REQUESTED = "PROVIDER_TRACE_REQUESTED"
    BANK_PROOF_REQUESTED = "BANK_PROOF_REQUESTED"
    SECURITY_ESCALATED = "SECURITY_ESCALATED"
    EVIDENCE_INSPECTED = "EVIDENCE_INSPECTED"
    DUAL_REVIEW_RECORDED = "DUAL_REVIEW_RECORDED"


@dataclass(frozen=True)
class TimelineEvent:
    tenant_id: UUID
    operation_id: str
    reason_code: str
    evidence_sha256: str
    sequence: int
    action: TimelineAction
    actor_id: UUID
    second_reviewer_id: UUID | None
    recorded_at: datetime
    previous_digest: str
    digest: str
    hold_active: bool = True
    financial_effect_applied: bool = False


@dataclass(frozen=True)
class TimelineCheck:
    tenant_id: UUID
    operation_id: str
    event_count: int
    head_digest: str
    last_action: TimelineAction
    hold_active: bool = True
    authenticated_audit_log: bool = False
    independently_verified_bank_proof: bool = False
    ledger_write_authorized: bool = False
    mark_paid_authorized: bool = False
    release_hold_authorized: bool = False
    payout_authorized: bool = False


def _aware(v: datetime) -> bool:
    return type(v) is datetime and v.tzinfo is not None and v.utcoffset() is not None


def make_timeline_event(
    incident: UnresolvedIncident, *,
    sequence: int, action: TimelineAction, actor_id: UUID,
    recorded_at: datetime, previous_digest: str,
    second_reviewer_id: UUID | None = None,
) -> TimelineEvent:
    validate_incident(incident)
    if (
        type(sequence) is not int or not 1 <= sequence <= 1000
        or type(action) is not TimelineAction
        or type(actor_id) is not UUID or not actor_id.int
        or not _aware(recorded_at) or recorded_at < incident.opened_at
        or type(previous_digest) is not str
        or fullmatch(_SHA, previous_digest) is None
        or (sequence == 1) != (action is TimelineAction.OPENED)
        or (sequence == 1) != (previous_digest == _GENESIS)
        or (sequence == 1 and actor_id != incident.reported_by)
    ):
        raise FinancialOperationBlocked("Evento de auditoria sem origem ou sequência válida")
    if action is TimelineAction.DUAL_REVIEW_RECORDED:
        if (
            type(second_reviewer_id) is not UUID or not second_reviewer_id.int
            or len({actor_id, second_reviewer_id, incident.reported_by}) != 3
        ):
            raise FinancialOperationBlocked("Revisão sem separação de dois responsáveis")
    elif second_reviewer_id is not None:
        raise FinancialOperationBlocked("Segundo revisor inesperado no evento")
    # Canonical UTC timestamps prevent timezone-alias fingerprint changes.
    opened = incident.opened_at.astimezone(timezone.utc).isoformat()
    instant = recorded_at.astimezone(timezone.utc).isoformat()
    data = "|".join((
        "FRCAIXINHA_AI_STUDIO_M9000_TIMELINE",
        str(incident.tenant_id), incident.operation_id,
        incident.provider_account_id, incident.reason.value,
        incident.evidence_sha256, opened, str(incident.reported_by),
        str(sequence), action.value, str(actor_id),
        str(second_reviewer_id or "-"), instant, previous_digest,
        "HOLD_REMAINS_NO_FINANCIAL_EFFECT",
    ))
    return TimelineEvent(
        tenant_id=incident.tenant_id, operation_id=incident.operation_id,
        reason_code=incident.reason.value,
        evidence_sha256=incident.evidence_sha256, sequence=sequence,
        action=action, actor_id=actor_id,
        second_reviewer_id=second_reviewer_id, recorded_at=recorded_at,
        previous_digest=previous_digest,
        digest=sha256(data.encode("ascii")).hexdigest(),
    )


def verify_timeline(
    incident: UnresolvedIncident, events: tuple[TimelineEvent, ...],
) -> TimelineCheck:
    validate_incident(incident)
    if type(events) is not tuple or not 1 <= len(events) <= 1000:
        raise FinancialOperationBlocked("Trilha de auditoria sem tamanho validado")
    previous = _GENESIS
    previous_time = incident.opened_at
    for index, event in enumerate(events, 1):
        if (
            type(event) is not TimelineEvent
            or type(event.sequence) is not int or event.sequence != index
            or type(event.hold_active) is not bool
            or event.hold_active is not True
            or type(event.financial_effect_applied) is not bool
            or event.financial_effect_applied is not False
            or not _aware(event.recorded_at)
            or event.recorded_at < previous_time
            or type(event.digest) is not str
            or fullmatch(_SHA, event.digest) is None
        ):
            raise FinancialOperationBlocked("Trilha desordenada ou com efeito indevido")
        calculated = make_timeline_event(
            incident, sequence=index, action=event.action,
            actor_id=event.actor_id, second_reviewer_id=event.second_reviewer_id,
            recorded_at=event.recorded_at, previous_digest=previous,
        )
        if not compare_digest(calculated.digest, event.digest) or (
            calculated != event
        ):
            raise FinancialOperationBlocked("Trilha adulterada ou fora de contexto")
        previous = event.digest
        previous_time = event.recorded_at
    return TimelineCheck(
        tenant_id=incident.tenant_id,
        operation_id=incident.operation_id, event_count=len(events),
        head_digest=previous, last_action=events[-1].action,
    )


def review_priority_is_not_a_payment_decision(
    incident: UnresolvedIncident, events: tuple[TimelineEvent, ...],
) -> bool:
    """True means the recorded preview is still blocked; never a release."""
    verify_timeline(incident, events)
    triage_incident(incident)
    return True
