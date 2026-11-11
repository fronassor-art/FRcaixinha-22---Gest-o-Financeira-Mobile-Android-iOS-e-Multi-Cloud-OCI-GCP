"""FR Finance AI Studio — convites e pré-diagnóstico seguro.

As rotas de criação real permanecem bloqueadas até existirem entrega,
verificação de titularidade, aceite contratual, RLS e auditoria aprovados.
"""
from fastapi import APIRouter, HTTPException, status, Depends, Request
from ..models import (
    InvitationCreateRequest, InvitationContractReadinessRequest,
    InvitationContractCatalogRequest, InvitationContractTextIntegrityRequest,
)
from ..dependencies import get_current_session, AuthenticatedSession
from ..config import settings
from ..access_delivery_binding import require_access_delivery, invitation_accepted_response
from ..database import get_rls_db_connection
from ..contract_text_integrity import verify_contract_body_digest
from ..canonical_contract_store import load_published_contract_body
from ..invitation_preflight import (
    authorize_invitation_intent, invitation_readiness, invitation_contract_readiness,
    published_membership_contract_catalog,
)

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


@router.post("/preflight/contracts")
async def preview_published_contract_readiness(
    payload: InvitationContractReadinessRequest,
    session: AuthenticatedSession = Depends(get_current_session),
    conn=Depends(get_rls_db_connection),
):
    """Confirma caixinha e documento publicado via PostgreSQL RLS.

    Nunca emite convite, e-mail, aceite, usuário ou vínculo; os bloqueios
    continuam ativos mesmo quando as duas referências são válidas.
    """
    return await invitation_contract_readiness(
        session=session, payload=payload, conn=conn,
    )


@router.post("/preflight/contract-catalog")
async def preview_published_contract_catalog(
    payload: InvitationContractCatalogRequest,
    session: AuthenticatedSession = Depends(get_current_session),
    conn=Depends(get_rls_db_connection),
):
    """Lista versões de adesão publicadas (metadados) sem permitir aceite."""
    return await published_membership_contract_catalog(
        session=session, payload=payload, conn=conn,
    )


@router.post("/preflight/contract-text")
async def preview_contract_text_integrity(
    payload: InvitationContractTextIntegrityRequest,
    session: AuthenticatedSession = Depends(get_current_session),
    conn=Depends(get_rls_db_connection),
):
    """Compara SHA-256 do texto exato à versão publicada sob PostgreSQL RLS.

    Não devolve texto ou hash do cliente; nenhuma concessão de aceite ou
    ativação é possível por esta rota.
    """
    return await verify_contract_body_digest(
        session=session, payload=payload, conn=conn,
    )


@router.post("/preflight/contract-content")
async def fetch_canonical_contract_content(
    payload: InvitationContractReadinessRequest,
    session: AuthenticatedSession = Depends(get_current_session),
    conn=Depends(get_rls_db_connection),
):
    """Entregar texto canônico somente após publicação e hash autenticados."""
    return await load_published_contract_body(
        session=session, payload=payload, conn=conn,
    )


@router.post("/preflight/saas-capacity")
async def preview_saas_member_capacity(
    payload: InvitationContractReadinessRequest,
    session: AuthenticatedSession = Depends(get_current_session),
    conn=Depends(get_rls_db_connection),
):
    """Leituras autenticadas de licença/capacidade; NUNCA emitir convite."""
    from ..saas_member_admission_readiness import member_admission_readiness
    return await member_admission_readiness(session=session,payload=payload,conn=conn)


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


@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def submit_invitation_to_existing_outbox(
    payload: InvitationCreateRequest,
    request: Request,
    session: AuthenticatedSession = Depends(get_current_session),
):
    """Connect the existing API route to an injected same-database outbox worker.

    No worker installed in the Termux/dev default: the endpoint remains 503.
    Master invites additionally require MFA/dual-control at worker level.
    """
    authorize_invitation_intent(session=session, payload=payload)
    if payload.required_document_id is None or not payload.tenant_id:
        raise HTTPException(422, "Caixinha e contrato publicado são obrigatórios.")
    if not settings.is_database_configured:
        raise HTTPException(503, "Banco PostgreSQL original indisponível.")
    runtime = require_access_delivery(request)
    # This port must atomically recheck RLS, contract, identity, outbox and
    # idempotency on the original database; intent-level checks are not proof.
    if session.role == "MASTER":
        raise HTTPException(
            503, "Convite administrativo aguarda prova real de MFA e dupla aprovação."
        )
    receipt = await runtime.invite(session=session, payload=payload)
    return invitation_accepted_response(receipt)
