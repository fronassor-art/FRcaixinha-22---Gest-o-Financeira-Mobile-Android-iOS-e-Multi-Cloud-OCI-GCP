"""
FRcaixinha 2.2 — Entrada Principal do Backend FastAPI
Contrato Técnico Mestre (Cláusulas 1.2, 14.1 e 16.2)
"""

from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from .config import settings
from .dependencies import auth_database_url
import asyncio
import asyncpg
from .routers import auth, tenants, invitations, master, contributions, loans, ledger, consents, closings, audit

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
    if request.url.path.startswith(("/api/v1/", "/api/health/ready")):
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
app.include_router(loans.router, prefix=settings.API_V1_STR)
app.include_router(ledger.router, prefix=settings.API_V1_STR)
app.include_router(consents.router, prefix=settings.API_V1_STR)
app.include_router(closings.router, prefix=settings.API_V1_STR)
app.include_router(audit.router, prefix=settings.API_V1_STR)

@app.get("/api/health")
def health_check():
    return {
        "status": "ONLINE",
        "app": "FRcaixinha 2.2",
        "framework": "FastAPI (Python)",
        "database_backend": "PostgreSQL com Row-Level Security (RLS)",
        "database_configured": settings.is_database_configured,
        "environment": "sandbox-development"
    }


@app.get("/api/health/ready")
async def backend_readiness():
    """Verifica conexões e esquema de homologação sem modificar o PostgreSQL."""
    if not settings.is_database_configured:
        raise HTTPException(status_code=503, detail="PostgreSQL não configurado.")
    # Jamais marcar pronto em produção: o login atual é somente de homologação.
    auth_url = auth_database_url()
    try:
        finance = await asyncpg.connect(settings.DATABASE_URL, timeout=3, command_timeout=3)
        try:
            await finance.fetchval("SELECT 1")
        finally:
            await finance.close()
        auth = await asyncpg.connect(auth_url, timeout=3, command_timeout=3)
        try:
            structure_ok = await auth.fetchrow(
                "SELECT to_regclass('public.users') IS NOT NULL AS users_ok, "
                "to_regclass('public.credentials') IS NOT NULL AS credentials_ok, "
                "to_regclass('public.sessions') IS NOT NULL AS sessions_ok, "
                "to_regprocedure('public.auth_active_memberships(text)') IS NOT NULL AS links_ok"
            )
        finally:
            await auth.close()
        if not structure_ok or not all(structure_ok.values()):
            raise HTTPException(status_code=503, detail="Estrutura de autenticação ainda não validada.")
    except (asyncpg.PostgresError, OSError, asyncio.TimeoutError, TimeoutError):
        raise HTTPException(status_code=503, detail="Banco de homologação indisponível.")
    return {"status": "READY_FOR_TEST_AUTH", "scope": "LOCAL_HOMOLOGATION_ONLY"}
