"""AI Studio M18000: notifications session-to-recipient boundary.

Only get_current_session is authorized to supply identity upstream.
This module validates shape/role consistency. It does NOT authenticate a
session from a plain AuthenticatedSession object or authorize DB delivery.
Never derive scope from HTTP headers, client body, or query parameters.
"""
from __future__ import annotations
from dataclasses import dataclass
from uuid import UUID

from .dependencies import AuthenticatedSession
from .notification_inbox_page_boundary import RecipientScope
from .notifications_policy import NoticeRole
from .pix_automation_contract import FinancialOperationBlocked

CONTRACT = "AI_STUDIO_M18000_SESSION_SCOPE_NO_REAL_INBOX_V1"


@dataclass(frozen=True)
class NotificationSessionGate:
    scope: RecipientScope
    authenticated_by_dependency: bool = False
    inbox_source_authorized: bool = False
    notification_read_allowed: bool = False
    marking_read_allowed: bool = False
    financial_effect_allowed: bool = False


def validate_notification_session_shape(
    session: AuthenticatedSession,
) -> NotificationSessionGate:
    """Sanity-check a server-bound session, not an authentication replacement.

    Only an HTTP path depending on get_current_session can mark its
    upstream authentication as validated in routing logic.
    """
    if (
        type(session) is not AuthenticatedSession
        or type(session.user_id) is not str
        or type(session.role) is not str
        or type(session.is_master) is not bool
        or (session.tenant_id is not None and
            type(session.tenant_id) is not str)
    ):
        raise FinancialOperationBlocked("Sessão de notificação malformada")
    try:
        uid = UUID(session.user_id)
        role = NoticeRole(session.role)
        tenant = UUID(session.tenant_id) if session.tenant_id else None
    except (TypeError, ValueError) as exc:
        raise FinancialOperationBlocked("Identidade de sessão inválida") from exc
    # is_master is a person's platform attribute, not the active tenant role.
    # A Master may hold verified Admin/Member memberships; upstream checks them.
    if (
        uid.int == 0 or str(uid) != session.user_id
        or (tenant is not None and (
            tenant.int == 0 or str(tenant) != session.tenant_id))
        or (role is NoticeRole.MASTER) != (tenant is None)
        or (role is NoticeRole.MASTER and not session.is_master)
    ):
        raise FinancialOperationBlocked("Papel e caixinha inconsistentes")
    return NotificationSessionGate(
        scope=RecipientScope(user_id=uid,role=role,tenant_id=tenant)
    )
