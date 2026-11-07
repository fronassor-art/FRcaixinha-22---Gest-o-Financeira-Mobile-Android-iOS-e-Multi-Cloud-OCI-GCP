"""
FRcaixinha 2.2 — Gerenciador Transacional de Banco de Dados com RLS
Contrato Técnico Mestre (Cláusulas 1.2, 2.3, 2.8, 14.1 e 16.2)

PADRÕES DE SEGURANÇA:
1. app.current_user_id e app.current_tenant_id são definidos EXCLUSIVAMENTE pelo backend após validação de sessão.
2. NUNCA aceita esses valores de parâmetros, cabeçalhos ou payloads enviados pelo cliente.
3. Utiliza 'SET LOCAL' dentro de transação, garantindo escopo limitado à requisição.
4. Executa 'RESET ALL' / 'DISCARD TEMP' ao liberar a conexão para a pool, impedindo contaminação cruzada.
"""

import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional
from fastapi import Depends, HTTPException, status
from .config import settings
from .dependencies import get_current_session, AuthenticatedSession

# Variável de pool global
_db_pool = None

async def get_db_pool():
    """Inicializa e retorna o pool de conexões PostgreSQL (asyncpg)."""
    global _db_pool
    if _db_pool is None:
        if not settings.DATABASE_URL or not settings.DATABASE_URL.startswith("postgres"):
            raise RuntimeError(
                "DATABASE_URL não configurada ou não aponta para instância PostgreSQL válida."
            )
        try:
            import asyncpg
            _db_pool = await asyncpg.create_pool(
                dsn=settings.DATABASE_URL,
                min_size=2,
                max_size=20,
                command_timeout=30,
            )
        except ImportError:
            raise RuntimeError(
                "Driver asyncpg não instalado. Execute 'pip install -r backend/requirements.txt'."
            )
    return _db_pool


async def close_db_pool():
    """Encerra graciosamente o pool de conexões."""
    global _db_pool
    if _db_pool is not None:
        await _db_pool.close()
        _db_pool = None


async def get_rls_db_connection(
    session: AuthenticatedSession = Depends(get_current_session)
) -> AsyncGenerator:
    """
    Injeta conexão transacional com RLS configurado de forma estrita no PostgreSQL.
    Os parâmetros são extraídos EXCLUSIVAMENTE da sessão autenticada no servidor.
    """
    if not settings.is_database_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Banco de dados PostgreSQL não conectado. Operação financeira ou de dados recusada com segurança."
        )
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        # Inicia transação explícita
        tx = conn.transaction()
        await tx.start()
        try:
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
