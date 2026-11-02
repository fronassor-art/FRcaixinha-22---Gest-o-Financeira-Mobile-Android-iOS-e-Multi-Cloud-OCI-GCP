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
    # Confere a hierarquia já prevista ANTES de qualquer execução futura.
    # Ainda não há emissão de token, aceite nem envio de e-mail.
    if session.role not in ('MASTER', 'TENANT_ADMIN'):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Somente Master ou administrador de caixinha podem solicitar convites."
        )

    if session.role == 'MASTER':
        if not session.is_master or payload.target_role != 'TENANT_ADMIN':
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="O Master somente pode convidar administradores de caixinha."
            )
    else:
        if payload.target_role != 'TENANT_MEMBER' or not session.tenant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="O administrador somente pode convidar membros de sua caixinha."
            )
        if payload.tenant_id is not None and payload.tenant_id != session.tenant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Não é permitido emitir convites para outra caixinha."
            )

    if not settings.is_database_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Banco de dados PostgreSQL não conectado. Não é possível emitir convites criptográficos."
        )
        
    # Uma URL configurada não cria convite, token, nem envio. Recusar até o
    # fluxo transacional e a entrega estarem implementados e testados.
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Convites ainda não implementados. Nenhum convite foi criado ou enviado."
    )
