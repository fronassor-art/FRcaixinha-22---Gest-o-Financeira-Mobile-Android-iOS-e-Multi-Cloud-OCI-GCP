"""FR Finance M40060: authenticated VIEW of unresolved review-policy gaps.

This is not a reviewer appointment, a two-person approval, an immutable audit
trail, a bank reconciliation, or permission to post any journal/PIX/payment.
Real get_current_session is mandatory; an authorized viewing session grants
only access to static, deny-by-default policy metadata. Do not accept any
reviewer/decision/mandate claims from request bodies or headers.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response

from ..database import get_rls_db_connection
from ..dependencies import (
    AuthenticatedSession, get_current_session, require_master,
)
from ..exclusive_cashbox_provenance import (
    EVENT_SCOPE, PLATFORM_MASTER, TENANT_ADMIN_OWN,
)
from ..exclusive_cashbox_review_readiness import (
    ReviewReadinessDenied, verify_review_readiness,
)

master_router = APIRouter(
    prefix="/master",
    tags=["M40060 — lacunas de revisão SaaS (somente leitura)"],
    include_in_schema=False,
)
tenant_router = APIRouter(
    prefix="/tenants/{tenant_id}",
    tags=["M40060 — lacunas de revisão do titular (somente leitura)"],
    include_in_schema=False,
)

# Static, non-negotiable gates; client supplied claims cannot relax them.
_PENDING = (
    "REVIEWER_POLICY_LEGAL_RATIFICATION_PENDING",
    "INDEPENDENT_REVIEWER_DESIGNATION_PENDING",
    "SEPARATE_SIGNED_AND_AUTHENTICATED_REVIEW_EVENTS_PENDING",
    "DURABLE_MANDATE_REVOCATION_AND_AUDIT_PENDING",
    "POSTGRES_RLS_REVIEW_RECEIPTS_RUNTIME_BINDING_PENDING",
    "PROVIDER_AND_FINANCIAL_RECONCILIATION_PENDING",
    "POSTING_PAYOUT_AND_PIX_BLOCKED",
)
_SCOPE_PENDING = {
    PLATFORM_MASTER: "MASTER_INDEPENDENT_REVIEWER_MANDATE_UNRATIFIED",
    TENANT_ADMIN_OWN: "TENANT_ADMIN_OWN_SECOND_REVIEWER_DESIGNATION_UNRATIFIED",
}


def _no_cache(response: Response) -> None:
    response.headers["Cache-Control"] = "private, no-store, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Vary"] = "Authorization"


def _view_only(scope: str, tenant_id: UUID | None) -> dict:
    # All event types are included as UNAUTHORIZED DRAFT CATEGORIES,
    # not as permissions. The event/scope map comes from M39900.
    if scope not in _SCOPE_PENDING:
        raise HTTPException(403, "Domínio financeiro sem política ratificada.")
    events = sorted(k for k, v in EVENT_SCOPE.items() if v == scope)
    return {
        "source": "SERVER_SESSION_READONLY_SCOPE",
        "scope": scope,
        "tenant_id": str(tenant_id) if tenant_id is not None else None,
        "state": "POLICY_AND_MANDATE_UNRATIFIED",
        "session_bound_for_view": True,
        "owner_verified_for_view": scope == TENANT_ADMIN_OWN,
        "draft_event_types_not_authorized": events,
        "policy_draft_reference": "M39980_NO_AUTHORITY",
        "mandate_draft_reference": "M39990_NO_EFFECTIVE_REVOCATION",
        "receipt_lab_reference": "M40050_CI_ONLY_NOT_RUNTIME_BOUND",
        "policy_ratified": False,
        "reviewer_grants_verified": False,
        "two_person_approval_verified": False,
        "effective_revocation_verified": False,
        "real_review_approved": False,
        "bank_reconciled": False,
        "journal_posted": False,
        "payout_enabled": False,
        "payment_enabled": False,
        "pix_enabled": False,
        "production_authorized": False,
        "available_balance_cents": None,
        "outstanding_gates": [_SCOPE_PENDING[scope], *_PENDING],
    }


@master_router.get("/exclusive-cashbox/review-policy-gaps")
async def master_review_policy_gaps(
    response: Response,
    session: AuthenticatedSession = Depends(require_master),
):
    """A bound Master sees only SaaS policy gaps, never a tenant balance."""
    _no_cache(response)
    try:
        verify_review_readiness(
            session,
            requested_scope=PLATFORM_MASTER,
            requested_tenant_id=None,
        )
    except ReviewReadinessDenied as exc:
        raise HTTPException(403, "Sessão não verificável para consulta.") from exc
    return _view_only(PLATFORM_MASTER, None)


@tenant_router.get("/admin-exclusive-cashbox/review-policy-gaps")
async def tenant_admin_review_policy_gaps(
    tenant_id: UUID,
    response: Response,
    session: AuthenticatedSession = Depends(get_current_session),
    conn=Depends(get_rls_db_connection),
):
    """A bound, active tenant-owner sees only own-remuneration policy gaps.

    The single read-only owner SELECT is performed under the existing RLS
    connection dependency. Never infer ownership from a client payload.
    """
    _no_cache(response)
    try:
        verify_review_readiness(
            session,
            requested_scope=TENANT_ADMIN_OWN,
            requested_tenant_id=tenant_id,
        )
    except ReviewReadinessDenied as exc:
        raise HTTPException(403, "Sessão não verificável para consulta.") from exc
    owner = await conn.fetchval(
        "SELECT admin_user_id FROM public.tenants "
        "WHERE id=$1 AND status='ATIVO'",
        tenant_id,
    )
    try:
        actor_id = UUID(session.user_id)
    except (AttributeError, TypeError, ValueError) as exc:
        raise HTTPException(403, "Titularidade não comprovada.") from exc
    # asyncpg may return its own UUID subtype: accept UUID instances only,
    # never a client string or an unrelated database value.
    if not isinstance(owner, UUID) or owner != actor_id:
        raise HTTPException(403, "Titularidade ativa não comprovada.")
    return _view_only(TENANT_ADMIN_OWN, tenant_id)
