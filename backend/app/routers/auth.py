"""
FRcaixinha 2.2 — Rotas Oficiais de Autenticação e Sessão
Contrato Técnico Mestre (Cláusulas 2.3, 2.8, 14.1 e 16.4)
"""

from fastapi import APIRouter, HTTPException, status, Response, Request, Depends
import datetime
from ..models import LoginRequest, SessionResponse, AuthStatusResponse, ForgotPasswordRequest, ContextSwitchRequest, UserResponse
from ..config import settings
from ..security import check_rate_limit, record_failed_attempt, clear_rate_limit, generate_session_token, hash_token, verify_password_secure
from ..dependencies import get_current_session, AuthenticatedSession, _active_server_sessions

router = APIRouter(prefix="/auth", tags=["Autenticação e Sessões"])

@router.get("/status", response_model=AuthStatusResponse)
def get_auth_status():
    """
    Informa o estado da infraestrutura de autenticação.
    Declara explicitamente a necessidade do backend contratual FastAPI + PostgreSQL.
    """
    database_url_configured = settings.is_database_configured
    return AuthStatusResponse(
        status="BLOCKED_PENDING_IMPLEMENTATION" if database_url_configured else "BLOCKED_PENDING_CONFIG",
        configured=False,
        provider="NONE",
        architecture_contract="FastAPI / PostgreSQL com RLS (Contrato Técnico Mestre)",
        scaffold_note="A autenticação PostgreSQL ainda não foi implementada; configurar uma URL não habilita o login.",
        requires_authentication=True,
        message="Autenticação ainda não implementada. Nenhuma sessão foi iniciada." if database_url_configured else "Autenticação ainda não configurada. Nenhuma sessão foi iniciada.",
        server_time=datetime.datetime.now(datetime.timezone.utc)
    )

@router.post("/login", response_model=SessionResponse)
def login(payload: LoginRequest, response: Response):
    """
    Autenticação real no servidor.
    O frontend NUNCA escolhe o papel, tenant ou permissões.
    """
    identifier = payload.username_or_email.strip().lower()
    
    # 1. Checagem de Rate Limiting
    is_blocked, wait_seconds = check_rate_limit(identifier)
    if is_blocked:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Muitas tentativas inválidas. Bloqueio preventivo ativado. Tente novamente em {wait_seconds} segundos."
        )

    # 2. Bloqueio Seguro se PostgreSQL não estiver configurado
    if not settings.is_database_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Autenticação ainda não configurada. Nenhuma sessão foi iniciada."
        )

    # Configurar uma URL não implementa a consulta nem verifica uma credencial.
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Autenticação PostgreSQL ainda não implementada. Nenhuma sessão foi iniciada."
    )

@router.post("/logout")
def logout(request: Request, response: Response):
    """
    Invalida a sessão de forma autoritativa no servidor e limpa os cookies HttpOnly.
    """
    token = None
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
    elif settings.SESSION_COOKIE_NAME in request.cookies:
        token = request.cookies[settings.SESSION_COOKIE_NAME]
        
    if token:
        token_digest = hash_token(token)
        _active_server_sessions.pop(token_digest, None)
        
    response.delete_cookie(
        key=settings.SESSION_COOKIE_NAME,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE
    )
    
    return {"success": True, "message": "Sessão revogada com sucesso no servidor."}

@router.get("/me", response_model=UserResponse)
def get_me(session: AuthenticatedSession = Depends(get_current_session)):
    """
    Retorna a identidade e papel validados pelo servidor.
    """
    return UserResponse(
        id=session.user_id,
        name=session.name,
        email=session.email,
        cpf="***",  # Mascarado conforme LGPD
        role=session.role,
        tenant_id=session.tenant_id,
        is_master=session.is_master
    )

@router.post("/forgot-password")
def forgot_password(payload: ForgotPasswordRequest):
    """
    Recuperação de senha segura:
    - Se provedor de envio não estiver configurado, informa claramente a indisponibilidade.
    - Se configurado, retorna mensagem genérica para não revelar existência de contas.
    """
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Recuperação de senha por e-mail ainda não implementada."
    )

@router.post("/switch-context")
def switch_context(payload: ContextSwitchRequest, session: AuthenticatedSession = Depends(get_current_session)):
    """
    Alternância de contexto segura para usuários com múltiplos vínculos legítimos:
    - A identidade é única;
    - O servidor valida no banco se o usuário possui a permissão requisitada;
    - Membro NUNCA herda privilégios de Administrador.
    """
    if not settings.is_database_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Autenticação ainda não configurada. Não é possível alternar vínculos sem banco de dados ativo."
        )
        
    # Não houve consulta de vínculos ao banco; mantenha a operação bloqueada.
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Alternância de vínculos ainda não implementada."
    )
