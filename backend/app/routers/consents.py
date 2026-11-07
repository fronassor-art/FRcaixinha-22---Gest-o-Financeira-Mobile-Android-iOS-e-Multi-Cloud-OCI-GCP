"""Consentimento anual: consulta e voto bloqueados até assinatura versionada persistente."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from ..dependencies import get_current_session, require_tenant_access, AuthenticatedSession
from ..models import AdminConsentResponse, AdminConsentVotePayload

router = APIRouter(prefix="/tenants/{tenant_id}/admin-self-consent",
                   tags=["Consentimentos de Autoempréstimo"])


@router.get("", response_model=AdminConsentResponse)
async def get_admin_self_loan_consent_status(
    tenant_id: str, loan_id: Optional[str] = None,
    session: AuthenticatedSession = Depends(get_current_session)
):
    require_tenant_access(tenant_id, session)
    # Os votos por empréstimo da tabela legada não representam assinatura anual.
    return AdminConsentResponse(
        tenant_id=tenant_id, loan_id=loan_id, total_members_required=0,
        favorable_votes=0, contrary_votes=0, is_unanimous=False,
        status="BLOQUEADO_ASSINATURA_ANUAL_INDISPONIVEL")


@router.post("/vote", response_model=AdminConsentResponse)
async def vote_admin_self_loan_consent(
    tenant_id: str, payload: AdminConsentVotePayload, loan_id: str,
    session: AuthenticatedSession = Depends(get_current_session)
):
    require_tenant_access(tenant_id, session)
    raise HTTPException(status_code=503, detail=(
        "Assinatura anual versionada ainda não disponível. Nenhum voto foi gravado."))
