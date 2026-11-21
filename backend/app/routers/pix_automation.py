"""AI Studio: in-app Pix control plane; no direct financial confirmation."""
from __future__ import annotations

from decimal import Decimal
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Request

from ..dependencies import get_current_session, require_tenant_access
from ..database import get_rls_db_connection

CONTRACT = "AI_STUDIO_M3800_PIX_APP_AUTOMATION_JOURNEYS_V1"
router = APIRouter(prefix="/tenants/{tenant_id}/financial-automation",
                   tags=["Automação Pix"])


def scope(tenant_id, session):
    require_tenant_access(tenant_id, session)
    if session.role not in ("TENANT_MEMBER", "TENANT_ADMIN"):
        raise HTTPException(403, "Perfil não autorizado")


def identifier(value):
    try:
        return UUID(value)
    except (ValueError, TypeError):
        raise HTTPException(422, "Identificador inválido") from None


def cents(value):
    d = Decimal(str(value))
    if not d.is_finite() or d < 0 or d.as_tuple().exponent < -2:
        raise HTTPException(503, "Saldo inconsistente")
    return int(d * 100)


def runtime(request):
    service = getattr(request.app.state, "pix_automation_runtime", None)
    if (service is None
            or getattr(service, "verified_provisioning", False) is not True
            or getattr(service, "bank_settlement_authorized", False) is not True
            or getattr(service, "provider_account_bound", False) is not True):
        raise HTTPException(503, "Pix aguarda integração e conciliação oficiais")
    return service


@router.get("/capabilities")
async def capabilities(tenant_id: str, session=Depends(get_current_session)):
    scope(tenant_id, session)
    return {
        "workstream": "AI_STUDIO", "contract": CONTRACT,
        "monthly_contribution_quote": True,
        "loan_installment_quote": True,
        "pix_collection_enabled": False,
        "pix_payout_enabled": False,
        "real_payments_enabled": False,
        "bank_reconciled": False,
    }


@router.get("/contributions/{contribution_id}/quote")
async def contribution_quote(
    tenant_id: str, contribution_id: str,
    session=Depends(get_current_session),
    conn=Depends(get_rls_db_connection),
):
    scope(tenant_id, session)
    row = await conn.fetchrow(
        "SELECT c.id,c.cycle_id,c.competence,c.due_date,c.amount_due,"
        "c.amount_paid,c.payment_status,m.user_id "
        "FROM contributions c JOIN memberships m ON m.id=c.membership_id "
        "WHERE c.tenant_id=$1 AND c.id=$2",
        identifier(tenant_id), identifier(contribution_id),
    )
    if row is None:
        raise HTTPException(404, "Contribuição não encontrada")
    if session.role == "TENANT_MEMBER" and str(row["user_id"]) != session.user_id:
        raise HTTPException(403, "Contribuição de outro membro")
    due, paid = cents(row["amount_due"]), cents(row["amount_paid"])
    if paid > due:
        raise HTTPException(503, "Saldo inconsistente")
    return {
        "obligation_kind": "CONTRIBUTION",
        "obligation_id": str(row["id"]),
        "cycle_id": str(row["cycle_id"]),
        "competence": str(row["competence"]),
        "due_date": str(row["due_date"]),
        "expected_cents": due,
        "paid_cents": paid, "open_cents": due - paid,
        "payment_status": str(row["payment_status"]),
        "pix_payable": False,
        "bank_reconciled": False,
    }


@router.get("/loans/{loan_id}/installments/{installment_id}/quote")
async def installment_quote(
    tenant_id: str, loan_id: str, installment_id: str,
    session=Depends(get_current_session),
    conn=Depends(get_rls_db_connection),
):
    scope(tenant_id, session)
    row = await conn.fetchrow(
        "SELECT i.id,i.installment_number,i.due_date,i.status,"
        "i.interest_due,i.principal_due,i.paid_interest,i.paid_principal,"
        "m.user_id FROM loan_installments i "
        "JOIN loans l ON l.id=i.loan_id "
        "JOIN memberships m ON m.id=l.borrower_membership_id "
        "WHERE i.tenant_id=$1 AND i.loan_id=$2 AND i.id=$3",
        identifier(tenant_id), identifier(loan_id), identifier(installment_id),
    )
    if row is None:
        raise HTTPException(404, "Parcela não encontrada")
    if session.role == "TENANT_MEMBER" and str(row["user_id"]) != session.user_id:
        raise HTTPException(403, "Empréstimo de outro membro")
    interest = cents(row["interest_due"]) - cents(row["paid_interest"])
    principal = cents(row["principal_due"]) - cents(row["paid_principal"])
    if min(interest, principal) < 0:
        raise HTTPException(503, "Dívida inconsistente")
    return {
        "obligation_kind": "LOAN_INSTALLMENT",
        "obligation_id": str(row["id"]),
        "loan_id": loan_id,
        "installment_number": int(row["installment_number"]),
        "due_date": str(row["due_date"]),
        "payment_status": str(row["status"]),
        "interest_open_cents": interest,
        "principal_open_cents": principal,
        "base_open_cents": interest + principal,
        "pix_payable": False,
        "bank_reconciled": False,
    }


@router.get("/loans/{loan_id}/disbursement-preview")
async def payout_preview(
    tenant_id: str, loan_id: str,
    session=Depends(get_current_session),
    conn=Depends(get_rls_db_connection),
):
    scope(tenant_id, session)
    row = await conn.fetchrow(
        "SELECT l.id,l.principal,l.status,m.user_id FROM loans l "
        "JOIN memberships m ON m.id=l.borrower_membership_id "
        "WHERE l.tenant_id=$1 AND l.id=$2",
        identifier(tenant_id), identifier(loan_id),
    )
    if row is None:
        raise HTTPException(404, "Empréstimo não encontrado")
    if session.role == "TENANT_MEMBER" and str(row["user_id"]) != session.user_id:
        raise HTTPException(403, "Crédito de outro membro")
    return {
        "loan_id": str(row["id"]), "status": str(row["status"]),
        "principal_cents": cents(row["principal"]),
        "destination_registered": False,
        "destination_masked": None,
        "reservation_confirmed": False,
        "pix_out_available": False,
        "external_transfer_confirmed": False,
    }


@router.post("/contributions/{contribution_id}/pix")
async def collect_contribution(
    tenant_id: str, contribution_id: str, request: Request,
    session=Depends(get_current_session),
):
    scope(tenant_id, session)
    identifier(tenant_id); identifier(contribution_id)
    service = runtime(request)
    return await service.collect_contribution(tenant_id, contribution_id, session)


@router.post("/loans/{loan_id}/installments/{installment_id}/pix")
async def collect_loan_installment(
    tenant_id: str, loan_id: str, installment_id: str,
    request: Request, session=Depends(get_current_session),
):
    scope(tenant_id, session)
    identifier(tenant_id); identifier(loan_id); identifier(installment_id)
    service = runtime(request)
    return await service.collect_loan_installment(
        tenant_id, loan_id, installment_id, session,
    )


@router.post("/loans/{loan_id}/payout")
async def issue_loan_payout(
    tenant_id: str, loan_id: str, request: Request,
    session=Depends(get_current_session),
):
    scope(tenant_id, session)
    if session.role != "TENANT_ADMIN":
        raise HTTPException(403, "Somente Administrador Contratante autoriza Pix")
    identifier(tenant_id); identifier(loan_id)
    service = runtime(request)
    return await service.issue_loan_payout(tenant_id, loan_id, session)


@router.get("/receipts/{operation_id}")
async def get_receipt(
    tenant_id: str, operation_id: str, request: Request,
    session=Depends(get_current_session),
):
    scope(tenant_id, session)
    identifier(tenant_id)
    if not operation_id.startswith("P_") or not (10 <= len(operation_id) <= 64):
        raise HTTPException(422, "Identificador de comprovante inválido")
    service = runtime(request)
    return await service.read_receipt(tenant_id, operation_id, session)
