"""
FRcaixinha 2.2 — Injeção de Dependências e Autorização Server-Side (RBAC)
Contrato Técnico Mestre (Cláusulas 2.3, 2.8, 4.1 e 16.4)
"""

from fastapi import Request, HTTPException, status, Depends
from typing import Optional
import datetime
from .security import hash_token
from .config import settings

class AuthenticatedSession:
    def __init__(self, user_id: str, role: str, tenant_id: Optional[str], email: str, name: str, is_master: bool):
        self.user_id = user_id
        self.role = role
        self.tenant_id = tenant_id
        self.email = email
        self.name = name
        self.is_master = is_master

# Repositório de sessões em memória para verificação no backend
_active_server_sessions = {}

def get_current_session(request: Request) -> AuthenticatedSession:
    """
    Extrai o token do cabeçalho Authorization ou do cookie HttpOnly seguro.
    O cliente NUNCA determina o próprio papel ou tenant.
    """
    token = None
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
    elif settings.SESSION_COOKIE_NAME in request.cookies:
        token = request.cookies[settings.SESSION_COOKIE_NAME]
        
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Autenticação necessária. Sessão ausente ou malformada.",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    token_digest = hash_token(token)
    session_data = _active_server_sessions.get(token_digest)
    
    if not session_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sessão não encontrada ou revogada.",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    expires_at = session_data.get("expires_at")
    if not expires_at or datetime.datetime.now(datetime.timezone.utc) > expires_at:
        _active_server_sessions.pop(token_digest, None)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sua sessão expirou por tempo de inatividade. Faça login novamente.",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    # Deslizar expiração por 15 minutos em caso de atividade legítima
    session_data["expires_at"] = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=settings.SESSION_EXPIRE_SECONDS)
    
    return AuthenticatedSession(
        user_id=session_data["user_id"],
        role=session_data["role"],
        tenant_id=session_data.get("tenant_id"),
        email=session_data["email"],
        name=session_data["name"],
        is_master=session_data.get("is_master", False)
    )

def require_master(session: AuthenticatedSession = Depends(get_current_session)) -> AuthenticatedSession:
    """
    Garante acesso exclusivo ao Administrador Master da plataforma.
    """
    if session.role != "MASTER" or not session.is_master:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso Proibido: Esta operação exige o papel de Administrador Master da plataforma."
        )
    return session

def require_tenant_access(target_tenant_id: str, session: AuthenticatedSession = Depends(get_current_session)) -> AuthenticatedSession:
    """
    Aplica as regras invioláveis de isolamento de inquilino (Multi-Tenant Isolation):
    1. Master NÃO acessa saldos, membros ou dados financeiros da caixinha (Cláusula 2.8).
    2. Admin A NÃO acessa caixinha B.
    3. Membro Acessa SOMENTE sua caixinha e seus próprios dados.
    """
    if session.role == "MASTER" or session.is_master:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso Proibido ao Master: O perfil Master gerencia apenas licenças e suporte técnico. "
                   "É estritamente vedado o acesso a saldos, membros ou dados bancários/financeiros da caixinha "
                   "(Cláusula 2.8 de Segregação Patrimonial e LGPD)."
        )
        
    if session.role not in ("TENANT_ADMIN", "TENANT_MEMBER"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Papel de acesso inválido.")

    if session.role == "TENANT_ADMIN":
        if session.tenant_id != target_tenant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Isolamento Multi-Inquilino Violado: O administrador da caixinha '{session.tenant_id}' "
                       f"não possui autorização para ler ou modificar a caixinha '{target_tenant_id}'."
            )
            
    if session.role == "TENANT_MEMBER":
        if session.tenant_id != target_tenant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acesso Negado: Você não é membro desta caixinha."
            )
            
    return session
