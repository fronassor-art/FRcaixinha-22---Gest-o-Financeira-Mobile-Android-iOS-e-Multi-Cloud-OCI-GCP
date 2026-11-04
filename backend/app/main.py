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
from . import financial_sandbox_reconciliation as _financial_lab
from . import synthetic_financial_journal as _synthetic_journal
from . import annual_evidence_preflight as _annual_evidence
from . import financial_three_source_preflight as _three_source
import os
from .routers import sandbox_evidence_ci as _sandbox_evidence_ci
from .routers import auth, tenants, invitations, master, contributions, loans, ledger, consents, closings, audit, member_cycle_previews, financial_integrity_previews, member_lifecycle_sandbox, member_lifecycle_reviews, member_obligations

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
app.include_router(member_lifecycle_sandbox.router, prefix=settings.API_V1_STR)
app.include_router(member_lifecycle_reviews.router, prefix=settings.API_V1_STR)
app.include_router(member_obligations.router, prefix=settings.API_V1_STR)
app.include_router(loans.router, prefix=settings.API_V1_STR)
app.include_router(ledger.router, prefix=settings.API_V1_STR)
app.include_router(consents.router, prefix=settings.API_V1_STR)
app.include_router(closings.router, prefix=settings.API_V1_STR)
app.include_router(audit.router, prefix=settings.API_V1_STR)

# M2040: endpoints de evidencias SINTETICAS apenas na CI efemera com opt-in.
# Nao registrar no Termux ou em producao mesmo que a flag esteja ligada.
_M2040_CI_EVIDENCE_READS = (
    os.getenv("FRCAIXINHA_CI_ISOLATED") == "1"
    and os.getenv("AI_STUDIO_M2040_CI_EVIDENCE_READS") == "1"
    and os.getenv("ENVIRONMENT", "development") != "production"
)
if _M2040_CI_EVIDENCE_READS:
    app.include_router(_sandbox_evidence_ci.router, prefix=settings.API_V1_STR)


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


@app.get("/api/health/features/m1720", include_in_schema=False)
def backend_m1720_feature_contract():
    """Somente contrato de capacidades locais; nunca indica conciliação bancária."""
    return {
        "product": "FR Caixinha",
        "workstream": "AI_STUDIO",
        "contract": _financial_lab.LAB_CONTRACT,
        "sandbox_preview_only": True,
        "sandbox_merchant_get_connected": False,
        "loan_allocation_preview": True,
        "exit_restitution_readiness_only": True,
        "real_payments_enabled": False,
        "bank_reconciled": False,
        "ledger_written": False,
        "financial_closing_authorized": False,
        "payout_authorized": False,
        "runtime_git_sha_verified": False,
    }


@app.get("/api/health/features/m1880", include_in_schema=False)
def backend_m1880_feature_contract():
    """Somente capacidades de oráculos puros, SEM prova bancária ou I/O."""
    return {
        "product": "FR Caixinha",
        "workstream": "AI_STUDIO",
        "journal_contract": _synthetic_journal.CONTRACT,
        "annual_contract": _annual_evidence.CONTRACT,
        "synthetic_only": True,
        "hash_chain_proves_provider_origin": False,
        "provider_get_connected": False,
        "durable_event_store_connected": False,
        "tenant_portfolio_cross_access": False,
        "bank_reconciled": False,
        "ledger_written": False,
        "financial_closing_authorized": False,
        "payout_authorized": False,
        "real_payments_enabled": False,
        "runtime_git_sha_verified": False,
    }


@app.get("/api/health/features/m2040", include_in_schema=False)
def backend_m2040_feature_contract():
    """Status de laboratorio CI; nao prova de pagamento, capital ou fechamento."""
    return {
        "product": "FR Caixinha",
        "workstream": "AI_STUDIO",
        "contract": "AI_STUDIO_M2040_CI_SANDBOX_PERSISTENCE_V1",
        "database_migration_applied_locally": False,
        "ci_only_synthetic_schema_in_repository": True,
        "synthetic_read_routes_registered": _M2040_CI_EVIDENCE_READS,
        "provider_get_connected": False,
        "oauth_connect_active": False,
        "real_webhooks_active": False,
        "bank_reconciled": False,
        "financial_effect_applied": False,
        "ledger_written": False,
        "financial_closing_authorized": False,
        "payout_authorized": False,
        "real_payments_enabled": False,
        "runtime_git_sha_verified": False,
    }


@app.get("/api/health/features/m2200", include_in_schema=False)
def backend_m2200_three_source_contract():
    """Diagnóstico do laboratório de reconciliação de registros, SEM I/O."""
    return {
        "product": "FR Caixinha",
        "workstream": "AI_STUDIO",
        "contract": _three_source.CONTRACT,
        "three_source_preflight_only": True,
        "settlement_is_bank_proof": False,
        "provider_connected": False,
        "real_webhooks_active": False,
        "bank_reconciled": False,
        "ledger_written": False,
        "closing_authorized": False,
        "capital_confirmed": False,
        "payout_authorized": False,
        "pix_enabled": False,
        "real_payments_enabled": False,
    }


@app.get("/api/health/features/m2300", include_in_schema=False)
def backend_m2300_operational_preflight_contract():
    """Status do parser offline e validador puro HMAC, sem conexão com PSP."""
    from .mp_operational_preflight import CONTRACT as mp_contract
    return {
        "product": "FR Caixinha",
        "workstream": "AI_STUDIO",
        "contract": mp_contract,
        "offline_csv_preview_only": True,
        "webhook_validator_not_registered": True,
        "provider_connected": False,
        "webhook_live_active": False,
        "bank_reconciled": False,
        "ledger_written": False,
        "financial_closing_authorized": False,
        "real_payments_enabled": False,
        "pix_enabled": False,
    }


@app.get("/api/health/features/m2400", include_in_schema=False)
def backend_m2400_connect_webhook_preflight_contract():
    """Pré-validação de segurança sem conexão OAuth, token, rota webhook ou banco."""
    from .mp_oauth_connect_preflight import CONTRACT as contract
    return {
        "product": "FR Caixinha",
        "workstream": "AI_STUDIO",
        "contract": contract,
        "oauth_pkce_preflight_only": True,
        "sandbox_webhook_signature_preflight_only": True,
        "oauth_exchange_active": False,
        "webhook_receiver_registered": False,
        "webhook_inbox_persistent": False,
        "provider_connected": False,
        "bank_reconciled": False,
        "ledger_written": False,
        "financial_closing_authorized": False,
        "real_payments_enabled": False,
    }


@app.get("/api/health/features/m2500", include_in_schema=False)
def backend_m2500_ci_only_persistence_contract():
    """Migração 032 SOMENTE CI descartável, sem acessar PostgreSQL."""
    return {
        "product": "FR Caixinha",
        "workstream": "AI_STUDIO",
        "contract": "AI_STUDIO_M2500_CI_OAUTH_INBOX_PERSISTENCE_V1",
        "ci_only_synthetic_migration_032": True,
        "database_migration_applied_locally": False,
        "oauth_exchange_active": False,
        "oauth_token_stored": False,
        "webhook_receiver_registered": False,
        "real_webhooks_active": False,
        "bank_reconciled": False,
        "ledger_written": False,
        "financial_closing_authorized": False,
        "real_payments_enabled": False,
        "pix_enabled": False,
    }


@app.get("/api/health/features/m2600", include_in_schema=False)
def backend_m2600_readonly_gateway_contract():
    """Somente informativo; não consulta Mercado Pago/OCI ou PostgreSQL."""
    from .mp_readonly_gateway import CONTRACT
    return {
        "product": "FR Caixinha",
        "workstream": "AI_STUDIO",
        "contract": CONTRACT,
        "gateway_unwired": True,
        "oci_staging_deployed": False,
        "provider_connected": False,
        "oauth_exchange_active": False,
        "webhook_live_active": False,
        "bank_reconciled": False,
        "ledger_written": False,
        "financial_closing_authorized": False,
        "real_payments_enabled": False,
    }


@app.get("/api/health/features/m2700", include_in_schema=False)
def backend_m2700_oci_plan_gate_contract():
    """Somente prova do código de verificação; NÃO é auditoria OCI em tempo real."""
    from .oci_staging_plan_guard import CONTRACT
    return {
        "product": "FR Caixinha",
        "workstream": "AI_STUDIO",
        "contract": CONTRACT,
        "oci_plan_guard_enabled": True,
        "oci_staging_deployed": False,
        "terraform_apply_authorized": False,
        "oauth_exchange_active": False,
        "provider_connected": False,
        "bank_reconciled": False,
        "ledger_written": False,
        "financial_closing_authorized": False,
        "real_payments_enabled": False,
    }


@app.get("/api/health/features/m2800", include_in_schema=False)
def backend_m2800_oci_mercado_pago_connectors_contract():
    """Somente presença de código: sem chamadas, tokens ou infraestrutura reais."""
    from .oci_secret_bridge import CONTRACT
    return {
        "product": "FR Caixinha",
        "workstream": "AI_STUDIO",
        "contract": CONTRACT,
        "oci_sdk_adapter_in_code": True,
        "mp_oauth_https_adapter_in_code": True,
        "oci_staging_deployed": False,
        "oci_vault_connected": False,
        "mp_app_registered": False,
        "mp_oauth_exchange_active": False,
        "webhook_receiver_registered": False,
        "bank_reconciled": False,
        "ledger_written": False,
        "financial_closing_authorized": False,
        "real_payments_enabled": False,
    }


@app.get("/api/health/features/m2900", include_in_schema=False)
def backend_m2900_staging_webhook_contract():
    """Pronto para injeção de dependências em staging, sem registrar receiver."""
    from .mp_webhook_staging_runtime import CONTRACT
    return {
        "workstream": "AI_STUDIO",
        "contract": CONTRACT,
        "webhook_staging_router_factory": True,
        "staging_migration_applied": False,
        "oci_staging_deployed": False,
        "real_webhooks_active": False,
        "bank_reconciled": False,
        "ledger_written": False,
        "financial_closing_authorized": False,
        "real_payments_enabled": False,
    }


@app.get("/api/health/features/m3000", include_in_schema=False)
def backend_m3000_oci_staging_server_contract():
    """Separado da API local; nenhum webhook ou OCI real no Termux."""
    from .oci_mp_staging_server import CONTRACT
    return {
        "workstream":"AI_STUDIO",
        "contract":CONTRACT,
        "oci_staging_server_module":True,
        "oci_staging_deployed":False,
        "webhook_receiver_registered_in_main":False,
        "mp_provider_connected":False,
        "bank_reconciled":False,
        "ledger_written":False,
        "real_payments_enabled":False,
        "financial_closing_authorized":False,
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
