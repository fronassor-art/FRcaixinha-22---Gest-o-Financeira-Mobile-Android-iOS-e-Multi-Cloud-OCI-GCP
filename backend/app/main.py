"""
FR Finance — backend da frente AI Studio.
Contrato Tecnico Mestre FR Finance exclusivo deste repositorio; FR Caixinha 2.2 independente.
"""

from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from .cookie_origin_guard import allow_cookie_request
from .config import settings
from .dependencies import auth_database_url, auth_verifier_database_url
from .security import auth_rate_limit_key
from .mp_orders_webhook import OrdersIngressBinding, create_orders_staging_router
from time import time as _epoch_seconds
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
from .routers import mercado_pago_oauth as _mercado_pago_oauth
from .routers import auth, tenants, invitations, master, contributions, loans, ledger, consents, closings, audit, member_cycle_previews, financial_integrity_previews, member_lifecycle_sandbox, member_lifecycle_reviews, member_obligations, pix_automation, notifications, cycle_contribution_price

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
    # Cookie sessions can be sent automatically by browsers; unlike bearer
    # tokens they require an explicit same-origin check for writes.
    allowed = allow_cookie_request(
        method=request.method,
        session_cookie_present=settings.SESSION_COOKIE_NAME in request.cookies,
        origins=request.headers.getlist("origin"),
        allowed_origins=settings.BACKEND_CORS_ORIGINS,
    )
    if not allowed:
        response = JSONResponse(
            status_code=403,
            content={"detail":"Origem não autorizada para sessão com cookie."},
        )
    else:
        response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    # Tokens de sessão, convites e dados SaaS nunca devem ser guardados por
    # proxies, navegadores compartilhados ou previews externos.
    response.headers["Referrer-Policy"] = "no-referrer"
    if request.url.path.startswith(("/api/v1/", "/api/health")):
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
app.include_router(cycle_contribution_price.router, prefix=settings.API_V1_STR)
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
app.include_router(pix_automation.router, prefix=settings.API_V1_STR)
app.include_router(notifications.router, prefix=settings.API_V1_STR)
app.include_router(_mercado_pago_oauth.router, prefix=settings.API_V1_STR)

# M38970: reuse the EXISTING main FastAPI for signed Mercado Pago Orders.
# No second ASGI service, no second PostgreSQL, and no live processing here.
# The existing HMAC verifier remains the sole request validator. Durable
# tenant/seller inbox + secret-store callbacks must be injected by a reviewed
# deployment; absent binding means 503, not a fabricated bank settlement.
def _existing_mp_ingress_binding() -> OrdersIngressBinding:
    binding = getattr(app.state, "mp_orders_ingress_runtime", None)
    if (type(binding) is not OrdersIngressBinding
            or binding.seller_registry_verified is not True
            or binding.secret_store_verified is not True
            or binding.durable_inbox_verified is not True
            or binding.ingress_https_verified is not True
            or binding.sandbox_only is not True):
        raise RuntimeError("FR Finance Orders inbox unavailable")
    return binding


async def _resolve_mp_order_seller(seller_id: str):
    return await _existing_mp_ingress_binding().resolve_account(seller_id)


async def _load_mp_order_secret(account):
    return await _existing_mp_ingress_binding().load_signing_secret(account)


async def _persist_mp_signed_order(event):
    return await _existing_mp_ingress_binding().persist_event(event)


app.include_router(create_orders_staging_router(
    resolve_account=_resolve_mp_order_seller,
    load_signing_secret=_load_mp_order_secret,
    persist_event=_persist_mp_signed_order,
    now_ms=lambda: int(_epoch_seconds() * 1000),
    allow_live_ingest=False,  # Real payments remain OFF until commercial E2E.
))


# M2040: endpoints de evidencias SINTETICAS apenas na CI efemera com opt-in.
# Nao registrar no Termux ou em producao mesmo que a flag esteja ligada.
_M2040_CI_EVIDENCE_READS = (
    os.getenv("FRCAIXINHA_CI_ISOLATED") == "1"
    and os.getenv("AI_STUDIO_M2040_CI_EVIDENCE_READS") == "1"
    and os.getenv("ENVIRONMENT", "development") != "production"
)
if _M2040_CI_EVIDENCE_READS:
    app.include_router(_sandbox_evidence_ci.router, prefix=settings.API_V1_STR)

# M37460: endpoint CI para contrato SaaS autenticado. Requer flags restritas,
# acesso autenticado ao backend e dependencias de CI; nunca em Termux/OCI real.
# As dependencias de contrato/executor recusam por padrao (503).
from .routers import saas_authenticated_contract_ci as _saas_authenticated_contract_ci
if _saas_authenticated_contract_ci.ci_endpoint_allowed(os.environ):
    app.include_router(_saas_authenticated_contract_ci.router, prefix=settings.API_V1_STR)


# M38990: the existing FastAPI can host a single, strictly opt-in email
# outbox consumer. Without operator review and M047 schema verification,
# startup performs NO email, token or database queue work.
@app.on_event("startup")
async def _original_frfinance_access_delivery_startup():
    # Keep existing Termux server fully functional when the optional queue
    # is disabled, even if the optional AES dependency is unavailable.
    if os.environ.get("FR_FINANCE_ACCESS_MAIL_ENABLE") != "REVIEWED_SINGLE_DB":
        if os.environ.get("FR_FINANCE_ACCESS_MAIL_WORKER") == "EXPLICITLY_APPROVED":
            raise RuntimeError("OUTBOX_WORKER_WITHOUT_APPROVED_SCHEMA")
        return
    from .access_delivery_pg18 import (
        AccessQueueBlocked, install_existing_access_delivery,
    )
    installed = await install_existing_access_delivery(app, os.environ)
    if os.environ.get("FR_FINANCE_ACCESS_MAIL_WORKER") == "EXPLICITLY_APPROVED":
        if not installed or not hasattr(app.state, "access_delivery_worker"):
            raise AccessQueueBlocked("OUTBOX_WORKER_WITHOUT_APPROVED_SCHEMA")
        async def _single_existing_api_worker():
            while True:
                try:
                    await app.state.access_delivery_worker.dispatch_one()
                except AccessQueueBlocked:
                    # Never log SMTP credentials, recipient or access tokens.
                    # Unknown submission states remain QUARANTINED, no retries.
                    pass
                await asyncio.sleep(15)
        app.state.access_delivery_worker_task = asyncio.create_task(
            _single_existing_api_worker()
        )


@app.on_event("shutdown")
async def _original_frfinance_access_delivery_shutdown():
    task = getattr(app.state, "access_delivery_worker_task", None)
    if task is not None:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


@app.get("/api/health")
def health_check():
    return {
        "status": "ONLINE",
        "app": "FR Finance",
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
        "product": "FR Finance",
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
        "product": "FR Finance",
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
        "product": "FR Finance",
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
        "product": "FR Finance",
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
        "product": "FR Finance",
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
        "product": "FR Finance",
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
        "product": "FR Finance",
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
        "product": "FR Finance",
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
        "product": "FR Finance",
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
        "product": "FR Finance",
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
        "product": "FR Finance",
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
        "product": "FR Finance",
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
        "product": "FR Finance",
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


@app.get("/api/health/features/m3100", include_in_schema=False)
def backend_m3100_mp_provider_account_contract():
    """Conta de provedor não é papel de usuário do SaaS."""
    from .mp_provider_account_contract import CONTRACT
    return {
        "workstream":"AI_STUDIO",
        "contract":CONTRACT,
        "seller_is_application_role":False,
        "provider_account_is_technical_identifier":True,
        "mercado_pago_real_connected":False,
        "ledger_written":False,
        "bank_reconciled":False,
        "real_payments_enabled":False,
    }


@app.get("/api/health/features/m3200", include_in_schema=False)
def backend_m3200_oci_recovery_policy():
    """Só contrato de recuperação, nunca estado real da OCI."""
    from .oci_recovery_policy import CONTRACT
    return {
        "workstream":"AI_STUDIO",
        "contract":CONTRACT,
        "backup_recovery_policy_in_code":True,
        "oci_staging_deployed":False,
        "terraform_apply_authorized":False,
        "financial_closing_authorized":False,
        "bank_reconciled":False,
        "ledger_written":False,
        "real_payments_enabled":False,
    }


@app.get("/api/health/features/m3300", include_in_schema=False)
def backend_m3300_webhook_stream_protection():
    """Proteções do código sem montar webhook no FastAPI local."""
    return {
        "workstream":"AI_STUDIO",
        "contract":"AI_STUDIO_M3300_MP_WEBHOOK_INGRESS_HARDENING_V1",
        "signed_webhook_stream_limit_bytes":16384,
        "duplicate_signed_headers_rejected":True,
        "staging_router_not_mounted_locally":True,
        "oci_staging_deployed":False,
        "real_webhooks_active":False,
        "bank_reconciled":False,
        "ledger_written":False,
        "real_payments_enabled":False,
    }


@app.get("/api/health/features/m3700", include_in_schema=False)
def backend_m3700_pix_persistence_staging_contract():
    return {
        "workstream":"AI_STUDIO",
        "contract":"AI_STUDIO_M3700_PIX_STAGING_PERSISTENCE_GUARD_V1",
        "staging_migration_applied":False,
        "real_payment_execution_active":False,
        "oci_staging_deployed":False,
        "bank_reconciled":False,
        "ledger_written":False,
        "financial_closing_authorized":False,
    }




@app.get("/api/health/features/m19000", include_in_schema=False)
async def backend_m19000_local_notification_contract():
    from .routers.notifications import _local_enabled, _schema_ready
    schema_ready = await _schema_ready()
    return {
        "workstream": "AI_STUDIO",
        "contract": "AI_STUDIO_M19000_LOCAL_IN_APP_NOTIFICATIONS_V1",
        "local_notification_flag_configured": _local_enabled(),
        "local_inbox_schema_verified": schema_ready,
        "local_in_app_ready": schema_ready,
        "local_inbox_schema_expected_after_031": True,
        "selftest_route_registered": True,
        "read_receipt_route_registered": True,
        "keyset_cursor_server_scope_enabled": True,
        "local_migration_applied": schema_ready,
        "external_email_active": False,
        "external_push_active": False,
        "external_whatsapp_active": False,
        "provider_events_authenticated": False,
        "real_payments_enabled": False,
        "bank_reconciled": False,
        "ledger_written": False,
        "financial_closing_authorized": False,
        "payout_authorized": False,
        "oci_staging_deployed": False,
    }


@app.get("/api/health/features/m18000", include_in_schema=False)
def backend_m18000_notification_ci_auth_gateway():
    return {
        "workstream": "AI_STUDIO",
        "contract": "AI_STUDIO_M18000_NOTIFICATION_CI_SESSION_GATE_V1",
        "session_scope_guard_prepared": True,
        "ci_disposable_reader_prepared": True,
        "read_receipt_ci_only_prepared": True,
        "ci_keyset_cursor_integrated": True,
        "route_readiness_requires_auth": True,
        "app_uses_real_inbox": False,
        "real_inbox_api_connected": False,
        "real_read_receipt_active": False,
        "production_event_source_authenticated": False,
        "local_migration_applied": False,
        "oci_staging_deployed": False,
        "in_app_delivery_active": False,
        "email_send_active": False,
        "push_send_active": False,
        "whatsapp_send_active": False,
        "real_payments_enabled": False,
        "bank_reconciled": False,
        "ledger_written": False,
        "financial_closing_authorized": False,
        "payout_authorized": False,
    }


@app.get("/api/health/features/m17000", include_in_schema=False)
def backend_m17000_notification_source_boundary():
    """Signed synthetic policy exercises, without production source binding."""
    from .notification_origin_attestation import CONTRACT as SOURCE_CONTRACT
    return {
        "workstream": "AI_STUDIO",
        "contract": "AI_STUDIO_M17000_NOTIFICATION_ORIGIN_PAGE_GUARDS_V1",
        "origin_contract": SOURCE_CONTRACT,
        "synthetic_hmac_source_validation": True,
        "scoped_hmac_keyset_cursor_prepared": True,
        "recipient_page_integrity_checked": True,
        "timestamp_skew_limit_checked": True,
        "role_recipient_scope_checked": True,
        "staging_041_active_link_policy_prepared": True,
        "authenticated_production_events": False,
        "production_signing_key_configured": False,
        "real_inbox_api_connected": False,
        "local_migration_applied": False,
        "oci_staging_deployed": False,
        "in_app_delivery_active": False,
        "email_send_active": False,
        "push_send_active": False,
        "whatsapp_send_active": False,
        "real_payments_enabled": False,
        "bank_reconciled": False,
        "ledger_written": False,
        "financial_closing_authorized": False,
        "payout_authorized": False,
    }


@app.get("/api/health/features/m16000", include_in_schema=False)
def backend_m16000_notification_database_ci_contract():
    return {
        "workstream": "AI_STUDIO",
        "contract": "AI_STUDIO_M16000_NOTIFICATION_STAGING_PG_CI_ONLY_V1",
        "disposable_outbox_inbox_schema_prepared": True,
        "disposable_pg16_pg18_tests_registered": True,
        "ci_only_recipient_rls_policy": True,
        "ci_only_read_receipt_contract": True,
        "local_migration_applied": False,
        "oci_staging_deployed": False,
        "real_inbox_api_connected": False,
        "authenticated_producer_connected": False,
        "in_app_delivery_active": False,
        "email_send_active": False,
        "push_send_active": False,
        "whatsapp_send_active": False,
        "real_payments_enabled": False,
        "bank_reconciled": False,
        "ledger_written": False,
        "financial_closing_authorized": False,
        "payout_authorized": False,
    }


@app.get("/api/health/features/m15000", include_in_schema=False)
def backend_m15000_notification_policy_contract():
    from .notifications_policy import CONTRACT as POLICY
    return {
        "workstream":"AI_STUDIO",
        "contract":"AI_STUDIO_M15000_NOTIFICATION_POLICY_OFFLINE_V1",
        "policy_contract":POLICY,
        "notification_kinds_validated":True,
        "recipient_tenant_role_binding_policy":True,
        "external_channel_consent_policy":True,
        "deterministic_dedupe_preview":True,
        "notification_center_ui_available":True,
        "durable_inbox_persisted":False,
        "in_app_dispatch_active":False,
        "email_send_active":False,
        "push_send_active":False,
        "whatsapp_send_active":False,
        "schedule_approved":False,
        "real_payments_enabled":False,
        "bank_reconciled":False,
        "ledger_written":False,
        "payout_authorized":False,
        "financial_closing_authorized":False,
    }


@app.get("/api/health/features/m14000", include_in_schema=False)
def backend_m14000_disposable_audit_contract():
    return {
        "workstream": "AI_STUDIO",
        "contract": "AI_STUDIO_M14000_STAGING_INCIDENT_AUDIT_DISPOSABLE_V1",
        "staging_sql_prepared": True,
        "ci_only_pg16_pg18_exercised": True,
        "append_only_event_policy": True,
        "staging_worker_rpc_scope": True,
        "local_migration_applied": False,
        "oci_staging_deployed": False,
        "real_audit_history_connected": False,
        "operator_authenticated": False,
        "bank_reconciled": False,
        "real_payments_enabled": False,
        "financial_effect_applied": False,
        "ledger_written": False,
        "payout_authorized": False,
        "financial_closing_authorized": False,
        "real_provider_get_active": False,
    }


@app.get("/api/health/features/m13000", include_in_schema=False)
def backend_m13000_checkpoint_readiness_contract():
    from .mp_orders_replay_checkpoint import CONTRACT as CHECKPOINT
    from .mp_orders_staging_readiness import CONTRACT as READINESS
    return {
        "workstream": "AI_STUDIO",
        "contract": "AI_STUDIO_M13000_CHECKPOINT_READINESS_OFFLINE_V1",
        "restart_contract": CHECKPOINT,
        "readiness_contract": READINESS,
        "snapshot_prefix_consistency_checked": True,
        "claimed_high_watermark_compared": True,
        "staging_requirements_enumerated": True,
        "readiness_claims_typed": True,
        "checkpoint_persisted": False,
        "checkpoint_source_authenticated": False,
        "operator_identity_authenticated": False,
        "globally_unique_idempotency": False,
        "real_bank_reconciled": False,
        "independent_bank_evidence_verified": False,
        "oci_staging_deployed": False,
        "real_payments_enabled": False,
        "ledger_written": False,
        "financial_effect_applied": False,
        "payout_authorized": False,
        "financial_closing_authorized": False,
        "migration_apply_authorized": False,
    }


@app.get("/api/health/features/m12000", include_in_schema=False)
def backend_m12000_replay_rollback_contract():
    from .mp_orders_replay_history import CONTRACT as HISTORY
    return {
        "workstream": "AI_STUDIO",
        "contract": "AI_STUDIO_M12000_REPLAY_ROLLBACK_GUARD_OFFLINE_V1",
        "history_contract": HISTORY,
        "offline_monotonic_history_guard": True,
        "rollback_and_duplicate_snapshot_rejected": True,
        "cross_tenant_order_payment_alias_rejected": True,
        "closed_auth_state_remains_blocked": True,
        "history_persisted": False,
        "operator_authenticated": False,
        "distributed_idempotency_registry": False,
        "real_provider_connected": False,
        "real_bank_statement_connected": False,
        "real_payments_enabled": False,
        "bank_reconciled": False,
        "ledger_written": False,
        "financial_effect_applied": False,
        "financial_closing_authorized": False,
        "payout_authorized": False,
        "oci_staging_deployed": False,
    }


@app.get("/api/health/features/m11000", include_in_schema=False)
def backend_m11000_retry_alias_integrity_contract():
    return {
        "workstream": "AI_STUDIO",
        "contract": "AI_STUDIO_M11000_RETRY_ALIAS_INTEGRITY_OFFLINE_V1",
        "complete_retry_snapshot_fingerprint": True,
        "strict_recovery_attempt_binding": True,
        "local_batch_order_payment_alias_rejected": True,
        "deterministic_negative_synthetic_regressions": True,
        "persisted_deduplication_registry": False,
        "real_provider_order_get": False,
        "real_bank_evidence": False,
        "operator_signatures_verified": False,
        "audit_log_persisted": False,
        "oci_staging_deployed": False,
        "real_payments_enabled": False,
        "bank_reconciled": False,
        "ledger_written": False,
        "financial_effect_applied": False,
        "payout_authorized": False,
        "financial_closing_authorized": False,
    }


@app.get("/api/health/features/m10200", include_in_schema=False)
def backend_m10200_case_integrity_contract():
    from .mp_orders_case_integrity import CONTRACT as INTEGRITY
    return {
        "workstream": "AI_STUDIO",
        "contract": "AI_STUDIO_M10200_CASE_INTEGRITY_BOUNDARIES_V1",
        "integrity_contract": INTEGRITY,
        "cross_component_binding_preflight": True,
        "queue_snapshot_consistency_preflight": True,
        "case_audit_persisted": False,
        "case_sources_authenticated": False,
        "distributed_recovery_lease_active": False,
        "real_orders_get_active": False,
        "real_bank_statement_connected": False,
        "oci_staging_deployed": False,
        "real_payments_enabled": False,
        "bank_reconciled": False,
        "ledger_written": False,
        "financial_effect_applied": False,
        "financial_closing_authorized": False,
        "payout_authorized": False,
    }


@app.get("/api/health/features/m9400", include_in_schema=False)
def backend_m9400_case_timeline_queue_contract():
    from .mp_orders_incident_timeline import CONTRACT as TIMELINE
    from .mp_orders_tenant_queue import CONTRACT as QUEUE
    return {
        "workstream": "AI_STUDIO",
        "contract": "AI_STUDIO_M9400_CASE_TIMELINE_QUEUE_PREFLIGHT_V1",
        "timeline_contract": TIMELINE,
        "queue_contract": QUEUE,
        "deterministic_chain_preview": True,
        "bounded_per_tenant_get_candidates": True,
        "cross_tenant_queue_rejected": True,
        "audit_event_persisted": False,
        "operator_identity_authenticated": False,
        "get_worker_live": False,
        "oci_staging_deployed": False,
        "real_payments_enabled": False,
        "bank_reconciled": False,
        "ledger_written": False,
        "financial_effect_applied": False,
        "financial_closing_authorized": False,
        "payout_authorized": False,
    }


@app.get("/api/health/features/m8600", include_in_schema=False)
def backend_m8600_discrepancy_circuit_contract():
    from .mp_orders_evidence_discrepancy import CONTRACT as EVIDENCE
    from .mp_orders_readonly_circuit import CONTRACT as CIRCUIT
    return {
        "workstream": "AI_STUDIO",
        "contract": "AI_STUDIO_M8600_DISCREPANCY_CIRCUIT_OFFLINE_V1",
        "evidence_contract": EVIDENCE,
        "circuit_contract": CIRCUIT,
        "three_source_claim_comparison_only": True,
        "readonly_circuit_policy_only": True,
        "cross_tenant_evidence_rejected": True,
        "review_digest_persisted": False,
        "recovery_circuit_persistent": False,
        "real_provider_connected": False,
        "real_bank_statement_reader_connected": False,
        "oci_staging_deployed": False,
        "real_payments_enabled": False,
        "bank_reconciled": False,
        "ledger_written": False,
        "financial_effect_applied": False,
        "financial_closing_authorized": False,
        "payout_authorized": False,
    }


@app.get("/api/health/features/m7900", include_in_schema=False)
def backend_m7900_incident_readonly_contract():
    from .mp_orders_incident_ops import CONTRACT as INCIDENTS
    from .mp_orders_recovery_scheduler import CONTRACT as RECOVERY
    return {
        "workstream": "AI_STUDIO",
        "contract": "AI_STUDIO_M7900_INCIDENT_REVIEW_READONLY_RECOVERY_V1",
        "incident_contract": INCIDENTS,
        "recovery_contract": RECOVERY,
        "immutable_review_preview": True,
        "bounded_get_retry_policy": True,
        "cross_tenant_case_rejected": True,
        "two_reviewer_preview": True,
        "incident_review_persisted_in_staging": False,
        "staging_m039_applied_locally": False,
        "oci_staging_deployed": False,
        "real_provider_connected": False,
        "real_bank_statement_reader_connected": False,
        "real_payments_enabled": False,
        "bank_reconciled": False,
        "ledger_written": False,
        "financial_effect_applied": False,
        "financial_closing_authorized": False,
        "payout_authorized": False,
    }


@app.get("/api/health/features/m7200", include_in_schema=False)
def backend_m7200_accounting_recovery_contract():
    from .mp_orders_holds import CONTRACT as HOLDS
    from .mp_orders_partial_refund import CONTRACT as PARTIAL_REFUND
    return {
        "workstream": "AI_STUDIO",
        "contract": "AI_STUDIO_M7200_RECONCILIATION_HOLDS_DISPOSABLE_LEDGER_V1",
        "reconciliation_holds_contract": HOLDS,
        "partial_refund_contract": PARTIAL_REFUND,
        "staging_reconciliation_hold_schema_prepared": True,
        "disposable_pg16_pg18_ledger_test_present": True,
        "orders_persisted_checkout_binding_hardened": True,
        "partial_refund_preview_present": True,
        "reconciliation_incident_logged_to_real_bank": False,
        "staging_m039_applied_locally": False,
        "oci_staging_deployed": False,
        "real_provider_connected": False,
        "real_bank_statement_reader_connected": False,
        "real_bank_balance_reader_connected": False,
        "real_payments_enabled": False,
        "real_pix_payout_active": False,
        "bank_reconciled": False,
        "ledger_written": False,
        "financial_effect_applied": False,
        "financial_closing_authorized": False,
        "payout_authorized": False,
    }


@app.get("/api/health/features/m6400", include_in_schema=False)
def backend_m6400_financial_staging_preflight():
    from .mp_orders_ledger_plan import CONTRACT as LEDGER
    from .mp_orders_ledger_plan import REVERSAL_CONTRACT as REVERSAL
    from .loan_credit_liquidity import CONTRACT as LIQUIDITY
    return {
        "workstream": "AI_STUDIO",
        "contract": "AI_STUDIO_M6400_STAGING_SQL_LEDGER_LIQUIDITY_PREFLIGHT_V1",
        "ledger_plan_contract": LEDGER,
        "reversal_plan_contract": REVERSAL,
        "liquidity_contract": LIQUIDITY,
        "staging_chain_ci_contract": "CI_PG16_PG18_M034_M038_V1",
        "staging_migrations_applied": False,
        "staging_sql_chain_executed_in_termux": False,
        "oci_staging_deployed": False,
        "ledger_plan_code_present": True,
        "reversal_preview_code_present": True,
        "credit_liquidity_preflight_code_present": True,
        "oci_apply_authorized": False,
        "real_bank_balance_reader_connected": False,
        "real_bank_statement_reader_connected": False,
        "provider_connected": False,
        "real_payments_enabled": False,
        "bank_reconciled": False,
        "ledger_written": False,
        "financial_effect_applied": False,
        "financial_closing_authorized": False,
        "payout_authorized": False,
    }


@app.get("/api/health/features/m5600", include_in_schema=False)
def backend_m5600_orders_journal_preflight_contract():
    from .mp_orders_reservation import CONTRACT as RESERVATION
    from .mp_orders_settlement import CONTRACT as SETTLEMENT
    from .mp_orders_recovery import CONTRACT as RECOVERY
    from .loan_payout_price import CONTRACT as PRICE
    return {
        "workstream": "AI_STUDIO",
        "contract": "AI_STUDIO_M5600_ORDERS_RESERVATION_CREDIT_CORRECTION_V1",
        "reservation_contract": RESERVATION,
        "settlement_contract": SETTLEMENT,
        "recovery_contract": RECOVERY,
        "payout_price_contract": PRICE,
        "loan_approval_creates_installments": False,
        "confirmed_payout_requires_tenant_timezone": True,
        "orders_staging_reservation_code_present": True,
        "three_source_settlement_preflight_present": True,
        "uncertain_pix_repost_allowed": False,
        "orders_m038_migration_applied": False,
        "real_bank_statement_reader_connected": False,
        "atomic_ledger_worker_connected": False,
        "provider_connected": False,
        "oci_staging_deployed": False,
        "real_payments_enabled": False,
        "real_pix_collection_active": False,
        "real_pix_payout_active": False,
        "bank_reconciled": False,
        "ledger_written": False,
        "financial_effect_applied": False,
        "financial_closing_authorized": False,
        "payout_authorized": False,
    }


@app.get("/api/health/features/m4800", include_in_schema=False)
def backend_m4800_orders_automation_contract():
    from .mp_orders_api import CONTRACT as ORDERS
    from .mp_oauth_rotation import CONTRACT as OAUTH
    from .mp_money_out_policy import CONTRACT as MONEY_OUT
    from .mp_orders_webhook import CONTRACT as ORDERS_WEBHOOK
    from .mp_orders_workflow import CONTRACT as WORKFLOW
    return {
        "workstream": "AI_STUDIO",
        "contract": "AI_STUDIO_M4800_MLB_ORDERS_CONNECT_MONEYOUT_MACRO_V1",
        "orders_contract": ORDERS,
        "oauth_contract": OAUTH,
        "money_out_contract": MONEY_OUT,
        "webhook_contract": ORDERS_WEBHOOK,
        "workflow_contract": WORKFLOW,
        "orders_gateway_code_present": True,
        "orders_webhook_not_publicly_mounted": True,
        "oauth_tokens_server_only": True,
        "money_out_unsigned_production_blocked": True,
        "orders_staging_migrations_applied": False,
        "oci_staging_deployed": False,
        "provider_connected": False,
        "bank_reconciled": False,
        "ledger_written": False,
        "financial_effect_applied": False,
        "financial_closing_authorized": False,
        "real_payments_enabled": False,
    }


@app.get("/api/health/features/m4000", include_in_schema=False)
def backend_m4000_pix_macro_contract():
    from .pix_automation_contract import CONTRACT as DOMAIN
    from .mp_pix_execution import CONTRACT as GATEWAY
    from .pix_automation_workflows import CONTRACT as WORKFLOW
    return {
        "workstream":"AI_STUDIO",
        "contract":"AI_STUDIO_M4000_PIX_LOAN_AUTOMATION_MACRO_V1",
        "domain_contract":DOMAIN,
        "provider_contract":GATEWAY,
        "workflow_contract":WORKFLOW,
        "pix_app_routes_registered":True,
        "real_pix_collection_active":False,
        "real_pix_payout_active":False,
        "oci_staging_deployed":False,
        "staging_035_applied":False,
        "bank_reconciled":False,
        "ledger_written":False,
        "financial_closing_authorized":False,
        "real_payments_enabled":False,
    }


@app.get("/api/health/features/m3800", include_in_schema=False)
def backend_pix_automation_contract():
    from .routers.pix_automation import CONTRACT
    return {
        "workstream":"AI_STUDIO","contract":CONTRACT,
        "member_pix_workflow_code_present":True,
        "loan_payout_management_in_app":True,
        "real_payments_enabled":False,
        "bank_reconciled":False,
        "ledger_written":False,
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
