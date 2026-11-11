"""
FR Finance AI Studio — Rotas Oficiais de Autenticação e Sessão
Contrato Técnico Mestre (Cláusulas 2.3, 2.8, 14.1 e 16.4)
"""

from fastapi import APIRouter, HTTPException, status, Response, Request, Depends
import datetime
import os
import asyncio
import asyncpg
import uuid
import hashlib
from ..models import LoginRequest, SessionResponse, AuthStatusResponse, ForgotPasswordRequest, ContextSwitchRequest, UserResponse
from ..config import settings
from ..security import check_rate_limit, record_failed_attempt, clear_rate_limit, generate_session_token, hash_token, verify_password_secure, auth_rate_limit_key
from ..dependencies import get_current_session, AuthenticatedSession, auth_database_url, auth_verifier_database_url, bearer_token
from ..login_role_policy import select_login_role
from ..access_delivery_binding import require_access_delivery, password_recovery_accepted_response

router = APIRouter(prefix="/auth", tags=["Autenticação e Sessões"])

@router.get("/status", response_model=AuthStatusResponse)
def get_auth_status():
    """
    Informa o estado da infraestrutura de autenticação.
    Declara explicitamente a necessidade do backend contratual FastAPI + PostgreSQL.
    """
    database_url_configured = settings.is_database_configured
    if os.getenv("ENVIRONMENT") == "production":
        from ..production_auth_gate import require_production_auth, ProductionAuthBlocked
        try:
            require_production_auth(os.environ)
            configured=True
        except ProductionAuthBlocked:
            configured=False
        return AuthStatusResponse(
            status="PRODUCTION_CONFIGURED_UNVERIFIED" if configured else "BLOCKED_PRODUCTION_AUTH",
            configured=configured,
            provider="POSTGRESQL_OCI_CONFIG" if configured else "NONE",
            architecture_contract="FastAPI/PostgreSQL RLS",
            scaffold_note="Configuração não comprova banco, RLS, TLS ou sessões operacionais.",
            requires_authentication=True,
            message="Teste E2E OCI pendente." if configured else "Login production bloqueado.",
            server_time=datetime.datetime.now(datetime.timezone.utc),
        )
    test_enabled = (os.getenv('FRCAIXINHA_TEST_AUTH') == '1'
                    and os.getenv('ENVIRONMENT', 'development') != 'production'
                    and bool(os.getenv('AUTH_DATABASE_URL', '').startswith('postgres'))
                    and bool(os.getenv('AUTH_VERIFIER_DATABASE_URL', '').startswith('postgres'))
                    and len(os.getenv('AUTH_RATE_LIMIT_HMAC_KEY','').encode('utf-8')) >= 32)
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
        rate_key = auth_rate_limit_key(identifier)
    except ValueError:
        raise HTTPException(status_code=503, detail='Protecao de autenticacao indisponivel.')
    try:
        # Rate limit compartilhado entre processos, antes da verificacao de senha.
        rc = await asyncpg.connect(auth_database_url(), timeout=5)
        try:
            remaining = await rc.fetchval('SELECT public.auth_login_rate_check($1::text)',rate_key)
        finally:
            await rc.close()
        if remaining is None or remaining < 0:
            raise HTTPException(status_code=503, detail='Protecao de autenticacao indisponivel.')
        if remaining > 0:
            raise HTTPException(status_code=429, detail='Muitas tentativas inválidas. Tente mais tarde.')
        # Credencial verificadora distinta: apenas ela enxerga hashes.
        verifier = await asyncpg.connect(auth_verifier_database_url(), timeout=5)
        try:
            record = await verifier.fetchrow(
                'SELECT u.id,u.email,u.full_name,u.status,u.is_master,c.password_hash '
                'FROM public.users u JOIN public.credentials c ON c.user_id=u.id WHERE lower(u.email)=$1',
                identifier)
            verified = bool(record and await asyncio.to_thread(
                verify_password_secure, payload.password, record['password_hash']))
            if not verified or record['status'] != 'ACTIVE':
                raise HTTPException(status_code=401, detail='Credenciais inválidas ou conta indisponível.')
            # So uma conta que comprovou a senha gera o atestado efemero.
            proof_raw, proof_hash = generate_session_token()
            await verifier.execute(
                "INSERT INTO public.auth_login_proofs("
                "proof_hash,user_id,credential_fingerprint,expires_at) "
                "VALUES($1,$2,$3,NOW()+INTERVAL '60 seconds')",
                proof_hash, record['id'],
                hashlib.sha256(record['password_hash'].encode('utf-8')).hexdigest())
        finally:
            await verifier.close()

        conn = await asyncpg.connect(auth_database_url(), timeout=5)
        try:
            # A senha é verificada ANTES de criar o token provisório. A consulta
            # de vínculos só aceita token bruto de sessão, nunca UUID arbitrário.
            # A prova efemera e de uso unico foi emitida por OUTRA role.
            # Emissao PENDING, escolha de vinculo e promocao na MESMA transacao:
            # sem vinculo valido => rollback da sessao; prova ja foi consumida.
            raw_token, _ = generate_session_token()
            async with conn.transaction():
                current_user = await conn.fetchrow(
                    "SELECT status,is_master FROM public.users WHERE id=$1", record['id'])
                if not current_user or current_user['status'] != 'ACTIVE':
                    raise HTTPException(status_code=401, detail='Credenciais inválidas ou conta indisponível.')
                is_master = current_user['is_master']
                issued = await conn.fetchval(
                    "SELECT public.auth_issue_pending_session("
                    "$1::uuid,$2::text,$3::text)",
                    record['id'], raw_token, proof_raw)
                if not issued:
                    raise HTTPException(status_code=401, detail='Prova de login invalida ou expirada.')
                links = await conn.fetch(
                    'SELECT tenant_id,role FROM public.auth_active_memberships($1::text) '
                    'ORDER BY tenant_id,role', raw_token)
                # Master nunca surge por fallback de cliente legado.
                role, tenant_id = select_login_role(
                    requested_role=payload.requested_role,
                    is_master=is_master,
                    links=links,
                    requested_tenant_id=payload.requested_tenant_id,
                )
                # Role Auth não pode UPDATE direto em perfil/tenant.
                # A função PostgreSQL valida token, identidade e vínculo
                # na mesma transação; retorna a expiração real da sessão.
                expires_at = await conn.fetchval(
                    "SELECT public.auth_promote_pending_session("
                    "$1::text,$2::varchar,$3::uuid)",
                    raw_token, role, tenant_id)
                if expires_at is None:
                    raise HTTPException(status_code=401, detail='Credenciais inválidas ou conta indisponível.')
                # Apagar falhas apenas no COMMIT da sessao validada.
                cleared = await conn.fetchval(
                    'SELECT public.auth_login_rate_success($1::text)',rate_key)
                if not cleared:
                    raise HTTPException(status_code=503, detail='Protecao de autenticacao indisponivel.')
                # Origem REAL e verificada do alerta interno de sessão:
                # o token recém-promovido é revalidado no próprio PostgreSQL.
                # Só modo local AI Studio autorizado; sem envio externo.
                if (os.getenv('AI_STUDIO_IN_APP_NOTIFICATIONS') == 'YES'
                        and os.getenv('FRCAIXINHA_TERMUX_LOCAL_API') == '1'):
                    notification_id = await conn.fetchval(
                        'SELECT public.notification_local_session_issued($1::text)',
                        raw_token)
                    if notification_id is None:
                        raise HTTPException(status_code=503,
                                            detail='Aviso de seguranca da sessao nao persistido.')

        finally:
            await conn.close()
    except HTTPException as error:
        if error.status_code == 401:
            record_failed_attempt(identifier)
            try:
                fc = await asyncpg.connect(auth_database_url(), timeout=5)
                try:
                    await fc.fetchval('SELECT public.auth_login_rate_failure($1::text)',rate_key)
                finally:
                    await fc.close()
            except (asyncpg.PostgresError, OSError, asyncio.TimeoutError):
                raise HTTPException(status_code=503, detail='Protecao de autenticacao indisponivel.')
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
                await conn.fetchval(
                    'SELECT public.auth_revoke_session($1::text)', token)
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
            revoked_count = await conn.fetchval(
                "SELECT public.auth_revoke_all_sessions($1::text)",
                bearer_token(request),
            )
            if revoked_count < 0:
                raise HTTPException(status_code=401, detail='Sessão expirada ou revogada.')
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
    return {"success":True,"revoked_sessions":revoked_count,
            "message":"Sessões de todos os perfis revogadas no PostgreSQL."}


@router.get("/me", response_model=UserResponse)
async def get_me(session: AuthenticatedSession = Depends(get_current_session)):
    return UserResponse(id=session.user_id, name=session.name, email=session.email,
                        cpf='***', role=session.role, tenant_id=session.tenant_id,
                        is_master=session.is_master)


@router.get('/contexts')
async def list_contexts(request: Request, session: AuthenticatedSession = Depends(get_current_session)):
    """A sessao revela somente o proprio papel; outros exigem novo login."""
    if session.role == 'MASTER':
        return [{'role': 'MASTER', 'tenant_id': None, 'tenant_name': None}]
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
        raise HTTPException(status_code=503, detail='Vinculo indisponivel.')
    return [
        {'role': row['role'], 'tenant_id': str(row['tenant_id']),
         'tenant_name': row['tenant_name']}
        for row in links
        if row['role'] == session.role and str(row['tenant_id']) == session.tenant_id
    ]


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
            result = await conn.fetchval(
                "SELECT public.auth_revoke_owned_session($1::text,$2::uuid)",
                bearer_token(request), session_id,
            )
        finally:
            await conn.close()
    except (asyncpg.PostgresError, OSError, asyncio.TimeoutError):
        raise HTTPException(status_code=503, detail='Revogação indisponível.')
    if not result:
        raise HTTPException(status_code=404, detail='Sessão não encontrada.')
    return {
        'success': True,
        'session_id': str(session_id),
        'current_revoked': result == 2,
    }


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



@router.post("/forgot-password", status_code=status.HTTP_202_ACCEPTED)
async def submit_password_recovery_to_existing_outbox(
    payload: ForgotPasswordRequest, request: Request,
):
    """Use existing PostgreSQL outbox/auth service, never send SMTP inline.

    HTTP 202 is returned only when a verified worker confirms a committed
    durable queue record. A non-existent account must not be distinguishable.
    No worker configured means HTTP 503, never a fake success.
    """
    if not settings.is_database_configured:
        raise HTTPException(503, "Recuperação de senha por e-mail ainda não implementada no banco ativo.")
    runtime = require_access_delivery(request)
    try:
        identifier = str(payload.email).strip().lower()
        blocked, _retry = check_rate_limit(identifier)
    except (ValueError, TypeError):
        raise HTTPException(503, "Proteção de recuperação indisponível.") from None
    if blocked:
        raise HTTPException(429, "Muitas solicitações. Tente novamente mais tarde.")
    # Real worker must enforce persistent per-IP/per-email abuse protection,
    # account enumeration resistance, one-use hashed token and post-commit send.
    receipt = await runtime.reset(email=identifier)
    return password_recovery_accepted_response(receipt)

@router.post("/switch-context")
async def switch_context_disabled(
    session: AuthenticatedSession = Depends(get_current_session),
):
    """Bloqueia troca de papel sem logout, inclusive chamada direta HTTP."""
    raise HTTPException(status_code=403, detail=
        'Troca de perfil bloqueada. Saia da conta e entre novamente no perfil desejado.')
