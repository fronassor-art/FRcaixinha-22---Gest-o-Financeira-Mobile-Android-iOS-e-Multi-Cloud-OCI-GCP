"""FR Caixinha AI Studio — in-app notifications for local authenticated testing.

No public SQL access, no untrusted event publisher, no emails/push/WhatsApp.
The real local path is enabled only after 001-027+031, session provisioning,
a private 0600 api.env, and explicit local environment gates. Everything else
fails closed with 503 instead of showing fake empty results.
"""
from __future__ import annotations

from datetime import datetime, timezone
import os
from urllib.parse import urlparse
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..config import settings
from ..database import get_rls_db_connection
from ..dependencies import AuthenticatedSession, get_current_session
from ..notification_inbox_page_boundary import (
    RecipientScope, preview_notification_page, decode_cursor,
)
from ..notification_session_gate import validate_notification_session_shape
from ..pix_automation_contract import FinancialOperationBlocked

router=APIRouter(prefix="/notifications",tags=["Notificações internas"])


def _local_enabled() -> bool:
    try:
        db=urlparse(settings.DATABASE_URL)
        secret=os.getenv("IN_APP_CURSOR_HMAC_KEY","")
        return (
            os.getenv("ENVIRONMENT","development") != "production"
            and os.getenv("FRCAIXINHA_TEST_AUTH") == "1"
            and os.getenv("FRCAIXINHA_TERMUX_LOCAL_API") == "1"
            and os.getenv("AI_STUDIO_IN_APP_NOTIFICATIONS") == "YES"
            and db.scheme in ("postgres","postgresql")
            and db.username == "frc_ai_app"
            and db.hostname == "127.0.0.1"
            and db.port == 5433
            and db.path == "/frcaixinha_aistudio_dev"
            # Do not accept service/PGOPTIONS overrides or URL fragments.
            and db.query == ""
            and db.fragment == ""
            and len(secret.encode("utf-8")) >= 32
        )
    except (ValueError, TypeError):
        return False


def _scope(session: AuthenticatedSession) -> RecipientScope:
    try:
        return validate_notification_session_shape(session).scope
    except FinancialOperationBlocked as exc:
        raise HTTPException(status_code=403,
                            detail="Contexto de notificações inconsistente") from exc


def _secret() -> bytes:
    if not _local_enabled():
        raise HTTPException(status_code=503,
                            detail="Notificações internas indisponíveis sem configuração local segura")
    return os.getenv("IN_APP_CURSOR_HMAC_KEY","").encode("utf-8")


async def _schema_ready() -> bool:
    if not _local_enabled():
        return False
    try:
        conn=await asyncpg.connect(settings.DATABASE_URL,timeout=3)
        try:
            return (await conn.fetchval(
                "SELECT COALESCE((SELECT c.relrowsecurity AND c.relforcerowsecurity "
                "FROM pg_class c WHERE c.oid=to_regclass('public.notification_inbox')),FALSE) "
                "AND has_table_privilege(current_user,to_regclass('public.notification_inbox'),'SELECT') "
                "AND NOT has_table_privilege(current_user,to_regclass('public.notification_inbox'),'INSERT') "
                "AND NOT has_table_privilege(current_user,to_regclass('public.notification_inbox'),'UPDATE') "
                "AND has_function_privilege(current_user,"
                "to_regprocedure('public.notification_local_create_selftest()'),'EXECUTE') "
                "AND has_function_privilege(current_user,"
                "to_regprocedure('public.notification_local_mark_read(uuid)'),'EXECUTE') "
                "AND has_function_privilege('frc_ai_auth',"
                "to_regprocedure('public.notification_local_session_issued(text)'),'EXECUTE')"
            )) is True
        finally:
            await conn.close()
    except (asyncpg.PostgresError,OSError,TimeoutError,ValueError):
        return False


def _must_be_local() -> None:
    if not _local_enabled():
        raise HTTPException(status_code=503,
            detail="Operação bloqueada: notificações internas exigem migração 031 e API local autenticada")


async def _authorized_local_scope(
    session: AuthenticatedSession=Depends(get_current_session),
) -> AuthenticatedSession:
    # Resolve before opening a DB transaction: wrong role=403, disabled=503.
    _scope(session)
    _must_be_local()
    return session


def _normalize(row: asyncpg.Record) -> dict:
    item=dict(row)
    for key in ("id","recipient_user_id","tenant_id"):
        raw=item[key]
        if raw is None:
            if key=="tenant_id":
                continue
            raise HTTPException(503,detail="Registro de notificação inconsistente")
        try:
            uid=UUID(str(raw))
        except (TypeError, ValueError, AttributeError) as exc:
            raise HTTPException(503,detail="Identificador de notificação inválido") from exc
        if uid.int==0 or str(uid)!=str(raw):
            raise HTTPException(503,detail="Identificador de notificação não canônico")
        item[key]=uid
    return item


@router.get("/capabilities")
async def notification_capabilities(
    session: AuthenticatedSession=Depends(get_current_session)
):
    scope=_scope(session)
    ready=await _schema_ready()
    return {
        "workstream":"AI_STUDIO",
        "contract":"AI_STUDIO_M19000_IN_APP_LOCAL_CAPABILITIES_V1" if ready
            else "AI_STUDIO_M15000_NOTIFICATION_CAPABILITIES_FAIL_CLOSED_V1",
        "role":scope.role.value,
        "authenticated_session_required":True,
        "inbox_schema_connected":ready,
        "inbox_read_available":ready,
        "unread_count_available":ready,
        "in_app_delivery_active":ready,
        "self_test_internal_available":ready,
        "email_delivery_active":False,
        "push_delivery_active":False,
        "whatsapp_delivery_active":False,
        "schedule_approved":False,
        "bank_reconciled":False,
        "real_payments_enabled":False,
    }


@router.get("/readiness")
async def notification_readiness(
    session: AuthenticatedSession=Depends(get_current_session)
):
    scope=_scope(session)
    ready=await _schema_ready()
    return {
        "workstream":"AI_STUDIO",
        "contract":"AI_STUDIO_M19000_NOTIFICATION_LOCAL_READINESS_V1",
        "role":scope.role.value,
        "session_dependency_checked":True,
        "recipient_scoped_preflight":True,
        "inbox_schema_deployed":ready,
        "inbox_api_connected":ready,
        "mark_read_active":ready,
        "unread_count_authoritative":ready,
        "production_event_authentication":False,
        "external_delivery_active":False,
        "bank_reconciled":False,
        "real_payments_enabled":False,
    }


@router.get("")
async def list_notifications(
    limit: int=Query(default=20,ge=1,le=50),
    cursor: str | None=Query(default=None,max_length=1400),
    session: AuthenticatedSession=Depends(_authorized_local_scope),
    conn: asyncpg.Connection=Depends(get_rls_db_connection),
):
    scope=_scope(session)
    secret=_secret()
    now=datetime.now(timezone.utc)
    try:
        marker=decode_cursor(cursor,scope,secret=secret,now=now) if cursor else None
        rows=await conn.fetch(
            "SELECT id,tenant_id,recipient_user_id,recipient_role,kind,"
            "title,message,created_at,read_at FROM public.notification_inbox "
            "WHERE recipient_user_id=$1::uuid AND recipient_role=$2::varchar "
            "AND tenant_id IS NOT DISTINCT FROM $3::uuid "
            "AND ($4::timestamptz IS NULL OR "
            "(created_at,id)<($4::timestamptz,$5::uuid)) "
            "ORDER BY created_at DESC,id DESC LIMIT $6",
            scope.user_id,scope.role.value,scope.tenant_id,
            marker[0] if marker else None,marker[1] if marker else None,
            limit+1,
        )
        page=preview_notification_page(
            tuple(_normalize(r) for r in rows),scope,
            secret=secret,now=now,limit=limit,after=cursor
        )
        unread=await conn.fetchval(
            "SELECT count(*) FROM public.notification_inbox WHERE "
            "recipient_user_id=$1::uuid AND recipient_role=$2::varchar "
            "AND tenant_id IS NOT DISTINCT FROM $3::uuid AND read_at IS NULL",
            scope.user_id,scope.role.value,scope.tenant_id,
        )
        if type(unread) is not int or unread<0:
            raise FinancialOperationBlocked("Contador não confiável")
    except FinancialOperationBlocked as exc:
        raise HTTPException(400,detail="Página ou cursor de notificação inválido") from exc
    except asyncpg.PostgresError as exc:
        raise HTTPException(503,detail="Inbox indisponível ou migração 031 ausente") from exc
    return {
        "workstream":"AI_STUDIO",
        "contract":"AI_STUDIO_M19000_IN_APP_LOCAL_INBOX_V1",
        "items":list(page.items),
        "next_cursor":page.next_cursor,
        "has_more":page.has_more,
        "unread_count":unread,
        "external_send_authorized":False,
        "financial_effect_authorized":False,
    }


@router.post("/self-test",status_code=status.HTTP_201_CREATED)
async def create_selftest_notice(
    session: AuthenticatedSession=Depends(_authorized_local_scope),
    conn: asyncpg.Connection=Depends(get_rls_db_connection),
):
    _scope(session)
    _must_be_local()
    try:
        nid=await conn.fetchval("SELECT public.notification_local_create_selftest()")
        if nid is None:
            raise FinancialOperationBlocked("Aviso não registrado")
        return {"id":str(nid),"kind":"SELF_TEST","channel":"IN_APP",
                "external_send_authorized":False,"financial_effect_authorized":False}
    except asyncpg.PostgresError as exc:
        if "daily synthetic notice rate limit" in str(exc):
            raise HTTPException(429,detail="Limite de dez avisos internos em 24 horas") from exc
        raise HTTPException(503,detail="Não foi possível registrar aviso interno") from exc


@router.post("/{notice_id}/read")
async def mark_notification_read(
    notice_id: UUID,
    session: AuthenticatedSession=Depends(_authorized_local_scope),
    conn: asyncpg.Connection=Depends(get_rls_db_connection),
):
    _scope(session)
    _must_be_local()
    try:
        result=await conn.fetchval(
            "SELECT public.notification_local_mark_read($1::uuid)",notice_id
        )
    except asyncpg.PostgresError as exc:
        raise HTTPException(503,detail="Não foi possível confirmar leitura") from exc
    if result=="NOT_FOUND":
        raise HTTPException(404,detail="Aviso não encontrado nesta conta")
    if result not in ("READ","ALREADY_READ"):
        raise HTTPException(503,detail="Confirmação de leitura inválida")
    return {"status":result,"id":str(notice_id),"financial_effect_authorized":False}
