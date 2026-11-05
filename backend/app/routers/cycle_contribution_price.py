"""AI Studio M20400 — per-tenant, per-cycle contribution policy; signed DB session.

Updating the policy before billing is allowed; existing obligations are NEVER
repriced by this route. Those create a pending review audit record instead.
"""
from __future__ import annotations
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, ConfigDict

from ..database import get_rls_db_connection
from ..dependencies import (
    AuthenticatedSession, bearer_token, get_current_session, require_tenant_access,
)

router=APIRouter(prefix="/tenants/{tenant_id}/cycle-contribution-price",
                 tags=["Política de cotas por ciclo e caixinha"])
CONTRACT="AI_STUDIO_M20400_CYCLE_PRICE_REVIEW_V1"


class PriceChange(BaseModel):
    model_config=ConfigDict(extra="forbid")
    cycle_id: UUID
    amount_cents: int=Field(strict=True,ge=15000,le=1000000)
    reason: str=Field(min_length=12,max_length=500)
    idempotency_key: UUID


def _admin(tenant_id: UUID,session: AuthenticatedSession)->None:
    require_tenant_access(str(tenant_id),session)
    if session.role!="TENANT_ADMIN" or session.tenant_id!=str(tenant_id):
        raise HTTPException(403,"Somente o administrador da própria caixinha pode alterar a política.")


def _db_error(exc: asyncpg.PostgresError):
    if exc.sqlstate=="42501":
        raise HTTPException(403,"Autorização de administrador não verificada.") from None
    if exc.sqlstate in ("P0001","23505"):
        raise HTTPException(409,"Política exige revisão: a alteração não foi efetivada ou está pendente.") from None
    if exc.sqlstate in ("42883","42P01"):
        raise HTTPException(503,"Migração local 042 ainda não disponível.") from None
    raise exc


@router.get("")
async def status(
    tenant_id: UUID,request: Request,
    session: AuthenticatedSession=Depends(get_current_session),
    conn=Depends(get_rls_db_connection),
):
    _admin(tenant_id,session)
    try:
        row=await conn.fetchrow(
          "SELECT * FROM public.cycle_price_status($1::text,$2::uuid)",
          bearer_token(request),tenant_id)
    except asyncpg.PostgresError as exc:
        _db_error(exc)
    if row is None:
        raise HTTPException(404,"Ciclo aberto com política ativa não encontrado.")
    return {
      "contract":CONTRACT,
      "source":"POSTGRESQL_VERIFIED_SESSION",
      "tenant_id":str(row["tenant_id"]),
      "cycle_id":str(row["cycle_id"]),
      "cycle_year":row["cycle_year"],
      "start_date":row["start_date"].isoformat(),
      "end_date":row["end_date"].isoformat(),
      "amount_cents":row["amount_cents"],
      "minimum_contribution_cents":15000,
      "legacy_below_minimum":row["amount_cents"]<15000,
      "policy_version":row["policy_version"],
      "registered_contributions":row["registered_contributions"],
      "can_edit":row["can_edit"],
      "blocked_reason":row["blocked_reason"],
      "pending_requested_cents":row["pending_requested_cents"],
      "real_payments_enabled":False,
    }


@router.post("")
async def change(
    tenant_id: UUID,payload:PriceChange,request:Request,
    session:AuthenticatedSession=Depends(get_current_session),
    conn=Depends(get_rls_db_connection),
):
    _admin(tenant_id,session)
    try:
        row=await conn.fetchrow(
          "SELECT * FROM public.cycle_price_change("
          "$1::text,$2::uuid,$3::uuid,$4::bigint,$5::text,$6::uuid)",
          bearer_token(request),tenant_id,payload.cycle_id,
          payload.amount_cents,payload.reason,payload.idempotency_key,
        )
    except asyncpg.PostgresError as exc:
        _db_error(exc)
    if not row:
        raise HTTPException(503,"Alteração não confirmada no banco.")
    return {
      "contract":CONTRACT,
      "source":"POSTGRESQL_VERIFIED_SESSION",
      "change_status":row["change_status"],
      "amount_cents":row["amount_cents"],
      "request_id":str(row["request_id"]),
      "real_payments_enabled":False,
      "existing_contributions_repriced":False,
    }
