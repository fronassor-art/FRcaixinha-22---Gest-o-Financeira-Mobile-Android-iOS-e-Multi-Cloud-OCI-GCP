"""M601: auditoria financeira integrada de caixinha/ciclo — SOMENTE leitura.

Não confundir saldos internos, lançamento registrado ou balanceamento de
partidas dobradas com confirmação de Pix, dinheiro disponível ou fechamento.
"""
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from ..database import get_rls_db_connection
from ..dependencies import AuthenticatedSession, get_current_session, require_tenant_access
from ..financial_integrity import (
    MemberFact, ContributionFact, LedgerFact, CyclePolicyFact,
    analyze_financial_integrity, money_cents, MAX_RECORDS,
)
from ..models import FinancialIntegrityPreviewResponse

router=APIRouter(prefix="/tenants/{tenant_id}/cycles/{year}/financial-integrity",
                 tags=["Auditoria financeira integrada — prévia não conciliada"])

def _uid(x) -> UUID:
    try:
        return UUID(str(x))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError("Identificador financeiro inválido") from exc

def _bounded(rows):
    if len(rows)>MAX_RECORDS:
        raise HTTPException(
            status_code=503,detail="Auditoria excede limite de registros; não apresentar dados truncados.")
    return rows

@router.get("/preview", response_model=FinancialIntegrityPreviewResponse)
async def get_tenant_financial_integrity_preview(
    tenant_id: UUID, year: int,
    session: AuthenticatedSession = Depends(get_current_session),
    conn = Depends(get_rls_db_connection),
):
    require_tenant_access(str(tenant_id),session)
    if session.role!="TENANT_ADMIN":
        raise HTTPException(status_code=403,detail="Auditoria consolidada exclusiva do administrador.")
    if type(year) is not int or not 2020<=year<=2100:
        raise HTTPException(status_code=422,detail="Ano fora do intervalo.")
    cycle=await conn.fetchrow(
        "SELECT c.id,c.year,c.status,c.start_date,c.end_date "
        "FROM public.cycles c WHERE c.tenant_id=$1 AND c.year=$2",
        tenant_id, year
    )
    if cycle is None:
        raise HTTPException(status_code=404,detail="Ciclo inexistente.")
    # Sem snapshot bancário. Se o ciclo estiver com datas inválidas, não
    # prosseguir sob hipótese de que um saldo possa ser fechamento.
    if (cycle["start_date"].year!=year or cycle["end_date"].year!=year or
        cycle["start_date"]>cycle["end_date"]):
        raise HTTPException(status_code=503,detail="Período de ciclo inconsistente.")
    mid=await conn.fetch(
        "SELECT id,tenant_id,user_id,role,status "
        "FROM public.memberships WHERE tenant_id=$1 ORDER BY id LIMIT 501",
        tenant_id,
    )
    contrib=await conn.fetch(
        "SELECT id,tenant_id,cycle_id,membership_id,competence,"
        "amount_due,amount_paid,payment_status "
        "FROM public.contributions WHERE tenant_id=$1 AND cycle_id=$2 "
        "ORDER BY id LIMIT 501",
        tenant_id,cycle["id"],
    )
    policy=await conn.fetch(
        "SELECT id,tenant_id,cycle_id,version,admin_pct,member_pct,"
        "contribution_per_quota,status "
        "FROM public.policies WHERE tenant_id=$1 AND cycle_id=$2 "
        "ORDER BY version LIMIT 501",
        tenant_id,cycle["id"],
    )
    accounts=await conn.fetch(
        "SELECT account_code FROM public.ledger_accounts "
        "WHERE tenant_id=$1 ORDER BY account_code LIMIT 501",tenant_id,
    )
    postings=await conn.fetch("""
        SELECT t.id,t.tenant_id,t.reference_id,
               count(e.id)::integer AS entries,
               count(e.id) FILTER (WHERE e.entry_type='DR')::integer AS dr_entries,
               count(e.id) FILTER (WHERE e.entry_type='CR')::integer AS cr_entries,
               COALESCE(sum(e.amount_cents) FILTER (WHERE e.entry_type='DR'),0)::bigint AS dr_cents,
               COALESCE(sum(e.amount_cents) FILTER (WHERE e.entry_type='CR'),0)::bigint AS cr_cents,
               COALESCE(sum(e.amount_cents) FILTER (
                 WHERE e.entry_type='DR' AND a.account_code='1.1.1'),0)::bigint AS cash_dr_cents,
               COALESCE(sum(e.amount_cents) FILTER (
                 WHERE e.entry_type='CR' AND a.account_code='2.1.1'),0)::bigint AS capital_cr_cents,
               count(e.id) FILTER (WHERE e.amount_cents IS NULL
                  OR e.amount_cents<=0 OR a.id IS NULL
                  OR e.entry_type NOT IN ('DR','CR'))::integer AS invalid_entries
        FROM public.ledger_transactions t
        LEFT JOIN public.ledger_entries e
          ON e.tenant_id=t.tenant_id AND e.transaction_id=t.id
        LEFT JOIN public.ledger_accounts a
          ON a.tenant_id=t.tenant_id AND a.id=e.account_id
        WHERE t.tenant_id=$1 AND
          (t.transaction_date AT TIME ZONE 'America/Belem')::date BETWEEN $2 AND $3
        GROUP BY t.id,t.tenant_id,t.reference_id
        ORDER BY t.id LIMIT 501
    """,tenant_id,cycle["start_date"],cycle["end_date"])
    for rows in (mid,contrib,policy,accounts,postings):
        _bounded(rows)
    try:
        data=analyze_financial_integrity(
            tenant_id=tenant_id,cycle_id=_uid(cycle["id"]),year=year,
            cycle_status=cycle["status"],
            members=tuple(MemberFact(
                _uid(row["id"]),_uid(row["tenant_id"]),
                _uid(row["user_id"]),row["role"],row["status"]
            ) for row in mid),
            contributions=tuple(ContributionFact(
                _uid(row["id"]),_uid(row["tenant_id"]),
                _uid(row["cycle_id"]),_uid(row["membership_id"]),
                row["competence"],money_cents(row["amount_due"]),
                money_cents(row["amount_paid"]),row["payment_status"]
            ) for row in contrib),
            ledger=tuple(LedgerFact(
                _uid(row["id"]),_uid(row["tenant_id"]),row["reference_id"],
                row["entries"],row["dr_entries"],row["cr_entries"],
                row["dr_cents"],row["cr_cents"],row["cash_dr_cents"],
                row["capital_cr_cents"],row["invalid_entries"]
            ) for row in postings),
            policies=tuple(CyclePolicyFact(
                _uid(row["id"]),_uid(row["tenant_id"]),_uid(row["cycle_id"]),
                row["version"],row["admin_pct"],row["member_pct"],
                money_cents(row["contribution_per_quota"]),row["status"]
            ) for row in policy),
            account_codes=tuple(row["account_code"] for row in accounts),
        )
    except (ValueError,OverflowError,TypeError) as exc:
        raise HTTPException(status_code=503,detail="Inconsistência financeira detectada; auditoria bloqueada.") from exc
    return FinancialIntegrityPreviewResponse(
        source="POSTGRESQL_RLS_REGISTERED_NOT_BANK_RECONCILED",
        scope="TENANT_ADMIN_READ_ONLY",
        **data.__dict__,
    )
