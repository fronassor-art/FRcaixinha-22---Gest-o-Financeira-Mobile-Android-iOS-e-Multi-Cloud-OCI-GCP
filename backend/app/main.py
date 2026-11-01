"""
FRcaixinha 2.2 — Entrada Principal do Backend FastAPI
Contrato Técnico Mestre (Cláusulas 1.2, 14.1 e 16.2)
"""

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from .config import settings
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
