"""M37460: strictly opt-in CI-only FastAPI SaaS acceptance contract boundary.

The real get_current_session dependency is required, but the CI context and
executor have NO default implementation, so nothing can be charged or persisted.
Only explicit dependency overrides in isolated tests may simulate a successful
request. The controller MUST NEVER be mounted on Termux or production.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import os
from typing import Mapping
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from ..dependencies import AuthenticatedSession, get_current_session
from ..saas_acceptance_api_contract_ci import (
    CIPrincipal, CIPublishedOffer, CIDisposableExecutor,
    evaluate_api_contract_ci, environment_allowed,
)

router = APIRouter(
    prefix="/saas/ci-contract",
    tags=["CI somente — contrato SaaS, sem autenticacao operacional"],
    include_in_schema=False,
)


@dataclass(frozen=True)
class CITrustedServerContext:
    """Must originate from a server DB readback in a later stage, NOT client."""
    tenant_id: UUID
    administrator_id: UUID
    session_id: UUID
    session_role: str
    session_active: bool
    email_verified: bool
    session_checked_at: datetime
    session_expires_at: datetime
    request_id: UUID
    challenge_id: UUID
    offer: CIPublishedOffer
    source: str = "CI_SYNTHETIC_SERVER_DB_READBACK"


def ci_endpoint_allowed(env: Mapping[str, str]) -> bool:
    return (
        environment_allowed(env)
        and env.get("FR_FINANCE_M37460_ROUTE") == "CI_DISPOSABLE_ONLY"
        and env.get("FRCAIXINHA_TERMUX_LOCAL_API") != "1"
        and env.get("FRCAIXINHA_TEST_AUTH") != "1"
    )


def get_ci_trusted_server_context() -> CITrustedServerContext:
    # There is no production implementation and no DB access in this route.
    raise HTTPException(503, detail="CI-only server-side offer readback absent")


def get_ci_disposable_executor() -> CIDisposableExecutor:
    raise HTTPException(503, detail="CI-only executor unavailable")


def _valid_uuid(x: object) -> bool:
    return type(x) is UUID and x.int != 0


def _aware(x: object) -> bool:
    return type(x) is datetime and x.tzinfo is not None and x.utcoffset() is not None


def check_server_identity_binding(
    session: AuthenticatedSession, context: CITrustedServerContext,
    *, now: datetime,
) -> CIPrincipal | None:
    """Verify a session's principal against distinct server-side DB claim.

    Real session ID and email verification are NOT available from the
    existing AuthenticatedSession object; the test context is synthetic and
    must not be mistaken for operational authentication/consent evidence.
    """
    if (type(session) is not AuthenticatedSession
        or type(context) is not CITrustedServerContext
        or not _aware(now)
        or context.source != "CI_SYNTHETIC_SERVER_DB_READBACK"
        or not all(_valid_uuid(x) for x in (
            context.tenant_id, context.administrator_id,
            context.session_id, context.request_id, context.challenge_id))
        or not _aware(context.session_checked_at)
        or not _aware(context.session_expires_at)
        or type(context.session_active) is not bool
        or type(context.email_verified) is not bool):
        return None
    if (session.is_master is not False
        or session.role != "TENANT_ADMIN"
        or context.session_role != "TENANT_ADMIN"
        or not context.session_active
        or not context.email_verified):
        return None
    try:
        user_id = UUID(session.user_id)
        tenant_id = UUID(session.tenant_id or "")
    except (ValueError, AttributeError, TypeError):
        return None
    if (user_id != context.administrator_id
        or tenant_id != context.tenant_id
        or context.tenant_id != context.offer.tenant_id
        or context.session_checked_at > now
        or now - context.session_checked_at > timedelta(minutes=5)
        or context.session_expires_at <= now):
        return None
    return CIPrincipal(
        user_id=user_id, tenant_id=tenant_id, session_id=context.session_id,
        active_role="TENANT_ADMIN", active=True, email_verified=True,
        server_checked_at=context.session_checked_at,
        expires_at=context.session_expires_at,
    )


@router.post("/transition")
async def ci_saas_acceptance_transition(
    request: Request,
    session: AuthenticatedSession = Depends(get_current_session),
    context: CITrustedServerContext = Depends(get_ci_trusted_server_context),
    executor: CIDisposableExecutor = Depends(get_ci_disposable_executor),
):
    if not ci_endpoint_allowed(os.environ):
        raise HTTPException(404, detail="CI-only route unavailable")
    # Fail-closed JSON parsing with an explicit size bound.
    if (request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
        != "application/json"):
        raise HTTPException(415, detail="JSON required")
    raw = await request.body()
    if not raw or len(raw) > 2048:
        raise HTTPException(413, detail="Invalid request length")
    try:
        body = await request.json()
    except ValueError:
        raise HTTPException(400, detail="Malformed JSON") from None
    now = datetime.now(timezone.utc)
    principal = check_server_identity_binding(session,context,now=now)
    if principal is None:
        raise HTTPException(403, detail="Server principal mismatch")
    outcome = evaluate_api_contract_ci(
        body=body,principal=principal,offer=context.offer,
        challenge_id_server=context.challenge_id,
        request_id_server=context.request_id,
        executor=executor,
        env=os.environ,now=now,
    )
    # Never echo session, bearer, raw contract, personal email, price or digest.
    response = JSONResponse(
        status_code=outcome.status_code,
        content={
            "state":outcome.state,
            "ci_only":True,
            "real_identity_verified":False,
            "legal_consent_verified":False,
            "payment_authorized":False,
            "license_authorized":False,
            "pix_authorized":False,
            "activation_authorized":False,
            "production_authorized":False,
        },
    )
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return response
