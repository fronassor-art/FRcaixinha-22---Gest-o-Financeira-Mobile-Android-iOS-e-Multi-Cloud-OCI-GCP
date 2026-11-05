"""Authenticated notifications capability; inbox requires durable tenant RLS.

No demo events, no mocked unread count, no external sender, no delivery success.
"""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from ..dependencies import AuthenticatedSession, get_current_session

router = APIRouter(prefix="/notifications",tags=["Notificações — preparação"])

@router.get("/capabilities")
async def notification_capabilities(
    session: AuthenticatedSession = Depends(get_current_session),
):
    if session.role not in ("MASTER", "TENANT_ADMIN", "TENANT_MEMBER"):
        raise HTTPException(403,detail="Perfil não autorizado")
    if (session.role=="MASTER" and (not session.is_master or session.tenant_id))
        or (session.role!="MASTER" and (not session.tenant_id or session.is_master)):
        raise HTTPException(403,detail="Contexto inconsistente")
    return {
        "workstream":"AI_STUDIO",
        "contract":"AI_STUDIO_M15000_NOTIFICATION_CAPABILITIES_FAIL_CLOSED_V1",
        "role":session.role,
        "authenticated_session_required":True,
        "inbox_schema_connected":False,
        "inbox_read_available":False,
        "unread_count_available":False,
        "in_app_delivery_active":False,
        "email_delivery_active":False,
        "push_delivery_active":False,
        "whatsapp_delivery_active":False,
        "schedule_approved":False,
        "bank_reconciled":False,
        "real_payments_enabled":False,
    }

@router.get("")
async def list_notifications(
    session: AuthenticatedSession = Depends(get_current_session),
):
    # Fail closed after session validation: empty list would imply a
    # trustworthy query against an authoritative personal inbox.
    raise HTTPException(
        status_code=503,
        detail="Central de notificações indisponível até persistência, RLS e autenticação de origem.",
    )
