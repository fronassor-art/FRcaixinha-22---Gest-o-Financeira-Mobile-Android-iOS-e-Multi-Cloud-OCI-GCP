"""FR Caixinha AI Studio — leitura de risco contratual com dados registrados.

A cláusula 6.5 pode ser codificada, testada e demonstrada antes da fase
jurídica. O histórico cadastral sozinho, sem prova de Pix/banco, NÃO ativa
a penalidade, não retém capital nem autoriza fechamento ou rateio.

Esta API é de consulta: zero INSERT/UPDATE/DELETE, sempre sessão + RLS.
"""
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query

from ..dependencies import (
    AuthenticatedSession, get_current_session, require_tenant_access,
)
from ..database import get_rls_db_connection
from ..member_cycle_rules import MonthlyDueProof, first_three_unpaid_trigger
from ..member_risk_review_signals import registered_review_signals
from ..models import MemberCycleRiskPreviewResponse

router = APIRouter(
    prefix="/tenants/{tenant_id}/cycles/{year}/member-risk",
    tags=["Risco contratual e ciclo — prévia segura"],
)
LIMIT = 120
BELEM = ZoneInfo("America/Belem")


def _int_cents(value) -> int:
    if not isinstance(value, Decimal) or not value.is_finite():
        raise HTTPException(status_code=503, detail="Valores registrados inconsistentes.")
    cents = value * Decimal(100)
    if cents != cents.to_integral_value() or cents < 0 or cents > 999999999999:
        raise HTTPException(status_code=503, detail="Valores registrados inconsistentes.")
    return int(cents)


def _check_access(tenant_id: UUID, session: AuthenticatedSession, *,
                  only_role: str | None = None) -> None:
    require_tenant_access(str(tenant_id), session)
    if only_role is not None and session.role != only_role:
        raise HTTPException(status_code=403, detail="Perfil não autorizado para esta prévia.")
    if session.role not in ("TENANT_ADMIN", "TENANT_MEMBER"):
        raise HTTPException(status_code=403, detail="Perfil inválido.")


async def _load_preview(
    tenant_id: UUID, year: int, member_id: UUID, *,
    as_of: date, session: AuthenticatedSession, conn,
) -> MemberCycleRiskPreviewResponse:
    _check_access(tenant_id, session)
    if type(year) is not int or not 2020 <= year <= 2100:
        raise HTTPException(status_code=422, detail="Ano fora do intervalo permitido.")
    if type(as_of) is not date:
        raise HTTPException(status_code=422, detail="Data de referência inválida.")
    cycle = await conn.fetchrow(
        "SELECT c.id, c.start_date, c.end_date, t.is_owner_box "
        "FROM public.cycles c JOIN public.tenants t ON t.id=c.tenant_id "
        "WHERE c.tenant_id=$1 AND c.year=$2 AND t.id=$1",
        tenant_id, year,
    )
    if cycle is None:
        raise HTTPException(status_code=404, detail="Ciclo não encontrado.")
    # Nunca aceitar 'admin' do cliente como identidade; sempre sessão validada.
    if session.role == "TENANT_MEMBER":
        found = await conn.fetchrow(
            "SELECT m.id FROM public.memberships m "
            "WHERE m.id=$1 AND m.tenant_id=$2 AND m.user_id=$3 "
            "AND m.role='TENANT_MEMBER' AND m.status='ATIVA'",
            member_id, tenant_id, UUID(session.user_id),
        )
    else:
        found = await conn.fetchrow(
            "SELECT m.id FROM public.memberships m "
            "WHERE m.id=$1 AND m.tenant_id=$2 AND m.role='TENANT_MEMBER'",
            member_id, tenant_id,
        )
    if found is None:
        raise HTTPException(status_code=404, detail="Vínculo não encontrado.")

    rows = await conn.fetch(
        "SELECT c.id, c.competence, c.due_date, c.amount_due, "
        "c.amount_paid, c.payment_status, c.paid_at "
        "FROM public.contributions c "
        "WHERE c.tenant_id=$1 AND c.cycle_id=$2 AND c.membership_id=$3 "
        "ORDER BY c.competence ASC LIMIT 121",
        tenant_id, cycle["id"], member_id,
    )
    if len(rows) > LIMIT:
        raise HTTPException(status_code=503, detail="Histórico excede limite da prévia.")
    proofs = []
    due_total = paid_total = 0
    oldest_overdue = 0
    for row in rows:
        if (not isinstance(row["competence"], str)
                or not row["competence"].startswith(f"{year:04d}-")):
            raise HTTPException(status_code=503, detail="Competência fora do ciclo.")
        due_cents = _int_cents(row["amount_due"])
        paid_cents = _int_cents(row["amount_paid"])
        if due_cents == 0 or paid_cents > due_cents:
            raise HTTPException(status_code=503, detail="Saldo inconsistente.")
        status = row["payment_status"]
        paid_at = row["paid_at"]
        if (status == "QUITADA" and
                (paid_cents != due_cents or paid_at is None)):
            raise HTTPException(status_code=503, detail="Quitação sem comprovação cadastral.")
        if status != "QUITADA" and paid_cents == due_cents:
            raise HTTPException(status_code=503, detail="Quitação sem estado consistente.")
        if status not in ("QUITADA", "PARCIAL", "PENDENTE"):
            raise HTTPException(status_code=503, detail="Estado não homologado.")
        due_total += due_cents
        paid_total += paid_cents
        # Nome 'fully_settled_on' expressa somente a data REGISTRADA.
        # A verificação da origem bancária ocorrerá em estágio próprio.
        settled = paid_at.astimezone(BELEM).date() if status == "QUITADA" else None
        try:
            proof = MonthlyDueProof(
                tenant_id, member_id, row["competence"], row["due_date"],
                due_cents, paid_cents, settled, f"DB-REGISTERED-{row['id']}"
            )
        except ValueError as exc:
            raise HTTPException(status_code=503, detail="Histórico inconsistente.") from exc
        proofs.append(proof)
        if row["due_date"] < as_of and (settled is None or settled > as_of):
            oldest_overdue = max(oldest_overdue, (as_of-row["due_date"]).days)
    # Simulação CONTRATUAL: sem atestado independente, não determinar
    # exclusão de lucro, bloqueio operacional ou restituição.
    try:
        potential = first_three_unpaid_trigger(
            tenant_id, member_id, tuple(proofs), as_of,
        )
    except ValueError as exc:
        raise HTTPException(status_code=503, detail="Sequência histórica inconsistente.") from exc
    streak = 0
    last_index = None
    for row in reversed(proofs):
        if row.due_on >= as_of:
            continue
        idx = int(row.competence[:4])*12 + int(row.competence[5:])-1
        if last_index is not None and idx != last_index-1:
            break
        if row.fully_settled_on is not None and row.fully_settled_on <= as_of:
            break
        streak += 1
        last_index = idx
    try:
        signals = registered_review_signals(
            oldest_days=oldest_overdue,
            three_competence_trigger=potential,
            as_of=as_of,
        )
    except ValueError as exc:
        raise HTTPException(status_code=503, detail="Sinais de revisão inconsistentes.") from exc
    return MemberCycleRiskPreviewResponse(
        tenant_id=str(tenant_id), cycle_year=year,
        membership_id=str(member_id), as_of=as_of,
        source="POSTGRESQL_RLS_REGISTERED_NOT_BANK_RECONCILED",
        scope=("SELF_READ_ONLY" if session.role == "TENANT_MEMBER"
               else "TENANT_ADMIN_READ_ONLY"),
        owner_box=bool(cycle["is_owner_box"]),
        registered_contributions_count=len(rows),
        registered_due_cents=due_total, registered_paid_cents=paid_total,
        registered_open_cents=due_total-paid_total,
        longest_registered_overdue_days=oldest_overdue,
        currently_unpaid_consecutive_months=streak,
        potential_three_unpaid_trigger_date=potential,
        registered_ninety_day_review_candidate=signals.registered_ninety_day_review_candidate,
        registered_three_competence_review_candidate=signals.registered_three_competence_review_candidate,
        requires_independent_review=signals.requires_independent_review,
        membership_profit_eligible=None,
        reconciled_principal_cents=None,
        capital_days_weight=None,
        contractual_effect_applied=False,
        real_financial_operations_enabled=False,
        financial_closing_authorized=False,
        bank_reconciled=False,
        result_status="HISTORY_AND_PROOF_NOT_ATTESTED",
    )


@router.get("/me", response_model=MemberCycleRiskPreviewResponse)
async def get_my_cycle_risk_preview(
    tenant_id: UUID, year: int, as_of: date | None = Query(default=None),
    session: AuthenticatedSession = Depends(get_current_session),
    conn = Depends(get_rls_db_connection),
):
    _check_access(tenant_id, session, only_role="TENANT_MEMBER")
    mid = await conn.fetchrow(
        "SELECT m.id FROM public.memberships m "
        "WHERE m.tenant_id=$1 AND m.user_id=$2 "
        "AND m.role='TENANT_MEMBER' AND m.status='ATIVA'",
        tenant_id, UUID(session.user_id),
    )
    if mid is None:
        raise HTTPException(status_code=404, detail="Vínculo não encontrado.")
    return await _load_preview(
        tenant_id, year, UUID(str(mid["id"])), 
        as_of=as_of or datetime.now(BELEM).date(), session=session, conn=conn,
    )


@router.get("/members/{member_id}", response_model=MemberCycleRiskPreviewResponse)
async def get_admin_member_cycle_risk_preview(
    tenant_id: UUID, year: int, member_id: UUID,
    as_of: date | None = Query(default=None),
    session: AuthenticatedSession = Depends(get_current_session),
    conn = Depends(get_rls_db_connection),
):
    _check_access(tenant_id, session, only_role="TENANT_ADMIN")
    return await _load_preview(
        tenant_id, year, member_id,
        as_of=as_of or datetime.now(BELEM).date(), session=session, conn=conn,
    )
