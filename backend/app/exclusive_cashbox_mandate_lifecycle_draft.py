"""FR Finance M39990 — draft-only reviewer mandate lifecycle.

A deterministic chain of caller-provided events is NOT a server log, an
authorization, an actual appointment, an effective revocation, a signature,
or proof of consent. Every event, identity, document digest and time here
may be forged. NO I/O, provider, database, web endpoint, or payment logic.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import re
from uuid import UUID

from .dependencies import AuthenticatedSession
from .exclusive_cashbox_documentary_review import DocumentaryReviewClaim
from .exclusive_cashbox_evidence_preflight import EvidenceDraft
from .exclusive_cashbox_journal_preflight import JournalCandidate
from .exclusive_cashbox_review_policy_draft import (
    DraftReviewPolicyDenied, ReviewPolicyDraft, assess_unapproved_review_policy,
)

_ACTIONS = frozenset((
    "APPOINTMENT_PROPOSED",
    "WITHDRAWAL_PROPOSED",
    "REVOCATION_PROPOSED",
))
_TERMINAL_ACTIONS = frozenset(("WITHDRAWAL_PROPOSED", "REVOCATION_PROPOSED"))
_DIGEST = re.compile(r"^[0-9a-f]{64}$")


class MandateLifecycleDraftDenied(ValueError):
    """Invalid draft-only sequence. No effect on real reviewer authority."""


@dataclass(frozen=True)
class MandateEventDraft:
    event_id: UUID
    policy_draft_fingerprint: str
    scope: str
    tenant_id: UUID | None
    reviewer_id: UUID
    action: str
    claimed_at: datetime
    claimed_actor_id: UUID
    claimed_document_digest: str


@dataclass(frozen=True)
class MandateLifecyclePreview:
    scope: str
    tenant_id: UUID | None
    policy_draft_fingerprint: str
    chain_fingerprint: str
    proposal_event_count: int
    nonterminal_proposal_count: int
    terminal_proposal_count: int
    state: str = "MANDATE_LIFECYCLE_DRAFT_ONLY"
    source_events_authenticated: bool = False
    durable_audit_events_recorded: bool = False
    reviewer_appointment_verified: bool = False
    consent_signatures_verified: bool = False
    effective_revocation_recorded: bool = False
    reviewer_grants_authorized: bool = False
    independent_review_approved: bool = False
    journal_posted: bool = False
    payment_enabled: bool = False
    payout_enabled: bool = False
    outstanding_gates: tuple[str, ...] = (
        "CLAIMED_EVENT_IDENTITIES_AND_TIMES_NOT_AUTHENTICATED",
        "MANDATE_AND_CONSENT_DOCUMENTS_UNVERIFIED",
        "NO_INDEPENDENT_SERVER_SIDE_SESSION_SIGNATURES",
        "NO_PERSISTED_APPEND_ONLY_AUDIT_RECORD",
        "NO_DURABLE_REPLAY_OR_CONCURRENCY_PROTECTION",
        "NO_VERIFIED_EFFECTIVE_REVOCATION_OR_APPOINTMENT",
        "NO_RATIFIED_POLICY_OR_DOCUMENT_AUTHORITY",
        "NO_LEDGER_POSTING_OR_REAL_PAYMENTS",
    )


def _uuid(value: object) -> UUID:
    if type(value) is not UUID or value.int == 0:
        raise MandateLifecycleDraftDenied("Identificador de evento, usuário ou revisor inválido")
    return value


def _utc(value: object) -> datetime:
    if type(value) is not datetime or value.tzinfo is None or (
        value.utcoffset() is None
    ):
        raise MandateLifecycleDraftDenied("Horário declarado sem fuso")
    return value.astimezone(timezone.utc)


def inspect_untrusted_mandate_lifecycle(
    journal: JournalCandidate,
    evidence: EvidenceDraft,
    review_claims: tuple[DocumentaryReviewClaim, ...],
    reviewer_sessions: tuple[AuthenticatedSession, ...],
    policy_draft: ReviewPolicyDraft,
    events: tuple[MandateEventDraft, ...],
    *,
    observed_at: datetime,
) -> MandateLifecyclePreview:
    """Check monotonic draft events; always deny real authorization.

    Caller inputs cannot prove independent authenticated requests, legal
    consent, policy grants, revocation or durable idempotency.
    """
    try:
        report = assess_unapproved_review_policy(
            journal, evidence, review_claims, reviewer_sessions,
            policy_draft, observed_at=observed_at,
        )
    except (DraftReviewPolicyDenied, ValueError, AttributeError, TypeError) as exc:
        raise MandateLifecycleDraftDenied("Política não ratificada inválida") from exc

    if type(events) is not tuple or not 2 <= len(events) <= 4:
        raise MandateLifecycleDraftDenied("Exigir duas propostas iniciais, até quatro eventos")
    observed = _utc(observed_at)
    from_time = _utc(policy_draft.valid_from)
    until_time = _utc(policy_draft.valid_until)
    fingerprint = report.policy_draft_fingerprint
    reviewers = {g.reviewer_id for g in policy_draft.reviewer_grants}
    creator = _uuid(policy_draft.created_by)
    seen_ids: set[UUID] = set()
    seen_digests: set[str] = set()
    active_draft_reviewers: set[UUID] = set()
    terminal_draft_reviewers: set[UUID] = set()
    latest_time: datetime | None = None
    chain = fingerprint
    for item in events:
        if type(item) is not MandateEventDraft:
            raise MandateLifecycleDraftDenied("Evento não corresponde a declaração de mandato")
        event_id = _uuid(item.event_id)
        reviewer = _uuid(item.reviewer_id)
        actor = _uuid(item.claimed_actor_id)
        if (event_id in seen_ids or reviewer not in reviewers or
            item.scope != policy_draft.scope or
            item.tenant_id != policy_draft.tenant_id or
            item.policy_draft_fingerprint != fingerprint):
            raise MandateLifecycleDraftDenied("Replay, outro caixa ou política diferente")
        if type(item.action) is not str or item.action not in _ACTIONS:
            raise MandateLifecycleDraftDenied("Estado de mandato aprovado é proibido")
        digest = item.claimed_document_digest
        if (type(digest) is not str or _DIGEST.fullmatch(digest) is None or
            digest in seen_digests):
            raise MandateLifecycleDraftDenied("Documento de evento inválido ou repetido")
        instant = _utc(item.claimed_at)
        if (not from_time <= instant < until_time or instant > observed or
            (latest_time is not None and instant <= latest_time)):
            raise MandateLifecycleDraftDenied("Evento fora da vigência ou sequência cronológica")
        if item.action == "APPOINTMENT_PROPOSED":
            if (actor != creator or reviewer in active_draft_reviewers or
                reviewer in terminal_draft_reviewers):
                raise MandateLifecycleDraftDenied("Nomeação duplicada ou não iniciada pelo proponente")
            active_draft_reviewers.add(reviewer)
        elif item.action in _TERMINAL_ACTIONS:
            if reviewer not in active_draft_reviewers:
                raise MandateLifecycleDraftDenied("Revogação ou desistência sem proposta anterior")
            expected_actor = (
                reviewer if item.action == "WITHDRAWAL_PROPOSED" else creator
            )
            if actor != expected_actor:
                raise MandateLifecycleDraftDenied("Declarante não coincide com ação proposta")
            active_draft_reviewers.remove(reviewer)
            terminal_draft_reviewers.add(reviewer)

        seen_ids.add(event_id)
        seen_digests.add(digest)
        latest_time = instant
        payload = {
            "version": "M39990_DRAFT_EVENT_CHAIN_V1",
            "previous_fingerprint": chain,
            "event_id": str(event_id),
            "policy_draft_fingerprint": fingerprint,
            "scope": item.scope,
            "tenant_id": str(item.tenant_id) if item.tenant_id else None,
            "reviewer_id": str(reviewer),
            "action": item.action,
            "claimed_actor_id": str(actor),
            "claimed_document_digest": digest,
            "claimed_at": instant.isoformat(timespec="microseconds"),
        }
        chain = sha256(json.dumps(
            payload, sort_keys=True, separators=(",",":"), ensure_ascii=True
        ).encode("utf-8")).hexdigest()

    if active_draft_reviewers | terminal_draft_reviewers != reviewers:
        raise MandateLifecycleDraftDenied("Falta proposta inicial de um dos dois revisores")
    if len(seen_ids) != len(events):
        raise MandateLifecycleDraftDenied("Evento duplicado")

    return MandateLifecyclePreview(
        scope=report.scope,
        tenant_id=report.tenant_id,
        policy_draft_fingerprint=fingerprint,
        chain_fingerprint=chain,
        proposal_event_count=len(events),
        nonterminal_proposal_count=len(active_draft_reviewers),
        terminal_proposal_count=len(terminal_draft_reviewers),
    )
