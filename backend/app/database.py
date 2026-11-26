"""
FR Finance — Gerenciador Transacional de Banco de Dados com RLS
Contrato Técnico Mestre (Cláusulas 1.2, 2.3, 2.8, 14.1 e 16.2)

PADRÕES DE SEGURANÇA:
1. app.current_user_id e app.current_tenant_id são definidos EXCLUSIVAMENTE pelo backend após validação de sessão.
2. NUNCA aceita esses valores de parâmetros, cabeçalhos ou payloads enviados pelo cliente.
3. Utiliza 'SET LOCAL' dentro de transação, garantindo escopo limitado à requisição.
4. Executa 'RESET ALL' / 'DISCARD TEMP' ao liberar a conexão para a pool, impedindo contaminação cruzada.
"""

import os
import asyncio
import hashlib
import json
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional
from fastapi import Depends, HTTPException, Request, status
from .config import settings
from .dependencies import get_current_session, AuthenticatedSession
from .m40610_verified_rls_session import UnverifiedRLSSession, require_verified_rls_session

# Variável de pool global
_db_pool = None
_db_pool_binding = None
_db_pool_lock = asyncio.Lock()


def _pool_binding(dsn: str, env) -> str:
    """Process-local configuration fingerprint; never expose it or its inputs."""
    fields = [dsn, *(env.get(k) for k in (
        "ENVIRONMENT", "FRCAIXINHA_TERMUX_LOCAL_API",
        "AUTH_DATABASE_URL", "AUTH_VERIFIER_DATABASE_URL",
        "DATABASE_URL", "PIX_REAL", "PAGAMENTOS_REAIS", "ATIVACAO_REAL",
    ))]
    return hashlib.sha256(json.dumps(fields, ensure_ascii=True).encode()).hexdigest()


async def get_db_pool():
    """Inicializa e retorna o pool de conexões PostgreSQL (asyncpg)."""
    global _db_pool, _db_pool_binding
    from .m40840_financial_sql_release_no_go import require_nonproduction_financial_sql
    from .m40800_financial_dsn_guard import (
        FinancialDSNBlocked, require_financial_dsn_shape,
    )
    # Serialize creation/closure; a different valid DSN must never reuse
    # a connection pool created under another configuration.
    async with _db_pool_lock:
        require_nonproduction_financial_sql(os.environ)
        dsn = settings.DATABASE_URL
        env = dict(os.environ)
        binding = None
        if _db_pool is not None:
            require_financial_dsn_shape(settings.DATABASE_URL, os.environ)
            require_financial_dsn_shape(dsn, env)
            binding = _pool_binding(dsn, env)
            if _db_pool_binding != binding:
                raise RuntimeError("M40961_FINANCIAL_POOL_CONFIGURATION_CHANGED")
        if _db_pool is None:
            if not dsn or not dsn.startswith("postgres"):
                raise RuntimeError("DATABASE_URL não configurada ou inválida.")
            try:
                require_financial_dsn_shape(dsn, env)
                binding = _pool_binding(dsn, env)
                if os.environ.get("ENVIRONMENT") == "production":
                    from .production_auth_gate import require_production_auth
                    require_production_auth(os.environ)
            except (FinancialDSNBlocked, ValueError, RuntimeError):
                raise RuntimeError("M40800_FINANCIAL_DSN_BLOCKED") from None
            try:
                import asyncpg
            except ImportError:
                raise RuntimeError("Driver asyncpg não instalado.") from None
            candidate = await asyncpg.create_pool(
                dsn=dsn, min_size=2, max_size=20, command_timeout=30,
            )
            try:
                current_env = dict(os.environ)
                require_nonproduction_financial_sql(current_env)
                require_financial_dsn_shape(settings.DATABASE_URL, current_env)
                if _pool_binding(settings.DATABASE_URL, current_env) != binding:
                    raise RuntimeError("M40961_FINANCIAL_POOL_CONFIGURATION_CHANGED")
            except BaseException:
                # Discard only the newly-created client pool, not PostgreSQL.
                candidate.terminate()
                raise
            _db_pool = candidate
            _db_pool_binding = binding
        return _db_pool


async def close_db_pool():
    """Encerra graciosamente o pool de conexões."""
    global _db_pool, _db_pool_binding
    async with _db_pool_lock:
        if _db_pool is not None:
            await _db_pool.close()
            _db_pool = None
            _db_pool_binding = None


async def get_rls_db_connection(
    request: Request,
    session: AuthenticatedSession = Depends(get_current_session)
) -> AsyncGenerator:
    """
    Injeta conexão transacional com RLS configurado de forma estrita no PostgreSQL.
    Os parâmetros são extraídos EXCLUSIVAMENTE da sessão autenticada no servidor.
    """
    # M40610: fail before pool acquisition when the evidence is legacy/stale.
    try:
        require_verified_rls_session(session)
    except UnverifiedRLSSession:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sessão financeira não verificada ou expirada."
        ) from None

    # M41180: the legacy custom-GUC context is not an approved HTTP read boundary.
    # Contain GET/HEAD requests before acquiring the financial connection pool.
    # This does not remediate SQL GUC spoofing or issuer/credential custody.
    if request.method in {"GET", "HEAD"}:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Leitura financeira bloqueada até contexto SQL atestado."
        )

    if not settings.is_database_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Banco de dados PostgreSQL não conectado. Operação financeira ou de dados recusada com segurança."
        )
    # M40840: this role/GUC data plane is not yet approved for production.
    from .m40840_financial_sql_release_no_go import (
        FinancialSQLReleaseBlocked, require_nonproduction_financial_sql,
    )
    try:
        require_nonproduction_financial_sql(os.environ)
    except FinancialSQLReleaseBlocked:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Acesso financeiro bloqueado até revisão da fronteira SQL."
        ) from None
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        # Inicia transação explícita
        tx = conn.transaction()
        await tx.start()
        try:
            # M40932: Master uses this legacy RLS connection only for
            # read-only governance views while the independent SQL trust
            # boundary is unapproved. This is the FIRST SQL command after
            # BEGIN, before any untrusted GUC context is set. PostgreSQL
            # rejects ordinary DML/DDL even if an HTTP route guard is missed.
            # It is NOT a substitute for privileges, RLS, or issuer custody.
            if session.role == "MASTER":
                await conn.execute("SET TRANSACTION READ ONLY")

            # 1. Parâmetros de contexto transacional seguros via set_config (is_local=true equivale a SET LOCAL)
            user_id = str(session.user_id)
            role = str(session.role)
            tenant_id = str(session.tenant_id) if session.tenant_id else ""

            await conn.execute("SELECT set_config('app.current_user_id', $1, true);", user_id)
            await conn.execute("SELECT set_config('app.current_role', $1, true);", role)
            await conn.execute("SELECT set_config('app.current_tenant_id', $1, true);", tenant_id)

            yield conn

            await tx.commit()
        except BaseException as err:
            await tx.rollback()
            raise err
        finally:
            # 2. Higienização mandatória para asyncpg: limpa resíduos de sessão antes de retornar à pool
            await conn.execute("RESET ALL; DISCARD TEMP;")
