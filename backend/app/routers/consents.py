"""
FRcaixinha 2.2 — Rotas de Consentimento Coletivo para Autoempréstimo de Administrador
Contrato Técnico Mestre (Cláusulas 2.5, 5.4, 8.8 e 16.4)
"""

from fastapi import APIRouter, HTTPException, status, Depends
from typing import Optional
import uuid
from ..models import AdminConsentResponse, AdminConsentVotePayload
from ..dependencies import get_current_session, require_tenant_access, AuthenticatedSession
from ..database import get_rls_db_connection

router = APIRouter(prefix="/tenants/{tenant_id}/admin-self-consent", tags=["Consentimentos de Autoempréstimo"])

@router.get("", response_model=AdminConsentResponse)
async def get_admin_self_loan_consent_status(
    tenant_id: str,
    loan_id: Optional[str] = None,
    session: AuthenticatedSession = Depends(get_current_session),
    conn = Depends(get_rls_db_connection)
):
    """
    Retorna o status de quórum do consentimento coletivo para autoempréstimo de administrador:
    - Exige unanimidade dos demais membros ativos (100% de assinaturas válidas).
    """
    require_tenant_access(tenant_id, session)

    if session.role == "MASTER":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso Proibido: Master não participa nem inspeciona consentimentos de caixinhas."
        )

    # Identificar administrador do tenant
    tenant = await conn.fetchrow("SELECT admin_user_id FROM tenants WHERE id = $1;", uuid.UUID(tenant_id))
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant não encontrado.")

    # Contagem dos demais membros ativos
    other_members = await conn.fetchval("""
        SELECT COUNT(*) FROM memberships
        WHERE tenant_id = $1 AND status = 'ATIVA' AND user_id != $2;
    """, uuid.UUID(tenant_id), tenant["admin_user_id"])

    # Votos favoráveis
    query_votes = """
        SELECT COUNT(*) FROM admin_self_loan_consents
        WHERE tenant_id = $1 AND decision = 'FAVORAVEL'
    """
    params = [uuid.UUID(tenant_id)]
    if loan_id:
        query_votes += " AND loan_id = $2"
        params.append(uuid.UUID(loan_id))

    favorable = await conn.fetchval(query_votes, *params)
    contrary = 0

    is_unanimous = (other_members > 0 and favorable >= other_members)
    consent_status = "UNANIMOUS_ACTIVE" if is_unanimous else "PENDING_OR_SUSPENDED"

    return AdminConsentResponse(
        tenant_id=tenant_id,
        loan_id=loan_id,
        total_members_required=other_members,
        favorable_votes=favorable,
        contrary_votes=contrary,
        is_unanimous=is_unanimous,
        status=consent_status
    )


@router.post("/vote", response_model=AdminConsentResponse)
async def vote_admin_self_loan_consent(
    tenant_id: str,
    payload: AdminConsentVotePayload,
    loan_id: str,
    session: AuthenticatedSession = Depends(get_current_session),
    conn = Depends(get_rls_db_connection)
):
    """
    Registra manifestação de vontade individual do membro (Cláusula 5.4):
    - O próprio administrador NÃO pode votar em si mesmo;
    - Membro pode votar FAVORAVEL, CONTRARIO ou revogar.
    """
    require_tenant_access(tenant_id, session)

    # Recupera o membership do votante
    voter = await conn.fetchrow("""
        SELECT id, role, status FROM memberships
        WHERE tenant_id = $1 AND user_id = $2 AND status = 'ATIVA';
    """, uuid.UUID(tenant_id), uuid.UUID(session.user_id))

    if not voter:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Apenas membros ativos podem manifestar consentimento.")

    if voter["role"] == "TENANT_ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Vedação Contratual: O Administrador requerente não pode votar na aprovação do seu próprio empréstimo (Cláusula 5.4)."
        )

    # Verifica se empréstimo existe
    loan = await conn.fetchrow("SELECT cycle_id FROM loans WHERE id = $1 AND tenant_id = $2;", uuid.UUID(loan_id), uuid.UUID(tenant_id))
    if not loan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Empréstimo não encontrado.")

    # Insere ou atualiza o voto (Upsert)
    await conn.execute("""
        INSERT INTO admin_self_loan_consents (id, tenant_id, cycle_id, loan_id, voter_membership_id, decision, justification, voted_at)
        VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())
        ON CONFLICT (tenant_id, loan_id, voter_membership_id)
        DO UPDATE SET decision = EXCLUDED.decision, justification = EXCLUDED.justification, voted_at = NOW();
    """, uuid.uuid4(), uuid.UUID(tenant_id), loan["cycle_id"], uuid.UUID(loan_id), voter["id"], payload.decision, payload.justification)

    return await get_admin_self_loan_consent_status(tenant_id, loan_id, session, conn)
