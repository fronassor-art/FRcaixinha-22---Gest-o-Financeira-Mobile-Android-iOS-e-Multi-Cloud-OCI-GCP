"""FR Finance M39980 — explicit draft review policy, never authority.

Compares the M39970 SESSION-SHAPE preflight with an unapproved policy draft.
All policy records and grants below are caller-controlled, not verified by
the original PostgreSQL; a valid draft is NOT a right to approve anything.

There are no API endpoints, providers, DB calls, signed attestation, payment
enablers or mutation paths. No collective reviewer policy is invented.
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
from .exclusive_cashbox_provenance import (
    PLATFORM_MASTER, TENANT_ADMIN_OWN, TENANT_COLLECTIVE, EVENT_SCOPE,
)
from .exclusive_cashbox_review_session_pair import (
    ReviewSessionPairDenied, correlate_unverified_review_sessions,
)

_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_ROLE_BY_SCOPE = {
    PLATFORM_MASTER: "MASTER",
    TENANT_ADMIN_OWN: "TENANT_ADMIN",
}
_POLICY_GAP_BY_SCOPE = {
    PLATFORM_MASTER: "MASTER_INDEPENDENT_REVIEWER_MANDATE_UNRATIFIED",
    TENANT_ADMIN_OWN: "TENANT_ADMIN_OWN_SECOND_REVIEWER_DESIGNATION_UNRATIFIED",
}

# Source code holds the mandatory gates. A caller cannot choose a lighter
# checklist, and supplying a digest is not proof that the original exists.
_EVENT_GATES = {
    "SAAS_SETTLEMENT": "PROVIDER_SETTLEMENT_AND_SAAS_ENTITLEMENT_UNVERIFIED",
    "PLATFORM_OPERATING_EXPENSE": "FISCAL_EXPENSE_AND_COST_CENTER_UNVERIFIED",
    "ADMIN_CLOSING_REMUNERATION": "ANNUAL_CLOSING_AND_15_85_ENTITLEMENTS_UNVERIFIED",
    "ADMIN_OWN_EXPENSE": "ADMIN_OWN_FISCAL_EXPENSE_UNVERIFIED",
    "MEMBER_CONTRIBUTION": "MEMBER_CONTRIBUTION_PROVIDER_UNVERIFIED",
    "TENANT_LOAN_REPAYMENT": "TENANT_LOAN_PROVIDER_UNVERIFIED",
    "TENANT_OPERATING_EXPENSE": "TENANT_COLLECTIVE_FISCAL_EXPENSE_UNVERIFIED",
}
assert set(_EVENT_GATES) == set(EVENT_SCOPE)


class DraftReviewPolicyDenied(ValueError):
    """Even a structural draft is invalid (not an authorization exception)."""


@dataclass(frozen=True)
class ReviewerGrantDraft:
    reviewer_id: UUID
    scope: str
    tenant_id: UUID | None
    role: str
    grant_origin: str = "DRAFT_NOT_ATTESTED"


@dataclass(frozen=True)
class ReviewPolicyDraft:
    policy_id: UUID
    policy_document_digest: str
    scope: str
    tenant_id: UUID | None
    event_type: str
    created_by: UUID
    created_by_role: str
    valid_from: datetime
    valid_until: datetime
    reviewer_grants: tuple[ReviewerGrantDraft, ...]
    status: str = "PROPOSED_ONLY"


@dataclass(frozen=True)
class ReviewPolicyGapReport:
    scope: str
    tenant_id: UUID | None
    event_type: str
    journal_fingerprint: str
    documentary_chain_fingerprint: str
    policy_draft_fingerprint: str
    state: str = "POLICY_DRAFT_NO_AUTHORITY"
    reviewer_grant_shapes_aligned: bool = True
    policy_approved: bool = False
    policy_source_authenticated: bool = False
    roles_and_tenant_authorized: bool = False
    independent_reviewer_appointment_verified: bool = False
    two_person_approval_verified: bool = False
    event_evidence_reconciled: bool = False
    journal_posted: bool = False
    payment_enabled: bool = False
    payout_enabled: bool = False
    outstanding_gates: tuple[str, ...] = ()


def _utc(value: object) -> datetime:
    if type(value) is not datetime or value.tzinfo is None or (
        value.utcoffset() is None
    ):
        raise DraftReviewPolicyDenied("Janela de política sem fuso verificável")
    return value.astimezone(timezone.utc)


def _uuid(value: object) -> UUID:
    if type(value) is not UUID or value.int == 0:
        raise DraftReviewPolicyDenied("Identificador de política ou pessoa inválido")
    return value


def assess_unapproved_review_policy(
    journal: JournalCandidate,
    evidence: EvidenceDraft,
    claims: tuple[DocumentaryReviewClaim, ...],
    reviewer_sessions: tuple[AuthenticatedSession, ...],
    draft: ReviewPolicyDraft,
    *,
    observed_at: datetime,
) -> ReviewPolicyGapReport:
    """Reject invalid drafts; always report unratified authorization gaps.

    These input objects can be constructed by a caller. This function checks
    shape and equality, NOT legal signature, membership, source bytes or
    independent server-side authentication. It CANNOT grant any authority.
    """
    if type(draft) is not ReviewPolicyDraft:
        raise DraftReviewPolicyDenied("Política declarada não é um rascunho")
    if draft.status != "PROPOSED_ONLY" or type(draft.status) is not str:
        raise DraftReviewPolicyDenied("Política ratificada não pode ser alegada pelo cliente")
    if (type(draft.event_type) is not str or
        draft.event_type not in EVENT_SCOPE or
        draft.scope != EVENT_SCOPE[draft.event_type] or
        draft.scope == TENANT_COLLECTIVE):
        raise DraftReviewPolicyDenied("Política de revisão do domínio não definida")
    if (draft.event_type != journal.event_type or
        draft.scope != journal.scope or draft.scope != evidence.scope or
        draft.tenant_id != journal.tenant_id or
        draft.tenant_id != evidence.tenant_id):
        raise DraftReviewPolicyDenied("Política de outra caixinha ou família de evento")

    policy_id = _uuid(draft.policy_id)
    creator = _uuid(draft.created_by)
    if creator == evidence.preparer_id:
        raise DraftReviewPolicyDenied("Preparador não pode emitir sua própria política de revisão")
    if type(draft.policy_document_digest) is not str or (
        _DIGEST.fullmatch(draft.policy_document_digest) is None
    ):
        raise DraftReviewPolicyDenied("Referência do documento de política inválida")
    role = _ROLE_BY_SCOPE[draft.scope]
    if draft.created_by_role != role or type(draft.created_by_role) is not str:
        raise DraftReviewPolicyDenied("Papel do autor do rascunho incompatível")
    if draft.scope == PLATFORM_MASTER:
        if draft.tenant_id is not None:
            raise DraftReviewPolicyDenied("Master não pertence a tenant")
    elif type(draft.tenant_id) is not UUID or draft.tenant_id.int == 0:
        raise DraftReviewPolicyDenied("Tenant do administrador inválido")

    start = _utc(draft.valid_from)
    end = _utc(draft.valid_until)
    observed = _utc(observed_at)
    if not (start < end and start <= observed < end):
        raise DraftReviewPolicyDenied("Rascunho fora da janela declarada")
    if type(draft.reviewer_grants) is not tuple or len(draft.reviewer_grants) != 2:
        raise DraftReviewPolicyDenied("Política requer dois vínculos propostos distintos")
    try:
        pair = correlate_unverified_review_sessions(
            journal,evidence,claims,reviewer_sessions,observed_at=observed_at,
        )
    except (ReviewSessionPairDenied, ValueError, TypeError, AttributeError) as exc:
        raise DraftReviewPolicyDenied("Revisores/sessões documentais não conferem") from exc

    reviewers = set()
    grant_manifest = []
    for i, grant in enumerate(draft.reviewer_grants):
        if type(grant) is not ReviewerGrantDraft:
            raise DraftReviewPolicyDenied("Designação não tipada")
        actor = _uuid(grant.reviewer_id)
        if (actor == creator or actor == evidence.preparer_id or
            actor in reviewers or actor != claims[i].reviewer_id or
            actor != UUID(reviewer_sessions[i].user_id)):
            raise DraftReviewPolicyDenied("Autorrevisão ou designação de outro ator")
        if (grant.scope != draft.scope or grant.tenant_id != draft.tenant_id or
            grant.role != role or grant.grant_origin != "DRAFT_NOT_ATTESTED"):
            raise DraftReviewPolicyDenied("Designação sem domínio, papel e origem válidos")
        reviewers.add(actor)
        grant_manifest.append({
            "reviewer_id": str(actor),
            "scope": grant.scope,
            "tenant_id": str(grant.tenant_id) if grant.tenant_id else None,
            "role": grant.role,
            "grant_origin": grant.grant_origin,
        })

    # A timestamp on a client draft does not establish an approved term.
    # Still forbid obviously inconsistent purported review times.
    for claim in claims:
        timestamp = _utc(claim.claimed_at)
        if not (start <= timestamp < end):
            raise DraftReviewPolicyDenied("Revisão declarada fora da vigência proposta")

    manifest = {
        "version": "M39980_POLICY_DRAFT_V1",
        "policy_id": str(policy_id),
        "scope": draft.scope,
        "tenant_id": str(draft.tenant_id) if draft.tenant_id else None,
        "event_type": draft.event_type,
        "created_by": str(creator),
        "created_by_role": draft.created_by_role,
        "document_digest": draft.policy_document_digest,
        "start": start.isoformat(timespec="microseconds"),
        "end": end.isoformat(timespec="microseconds"),
        "reviewers": grant_manifest,
        "documentary_chain_fingerprint": pair.documentary_chain_fingerprint,
    }
    fingerprint = sha256(json.dumps(manifest,sort_keys=True,separators=(",",":"),
        ensure_ascii=True).encode("utf-8")).hexdigest()

    gaps = (
        "POLICY_DRAFT_ORIGIN_AND_LEGAL_CONSENT_UNVERIFIED",
        _POLICY_GAP_BY_SCOPE[draft.scope],
        _EVENT_GATES[draft.event_type],
        "TWO_SEPARATE_AUTHENTICATED_REVIEW_EVENTS_NOT_CAPTURED",
        "DURABLE_NONCE_AND_IDEMPOTENCY_UNAVAILABLE",
        "SERVER_SIDE_GRANT_MEMBERSHIP_AND_OWNERSHIP_NOT_ATTESTED",
        "EVIDENCE_CLOSING_AND_PROVIDER_RECONCILIATION_PENDING",
        "JOURNAL_POSTING_AND_PAYOUT_DISABLED",
    )
    return ReviewPolicyGapReport(
        scope=draft.scope,tenant_id=draft.tenant_id,
        event_type=draft.event_type,
        journal_fingerprint=pair.journal_fingerprint,
        documentary_chain_fingerprint=pair.documentary_chain_fingerprint,
        policy_draft_fingerprint=fingerprint,
        outstanding_gates=gaps,
    )
