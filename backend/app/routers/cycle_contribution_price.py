"""AI Studio M20400 — per-tenant, per-cycle contribution policy; signed DB session.

Updating the policy before billing is allowed; existing obligations are NEVER
repriced by this route. Those create a pending review audit record instead.
"""
from __future__ import annotations
import os
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
    if row["amount_cents"] is None or row["amount_cents"]<15000:
        raise HTTPException(409,
            "Política de desenvolvimento incompatível com o mínimo contratual. "
            "Regularização auditada necessária no mesmo banco.")
    if (row["pending_requested_cents"] is not None
            and row["pending_requested_cents"]<15000):
        raise HTTPException(409,"Revisão antiga incompatível com o mínimo contratual.")
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


class CycleOpeningCommitRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    year:int=Field(strict=True,ge=2027,le=2100)
    amount_cents:int=Field(strict=True,ge=15000,le=1000000)
    reason:str=Field(min_length=12,max_length=500)
    idempotency_key:UUID


class CycleOpeningPreviewRequest(BaseModel):
    """An admin must choose the quota amount explicitly for their next cycle."""
    model_config=ConfigDict(extra="forbid")
    year: int=Field(strict=True,ge=2027,le=2100)
    amount_cents: int=Field(strict=True,ge=15000,le=1000000)
    reason: str=Field(min_length=12,max_length=500)


@router.post("/opening-preview")
async def opening_preview(
    tenant_id: UUID,payload: CycleOpeningPreviewRequest,
    session: AuthenticatedSession=Depends(get_current_session),
    conn=Depends(get_rls_db_connection),
):
    """Safe, read-only preparation; not yet an authorized cycle creation."""
    from datetime import date
    _admin(tenant_id,session)
    if len(payload.reason.strip())<12:
        raise HTTPException(422,"Justificativa de abertura insuficiente.")
    tenant=await conn.fetchrow(
        "SELECT id,status,admin_user_id FROM public.tenants WHERE id=$1",tenant_id,
    )
    if tenant is None or str(tenant["admin_user_id"])!=session.user_id:
        raise HTTPException(403,"Responsável administrativo não confirmado.")
    active=await conn.fetchval(
        "SELECT count(*) FROM public.memberships "
        "WHERE tenant_id=$1 AND user_id=$2 "
        "AND role='TENANT_ADMIN' AND status='ATIVA'",
        tenant_id,UUID(session.user_id),
    )
    if active!=1:
        raise HTTPException(403,"Vínculo administrativo ativo não confirmado.")
    cycles=await conn.fetch(
        "SELECT year,status FROM public.cycles WHERE tenant_id=$1 "
        "ORDER BY year DESC LIMIT 200",tenant_id,
    )
    reasons=[]
    if tenant["status"]!="ATIVO":
        reasons.append("TENANT_INACTIVE")
    if any(c["year"]==payload.year for c in cycles):
        reasons.append("YEAR_ALREADY_EXISTS")
    if any(c["status"]!="LIQUIDADO" for c in cycles):
        reasons.append("PREVIOUS_CYCLE_NOT_CLOSED")
    if date(payload.year,1,1)<=date.today():
        reasons.append("YEAR_START_NOT_FUTURE")
    return {
        "contract":"AI_STUDIO_M20800_CYCLE_OPENING_PREVIEW_V1",
        "source":"POSTGRESQL_RLS_AUTHENTICATED_ADMIN",
        "tenant_id":str(tenant_id),"year":payload.year,
        "start_date":date(payload.year,1,1).isoformat(),
        "end_date":date(payload.year,12,31).isoformat(),
        "amount_cents":payload.amount_cents,
        "minimum_amount_cents":15000,
        "price_explicitly_entered":True,
        "historical_obligations_unchanged":True,
        "blocked_reasons":reasons,
        "preconditions_satisfied":not reasons,
        "cycle_creation_enabled":bool(not reasons and
            os.getenv('FR_FINANCE_CYCLE_OPEN_ENABLED')=='YES' and
            await conn.fetchval("SELECT to_regprocedure('public.cycle_open_create(text,uuid,integer,bigint,text,uuid)') IS NOT NULL") is True),
        "financial_effect":False,
        "reason_recorded":False,
    }




@router.post("/opening")
async def commit_cycle_opening(
    tenant_id:UUID,payload:CycleOpeningCommitRequest,request:Request,
    session:AuthenticatedSession=Depends(get_current_session),
    conn=Depends(get_rls_db_connection),
):
    """Authorized cycle creation uses PG security-definer M044, never seeds a price."""
    _admin(tenant_id,session)
    if os.getenv('FR_FINANCE_CYCLE_OPEN_ENABLED')!='YES':
        raise HTTPException(503,"Abertura de ciclo indisponível até homologação e autorização operacional.")
    if len(payload.reason.strip())<12:
        raise HTTPException(422,"Justificativa de abertura inválida.")
    try:
        row=await conn.fetchrow(
            "SELECT * FROM public.cycle_open_create("
            "$1::text,$2::uuid,$3::integer,$4::bigint,$5::text,$6::uuid)",
            bearer_token(request),tenant_id,payload.year,payload.amount_cents,
            payload.reason.strip(),payload.idempotency_key,
        )
    except asyncpg.PostgresError as exc:
        if exc.sqlstate=='42501':
            raise HTTPException(403,"Abertura de ciclo não autorizada.") from None
        if exc.sqlstate in ('23505','22023','P0001'):
            raise HTTPException(409,"Abertura recusada pelas regras do contrato e do ciclo.") from None
        if exc.sqlstate in ('42883','42P01'):
            raise HTTPException(503,"Instalação M044 de abertura de ciclos ainda não homologada.") from None
        raise HTTPException(503,"Abertura não confirmada no PostgreSQL.") from None
    if (not row or row['opening_status'] not in ('CREATED','REPLAY')
            or row['opened_year']!=payload.year
            or row['opened_amount_cents']!=payload.amount_cents):
        raise HTTPException(503,"Abertura não confirmada no PostgreSQL.")
    return {
        'contract':'FR_FINANCE_M37423_CYCLE_OPENING_V1',
        'source':'POSTGRESQL_AUTHENTICATED_ADMIN_M044',
        'tenant_id':str(tenant_id),
        'opened_cycle_id':str(row['opened_cycle_id']),
        'opened_policy_id':str(row['opened_policy_id']),
        'year':row['opened_year'],
        'amount_cents':row['opened_amount_cents'],
        'opening_status':row['opening_status'],
        'opening_audit_persisted':True,
        'existing_contributions_repriced':False,
        'payments_executed':False,
    }


# M22400: legacy contribution review; read-only, admin-specific and no PII.
# Historical R$100 registered obligations are not silently changed.
def _money_cents(value) -> int:
    from decimal import Decimal
    if type(value) is not Decimal or not value.is_finite():
        raise HTTPException(503,"Histórico com valor não confiável.")
    x=value*Decimal(100)
    if x!=x.to_integral_value() or x<0 or x>Decimal(999999999999):
        raise HTTPException(503,"Histórico com centavos inconsistentes.")
    return int(x)


@router.get("/legacy-review/{cycle_id}")
async def legacy_contributions_review(
    tenant_id: UUID, cycle_id: UUID,
    session: AuthenticatedSession=Depends(get_current_session),
    conn=Depends(get_rls_db_connection),
):
    """Read-only grouping: NEVER changes obligations or implies bank proof."""
    _admin(tenant_id,session)
    cycle=await conn.fetchrow(
        "SELECT id,year FROM public.cycles "
        "WHERE id=$1 AND tenant_id=$2",cycle_id,tenant_id)
    if cycle is None:
        raise HTTPException(404,"Ciclo da caixinha não encontrado.")
    records=await conn.fetch(
        "SELECT c.amount_due,c.amount_paid,c.payment_status,"
        "COUNT(*)::integer AS registered_count "
        "FROM public.contributions c "
        "WHERE c.tenant_id=$1 AND c.cycle_id=$2 AND c.amount_due<150.00 "
        "GROUP BY c.amount_due,c.amount_paid,c.payment_status "
        "ORDER BY c.amount_due,c.amount_paid,c.payment_status LIMIT 201",
        tenant_id,cycle_id,
    )
    if len(records)>200:
        raise HTTPException(503,"Histórico extenso requer auditoria paginada.")
    count=due=registered_paid=0
    groups=[]
    for row in records:
        amount=_money_cents(row["amount_due"])
        paid=_money_cents(row["amount_paid"])
        n=row["registered_count"]
        state=row["payment_status"]
        if (type(n) is not int or not 1<=n<=1000000
                or not 0<amount<15000 or paid>amount
                or state not in ("QUITADA","PARCIAL","PENDENTE")):
            raise HTTPException(503,"Dados legados inconsistentes.")
        count+=n
        due+=amount*n
        registered_paid+=paid*n
        if due>999999999999 or registered_paid>due:
            raise HTTPException(503,"Totais legados inconsistentes.")
        groups.append({
            "registered_amount_cents":amount,
            "registered_paid_cents":paid,
            "recorded_status":state,
            "registered_contributions":n,
            "bank_settlement_verified":False,
        })
    return {
        "contract":"AI_STUDIO_M22400_LEGACY_CONTRIBUTION_REVIEW_V1",
        "source":"POSTGRESQL_RLS_REGISTERED_HISTORY_ONLY",
        "tenant_id":str(tenant_id),"cycle_id":str(cycle_id),
        "cycle_year":cycle["year"],"minimum_new_quota_cents":15000,
        "legacy_registered_contributions":count,
        "legacy_due_cents":due,
        "legacy_paid_recorded_cents":registered_paid,
        "legacy_open_recorded_cents":due-registered_paid,
        "groups":groups,
        "historical_obligations_changed":False,
        "price_adjustment_authorized":False,
        "bank_reconciled":False,
        "real_payment_enabled":False,
        "requires_administrator_review":bool(count),
    }
