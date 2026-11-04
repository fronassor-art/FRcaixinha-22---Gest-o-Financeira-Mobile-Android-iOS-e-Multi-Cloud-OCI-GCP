"""M1081+ FR Caixinha AI Studio — revisão de documentos e contestação sandbox.

Não executa bloqueio, desbloqueio, saída, rateio, restituição, Pix,
fechamento ou transação real. Toda decisão é apenas EVENTO TÉCNICO.
"""
from __future__ import annotations
import os
from datetime import datetime
from typing import Literal
from uuid import UUID
import asyncpg
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from ..dependencies import AuthenticatedSession, get_current_session
from ..database import get_rls_db_connection
from .member_lifecycle_sandbox import _auth, _cycle, _test_sandbox

router = APIRouter(
    prefix="/tenants/{tenant_id}/cycles/{year}/member-lifecycle",
    tags=["Revisões e contestações contratuais — sandbox"],
)

Kind = Literal[
    "ADMIN_DOCUMENTS_REQUESTED",
    "ADMIN_REVIEW_ACCEPTED_SANDBOX",
    "ADMIN_REVIEW_REJECTED_SANDBOX",
    "MEMBER_CONTESTED",
]
FINAL = frozenset(("ADMIN_REVIEW_ACCEPTED_SANDBOX", "ADMIN_REVIEW_REJECTED_SANDBOX"))
MAX_EVENTS = 100

class ReviewEventPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    idempotency_key: UUID
    event_kind: Kind
    evidence_reference: str = Field(
        min_length=8, max_length=120,
        pattern=r"^[A-Za-z0-9._:-]{8,120}$",
    )

class ReviewCapabilitiesResponse(BaseModel):
    tenant_id: str
    year: int
    role: str
    schema_ready: bool
    sandbox_only: bool = True
    can_submit_contestation: bool = False
    can_review_independently: bool = False
    financial_effects_enabled: bool = False
    real_payout_enabled: bool = False

class ReviewEventResponse(BaseModel):
    event_id: str
    event_seq: int
    tenant_id: str
    request_id: str
    membership_id: str
    actor_user_id: str
    event_kind: Kind
    evidence_reference: str
    recorded_at: datetime
    financial_effect_applied: bool = False
    bank_reconciled: bool = False

class ReviewTimelineResponse(BaseModel):
    tenant_id: str
    request_id: str
    membership_id: str
    request_kind: str
    latest_event_kind: Kind | None = None
    pending_technical_review: bool = True
    items: list[ReviewEventResponse]
    has_more: bool = False
    financial_effect_applied: bool = False
    bank_reconciled: bool = False
    membership_status_changed: bool = False
    closing_authorized: bool = False
    payout_authorized: bool = False

def _missing_schema(exc):
    if isinstance(exc, (asyncpg.UndefinedTableError, asyncpg.UndefinedFunctionError,
                        asyncpg.InsufficientPrivilegeError,
                        asyncpg.InvalidSchemaNameError)):
        raise HTTPException(
            status_code=503,
            detail="Revisão indisponível: exige migração 029 e RLS de homologação.",
        ) from exc

async def _request(tenant_id, year, request_id, conn):
    cid = await _cycle(tenant_id, year, conn)
    try:
        row = await conn.fetchrow(
            "SELECT id,tenant_id,cycle_id,membership_id,request_kind "
            "FROM public.member_lifecycle_requests "
            "WHERE id=$1 AND tenant_id=$2 AND cycle_id=$3",
            request_id, tenant_id, cid,
        )
    except asyncpg.PostgresError as exc:
        _missing_schema(exc)
        raise HTTPException(status_code=503, detail="Consulta de solicitação indisponível.") from exc
    if row is None:
        raise HTTPException(status_code=404, detail="Solicitação não encontrada no contexto.")
    return row

def _format(row):
    return ReviewEventResponse(
        event_id=str(row["event_id"]),event_seq=row["event_seq"],
        tenant_id=str(row["tenant_id"]),
        request_id=str(row["request_id"]),
        membership_id=str(row["membership_id"]),
        actor_user_id=str(row["actor_user_id"]),
        event_kind=row["event_kind"],
        evidence_reference=row["evidence_reference"],
        recorded_at=row["recorded_at"],
    )

@router.get("/review-capabilities", response_model=ReviewCapabilitiesResponse)
async def lifecycle_review_capabilities(
    tenant_id: UUID, year: int,
    session: AuthenticatedSession = Depends(get_current_session),
    conn=Depends(get_rls_db_connection),
):
    _auth(tenant_id,session)
    await _cycle(tenant_id,year,conn)
    try:
        ready = await conn.fetchval(
            "SELECT to_regclass('public.member_lifecycle_review_events') IS NOT NULL "
            "AND to_regprocedure('public.lifecycle_append_review_event_sandbox("
            "uuid,uuid,varchar,uuid,varchar)') IS NOT NULL"
        )
    except asyncpg.PostgresError as exc:
        raise HTTPException(status_code=503,detail="Schema de revisão não verificável.") from exc
    enabled=(os.getenv("ENVIRONMENT","development")!="production" and
             os.getenv("FRCAIXINHA_LIFECYCLE_SANDBOX")=="1" and ready is True)
    return ReviewCapabilitiesResponse(
        tenant_id=str(tenant_id),year=year,role=session.role,
        schema_ready=bool(ready),
        can_submit_contestation=enabled and session.role=="TENANT_MEMBER",
        can_review_independently=enabled and session.role=="TENANT_ADMIN",
    )

@router.get("/requests/{request_id}/review-events",
            response_model=ReviewTimelineResponse)
async def list_member_review_events(
    tenant_id: UUID, year: int, request_id: UUID,
    session: AuthenticatedSession = Depends(get_current_session),
    conn=Depends(get_rls_db_connection),
):
    _auth(tenant_id,session)
    req=await _request(tenant_id,year,request_id,conn)
    try:
        rows=await conn.fetch(
            "SELECT event_id,event_seq,tenant_id,request_id,membership_id,"
            "actor_user_id,event_kind,evidence_reference,recorded_at "
            "FROM public.member_lifecycle_review_events "
            "WHERE tenant_id=$1 AND request_id=$2 "
            "ORDER BY event_seq ASC LIMIT 101",
            tenant_id,request_id,
        )
    except asyncpg.PostgresError as exc:
        _missing_schema(exc)
        raise HTTPException(status_code=503,detail="Histórico de revisão indisponível.") from exc
    if len(rows)>MAX_EVENTS:
        raise HTTPException(status_code=503,detail="Histórico maior que o limite auditado.")
    events=[_format(row) for row in rows]
    last=events[-1].event_kind if events else None
    return ReviewTimelineResponse(
        tenant_id=str(tenant_id),request_id=str(request_id),
        membership_id=str(req["membership_id"]),
        request_kind=req["request_kind"],
        latest_event_kind=last,
        pending_technical_review=last not in FINAL,
        items=events,
    )

@router.post("/requests/{request_id}/review-events",
             response_model=ReviewEventResponse)
async def submit_member_review_event_sandbox(
    tenant_id:UUID, year:int, request_id:UUID, payload:ReviewEventPayload,
    session:AuthenticatedSession=Depends(get_current_session),
    conn=Depends(get_rls_db_connection),
):
    _auth(tenant_id,session)
    _test_sandbox()
    await _request(tenant_id,year,request_id,conn)
    if (payload.event_kind=="MEMBER_CONTESTED" and
        session.role!="TENANT_MEMBER") or (
        payload.event_kind!="MEMBER_CONTESTED" and
        session.role!="TENANT_ADMIN"
    ):
        raise HTTPException(status_code=403,detail="Evento incompatível com perfil.")
    try:
        event_id=await conn.fetchval(
            "SELECT public.lifecycle_append_review_event_sandbox("
            "$1::uuid,$2::uuid,$3::varchar,$4::uuid,$5::varchar)",
            tenant_id,request_id,payload.event_kind,
            payload.idempotency_key,payload.evidence_reference,
        )
    except asyncpg.PostgresError as exc:
        _missing_schema(exc)
        raise HTTPException(
            status_code=409, detail="Revisão não admitida: verifique autoria, fase e idempotência."
        ) from exc
    except Exception as exc:
        raise HTTPException(status_code=503,detail="Registro de revisão não confirmado.") from exc
    if event_id is None:
        raise HTTPException(status_code=503,detail="Evento não confirmado.")
    try:
        row=await conn.fetchrow(
            "SELECT event_id,event_seq,tenant_id,request_id,membership_id,"
            "actor_user_id,event_kind,evidence_reference,recorded_at "
            "FROM public.member_lifecycle_review_events "
            "WHERE tenant_id=$1 AND request_id=$2 AND event_id=$3",
            tenant_id,request_id,UUID(str(event_id)),
        )
    except asyncpg.PostgresError as exc:
        _missing_schema(exc)
        raise HTTPException(status_code=503,detail="Evento não pode ser verificado.") from exc
    if row is None:
        raise HTTPException(status_code=503,detail="Evento não visível após inclusão.")
    return _format(row)
