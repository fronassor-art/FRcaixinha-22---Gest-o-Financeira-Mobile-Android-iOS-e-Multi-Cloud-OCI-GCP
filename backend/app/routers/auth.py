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
            links = await conn.fetch(
                'SELECT tenant_id,role FROM public.auth_active_memberships($1) ORDER BY tenant_id,role', record['id'])
            if record['is_master']:
                role, tenant_id = 'MASTER', None
            elif links:
                role, tenant_id = links[0]['role'], links[0]['tenant_id']
            else:
                raise HTTPException(status_code=403, detail='Conta sem vínculo ativo.')
            raw_token, token_hash = generate_session_token()
            expires_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
                seconds=settings.SESSION_EXPIRE_SECONDS)
            await conn.execute(
                'INSERT INTO public.sessions(id,token_hash,user_id,active_role,active_tenant_id,expires_at) '
                'VALUES($1,$2,$3,$4,$5,$6)',
                uuid.uuid4(), token_hash, record['id'], role, tenant_id, expires_at)
        finally:
            await conn.close()
    except HTTPException:
        raise
    except (asyncpg.PostgresError, OSError, asyncio.TimeoutError):
        raise HTTPException(status_code=503, detail='Serviço de autenticação indisponível.')
    clear_rate_limit(identifier)
    user = UserResponse(id=str(record['id']), name=record['full_name'], email=record['email'],
                        cpf='***', role=role, tenant_id=str(tenant_id) if tenant_id else None,
                        is_master=record['is_master'])
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


@router.get("/me", response_model=UserResponse)
async def get_me(session: AuthenticatedSession = Depends(get_current_session)):
    return UserResponse(id=session.user_id, name=session.name, email=session.email,
                        cpf='***', role=session.role, tenant_id=session.tenant_id,
                        is_master=session.is_master)


@router.get('/contexts')
async def list_contexts(session: AuthenticatedSession = Depends(get_current_session)):
    try:
        conn = await asyncpg.connect(auth_database_url(), timeout=5)
        try:
            links = await conn.fetch(
                'SELECT tenant_id,role FROM public.auth_active_memberships($1) ORDER BY tenant_id,role',
                uuid.UUID(session.user_id))
        finally:
            await conn.close()
    except (asyncpg.PostgresError, OSError, asyncio.TimeoutError):
        raise HTTPException(status_code=503, detail='Vínculos indisponíveis.')
    contexts = ([{'role': 'MASTER', 'tenant_id': None}] if session.is_master else [])
    contexts.extend({'role': row['role'], 'tenant_id': str(row['tenant_id'])} for row in links)
    return contexts


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
    target_tenant = None
    if payload.target_role == 'MASTER':
        if not session.is_master or payload.target_tenant_id is not None:
            raise HTTPException(status_code=403, detail='Contexto não autorizado.')
    else:
        try:
            target_tenant = uuid.UUID(payload.target_tenant_id or '')
        except ValueError:
            raise HTTPException(status_code=422, detail='Caixinha inválida.')
    try:
        conn = await asyncpg.connect(auth_database_url(), timeout=5)
        try:
            async with conn.transaction():
                if target_tenant:
                    links = await conn.fetch(
                        'SELECT tenant_id,role FROM public.auth_active_memberships($1)',
                        uuid.UUID(session.user_id))
                    if not any(row['tenant_id'] == target_tenant and
                               row['role'] == payload.target_role for row in links):
                        raise HTTPException(status_code=403, detail='Vínculo não autorizado.')
                result = await conn.execute(
                    'UPDATE public.sessions SET active_role=$2,active_tenant_id=$3 '
                    'WHERE token_hash=$1 AND revoked_at IS NULL AND expires_at>NOW()',
                    hash_token(bearer_token(request)), payload.target_role, target_tenant)
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
