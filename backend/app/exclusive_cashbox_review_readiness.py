"""FR Finance M39960 — session-bound viewer readiness, NOT reviewer approval.

This gate consumes AuthenticatedSession emitted by the server's get_current_session.
Never instantiate from client payload, headers, applicant claims or review hashes.

No database, provider, network, filesystem or mutation. Session binding can
allow a protected READ-ONLY readiness response only, never a signed review,
posting, bank reconciliation, expense approval or payment.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID

from .dependencies import AuthenticatedSession
from .exclusive_cashbox_provenance import PLATFORM_MASTER, TENANT_ADMIN_OWN

_VERIFICATION_SOURCE = "POSTGRES_TOKEN_HASH_REFRESH"
_MAX_VERIFICATION_AGE = timedelta(minutes=5)
_MAX_SESSION_LIFETIME = timedelta(minutes=30)


class ReviewReadinessDenied(ValueError):
    """Fail closed; must not expose session tokens, email or actors."""


@dataclass(frozen=True)
class ReviewReadiness:
    scope: str
    tenant_id: UUID | None
    state: str = "SESSION_BOUND_VIEW_ONLY"
    session_bound: bool = True
    independent_reviewer_verified: bool = False
    documentary_review_authorized: bool = False
    document_authenticated: bool = False
    provider_reconciled: bool = False
    journal_posted: bool = False
    payment_enabled: bool = False
    payout_enabled: bool = False


def verify_review_readiness(
    session: AuthenticatedSession, *,
    requested_scope: str, requested_tenant_id: UUID | None,
    observed_at: datetime | None = None,
) -> ReviewReadiness:
    """Validate *server-verification metadata* and request scope only.

    For tenant-admin requests the route must additionally check the active
    tenant's owner using the RLS-scoped database connection. No approval
    can be conferred even if this preflight accepts the read-only viewer.
    """
    if type(session) is not AuthenticatedSession:
        raise ReviewReadinessDenied("Sessão verificável indisponível")
    if session.verification_source != _VERIFICATION_SOURCE:
        raise ReviewReadinessDenied("Sessão sem vínculo PostgreSQL comprovado")
    try:
        user_id = UUID(session.user_id)
        verified_session_id = UUID(session.verified_session_id)
    except (AttributeError, TypeError, ValueError) as exc:
        raise ReviewReadinessDenied("Identidade verificável inválida") from exc
    if user_id.int == 0 or verified_session_id.int == 0:
        raise ReviewReadinessDenied("Identidade verificável vazia")
    if type(session.verified_session_at) is not datetime or (
        type(session.verified_session_expires_at) is not datetime
    ):
        raise ReviewReadinessDenied("Horários da sessão indisponíveis")
    verified_at = session.verified_session_at
    expires_at = session.verified_session_expires_at
    if (verified_at.tzinfo is None or verified_at.utcoffset() is None or
        expires_at.tzinfo is None or expires_at.utcoffset() is None):
        raise ReviewReadinessDenied("Sessão não possui fuso válido")
    if observed_at is None:
        observed_at = datetime.now(timezone.utc)
    if (type(observed_at) is not datetime or observed_at.tzinfo is None or
        observed_at.utcoffset() is None):
        raise ReviewReadinessDenied("Horário de observação inválido")
    # Fail closed on stale, future, expired or implausibly long renewal windows.
    age = observed_at - verified_at
    lifetime = expires_at - verified_at
    if (age < timedelta(0) or age > _MAX_VERIFICATION_AGE or
        observed_at >= expires_at or lifetime <= timedelta(0) or
        lifetime > _MAX_SESSION_LIFETIME):
        raise ReviewReadinessDenied("Sessão fora da janela verificada")

    if requested_scope == PLATFORM_MASTER:
        if (requested_tenant_id is not None or session.role != "MASTER" or
            session.is_master is not True or session.tenant_id is not None):
            raise ReviewReadinessDenied("Escopo Master inválido")
        return ReviewReadiness(scope=PLATFORM_MASTER, tenant_id=None)
    if requested_scope == TENANT_ADMIN_OWN:
        if (type(requested_tenant_id) is not UUID or
            session.role != "TENANT_ADMIN" or
            session.is_master is not False):
            raise ReviewReadinessDenied("Escopo de administrador inválido")
        try:
            session_tenant = UUID(session.tenant_id)
        except (AttributeError, TypeError, ValueError) as exc:
            raise ReviewReadinessDenied("Tenant da sessão inválido") from exc
        if (session_tenant.int == 0 or requested_tenant_id.int == 0 or
            session_tenant != requested_tenant_id):
            raise ReviewReadinessDenied("Sessão de outro tenant")
        return ReviewReadiness(scope=TENANT_ADMIN_OWN,
                               tenant_id=requested_tenant_id)
    raise ReviewReadinessDenied("Domínio financeiro não consultável")
