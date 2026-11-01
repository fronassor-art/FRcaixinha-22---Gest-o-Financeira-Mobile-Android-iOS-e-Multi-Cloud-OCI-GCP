"""
FRcaixinha 2.2 — Rotas de Caixinhas e Isolamento Multi-Inquilino
Contrato Técnico Mestre (Cláusulas 2.3, 2.8, 4.1, 7.1 e 16.4)
"""

from fastapi import APIRouter, HTTPException, status, Depends
from ..dependencies import get_current_session, require_tenant_access, AuthenticatedSession
from ..config import settings

router = APIRouter(prefix="/tenants", tags=["Caixinhas e Isolamento Multi-Tenant"])

@router.get("/{tenant_id}/dashboard")
def get_tenant_dashboard(tenant_id: str, session: AuthenticatedSession = Depends(get_current_session)):
    """
    Retorna o resumo financeiro da caixinha:
    - Master é RECUSADO com 403 (Cláusula 2.8);
    - Administrador de outro tenant é RECUSADO com 403;
    - Membro visualiza apenas dados agregados permitidos da caixinha.
    """
    require_tenant_access(tenant_id, session)
    
    if not settings.is_database_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Banco de dados PostgreSQL não conectado. Não é permitido carregar dados financeiros simulados como se fossem reais."
        )
        
    return {"tenant_id": tenant_id, "status": "AUTHORIZED"}

@router.get("/{tenant_id}/members")
def get_tenant_members(tenant_id: str, session: AuthenticatedSession = Depends(get_current_session)):
    """
    Lista de membros da caixinha:
    - Master: RECUSADO com 403;
    - Admin: Vê os membros do seu próprio tenant;
    - Membro: RECUSADO com 403 (não acessa lista com CPFs, telefones e dados de outros membros).
    """
    require_tenant_access(tenant_id, session)
    
    if session.role == "TENANT_MEMBER":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso Proibido: Membros não possuem autorização para inspecionar dados cadastrais e financeiros de outros membros (LGPD)."
        )
        
    if not settings.is_database_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Banco de dados PostgreSQL não conectado."
        )
        
    return {"tenant_id": tenant_id, "members": []}
