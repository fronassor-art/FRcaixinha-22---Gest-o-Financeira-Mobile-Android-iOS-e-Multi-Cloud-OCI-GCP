"""FR Caixinha AI Studio — pedidos de ciclo em HOMOLOGAÇÃO.

Registra pedido de saída voluntária ou revisão administrativa sem mexer em
membership status, capital, multa, lucro, lançamento contábil ou Pix.
Sem a feature flag explícita, POST sempre falha fechado.
"""
from __future__ import annotations

import os
import asyncpg
from uuid import UUID
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, ConfigDict

from ..database import get_rls_db_connection
from ..dependencies import (
    AuthenticatedSession, get_current_session, require_tenant_access,
)

router=APIRouter(
    prefix="/tenants/{tenant_id}/cycles/{year}/member-lifecycle",
    tags=["Solicitações e revisões de membros — homologação"]
)
LIMIT=100


class LifecycleSandboxRequest(BaseModel):
    model_config=ConfigDict(extra="forbid")
    idempotency_key: UUID
    policy_reference: str = Field(
        ..., min_length=8, max_length=120,
        pattern=r"^[A-Za-z0-9._:-]{8,120}$",
    )


class LifecycleRequestResponse(BaseModel):
    id: str
    tenant_id: str
    cycle_id: str
    membership_id: str
    requested_by_user_id: str
    request_kind: str
    policy_reference: str
    status: str
    requested_at: datetime
    latest_review_event: str | None = None
    technical_review_pending: bool = True
    sandbox_only: bool = True
    bank_reconciled: bool = False
    financial_effect_applied: bool = False
    member_status_changed: bool = False
    profit_rights_modified: bool = False
    payment_authorized: bool = False


class LifecycleClosingGatesResponse(BaseModel):
    tenant_id: str
    cycle_id: str
    year: int
    pending_voluntary_exits: int
    pending_delinquency_reviews: int
    registered_unsettled_contributions: int
    unclosed_loans: int
    status: str = "REVIEW_AND_BANK_EVIDENCE_REQUIRED"
    bank_reconciled: bool = False
    can_close_cycle: bool = False
    can_distribute_profit: bool = False
    real_payout_enabled: bool = False


class LifecycleCapabilitiesResponse(BaseModel):
    tenant_id: str
    year: int
    role: str
    schema_ready: bool = False
    sandbox_only: bool = True
    can_submit_voluntary_exit: bool = False
    can_submit_delinquency_review: bool = False
    financial_effects_enabled: bool = False
    bank_reconciled: bool = False
    production_payments_enabled: bool = False


class LifecycleListResponse(BaseModel):
    tenant_id: str
    year: int
    scope: str
    items: list[LifecycleRequestResponse]
    has_more: bool = False
    bank_reconciled: bool = False
    financial_effect_applied: bool = False


def _test_sandbox():
    if (os.getenv("ENVIRONMENT","development")=="production"
        or os.getenv("FRCAIXINHA_LIFECYCLE_SANDBOX")!="1"):
        raise HTTPException(
            status_code=503,
            detail="Solicitações em escrita habilitadas apenas no ambiente de homologação isolado.",
        )


def _auth(tenant_id:UUID, session:AuthenticatedSession, role:str|None=None):
    require_tenant_access(str(tenant_id),session)
    if session.role not in ("TENANT_MEMBER","TENANT_ADMIN"):
        raise HTTPException(status_code=403,detail="Perfil não autorizado.")
    if role and session.role!=role:
        raise HTTPException(status_code=403,detail="Contexto sem autorização.")


async def _cycle(tenant_id:UUID,year:int,conn):
    if type(year) is not int or not 2020<=year<=2100:
        raise HTTPException(status_code=422,detail="Exercício inválido.")
    row=await conn.fetchrow(
        "SELECT id,status FROM public.cycles "
        "WHERE tenant_id=$1 AND year=$2",
        tenant_id,year,
    )
    if row is None:
        raise HTTPException(status_code=404,detail="Ciclo não encontrado.")
    return UUID(str(row["id"]))


async def _fetch_request_rows(conn,sql,*args):
    """Falha explícita se 028 ainda não existe; não cria dados sintéticos."""
    try:
        return await conn.fetch(sql,*args)
    except (asyncpg.UndefinedTableError,asyncpg.InvalidSchemaNameError,
            asyncpg.InsufficientPrivilegeError) as exc:
        raise HTTPException(
            status_code=503,
            detail="Fila indisponível: banco de homologação sem migration 028 ou RLS.",
        ) from exc


async def _format(row):
    return LifecycleRequestResponse(
        id=str(row["id"]),tenant_id=str(row["tenant_id"]),
        cycle_id=str(row["cycle_id"]),
        membership_id=str(row["membership_id"]),
        requested_by_user_id=str(row["requested_by_user_id"]),
        request_kind=row["request_kind"],
        policy_reference=row["policy_reference"],
        status=row["status"],
        requested_at=row["requested_at"],
        latest_review_event=row.get("latest_review_event"),
        technical_review_pending=row.get("latest_review_event") not in (
            "ADMIN_REVIEW_ACCEPTED_SANDBOX",
            "ADMIN_REVIEW_REJECTED_SANDBOX",
        ),
    )


@router.get("/capabilities",response_model=LifecycleCapabilitiesResponse)
async def member_lifecycle_capabilities(
    tenant_id:UUID,year:int,
    session:AuthenticatedSession=Depends(get_current_session),
    conn=Depends(get_rls_db_connection),
):
    _auth(tenant_id,session)
    await _cycle(tenant_id,year,conn)
    try:
        installed=await conn.fetchval(
            "SELECT (to_regclass('public.member_lifecycle_requests') IS NOT NULL "
            "AND to_regprocedure('public.lifecycle_submit_request_sandbox("
            "uuid,uuid,uuid,varchar,uuid,varchar)') IS NOT NULL)"
        )
    except asyncpg.PostgresError as exc:
        raise HTTPException(status_code=503,
            detail="Verificação de capacidade indisponível.") from exc
    isolated=(os.getenv("ENVIRONMENT","development")!="production" and
              os.getenv("FRCAIXINHA_LIFECYCLE_SANDBOX")=="1" and
              installed is True)
    return LifecycleCapabilitiesResponse(
        tenant_id=str(tenant_id),year=year,role=session.role,
        schema_ready=bool(installed),
        can_submit_voluntary_exit=isolated and session.role=="TENANT_MEMBER",
        can_submit_delinquency_review=isolated and session.role=="TENANT_ADMIN",
    )


@router.get("/closing-gates",response_model=LifecycleClosingGatesResponse)
async def member_lifecycle_closing_gates(
    tenant_id:UUID,year:int,
    session:AuthenticatedSession=Depends(get_current_session),
    conn=Depends(get_rls_db_connection),
):
    """Bloqueios operacionais do ciclo sem liquidação ou alteração de membros."""
    _auth(tenant_id,session,role="TENANT_ADMIN")
    cycle_id=await _cycle(tenant_id,year,conn)
    try:
        # M1081: a solicitação permanece imutável em 028; o evento mais
        # recente de 029 define se a revisão documental ainda está pendente.
        pending=await conn.fetchrow(
            "SELECT count(*) FILTER "
            "(WHERE r.request_kind='VOLUNTARY_EXIT')::integer AS exits, "
            "count(*) FILTER "
            "(WHERE r.request_kind='DELINQUENCY_REVIEW')::integer AS reviews "
            "FROM public.member_lifecycle_requests r "
            "LEFT JOIN LATERAL ("
            "SELECT e.event_kind FROM public.member_lifecycle_review_events e "
            "WHERE e.tenant_id=r.tenant_id AND e.request_id=r.id "
            "ORDER BY e.event_seq DESC LIMIT 1"
            ") last_review ON TRUE "
            "WHERE r.tenant_id=$1 AND r.cycle_id=$2 AND r.status='PENDING_REVIEW' "
            "AND (last_review.event_kind IS NULL OR last_review.event_kind NOT IN "
            "('ADMIN_REVIEW_ACCEPTED_SANDBOX','ADMIN_REVIEW_REJECTED_SANDBOX'))",
            tenant_id,cycle_id,
        )
        unsettled=await conn.fetchval(
            "SELECT count(*) FROM public.contributions "
            "WHERE tenant_id=$1 AND cycle_id=$2 AND payment_status<>'QUITADA'",
            tenant_id,cycle_id,
        )
        loans=await conn.fetchval(
            "SELECT count(*) FROM public.loans "
            "WHERE tenant_id=$1 AND cycle_id=$2 "
            "AND status NOT IN ('QUITADO','CANCELADO','RECUSADO')",
            tenant_id,cycle_id,
        )
    except (asyncpg.UndefinedTableError,asyncpg.InsufficientPrivilegeError,
            asyncpg.InvalidSchemaNameError) as exc:
        raise HTTPException(status_code=503,
            detail="Conferência de encerramento requer schema 028 e RLS ativo.") from exc
    if (pending is None or unsettled is None or loans is None or
            any(type(x) is not int or x<0 for x in (
                pending["exits"],pending["reviews"],unsettled,loans))):
        raise HTTPException(status_code=503,
            detail="Dados de conferência do ciclo inconsistentes.")
    return LifecycleClosingGatesResponse(
        tenant_id=str(tenant_id),cycle_id=str(cycle_id),year=year,
        pending_voluntary_exits=pending["exits"],
        pending_delinquency_reviews=pending["reviews"],
        registered_unsettled_contributions=unsettled,
        unclosed_loans=loans,
    )


@router.get("/me",response_model=LifecycleListResponse)
async def my_member_lifecycle_requests(
    tenant_id:UUID,year:int,
    session:AuthenticatedSession=Depends(get_current_session),
    conn=Depends(get_rls_db_connection),
):
    _auth(tenant_id,session,role="TENANT_MEMBER")
    cycle_id=await _cycle(tenant_id,year,conn)
    rows=await _fetch_request_rows(conn,
        "SELECT r.id,r.tenant_id,r.cycle_id,r.membership_id,r.requested_by_user_id,"
        "r.request_kind,r.policy_reference,r.status,r.requested_at,"
        "latest.event_kind AS latest_review_event "
        "FROM public.member_lifecycle_requests r "
        "LEFT JOIN LATERAL ("
        "SELECT e.event_kind FROM public.member_lifecycle_review_events e "
        "WHERE e.tenant_id=r.tenant_id AND e.request_id=r.id "
        "ORDER BY e.event_seq DESC LIMIT 1"
        ") latest ON TRUE "
        "WHERE r.tenant_id=$1 AND r.cycle_id=$2 AND r.membership_id IN ("
        "SELECT public.rls_user_membership_ids($3::uuid,$1::uuid)) "
        "ORDER BY r.requested_at DESC,r.id DESC LIMIT 101",
        tenant_id,cycle_id,UUID(session.user_id),
    )
    if len(rows)>LIMIT:
        raise HTTPException(status_code=503,detail="Mais de 100 pedidos; paginação pendente.")
    return LifecycleListResponse(
        tenant_id=str(tenant_id),year=year,scope="SELF_READ_ONLY",
        items=[await _format(row) for row in rows],
    )


@router.get("/admin-queue",response_model=LifecycleListResponse)
async def administrative_member_lifecycle_queue(
    tenant_id:UUID,year:int,
    session:AuthenticatedSession=Depends(get_current_session),
    conn=Depends(get_rls_db_connection),
):
    _auth(tenant_id,session,role="TENANT_ADMIN")
    cycle_id=await _cycle(tenant_id,year,conn)
    rows=await _fetch_request_rows(conn,
        "SELECT r.id,r.tenant_id,r.cycle_id,r.membership_id,r.requested_by_user_id,"
        "r.request_kind,r.policy_reference,r.status,r.requested_at,"
        "latest.event_kind AS latest_review_event "
        "FROM public.member_lifecycle_requests r "
        "LEFT JOIN LATERAL ("
        "SELECT e.event_kind FROM public.member_lifecycle_review_events e "
        "WHERE e.tenant_id=r.tenant_id AND e.request_id=r.id "
        "ORDER BY e.event_seq DESC LIMIT 1"
        ") latest ON TRUE "
        "WHERE r.tenant_id=$1 AND r.cycle_id=$2 "
        "ORDER BY r.requested_at DESC,r.id DESC LIMIT 101",
        tenant_id,cycle_id,
    )
    if len(rows)>LIMIT:
        raise HTTPException(status_code=503,detail="Mais de 100 pedidos; paginação pendente.")
    return LifecycleListResponse(
        tenant_id=str(tenant_id),year=year,scope="TENANT_ADMIN_READ_ONLY",
        items=[await _format(row) for row in rows],
    )


async def _submit(tenant_id:UUID,year:int,member_id:UUID,kind:str,
                  payload:LifecycleSandboxRequest,
                  session:AuthenticatedSession,conn):
    _test_sandbox()
    cycle_id=await _cycle(tenant_id,year,conn)
    # O PostgreSQL verifica em seguida: tenant, role, dono do vínculo,
    # situação ATIVA, sessão server-side, ciclo e idempotência.
    try:
        identifier=await conn.fetchval(
            "SELECT public.lifecycle_submit_request_sandbox("
            "$1::uuid,$2::uuid,$3::uuid,$4::varchar,$5::uuid,$6::varchar)",
            tenant_id,cycle_id,member_id,kind,
            payload.idempotency_key,payload.policy_reference,
        )
    except (asyncpg.UndefinedFunctionError,asyncpg.UndefinedTableError,
            asyncpg.InvalidSchemaNameError,
            asyncpg.InsufficientPrivilegeError) as exc:
        raise HTTPException(
            status_code=503,
            detail="Fluxo de homologação ainda não preparado neste banco.",
        ) from exc
    except asyncpg.PostgresError as exc:
        raise HTTPException(
            status_code=409,
            detail="Solicitação não aceita: contexto, política ou idempotência inválidos.",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="Serviço de homologação indisponível: operação não confirmada.",
        ) from exc
    if identifier is None:
        raise HTTPException(status_code=503,detail="Registro não confirmado.")
    try:
        row=await conn.fetchrow(
            "SELECT r.id,r.tenant_id,r.cycle_id,r.membership_id,r.requested_by_user_id,"
            "r.request_kind,r.policy_reference,r.status,r.requested_at,"
            "latest.event_kind AS latest_review_event "
            "FROM public.member_lifecycle_requests r "
            "LEFT JOIN LATERAL ("
            "SELECT e.event_kind FROM public.member_lifecycle_review_events e "
            "WHERE e.tenant_id=r.tenant_id AND e.request_id=r.id "
            "ORDER BY e.event_seq DESC LIMIT 1"
            ") latest ON TRUE "
            "WHERE r.tenant_id=$1 AND r.cycle_id=$2 AND r.id=$3",
            tenant_id,cycle_id,UUID(str(identifier)),
        )
    except (asyncpg.UndefinedTableError,asyncpg.InsufficientPrivilegeError) as exc:
        raise HTTPException(status_code=503,
            detail="Registro não consultável: migration 028/RLS indisponível.") from exc
    if row is None:
        raise HTTPException(status_code=503,detail="Solicitação não acessível após registro.")
    return await _format(row)


@router.post("/me/voluntary-exit",response_model=LifecycleRequestResponse)
async def request_voluntary_exit_sandbox(
    tenant_id:UUID,year:int,payload:LifecycleSandboxRequest,
    session:AuthenticatedSession=Depends(get_current_session),
    conn=Depends(get_rls_db_connection),
):
    _auth(tenant_id,session,role="TENANT_MEMBER")
    _test_sandbox()
    member=await conn.fetchrow(
        "SELECT id FROM public.memberships WHERE "
        "tenant_id=$1 AND user_id=$2 AND role='TENANT_MEMBER' "
        "AND status='ATIVA'",
        tenant_id,UUID(session.user_id),
    )
    if member is None:
        raise HTTPException(status_code=404,detail="Vínculo ativo não encontrado.")
    return await _submit(tenant_id,year,UUID(str(member["id"])),
                         "VOLUNTARY_EXIT",payload,session,conn)


@router.post("/members/{membership_id}/delinquency-review",
             response_model=LifecycleRequestResponse)
async def request_delinquency_review_sandbox(
    tenant_id:UUID,year:int,membership_id:UUID,payload:LifecycleSandboxRequest,
    session:AuthenticatedSession=Depends(get_current_session),
    conn=Depends(get_rls_db_connection),
):
    _auth(tenant_id,session,role="TENANT_ADMIN")
    _test_sandbox()
    return await _submit(tenant_id,year,membership_id,
                         "DELINQUENCY_REVIEW",payload,session,conn)
