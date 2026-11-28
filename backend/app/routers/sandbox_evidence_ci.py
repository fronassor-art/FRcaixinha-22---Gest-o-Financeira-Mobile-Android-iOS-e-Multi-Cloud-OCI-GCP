"""M1881-M2040: leitura de EVIDENCIAS SINTETICAS em PostgreSQL CI descartavel.

Router só deve ser registrado sob opt-in da CI. Não confirma pagamentos,
não grava, não recebe webhooks, não pode ser usado em produção ou Termux 5433.
A fonte é sempre SYNTHETIC_FIXTURE_ONLY, NUNCA banco/PSP.
"""
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from ..dependencies import (
    AuthenticatedSession, get_current_session, require_tenant_access,
)
from ..database import get_rls_db_connection

router = APIRouter(
    prefix="/tenants/{tenant_id}/sandbox-evidence",
    tags=["Laboratório CI — eventos sintéticos sem efeito financeiro"],
)
MAX_PAGE = 100


class SandboxEvidenceRow(BaseModel):
    event_id: UUID
    event_seq: int
    membership_id: UUID
    provider_payment_id: str
    collector_id: str
    external_reference: str
    event_kind: str
    amount_cents: int
    recorded_at: datetime
    source: str = "SYNTHETIC_FIXTURE_ONLY"
    bank_reconciled: bool = False
    financial_effect_applied: bool = False


class SandboxEvidencePage(BaseModel):
    tenant_id: UUID
    membership_id: UUID
    scope: str
    events: list[SandboxEvidenceRow]
    page_size: int
    has_more: bool
    next_before_seq: int | None
    synthetic_only: bool = True
    bank_reconciled: bool = False
    financial_effect_applied: bool = False
    real_payments_enabled: bool = False
    closing_authorized: bool = False
    payout_authorized: bool = False


async def _ensure_ci_db(conn):
    # Segunda barreira mesmo se o router for registrado indevidamente.
    ok = await conn.fetchval(
        "SELECT current_database()='frcaixinha_ci' AND "
        "to_regclass('public.mp_sandbox_evidence_events') IS NOT NULL"
    )
    if ok is not True:
        raise HTTPException(503, detail="Laboratório de eventos indisponível.")


async def _read_page(*, tenant_id: UUID, membership_id: UUID,
                     role: str, page_size: int, before_seq: int | None, conn):
    await _ensure_ci_db(conn)
    rows = await conn.fetch(
        "SELECT event_id,event_seq,membership_id,provider_payment_id,"
        "collector_id,external_reference,event_kind,amount_cents,recorded_at "
        "FROM public.mp_sandbox_evidence_events "
        "WHERE tenant_id=$1 AND membership_id=$2 "
        "AND ($3::bigint IS NULL OR event_seq<$3::bigint) "
        "ORDER BY event_seq DESC LIMIT $4",
        tenant_id, membership_id, before_seq, page_size+1,
    )
    # O SQL jamais usa LIMIT exato e depois finge que o histórico está completo.
    has_more = len(rows)>page_size
    visible = rows[:page_size]
    events = [SandboxEvidenceRow(**dict(row)) for row in visible]
    return SandboxEvidencePage(
        tenant_id=tenant_id, membership_id=membership_id,
        scope=role, events=events, page_size=page_size,
        has_more=has_more,
        next_before_seq=int(visible[-1]["event_seq"]) if has_more else None,
    )


@router.get("/me", response_model=SandboxEvidencePage)
async def read_my_sandbox_evidence(
    tenant_id: UUID,
    page_size: int = Query(default=25, ge=1, le=MAX_PAGE),
    before_seq: int | None = Query(default=None, ge=1),
    session: AuthenticatedSession = Depends(get_current_session),
    conn=Depends(get_rls_db_connection),
):
    require_tenant_access(str(tenant_id),session)
    if session.role != "TENANT_MEMBER":
        raise HTTPException(403, detail="Consulta individual exclusiva do membro.")
    await _ensure_ci_db(conn)
    member = await conn.fetchrow(
        "SELECT id FROM public.memberships "
        "WHERE tenant_id=$1 AND user_id=$2 AND role='TENANT_MEMBER' "
        "AND status='ATIVA' LIMIT 1",
        tenant_id, UUID(session.user_id),
    )
    if member is None:
        raise HTTPException(404, detail="Vínculo do membro indisponível.")
    return await _read_page(
        tenant_id=tenant_id, membership_id=UUID(str(member["id"])),
        role="SELF_READ_ONLY_SYNTHETIC", page_size=page_size,
        before_seq=before_seq, conn=conn,
    )


@router.get("/members/{membership_id}", response_model=SandboxEvidencePage)
async def read_admin_sandbox_evidence(
    tenant_id: UUID, membership_id: UUID,
    page_size: int = Query(default=25, ge=1, le=MAX_PAGE),
    before_seq: int | None = Query(default=None, ge=1),
    session: AuthenticatedSession = Depends(get_current_session),
    conn=Depends(get_rls_db_connection),
):
    require_tenant_access(str(tenant_id),session)
    if session.role != "TENANT_ADMIN":
        raise HTTPException(403, detail="Consulta administrativa exclusiva.")
    await _ensure_ci_db(conn)
    member = await conn.fetchrow(
        "SELECT id FROM public.memberships WHERE id=$1 AND tenant_id=$2 "
        "AND role='TENANT_MEMBER' AND status IN ('ATIVA','SUSPENSA')",
        membership_id,tenant_id,
    )
    if member is None:
        raise HTTPException(404, detail="Vínculo inacessível.")
    return await _read_page(
        tenant_id=tenant_id, membership_id=membership_id,
        role="TENANT_ADMIN_READ_ONLY_SYNTHETIC",
        page_size=page_size, before_seq=before_seq, conn=conn,
    )
