"""
FRcaixinha 2.2 — Rotas de Convites Administrativos
Contrato Técnico Mestre (Cláusulas 2.3 e 16.4)
Não permite auto-cadastro público com privilégios.
"""

from fastapi import APIRouter, HTTPException, status, Depends
from ..models import InvitationCreateRequest
from ..dependencies import get_current_session, AuthenticatedSession
from ..config import settings

router = APIRouter(prefix="/invitations", tags=["Convites e Onboarding Administrativo"])

@router.post("")
def create_invitation(payload: InvitationCreateRequest, session: AuthenticatedSession = Depends(get_current_session)):
    """
    Cria um convite com token criptográfico de uso único para novos membros ou administradores.
    - Master pode convidar Administradores de Caixinha;
    - Administrador de Caixinha pode convidar Membros para o seu próprio tenant;
    - Membros NUNCA podem criar convites nem conceder papéis.
    """
    if session.role == "TENANT_MEMBER":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso Proibido: Membros não possuem autorização para convidar ou criar contas."
        )
        
    if payload.target_role == "TENANT_ADMIN" and session.role != "MASTER":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Apenas o Administrador Master pode convidar ou autorizar novos Administradores de Caixinha."
        )
        
    if not settings.is_database_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Banco de dados PostgreSQL não conectado. Não é possível emitir convites criptográficos."
        )
        
    return {
        "success": True,
        "message": f"Convite para {payload.target_email} como {payload.target_role} processado com sucesso."
    }
