"""
FR Caixinha — backend da frente AI Studio.
Mesmo produto e Contrato Tecnico Mestre, com codigo/banco isolados da frente anterior.
"""

from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from .config import settings
from .dependencies import auth_database_url, auth_verifier_database_url
from .security import auth_rate_limit_key
import asyncio
import asyncpg
import hashlib
from pathlib import Path
from . import ledger_keyset as _ledger_keyset
from .routers import auth, tenants, invitations, master, contributions, loans, ledger, consents, closings, audit, member_cycle_previews, financial_integrity_previews

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Backend oficial em FastAPI e PostgreSQL para automação de caixinhas privadas com segregação patrimonial e RLS.",
    docs_url="/api/docs" if settings.COOKIE_SECURE is False else None,
    redoc_url="/api/redoc" if settings.COOKIE_SECURE is False else None,
)

# Middleware de Segurança e Headers HTTP
@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    response: Response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    # Tokens de sessão, convites e dados SaaS nunca devem ser guardados por
    # proxies, navegadores compartilhados ou previews externos.
    response.headers["Referrer-Policy"] = "no-referrer"
    if request.url.path.startswith(("/api/v1/", "/api/health/ready", "/api/health/runtime", "/api/health/features")):
        response.headers["Cache-Control"] = "no-store"
        response.headers["Pragma"] = "no-cache"
    return response

# CORS restrito
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin for origin in settings.BACKEND_CORS_ORIGINS if origin],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Registro dos Roteadores da API v1
app.include_router(auth.router, prefix=settings.API_V1_STR)
app.include_router(tenants.router, prefix=settings.API_V1_STR)
app.include_router(invitations.router, prefix=settings.API_V1_STR)
app.include_router(master.router, prefix=settings.API_V1_STR)
app.include_router(contributions.router, prefix=settings.API_V1_STR)
app.include_router(member_cycle_previews.router, prefix=settings.API_V1_STR)
app.include_router(financial_integrity_previews.router, prefix=settings.API_V1_STR)
app.include_router(loans.router, prefix=settings.API_V1_STR)
app.include_router(ledger.router, prefix=settings.API_V1_STR)
app.include_router(consents.router, prefix=settings.API_V1_STR)
app.include_router(closings.router, prefix=settings.API_V1_STR)
app.include_router(audit.router, prefix=settings.API_V1_STR)

@app.get("/api/health")
def health_check():
    return {
        "status": "ONLINE",
        "app": "FR Caixinha",
        "framework": "FastAPI (Python)",
        "database_backend": "PostgreSQL com Row-Level Security (RLS)",
        "database_configured": settings.is_database_configured,
        "environment": "sandbox-development"
    }


@app.get("/api/health/runtime", include_in_schema=False)
def backend_runtime_contract():
    """Versao do contrato e limites de leitura ja carregados no processo Python.

    Nenhum dado financeiro, URL de banco, usuario, token ou chave e consultado.
    O contrato nao prova SHA Git, reconciliacao ou autorizacao de fechamento.
    """
    return {
        "project": "FRCAIXINHA_AI_STUDIO_MOBILE",
        "runtime_contract": "AI_STUDIO_M280_RUNTIME_V1",
        "ledger_account_limit": ledger.MAX_LEDGER_ACCOUNTS,
        "ledger_transaction_limit": ledger.MAX_LEDGER_TRANSACTIONS,
        "ledger_entry_limit": ledger.MAX_LEDGER_ENTRIES_PER_TRANSACTION,
        "financial_closing_authorized": False,
        "bank_reconciled": False,
        "runtime_git_sha_verified": False,
    }


@app.get("/api/health/features", include_in_schema=False)
def backend_feature_gates():
    """Identidade oficial e funcionalidades em homologacao carregadas pelo processo."""
    return {
        "product": "FR Caixinha",
        "workstream": "AI_STUDIO",
        "feature_contract": "FR_CAIXINHA_M300_RUNTIME_V1",
        "ledger_account_journal_page_max": ledger.MAX_LEDGER_ACCOUNT_JOURNAL_PAGE_SIZE,
        "bank_reconciled": False,
        "financial_closing_authorized": False,
        "real_payments_enabled": False,
        "master_tenant_ledger_allowed": False,
        "runtime_git_sha_verified": False,
    }


@app.get("/api/health/features/m320", include_in_schema=False)
def backend_m320_feature_contract():
    """Prova do modulo diretorio M320 carregado, sem consultar dados privados."""
    return {
        "product": "FR Caixinha",
        "workstream": "AI_STUDIO",
        "contract": "FR_CAIXINHA_M320_EMPTY_LEDGER_V1",
        "account_directory_read_only": True,
        "account_directory_max_accounts": ledger.MAX_LEDGER_ACCOUNTS,
        "tenant_admin_only": True,
        "empty_ledger_balance_values_hidden": True,
        "financial_closing_authorized": False,
        "real_payments_enabled": False,
        "bank_reconciled": False,
        "runtime_git_sha_verified": False,
    }


# M360: hashes dos arquivos .py capturados no instante do import.
# Nunca equiparar a hash do bytecode ou SHA completo do commit executado.
_M360_SOURCE_AT_IMPORT = {
    "main_py": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    "ledger_py": hashlib.sha256(Path(ledger.__file__).read_bytes()).hexdigest(),
    "ledger_keyset_py": hashlib.sha256(Path(_ledger_keyset.__file__).read_bytes()).hexdigest(),
}


@app.get("/api/health/features/m360", include_in_schema=False)
def backend_m360_feature_contract():
    return {
        "product": "FR Caixinha",
        "workstream": "AI_STUDIO",
        "contract": "FR_CAIXINHA_M360_KEYSET_V1",
        "keyset_read_only": True,
        "page_max": ledger.MAX_LEDGER_ACCOUNT_JOURNAL_PAGE_SIZE,
        "tenant_admin_only": True,
        "financial_closing_authorized": False,
        "real_payments_enabled": False,
        "bank_reconciled": False,
        "source_fingerprints_at_import": _M360_SOURCE_AT_IMPORT,
        "runtime_git_sha_verified": False,
    }


@app.get("/api/health/ready")
async def backend_readiness():
    """Verifica conexões e esquema de homologação sem modificar o PostgreSQL."""
    if not settings.is_database_configured:
        raise HTTPException(status_code=503, detail="PostgreSQL não configurado.")
    # Jamais marcar pronto em produção: o login atual é somente de homologação.
    auth_url = auth_database_url()
    verifier_url = auth_verifier_database_url()
    try:
        auth_rate_limit_key('readiness')
    except ValueError:
        raise HTTPException(status_code=503, detail='Limitador de login nao configurado.')
    try:
        finance = await asyncpg.connect(settings.DATABASE_URL, timeout=3, command_timeout=3)
        try:
            finance_role_ok = await finance.fetchval(
                "SELECT NOT (rolsuper OR rolbypassrls) FROM pg_roles "
                "WHERE rolname=current_user")
        finally:
            await finance.close()
        auth = await asyncpg.connect(auth_url, timeout=3, command_timeout=3)
        try:
            auth_role_ok = await auth.fetchrow(
                "SELECT NOT (r.rolsuper OR r.rolbypassrls) AS safe, "
                "NOT has_column_privilege(current_user,'public.credentials',"
                "'password_hash','SELECT') AS no_hash, "
                "NOT has_table_privilege(current_user,'public.sessions','INSERT') "
                "AS no_direct_issue, "
                "has_function_privilege(current_user,"
                "'public.auth_issue_pending_session(uuid,text,text)','EXECUTE') "
                "AS allowed_issuer, "
                "NOT has_table_privilege(current_user,'public.auth_login_rate_limits','SELECT') AS no_direct_rate, "
                "has_function_privilege(current_user,'public.auth_login_rate_check(text)','EXECUTE') AS can_rate_check, "
                "has_function_privilege(current_user,'public.auth_login_rate_failure(text)','EXECUTE') AS can_rate_failure, "
                "has_function_privilege(current_user,'public.auth_login_rate_success(text)','EXECUTE') AS can_rate_success "
                "FROM pg_roles r WHERE r.rolname=current_user")
            structure_ok = await auth.fetchrow(
                "SELECT to_regclass('public.users') IS NOT NULL AS users_ok, "
                "to_regclass('public.credentials') IS NOT NULL AS credentials_ok, "
                "to_regclass('public.sessions') IS NOT NULL AS sessions_ok, "
                "to_regprocedure('public.auth_active_memberships(text)') IS NOT NULL AS links_ok, "
                "to_regprocedure('public.auth_issue_pending_session(uuid,text,text)') IS NOT NULL AS issuer_ok, "
                "to_regclass('public.auth_login_proofs') IS NOT NULL AS proofs_ok, "
                "to_regclass('public.auth_login_rate_limits') IS NOT NULL AS rate_ok"
            )
        finally:
            await auth.close()
        verifier = await asyncpg.connect(verifier_url, timeout=3, command_timeout=3)
        try:
            verifier_ok = await verifier.fetchrow(
                "SELECT has_column_privilege(current_user,'public.credentials',"
                "'password_hash','SELECT') AS can_verify, "
                "has_table_privilege(current_user,'public.sessions','INSERT') AS can_issue, "
                "has_function_privilege(current_user,"
                "'public.auth_issue_pending_session(uuid,text,text)','EXECUTE') AS can_call_issue, "
                "has_function_privilege(current_user,'public.auth_login_rate_check(text)',"
                "'EXECUTE') AS can_rate_check, "
                "has_table_privilege(current_user,'public.auth_login_proofs','SELECT') AS can_read_proofs, "
                "has_table_privilege(current_user,'public.auth_login_rate_limits','SELECT') AS can_read_rate, "
                "(SELECT NOT (rolsuper OR rolbypassrls) FROM pg_roles "
                "WHERE rolname=current_user) AS safe"
            )
        finally:
            await verifier.close()
        if (not finance_role_ok or not auth_role_ok
                or not all(auth_role_ok.values())):
            raise HTTPException(status_code=503, detail='Conta SQL de API privilegiada ou sem segregacao.')
        if (not verifier_ok or not verifier_ok['safe']
                or not verifier_ok['can_verify'] or verifier_ok['can_issue']
                or verifier_ok['can_call_issue'] or verifier_ok['can_read_proofs']
                or verifier_ok['can_rate_check'] or verifier_ok['can_read_rate']):
            raise HTTPException(status_code=503, detail='Verificador de senha nao segregado.')
        if not structure_ok or not all(structure_ok.values()):
            raise HTTPException(status_code=503, detail="Estrutura de autenticação ainda não validada.")
    except (asyncpg.PostgresError, OSError, asyncio.TimeoutError, TimeoutError):
        raise HTTPException(status_code=503, detail="Banco de homologação indisponível.")
    return {"status": "READY_FOR_TEST_AUTH", "scope": "LOCAL_HOMOLOGATION_ONLY"}
