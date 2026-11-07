"""M1401 AI Studio — obrigações cadastrais por membro (RLS + SOMENTE SELECT).

A prévia não é boleto, cobrança, prova de pagamento ou cálculo de restituição.
Parcela de empréstimo SOLICITADO/APROVADO/RESERVADO nunca é dívida.
"""
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from ..database import get_rls_db_connection
from ..dependencies import (
    AuthenticatedSession, get_current_session, require_tenant_access,
)
from ..member_obligation_audit import (
    ContributionRecord, LoanRecord, InstallmentRecord,
    audit_member_obligations, MAX_ROWS,
)

router = APIRouter(
    prefix="/tenants/{tenant_id}/cycles/{year}/member-obligations",
    tags=["Prévia de obrigações por membro — registrada, não conciliada"],
)
BELEM = ZoneInfo("America/Belem")


class MemberObligationPreviewResponse(BaseModel):
    tenant_id: str
    cycle_id: str
    membership_id: str
    cycle_year: int
    as_of: date
    source: str = "POSTGRESQL_RLS_REGISTERED_NOT_BANK_RECONCILED"
    scope: str
    contribution_count: int
    contribution_due_cents: int
    contribution_paid_recorded_cents: int
    contribution_open_cents: int
    contribution_now_open_cents: int
    contribution_overdue_count: int
    loan_proposal_count: int
    loan_active_count: int
    loan_closed_count: int
    loan_unscheduled_count: int
    installment_count: int
    loan_now_principal_cents: int
    loan_now_interest_cents: int
    loan_future_principal_cents: int
    loan_future_interest_cents: int
    loan_overdue_installment_count: int
    registered_now_open_cents: int
    status: str
    bank_reconciled: bool = False
    capital_reconciled_cents: None = None
    net_exit_restitution_cents: None = None
    accrued_mora_cents: None = None
    accrued_fine_cents: None = None
    profit_eligible: None = None
    sanction_applied: bool = False
    closing_authorized: bool = False
    payout_authorized: bool = False


def _cents(value: Decimal) -> int:
    if type(value) is not Decimal or not value.is_finite():
        raise ValueError("Pagamento sem precisão decimal")
    cents = value * 100
    if (cents != cents.to_integral_value() or cents < 0
            or cents > 999999999999):
        raise ValueError("Valor não representável em centavos")
    return int(cents)


def _check(tenant_id: UUID, year: int, as_of: date,
           session: AuthenticatedSession, role: str | None = None):
    require_tenant_access(str(tenant_id), session)
    if session.role not in ("TENANT_ADMIN", "TENANT_MEMBER"):
        raise HTTPException(403, detail="Perfil sem permissão de obrigações.")
    if role and session.role != role:
        raise HTTPException(403, detail="Perfil sem permissão.")
    if type(year) is not int or not 2020 <= year <= 2100:
        raise HTTPException(422, detail="Ciclo inválido.")
    if type(as_of) is not date or not 2020 <= as_of.year <= 2100:
        raise HTTPException(422, detail="Data inválida.")


async def _snapshot(tenant_id: UUID, year: int, membership_id: UUID,
                    as_of: date, session: AuthenticatedSession, conn):
    _check(tenant_id, year, as_of, session)
    cycle = await conn.fetchrow(
        "SELECT c.id FROM public.cycles c WHERE c.tenant_id=$1 AND c.year=$2",
        tenant_id, year,
    )
    if cycle is None:
        raise HTTPException(404, detail="Ciclo não encontrado.")
    cycle_id = UUID(str(cycle["id"]))
    if session.role == "TENANT_MEMBER":
        own = await conn.fetchrow(
            "SELECT m.id FROM public.memberships m "
            "WHERE m.tenant_id=$1 AND m.id=$2 AND m.user_id=$3 "
            "AND m.role='TENANT_MEMBER'",
            tenant_id, membership_id, UUID(session.user_id),
        )
    else:
        own = await conn.fetchrow(
            "SELECT m.id FROM public.memberships m "
            "WHERE m.tenant_id=$1 AND m.id=$2 AND m.role='TENANT_MEMBER'",
            tenant_id, membership_id,
        )
    if own is None:
        raise HTTPException(404, detail="Vínculo inacessível.")

    contrib = await conn.fetch(
        "SELECT id,tenant_id,cycle_id,membership_id,competence,due_date,"
        "amount_due,amount_paid,payment_status "
        "FROM public.contributions "
        "WHERE tenant_id=$1 AND cycle_id=$2 AND membership_id=$3 "
        "ORDER BY competence,id LIMIT 501",
        tenant_id, cycle_id, membership_id,
    )
    loan_rows = await conn.fetch(
        "SELECT id,tenant_id,cycle_id,borrower_membership_id,status,disbursed_at "
        "FROM public.loans "
        "WHERE tenant_id=$1 AND cycle_id=$2 AND borrower_membership_id=$3 "
        "ORDER BY id LIMIT 501",
        tenant_id, cycle_id, membership_id,
    )
    installment_rows = await conn.fetch(
        "SELECT i.id,i.tenant_id,i.loan_id,i.installment_number,i.due_date,"
        "i.principal_due,i.interest_due,i.total_due,i.paid_principal,"
        "i.paid_interest,i.paid_mora,i.paid_fine,i.status "
        "FROM public.loan_installments i "
        "JOIN public.loans l ON l.id=i.loan_id AND l.tenant_id=i.tenant_id "
        "WHERE l.tenant_id=$1 AND l.cycle_id=$2 AND "
        "l.borrower_membership_id=$3 "
        "ORDER BY i.loan_id,i.installment_number LIMIT 501",
        tenant_id, cycle_id, membership_id,
    )
    if any(len(rows)>MAX_ROWS for rows in (contrib,loan_rows,installment_rows)):
        raise HTTPException(503, detail="Histórico excede limite; relatório não pode ser truncado.")

    try:
        crows = tuple(ContributionRecord(
            UUID(str(r["id"])),UUID(str(r["tenant_id"])),
            UUID(str(r["cycle_id"])),UUID(str(r["membership_id"])),
            r["competence"],r["due_date"],_cents(r["amount_due"]),
            _cents(r["amount_paid"]),r["payment_status"],
        ) for r in contrib)
        lrows = tuple(LoanRecord(
            UUID(str(r["id"])),UUID(str(r["tenant_id"])),
            UUID(str(r["cycle_id"])),UUID(str(r["borrower_membership_id"])),
            r["status"],r["disbursed_at"],
        ) for r in loan_rows)
        irows = tuple(InstallmentRecord(
            UUID(str(r["id"])),UUID(str(r["tenant_id"])),
            UUID(str(r["loan_id"])),r["installment_number"],r["due_date"],
            _cents(r["principal_due"]),_cents(r["interest_due"]),
            _cents(r["total_due"]),_cents(r["paid_principal"]),
            _cents(r["paid_interest"]),_cents(r["paid_mora"]),
            _cents(r["paid_fine"]),r["status"],
        ) for r in installment_rows)
        report = audit_member_obligations(
            tenant_id,cycle_id,membership_id,year,as_of,crows,lrows,irows,
        )
    except (ValueError,TypeError,OverflowError) as exc:
        raise HTTPException(503, detail="Inconsistência cadastral; prévia bloqueada.") from exc
    return MemberObligationPreviewResponse(
        tenant_id=str(report.tenant_id),
        cycle_id=str(report.cycle_id),
        membership_id=str(report.membership_id),
        cycle_year=report.cycle_year,as_of=report.as_of,
        scope=("SELF_READ_ONLY" if session.role=="TENANT_MEMBER"
               else "TENANT_ADMIN_READ_ONLY"),
        contribution_count=report.contribution_count,
        contribution_due_cents=report.contribution_due_cents,
        contribution_paid_recorded_cents=report.contribution_paid_recorded_cents,
        contribution_open_cents=report.contribution_open_cents,
        contribution_now_open_cents=report.contribution_now_open_cents,
        contribution_overdue_count=report.contribution_overdue_count,
        loan_proposal_count=report.loan_proposal_count,
        loan_active_count=report.loan_active_count,
        loan_closed_count=report.loan_closed_count,
        loan_unscheduled_count=report.loan_unscheduled_count,
        installment_count=report.installment_count,
        loan_now_principal_cents=report.loan_now_principal_cents,
        loan_now_interest_cents=report.loan_now_interest_cents,
        loan_future_principal_cents=report.loan_future_principal_cents,
        loan_future_interest_cents=report.loan_future_interest_cents,
        loan_overdue_installment_count=report.loan_overdue_installment_count,
        registered_now_open_cents=report.registered_now_open_cents,
        status=report.status,
    )


@router.get("/me", response_model=MemberObligationPreviewResponse)
async def get_my_member_obligations(
    tenant_id: UUID,year: int,as_of: date | None=Query(default=None),
    session: AuthenticatedSession=Depends(get_current_session),
    conn=Depends(get_rls_db_connection),
):
    target=as_of or datetime.now(BELEM).date()
    _check(tenant_id,year,target,session,role="TENANT_MEMBER")
    own=await conn.fetchrow(
        "SELECT m.id FROM public.memberships m "
        "WHERE m.tenant_id=$1 AND m.user_id=$2 AND m.role='TENANT_MEMBER'",
        tenant_id,UUID(session.user_id),
    )
    if own is None:
        raise HTTPException(404, detail="Vínculo do membro inacessível.")
    return await _snapshot(tenant_id,year,UUID(str(own["id"])),target,session,conn)


@router.get("/members/{membership_id}", response_model=MemberObligationPreviewResponse)
async def get_admin_member_obligations(
    tenant_id: UUID,year: int,membership_id: UUID,
    as_of: date | None=Query(default=None),
    session: AuthenticatedSession=Depends(get_current_session),
    conn=Depends(get_rls_db_connection),
):
    target=as_of or datetime.now(BELEM).date()
    _check(tenant_id,year,target,session,role="TENANT_ADMIN")
    return await _snapshot(tenant_id,year,membership_id,target,session,conn)
