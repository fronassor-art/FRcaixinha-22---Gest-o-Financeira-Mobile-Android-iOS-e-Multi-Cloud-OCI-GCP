"""
FRcaixinha 2.2 — Injeção de Dependências e Autorização Server-Side (RBAC)
Contrato Técnico Mestre (Cláusulas 2.3, 2.8, 4.1 e 16.4)
"""

from fastapi import Request, HTTPException, status, Depends
from typing import Optional
import datetime
import os
from urllib.parse import urlparse
import asyncpg
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

def auth_database_url() -> str:
    """Papel dedicado de autenticação em homologação; nunca o papel financeiro."""
    url = os.getenv('AUTH_DATABASE_URL', '')
    if (os.getenv('FRCAIXINHA_TEST_AUTH') != '1'
            or os.getenv('ENVIRONMENT', 'development') == 'production'
            or not url.startswith('postgres')):
        raise HTTPException(status_code=503, detail='Autenticação disponível apenas em homologação configurada.')
    return url


def auth_verifier_database_url() -> str:
    """Credencial independente: so comprova senha; nao emite sessao."""
    session_url = auth_database_url()
    url = os.getenv('AUTH_VERIFIER_DATABASE_URL', '')
    if not url.startswith('postgres'):
        raise HTTPException(status_code=503, detail='Verificador separado nao configurado.')
    a, b = urlparse(session_url), urlparse(url)
    if (not a.username or not b.username or a.username == b.username
            or (a.hostname, a.port, a.path) != (b.hostname, b.port, b.path)):
        raise HTTPException(status_code=503, detail='Credenciais tecnicas nao segregadas.')
    return url


def bearer_token(request: Request) -> str:
    header = request.headers.get('Authorization', '')
    if header.startswith('Bearer ') and len(header.split(' ', 1)[1]) > 0:
        return header.split(' ', 1)[1]
    if settings.SESSION_COOKIE_NAME in request.cookies:
        return request.cookies[settings.SESSION_COOKIE_NAME]
    raise HTTPException(status_code=401, detail='Autenticação necessária. Sessão ausente.', headers={'WWW-Authenticate': 'Bearer'})


async def get_current_session(request: Request) -> AuthenticatedSession:
    """Verifica hash, revogação, expiração e vínculo ativo no PostgreSQL."""
    raw_token = bearer_token(request)
    digest = hash_token(raw_token)
    try:
        conn = await asyncpg.connect(auth_database_url(), timeout=5)
        try:
            async with conn.transaction():
                row = await conn.fetchrow(
                    "SELECT s.user_id,s.active_role,s.active_tenant_id,s.expires_at,s.revoked_at,"
                    "u.email,u.full_name,u.is_master,u.status "
                    "FROM public.sessions s JOIN public.users u ON u.id=s.user_id "
                    "WHERE s.token_hash=$1", digest)
                now = datetime.datetime.now(datetime.timezone.utc)
                if (not row or row['revoked_at'] or row['expires_at'] <= now
                        or row['status'] != 'ACTIVE'):
                    raise HTTPException(status_code=401, detail='Sessão ausente, revogada ou expirada.')
                if row['active_role'] == 'MASTER':
                    valid = row['is_master'] and row['active_tenant_id'] is None
                else:
                    links = await conn.fetch(
                        'SELECT tenant_id,role FROM public.auth_active_memberships($1::text)', raw_token)
                    valid = any(link['tenant_id'] == row['active_tenant_id'] and
                                link['role'] == row['active_role'] for link in links)
                if not valid:
                    raise HTTPException(status_code=401, detail='Vínculo ativo não encontrado.')
                renewed_until = await conn.fetchval(
                    "SELECT public.auth_refresh_session($1::text)", raw_token)
                if renewed_until is None:
                    raise HTTPException(status_code=401, detail='Sessão expirada ou revogada.')
            return AuthenticatedSession(
                str(row['user_id']), row['active_role'],
                str(row['active_tenant_id']) if row['active_tenant_id'] else None,
                row['email'], row['full_name'], row['is_master'])
        finally:
            await conn.close()
    except HTTPException:
        raise
    except (asyncpg.PostgresError, OSError, TimeoutError):
        raise HTTPException(status_code=503, detail='Serviço de autenticação indisponível.')


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
    if session.role == "MASTER":
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
