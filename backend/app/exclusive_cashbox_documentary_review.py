"""FR Finance M39950 — pure documentary review *claims*, never approval.

A client's two distinct UUIDs, timestamps, hashes and decisions are untrusted.
Neither this preflight nor its digest proves reviewer identity, independent
authorization, provider reconciliation, settlement, posting or permission to pay.
No I/O, SQL, network, side effects or source-of-truth lookups are performed.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
import json
from uuid import UUID

from .exclusive_cashbox_evidence_preflight import (
    EvidenceDraft, preflight_cashbox_evidence,
)
from .exclusive_cashbox_journal_preflight import JournalCandidate

_DECISIONS = frozenset({"DOCUMENTARY_CHECK_PROPOSED", "REQUEST_MORE_EVIDENCE"})
_NOTE_CODES = frozenset({
    "SHAPE_REVIEW_PENDING", "PROVIDER_AUTHENTICITY_PENDING",
    "POLICY_AND_CYCLE_PENDING", "EXPENSE_AUTHENTICITY_PENDING",
})
_DOCUMENT_CLAIMS = 2


@dataclass(frozen=True)
class DocumentaryReviewClaim:
    scope: str
    tenant_id: UUID | None
    journal_fingerprint: str
    document_digest: str
    reviewer_id: UUID
    claimed_at: datetime
    decision: str
    note_code: str


@dataclass(frozen=True)
class DocumentaryReviewPreflight:
    scope: str
    tenant_id: UUID | None
    journal_fingerprint: str
    chain_fingerprint: str
    claimed_review_count: int = 2
    state: str = "DOCUMENTARY_REVIEW_CLAIMS_UNVERIFIED"
    document_authenticated: bool = False
    reviewer_identities_verified: bool = False
    two_person_approval_verified: bool = False
    independent_authorization_verified: bool = False
    provider_reconciled: bool = False
    journal_posted: bool = False
    payout_enabled: bool = False
    outstanding_gates: tuple[str, ...] = (
        "DOCUMENT_AUTHENTICITY_NOT_ESTABLISHED",
        "AUTHENTICATED_REVIEWER_IDENTITIES_REQUIRED",
        "SERVER_SIDE_ROLE_AND_TENANT_AUTHORIZATION_REQUIRED",
        "INDEPENDENT_SIGNATURES_OR_SERVER_ATTESTATION_REQUIRED",
        "IDEMPOTENT_APPEND_ONLY_REVIEW_RECORD_REQUIRED",
        "PROVIDER_AND_CYCLE_RECONCILIATION_REQUIRED",
        "NO_POSTING_OR_PAYOUT_PERMITTED",
    )


def _timestamp_utc(value: object) -> str:
    if type(value) is not datetime or value.tzinfo is None:
        raise ValueError("Horário documental inválido")
    offset = value.utcoffset()
    if offset is None:
        raise ValueError("Fuso horário documental ausente")
    from datetime import timezone
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds")


def inspect_documentary_review_claims(
    journal: JournalCandidate,
    evidence: EvidenceDraft,
    claims: tuple[DocumentaryReviewClaim, ...],
) -> DocumentaryReviewPreflight:
    """Inspect unverified *claims*, do not approve or recognize money."""
    preflight_cashbox_evidence(journal, evidence)
    if type(claims) is not tuple or len(claims) != _DOCUMENT_CLAIMS:
        raise ValueError("Exatamente duas revisões documentais propostas são exigidas")
    seen = {evidence.preparer_id}
    review_manifest = []
    last_moment = None
    for claim in claims:
        if type(claim) is not DocumentaryReviewClaim:
            raise ValueError("Revisão documental inválida")
        if (claim.scope != journal.scope or
            claim.tenant_id != journal.tenant_id or
            claim.journal_fingerprint != journal.fingerprint or
            claim.document_digest != evidence.document_digest):
            raise ValueError("Revisão pertence a outro documento ou caixa")
        if type(claim.reviewer_id) is not UUID or claim.reviewer_id in seen:
            raise ValueError("Identificadores de preparador/revisores não independentes")
        seen.add(claim.reviewer_id)
        if type(claim.decision) is not str or claim.decision not in _DECISIONS:
            raise ValueError("Decisão de aprovação ou pagamento proibida")
        if type(claim.note_code) is not str or claim.note_code not in _NOTE_CODES:
            raise ValueError("Motivo documental inválido")
        instant = _timestamp_utc(claim.claimed_at)
        if last_moment is not None and instant < last_moment:
            raise ValueError("Revisões com ordem temporal inconsistente")
        last_moment = instant
        review_manifest.append({
            "reviewer_id": str(claim.reviewer_id),
            "claimed_at": instant,
            "decision": claim.decision,
            "note_code": claim.note_code,
        })

    if evidence.proposed_reviewer_id not in seen:
        raise ValueError("O revisor proposto não integra as declarações")
    manifest = {
        "version": "M39950_REVIEW_CLAIM_V1",
        "scope": journal.scope,
        "tenant_id": str(journal.tenant_id) if journal.tenant_id else None,
        "journal_fingerprint": journal.fingerprint,
        "document_digest": evidence.document_digest,
        "evidence_reference": evidence.evidence_reference,
        "preparer_claim_id": str(evidence.preparer_id),
        "claims": review_manifest,
    }
    digest = sha256(json.dumps(manifest, sort_keys=True,
        separators=(",",":"), ensure_ascii=True).encode("utf-8")).hexdigest()
    return DocumentaryReviewPreflight(
        scope=journal.scope, tenant_id=journal.tenant_id,
        journal_fingerprint=journal.fingerprint, chain_fingerprint=digest,
    )
