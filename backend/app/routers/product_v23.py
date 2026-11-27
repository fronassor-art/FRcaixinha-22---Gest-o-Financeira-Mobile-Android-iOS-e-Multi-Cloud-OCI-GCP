"""V2.3 transactional API; default runtime has no authorized provider.
CI overrides only in its isolated test application, never in production.
"""
from datetime import date
from typing import Literal
from uuid import UUID
import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from ..dependencies import bearer_token

router=APIRouter(prefix="/tenants/{tenant_id}/v23",tags=["FR Finance V2.3"])

async def unreleased_transaction():
    raise HTTPException(503,"Integração V2.3 aguardando autorização transacional e migração revisada.")

class Strict(BaseModel):
    model_config=ConfigDict(extra="forbid")

class CycleInput(Strict):
    request_id: UUID
    start: date
    first_due: date
    last_due: date
    closing: date
    quota_cents: int=Field(strict=True,gt=0,le=100000000)
    admin_bps: int=Field(strict=True,ge=0,le=10000)
    late_days: int=Field(strict=True,ge=1,le=3650)
    late_competences: int=Field(strict=True,ge=1,le=120)
    mode: Literal["MANUAL","MERCADO_PAGO","HYBRID"]
    document_id: UUID

class AdmissionInput(Strict):
    membership_id: UUID
    joined: date
    quotas: int=Field(strict=True,ge=1,le=400)

class ReceiptInput(Strict):
    request_id: UUID
    contribution_id: UUID
    cents: int=Field(strict=True,gt=0,le=100000000)
    method: Literal["DINHEIRO","PIX_EXTERNO","TRANSFERENCIA","DEPOSITO"]
    occurred: date
    reference: str=Field(min_length=3,max_length=100)
    evidence_ref: str=Field(min_length=3,max_length=160)

class ReviewInput(Strict):
    request_id: UUID
    occurred: date
    evidence_ref: str=Field(min_length=3,max_length=160)

async def call(conn,query,*args):
    try:
        result=await conn.fetchrow(query,*args)
    except asyncpg.PostgresError as exc:
        if exc.sqlstate=="42501": raise HTTPException(403,"Operação fora do escopo autorizado.") from None
        if exc.sqlstate in ("23505","23514","P0001"): raise HTTPException(409,"Conflito ou pendência financeira.") from None
        if exc.sqlstate=="22023": raise HTTPException(422,"Dados incompatíveis com a política do ciclo.") from None
        raise HTTPException(503,"Integração transacional indisponível.") from None
    if result is None: raise HTTPException(503,"Resultado transacional não confirmado.")
    return dict(result)

@router.get("/capabilities")
async def capabilities(tenant_id:UUID):
    return {"contract":"FR_FINANCE_V23_TRANSACTION_V1","available":False,"manual_receipts_enabled":False,
            "cycle_writes_enabled":False,"real_payments_enabled":False,"production_authorized":False}

@router.post("/cycles")
async def create_cycle(tenant_id:UUID,p:CycleInput,request:Request,conn=Depends(unreleased_transaction)):
    return await call(conn,"SELECT public.fr_v23_cycle($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13) AS cycle_id",
        bearer_token(request),tenant_id,p.request_id,p.start,p.first_due,p.last_due,p.closing,p.quota_cents,p.admin_bps,p.late_days,p.late_competences,p.mode,p.document_id)

@router.post("/cycles/{cycle_id}/admissions")
async def admit(tenant_id:UUID,cycle_id:UUID,p:AdmissionInput,request:Request,conn=Depends(unreleased_transaction)):
    return await call(conn,"SELECT public.fr_v23_admit($1,$2,$3,$4,$5,$6) AS obligations",
        bearer_token(request),tenant_id,cycle_id,p.membership_id,p.joined,p.quotas)

@router.post("/manual-receipts")
async def record(tenant_id:UUID,p:ReceiptInput,request:Request,conn=Depends(unreleased_transaction)):
    return await call(conn,"SELECT public.fr_v23_record($1,$2,$3,$4,$5,$6,$7,$8,$9) AS receipt_id",
        bearer_token(request),tenant_id,p.request_id,p.contribution_id,p.cents,p.method,p.occurred,p.reference,p.evidence_ref)

@router.post("/manual-receipts/{receipt_id}/{action}")
async def review(tenant_id:UUID,receipt_id:UUID,action:Literal["CONFIRM","REVERSE","CONTEST"],p:ReviewInput,request:Request,conn=Depends(unreleased_transaction)):
    return await call(conn,"SELECT public.fr_v23_review($1,$2,$3,$4,$5,$6,$7) AS state",
        bearer_token(request),tenant_id,receipt_id,action,p.request_id,p.occurred,p.evidence_ref)

@router.get("/manual-receipts/{receipt_id}")
async def read_receipt(tenant_id:UUID,receipt_id:UUID,request:Request,conn=Depends(unreleased_transaction)):
    return await call(conn,"SELECT * FROM public.fr_v23_receipt($1,$2,$3)",bearer_token(request),tenant_id,receipt_id)
