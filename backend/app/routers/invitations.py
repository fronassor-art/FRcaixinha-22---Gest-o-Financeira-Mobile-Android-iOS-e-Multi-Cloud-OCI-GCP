"""FR Finance AI Studio — convites e pré-diagnóstico seguro.

As rotas de criação real permanecem bloqueadas até existirem entrega,
verificação de titularidade, aceite contratual, RLS e auditoria aprovados.
"""
from fastapi import APIRouter, HTTPException, status, Depends
from ..models import InvitationCreateRequest
from ..dependencies import get_current_session, AuthenticatedSession
from ..config import settings
from ..invitation_preflight import authorize_invitation_intent, invitation_readiness

router = APIRouter(prefix="/invitations", tags=["Convites e Onboarding Administrativo"])


@router.post("/preflight")
def preview_invitation_readiness(
    payload: InvitationCreateRequest,
    session: AuthenticatedSession = Depends(get_current_session),
):
    """Verifica a intenção autorizada; nenhum convite ou conta é criado."""
    return invitation_readiness(
        session=session,
        payload=payload,
        database_configured=settings.is_database_configured,
    )


@router.post("")
def create_invitation(
    payload: InvitationCreateRequest,
    session: AuthenticatedSession = Depends(get_current_session),
):
    """Preserva recusa segura até integração transacional real homologada."""
    authorize_invitation_intent(session=session, payload=payload)
    if not settings.is_database_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Banco de dados PostgreSQL não conectado. Não é possível emitir convites criptográficos.",
        )
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Convites ainda não implementados. Nenhum convite foi criado ou enviado.",
    )
