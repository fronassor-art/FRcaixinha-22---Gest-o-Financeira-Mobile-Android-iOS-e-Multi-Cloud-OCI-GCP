"""FR Caixinha AI Studio — pedidos de ciclo em HOMOLOGAÇÃO.

Registra pedido de saída voluntária ou revisão administrativa sem mexer em
membership status, capital, multa, lucro, lançamento contábil ou Pix.
Sem a feature flag explícita, POST sempre falha fechado.
"""
from __future__ import annotations

import os
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
    sandbox_only: bool = True
    bank_reconciled: bool = False
    financial_effect_applied: bool = False
    member_status_changed: bool = False
    profit_rights_modified: bool = False
    payment_authorized: bool = False


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
    )


@router.get("/me",response_model=LifecycleListResponse)
async def my_member_lifecycle_requests(
    tenant_id:UUID,year:int,
    session:AuthenticatedSession=Depends(get_current_session),
    conn=Depends(get_rls_db_connection),
):
    _auth(tenant_id,session,role="TENANT_MEMBER")
    cycle_id=await _cycle(tenant_id,year,conn)
    rows=await conn.fetch(
        "SELECT id,tenant_id,cycle_id,membership_id,requested_by_user_id,"
        "request_kind,policy_reference,status,requested_at "
        "FROM public.member_lifecycle_requests "
        "WHERE tenant_id=$1 AND cycle_id=$2 AND requested_by_user_id=$3 "
        "ORDER BY requested_at DESC,id DESC LIMIT 101",
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
    rows=await conn.fetch(
        "SELECT id,tenant_id,cycle_id,membership_id,requested_by_user_id,"
        "request_kind,policy_reference,status,requested_at "
        "FROM public.member_lifecycle_requests "
        "WHERE tenant_id=$1 AND cycle_id=$2 "
        "ORDER BY requested_at DESC,id DESC LIMIT 101",
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
    except Exception as exc:
        # Nunca expor detalhes da função de segurança do banco.
        raise HTTPException(
            status_code=409,
            detail="Solicitação não aceita: contexto, política ou idempotência inválidos.",
        ) from exc
    if identifier is None:
        raise HTTPException(status_code=503,detail="Registro não confirmado.")
    row=await conn.fetchrow(
        "SELECT id,tenant_id,cycle_id,membership_id,requested_by_user_id,"
        "request_kind,policy_reference,status,requested_at "
        "FROM public.member_lifecycle_requests "
        "WHERE tenant_id=$1 AND cycle_id=$2 AND id=$3",
        tenant_id,cycle_id,UUID(str(identifier)),
    )
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
