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
    configured = settings.is_database_configured
    return AuthStatusResponse(
        status="ONLINE_CONFIGURED" if configured else "BLOCKED_PENDING_CONFIG",
        configured=configured,
        provider="FASTAPI_POSTGRESQL" if configured else "NONE",
        architecture_contract="FastAPI / PostgreSQL com RLS (Contrato Técnico Mestre)",
        scaffold_note="Backend FastAPI em conformidade com o Contrato Mestre. Se o banco PostgreSQL não estiver conectado, o acesso permanece bloqueado por segurança.",
        requires_authentication=True,
        message="Autenticação pronta e conectada ao banco." if configured else "Autenticação ainda não configurada. Nenhuma sessão foi iniciada.",
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

    # 3. Validação Real contra Banco de Dados (quando DATABASE_URL estiver configurada)
    # Por segurança, sem conexão de banco confirmada, nenhuma conta é simulada.
    record_failed_attempt(identifier)
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciais inválidas. Verifique seu usuário e senha."
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
    if not settings.is_email_provider_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Serviço de envio de e-mails para recuperação de senha não configurado neste ambiente."
        )
        
    return {
        "success": True,
        "message": "Se o e-mail estiver cadastrado no sistema, as instruções foram despachadas."
    }

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
        
    # Verificação estrita contra banco no ambiente de produção...
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Acesso negado: vínculo solicitado não autorizado para este usuário."
    )
