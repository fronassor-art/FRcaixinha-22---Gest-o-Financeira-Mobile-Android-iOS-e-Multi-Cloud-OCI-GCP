"""
FRcaixinha 2.2 — Rotas Oficiais de Autenticação e Sessão
Contrato Técnico Mestre (Cláusulas 2.3, 2.8, 14.1 e 16.4)
"""

from fastapi import APIRouter, HTTPException, status, Response, Request, Depends
import datetime
import os
import asyncio
import asyncpg
import uuid
from ..models import LoginRequest, SessionResponse, AuthStatusResponse, ForgotPasswordRequest, ContextSwitchRequest, UserResponse
from ..config import settings
from ..security import check_rate_limit, record_failed_attempt, clear_rate_limit, generate_session_token, hash_token, verify_password_secure
from ..dependencies import get_current_session, AuthenticatedSession, auth_database_url, bearer_token

router = APIRouter(prefix="/auth", tags=["Autenticação e Sessões"])

@router.get("/status", response_model=AuthStatusResponse)
def get_auth_status():
    """
    Informa o estado da infraestrutura de autenticação.
    Declara explicitamente a necessidade do backend contratual FastAPI + PostgreSQL.
    """
    database_url_configured = settings.is_database_configured
    test_enabled = os.getenv('FRCAIXINHA_TEST_AUTH') == '1' and os.getenv('ENVIRONMENT', 'development') != 'production' and bool(os.getenv('AUTH_DATABASE_URL', '').startswith('postgres'))
    return AuthStatusResponse(
        status="TEST_MODE" if test_enabled else ("BLOCKED_PENDING_IMPLEMENTATION" if database_url_configured else "BLOCKED_PENDING_CONFIG"),
        configured=test_enabled,
        provider="POSTGRES_TEST" if test_enabled else "NONE",
        architecture_contract="FastAPI / PostgreSQL com RLS (Contrato Técnico Mestre)",
        scaffold_note="Sessões PostgreSQL de homologação; produção depende de endurecimento operacional e revisão independente.",
        requires_authentication=True,
        message="Autenticação PostgreSQL de homologação com sessão persistente." if test_enabled else ("Autenticação ainda não implementada. Nenhuma sessão foi iniciada." if database_url_configured else "Autenticação ainda não configurada. Nenhuma sessão foi iniciada."),
        server_time=datetime.datetime.now(datetime.timezone.utc)
    )

@router.post("/login", response_model=SessionResponse)
async def login(payload: LoginRequest, response: Response):
    identifier = payload.username_or_email.strip().lower()
    blocked, wait_seconds = check_rate_limit(identifier)
    if blocked:
        raise HTTPException(status_code=429, detail=f'Muitas tentativas inválidas. Tente em {wait_seconds} segundos.')
    if not settings.is_database_configured:
        raise HTTPException(status_code=503, detail='Banco de dados não configurado.')
    try:
        conn = await asyncpg.connect(auth_database_url(), timeout=5)
        try:
            record = await conn.fetchrow(
                'SELECT u.id,u.email,u.full_name,u.status,u.is_master,c.password_hash '
                'FROM public.users u JOIN public.credentials c ON c.user_id=u.id WHERE lower(u.email)=$1',
                identifier)
            verified = bool(record and await asyncio.to_thread(
                verify_password_secure, payload.password, record['password_hash']))
            if not verified or record['status'] != 'ACTIVE':
                record_failed_attempt(identifier)
                raise HTTPException(status_code=401, detail='Credenciais inválidas ou conta indisponível.')

            # A senha é verificada ANTES de criar o token provisório. A consulta
            # de vínculos só aceita token bruto de sessão, nunca UUID arbitrário.
            # INSERT, escolha do vínculo e promoção ocorrem na MESMA transação:
            # sem vínculo válido => rollback, sem sessão provisória persistida.
            raw_token, token_hash = generate_session_token()
            async with conn.transaction():
                current_user = await conn.fetchrow(
                    "SELECT status,is_master FROM public.users WHERE id=$1", record['id'])
                if not current_user or current_user['status'] != 'ACTIVE':
                    record_failed_attempt(identifier)
                    raise HTTPException(status_code=401, detail='Credenciais inválidas ou conta indisponível.')
                is_master = current_user['is_master']
                await conn.execute(
                    "INSERT INTO public.sessions(id,token_hash,user_id,active_role,"
                    "active_tenant_id,expires_at) VALUES($1,$2,$3,'PENDING_CONTEXT',NULL,"
                    "NOW()+INTERVAL '90 seconds')",
                    uuid.uuid4(), token_hash, record['id'])
                links = await conn.fetch(
                    'SELECT tenant_id,role FROM public.auth_active_memberships($1::text) '
                    'ORDER BY tenant_id,role', raw_token)
                if is_master:
                    role, tenant_id = 'MASTER', None
                elif links:
                    role, tenant_id = links[0]['role'], links[0]['tenant_id']
                else:
                    record_failed_attempt(identifier)
                    raise HTTPException(status_code=401, detail='Credenciais inválidas ou conta indisponível.')
                expires_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
                    seconds=settings.SESSION_EXPIRE_SECONDS)
                updated = await conn.execute(
                    "UPDATE public.sessions SET active_role=$2,active_tenant_id=$3,"
                    "expires_at=$4 WHERE token_hash=$1 AND user_id=$5 "
                    "AND active_role='PENDING_CONTEXT' AND revoked_at IS NULL "
                    "AND expires_at>NOW()",
                    token_hash, role, tenant_id, expires_at, record['id'])
                if updated != 'UPDATE 1':
                    raise HTTPException(status_code=401, detail='Credenciais inválidas ou conta indisponível.')
        finally:
            await conn.close()
    except HTTPException:
        raise
    except (asyncpg.PostgresError, OSError, asyncio.TimeoutError):
        raise HTTPException(status_code=503, detail='Serviço de autenticação indisponível.')
    clear_rate_limit(identifier)
    user = UserResponse(id=str(record['id']), name=record['full_name'], email=record['email'],
                        cpf='***', role=role, tenant_id=str(tenant_id) if tenant_id else None,
                        is_master=is_master)
    return SessionResponse(success=True, user=user, expires_at=expires_at,
                           message='Sessão de homologação iniciada.', token=raw_token)


@router.post("/logout")
async def logout(request: Request, response: Response):
    try:
        token = bearer_token(request)
    except HTTPException:
        token = None
    if token:
        try:
            conn = await asyncpg.connect(auth_database_url(), timeout=5)
            try:
                await conn.execute('UPDATE public.sessions SET revoked_at=NOW() WHERE token_hash=$1',
                                   hash_token(token))
            finally:
                await conn.close()
        except (asyncpg.PostgresError, OSError, asyncio.TimeoutError):
            raise HTTPException(status_code=503, detail='Não foi possível confirmar a revogação da sessão.')
    response.delete_cookie(key=settings.SESSION_COOKIE_NAME, httponly=True,
                           secure=settings.COOKIE_SECURE, samesite=settings.COOKIE_SAMESITE)
    return {'success': True, 'message': 'Sessão revogada.'}


@router.post("/logout-all")
async def logout_all_sessions(
    request: Request,
    response: Response,
    session: AuthenticatedSession = Depends(get_current_session),
):
    """Revoga todas as sessões (todos os papéis/tenants) do usuário autenticado.

    A confirmação só é emitida após COMMIT no PostgreSQL da autenticação.
    Não usa a conta financeira e não altera outros usuários.
    """
    try:
        conn = await asyncpg.connect(auth_database_url(), timeout=5)
        try:
            async with conn.transaction():
                rows = await conn.fetch(
                    "UPDATE public.sessions SET revoked_at=NOW() "
                    "WHERE user_id=$1 AND revoked_at IS NULL RETURNING id",
                    uuid.UUID(session.user_id),
                )
        finally:
            await conn.close()
    except HTTPException:
        raise
    except (asyncpg.PostgresError, OSError, asyncio.TimeoutError):
        raise HTTPException(
            status_code=503, detail="Não foi possível confirmar a revogação de todas as sessões."
        )
    response.delete_cookie(
        key=settings.SESSION_COOKIE_NAME, httponly=True,
        secure=settings.COOKIE_SECURE, samesite=settings.COOKIE_SAMESITE
    )
    return {"success":True,"revoked_sessions":len(rows),
            "message":"Sessões de todos os perfis revogadas no PostgreSQL."}


@router.get("/me", response_model=UserResponse)
async def get_me(session: AuthenticatedSession = Depends(get_current_session)):
    return UserResponse(id=session.user_id, name=session.name, email=session.email,
                        cpf='***', role=session.role, tenant_id=session.tenant_id,
                        is_master=session.is_master)


@router.get('/contexts')
async def list_contexts(request: Request, session: AuthenticatedSession = Depends(get_current_session)):
    try:
        conn = await asyncpg.connect(auth_database_url(), timeout=5)
        try:
            links = await conn.fetch(
                'SELECT tenant_id,role,tenant_name '
                'FROM public.auth_active_membership_contexts($1::text)',
                bearer_token(request))
        finally:
            await conn.close()
    except (asyncpg.PostgresError, OSError, asyncio.TimeoutError):
        raise HTTPException(status_code=503, detail='Vínculos indisponíveis.')
    contexts = ([{'role': 'MASTER', 'tenant_id': None,
                  'tenant_name': None}] if session.is_master else [])
    contexts.extend(
        {'role': row['role'], 'tenant_id': str(row['tenant_id']),
         'tenant_name': row['tenant_name']} for row in links
    )
    return contexts


@router.get("/sessions")
async def list_my_sessions(
    request: Request,
    session: AuthenticatedSession = Depends(get_current_session),
):
    """Lista sessões da identidade autenticada sem expor hash/token/IP/UA."""
    try:
        conn = await asyncpg.connect(auth_database_url(), timeout=5)
        try:
            rows = await conn.fetch(
                "SELECT id,active_role,active_tenant_id,created_at,expires_at,"
                "(token_hash=$2) AS is_current "
                "FROM public.sessions WHERE user_id=$1 "
                "AND revoked_at IS NULL AND expires_at>NOW() "
                "ORDER BY created_at DESC,id DESC LIMIT 100",
                uuid.UUID(session.user_id),hash_token(bearer_token(request)),
            )
        finally:
            await conn.close()
    except (asyncpg.PostgresError, OSError, asyncio.TimeoutError):
        raise HTTPException(status_code=503, detail='Sessões indisponíveis.')
    return {
        'source': 'POSTGRESQL_AUTH',
        'sessions': [
            {'id': str(r['id']), 'role': r['active_role'],
             'tenant_id': str(r['active_tenant_id']) if r['active_tenant_id'] else None,
             'created_at': r['created_at'].isoformat(),
             'expires_at': r['expires_at'].isoformat(),
             'current': r['is_current']}
            for r in rows
        ]
    }


@router.post("/sessions/{session_id}/revoke")
async def revoke_my_session(
    session_id: uuid.UUID,
    request: Request,
    session: AuthenticatedSession = Depends(get_current_session),
):
    """Revoga somente sessão própria; não aceita user_id fornecido pelo cliente."""
    try:
        conn = await asyncpg.connect(auth_database_url(), timeout=5)
        try:
            async with conn.transaction():
                row = await conn.fetchrow(
                    "UPDATE public.sessions SET revoked_at=NOW() "
                    "WHERE id=$1 AND user_id=$2 AND revoked_at IS NULL "
                    "AND expires_at>NOW() RETURNING id,token_hash",
                    session_id, uuid.UUID(session.user_id),
                )
        finally:
            await conn.close()
    except (asyncpg.PostgresError, OSError, asyncio.TimeoutError):
        raise HTTPException(status_code=503, detail='Revogação indisponível.')
    if not row:
        raise HTTPException(status_code=404, detail='Sessão não encontrada.')
    return {
        'success': True,
        'session_id': str(row['id']),
        'current_revoked': row['token_hash'] == hash_token(bearer_token(request)),
    }


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

@router.post("/switch-context", response_model=UserResponse)
async def switch_context(payload: ContextSwitchRequest, request: Request,
                         session: AuthenticatedSession = Depends(get_current_session)):
    """Troca o papel do MESMO usuário somente após revalidar a sessão e o vínculo.

    Verificação e UPDATE compartilham a mesma transação/row lock; um logout
    concorrente, suspensão de usuário ou revogação de vínculo falha fechado.
    """
    target_tenant = None
    if payload.target_role == 'MASTER':
        if payload.target_tenant_id is not None:
            raise HTTPException(status_code=403, detail='Contexto não autorizado.')
    else:
        try:
            target_tenant = uuid.UUID(payload.target_tenant_id or '')
        except (ValueError, TypeError):
            raise HTTPException(status_code=422, detail='Caixinha inválida.')
    try:
        conn = await asyncpg.connect(auth_database_url(), timeout=5)
        try:
            async with conn.transaction():
                actor_id = uuid.UUID(session.user_id)
                digest = hash_token(bearer_token(request))
                current = await conn.fetchrow(
                    "SELECT s.user_id,s.active_role,s.active_tenant_id," 
                    "s.revoked_at,s.expires_at,u.is_master,u.status "
                    "FROM public.sessions s JOIN public.users u ON u.id=s.user_id "
                    "WHERE s.token_hash=$1 FOR UPDATE OF s", digest)
                now = datetime.datetime.now(datetime.timezone.utc)
                if (not current or current['user_id'] != actor_id
                        or current['revoked_at'] is not None
                        or current['expires_at'] <= now
                        or current['status'] != 'ACTIVE'):
                    raise HTTPException(status_code=401, detail='Sessão expirada ou revogada.')
                # O contexto ATUAL também precisa permanecer válido. Uma
                # suspensão entre a dependência HTTP e o row lock da troca
                # não pode ser usada para migrar um token revogado de papel.
                links = await conn.fetch(
                    'SELECT tenant_id,role FROM public.auth_active_memberships($1::text)',
                    bearer_token(request)))
                if current['active_role'] == 'MASTER':
                    authorized_current = (
                        current['is_master'] and current['active_tenant_id'] is None
                    )
                else:
                    authorized_current = any(
                        row['tenant_id'] == current['active_tenant_id'] and
                        row['role'] == current['active_role'] for row in links
                    )
                if not authorized_current:
                    raise HTTPException(status_code=401, detail='Vínculo ativo não encontrado.')
                if payload.target_role == 'MASTER':
                    if not current['is_master']:
                        raise HTTPException(status_code=403, detail='Contexto não autorizado.')
                elif not any(row['tenant_id'] == target_tenant and
                             row['role'] == payload.target_role for row in links):
                    raise HTTPException(status_code=403, detail='Vínculo não autorizado.')
                result = await conn.execute(
                    'UPDATE public.sessions SET active_role=$2,active_tenant_id=$3 '
                    'WHERE token_hash=$1 AND user_id=$4 '
                    'AND revoked_at IS NULL AND expires_at>NOW()',
                    digest, payload.target_role, target_tenant, actor_id)
                if result != 'UPDATE 1':
                    raise HTTPException(status_code=401, detail='Sessão expirada ou revogada.')
        finally:
            await conn.close()
    except HTTPException:
        raise
    except (asyncpg.PostgresError, OSError, asyncio.TimeoutError):
        raise HTTPException(status_code=503, detail='Troca de contexto indisponível.')
    return UserResponse(id=session.user_id, name=session.name, email=session.email,
                        cpf='***', role=payload.target_role,
                        tenant_id=str(target_tenant) if target_tenant else None,
                        is_master=session.is_master)
