"""FR Finance M39970 — compare documentary claims with two session shapes.

NO AUTHORIZATION: this is an offline, pure comparison of input objects.
AuthenticatedSession is constructible in Python, so this function CANNOT prove
either the inputs came from get_current_session or that reviewers signed.
A real workflow needs independently authenticated requests, server-side
tenant/role proof, durable anti-replay receipts, and immutable audit trails.
No API, SQL, network, posting, deposits, payout or provider IO.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from .dependencies import AuthenticatedSession
from .exclusive_cashbox_documentary_review import (
    DocumentaryReviewClaim, inspect_documentary_review_claims,
)
from .exclusive_cashbox_evidence_preflight import EvidenceDraft
from .exclusive_cashbox_journal_preflight import JournalCandidate
from .exclusive_cashbox_review_readiness import (
    ReviewReadinessDenied, verify_review_readiness,
)
from .exclusive_cashbox_provenance import PLATFORM_MASTER, TENANT_ADMIN_OWN


class ReviewSessionPairDenied(ValueError):
    """Inputs cannot form even an unverified independent-session preview."""


@dataclass(frozen=True)
class ReviewSessionPairPreflight:
    scope: str
    tenant_id: UUID | None
    journal_fingerprint: str
    documentary_chain_fingerprint: str
    state: str = "REVIEW_SESSION_PAIR_STRUCTURAL_ONLY"
    session_claim_alignment: bool = True
    claims_cryptographically_signed: bool = False
    verified_independent_reviewers: bool = False
    reviewer_roles_authorized: bool = False
    tenant_owner_attested: bool = False
    documentary_review_authorized: bool = False
    source_document_authenticated: bool = False
    provider_reconciled: bool = False
    journal_posted: bool = False
    payout_enabled: bool = False
    outstanding_gates: tuple[str, ...] = (
        "SERVER_MUST_OBTAIN_EACH_SESSION_IN_INDEPENDENT_AUTHENTICATED_REQUEST",
        "SERVER_MUST_ATTEST_REVIEWER_ROLE_AND_TENANT_MEMBERSHIP_AT_REVIEW_TIME",
        "ADMIN_TENANT_OWNERSHIP_AND_REVIEWER_POLICY_NOT_ATTESTED",
        "CLAIM_TIMESTAMPS_ARE_UNTRUSTED_AND_NOT_SIGNATURES",
        "SIGNED_NONCE_AND_PERSISTED_IDEMPOTENT_REVIEW_EVENTS_ABSENT",
        "SOURCE_EVIDENCE_AND_PROVIDER_RECONCILIATION_UNVERIFIED",
        "JOURNAL_POSTING_AND_PAYOUT_DISABLED",
    )


def correlate_unverified_review_sessions(
    journal: JournalCandidate,
    evidence: EvidenceDraft,
    claims: tuple[DocumentaryReviewClaim, ...],
    reviewer_sessions: tuple[AuthenticatedSession, ...],
    *,
    observed_at: datetime,
) -> ReviewSessionPairPreflight:
    """Verify field alignment only; never promote claims to approval.

    Two independently supplied session *objects* are not proof of two
    independently authenticated HTTP requests. The caller cannot use this
    preview to attest reviewer signatures or source documents.
    """
    try:
        reviewed = inspect_documentary_review_claims(journal, evidence, claims)
    except (ValueError, TypeError, AttributeError) as exc:
        raise ReviewSessionPairDenied("Alegações documentais inválidas") from exc
    if reviewed.scope not in (PLATFORM_MASTER, TENANT_ADMIN_OWN):
        raise ReviewSessionPairDenied("Política de revisores do caixa coletivo pendente")
    if type(reviewer_sessions) is not tuple or len(reviewer_sessions) != 2:
        raise ReviewSessionPairDenied("São necessárias duas sessões distintas")
    if (type(observed_at) is not datetime or observed_at.tzinfo is None or
        observed_at.utcoffset() is None):
        raise ReviewSessionPairDenied("Horário de observação sem fuso")
    observed_utc = observed_at.astimezone(timezone.utc)

    session_ids: set[UUID] = set()
    user_ids: set[UUID] = set()
    for claim, session in zip(claims, reviewer_sessions):
        try:
            verify_review_readiness(
                session,
                requested_scope=reviewed.scope,
                requested_tenant_id=reviewed.tenant_id,
                observed_at=observed_at,
            )
            actor = UUID(session.user_id)
            sid = UUID(session.verified_session_id)
            claimed_time = claim.claimed_at.astimezone(timezone.utc)
            refreshed_time = session.verified_session_at.astimezone(timezone.utc)
            expiry_time = session.verified_session_expires_at.astimezone(timezone.utc)
        except (ReviewReadinessDenied, TypeError, AttributeError, ValueError) as exc:
            raise ReviewSessionPairDenied("Sessão alegada não verificável") from exc

        if (actor != claim.reviewer_id or actor in user_ids or
            sid in session_ids or actor == evidence.preparer_id):
            raise ReviewSessionPairDenied("Revisor não coincide com sessão distinta")
        # A supplied timestamp is still not a trusted timestamp or signature.
        # Reject an alleged review outside the purported verified session window.
        if not (refreshed_time <= claimed_time <= observed_utc < expiry_time):
            raise ReviewSessionPairDenied("Revisão alegada fora da sessão")
        user_ids.add(actor)
        session_ids.add(sid)

    return ReviewSessionPairPreflight(
        scope=reviewed.scope,
        tenant_id=reviewed.tenant_id,
        journal_fingerprint=reviewed.journal_fingerprint,
        documentary_chain_fingerprint=reviewed.chain_fingerprint,
    )
