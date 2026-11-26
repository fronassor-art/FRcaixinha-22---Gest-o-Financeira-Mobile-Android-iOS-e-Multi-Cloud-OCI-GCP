"""M41150: optional FastAPI-to-PostgreSQL capability path for a read-only ledger route.

The capability provider is deliberately absent from the default application. The
legacy database dependency remains the compatibility path while M40840 blocks
production financial SQL. A provider must independently validate the server
session, issue a one-use signed ticket, and bind it to a short-lived capability.
"""
from __future__ import annotations

import inspect
import os
import re
from typing import AsyncGenerator, Protocol
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status

from .database import get_db_pool, get_rls_db_connection
from .dependencies import AuthenticatedSession, get_current_session
from .m40610_verified_rls_session import (
    UnverifiedRLSSession,
    require_verified_rls_session,
)
from .m40840_financial_sql_release_no_go import (
    FinancialSQLReleaseBlocked,
    require_nonproduction_financial_sql,
)
from .m41050_session_context_seal_prototype import (
    InvalidSessionCapability,
    install_session_capability,
    validate_session_capability,
)

READ_SCOPE = "READ_ENTRIES"
PROVIDER_STATE_ATTRIBUTE = "frfinance_session_capability_provider"
_TICKET_PATTERN = re.compile(r"[0-9a-f]{64}\Z")


class SessionCapabilityProvider(Protocol):
    """Runtime-supplied issuer/binder; no signing key is held by this module."""

    async def issue_ticket(
        self, session: AuthenticatedSession, *, scope: str
    ) -> object: ...

    async def bind_ticket(self, ticket: str, *, tenant_id: UUID) -> object: ...


class InvalidSessionTicket(ValueError):
    """Constant error that never exposes a ticket."""


def validate_signed_session_ticket(value: object) -> str:
    """Accept only the opaque lowercase 256-bit ticket form."""
    if type(value) is not str or _TICKET_PATTERN.fullmatch(value) is None:
        raise InvalidSessionTicket("M41150_INVALID_SESSION_TICKET")
    return value


async def _provider_call(provider: object, method_name: str, *args, **kwargs):
    method = getattr(provider, method_name, None)
    if not callable(method):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Autorização financeira indisponível.",
        )
    try:
        result = method(*args, **kwargs)
        if not inspect.isawaitable(result):
            raise TypeError("M41150_PROVIDER_MUST_BE_ASYNC")
        return await result
    except Exception:
        # Do not disclose ticket, capability, key, DSN, or issuer errors.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Autorização financeira indisponível.",
        ) from None


def _directory_tenant(request: Request, session: AuthenticatedSession) -> UUID:
    if getattr(session, "role", None) != "TENANT_ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Diretório contábil exclusivo do administrador.",
        )
    value = getattr(session, "tenant_id", None)
    target = request.path_params.get("tenant_id")
    try:
        tenant = UUID(value) if isinstance(value, str) else None
    except (ValueError, TypeError, AttributeError):
        tenant = None
    if (tenant is None or tenant.int == 0 or str(tenant) != value
            or target != value):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Caixinha fora do escopo da sessão.",
        )
    return tenant


async def _capability_db_connection(
    request: Request,
    session: AuthenticatedSession,
    provider: SessionCapabilityProvider,
    tenant: UUID,
) -> AsyncGenerator:
    try:
        require_verified_rls_session(session)
    except UnverifiedRLSSession:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sessão financeira não verificada ou expirada.",
        ) from None

    # M40840 stays authoritative: provider presence never enables production.
    try:
        require_nonproduction_financial_sql(os.environ)
    except FinancialSQLReleaseBlocked:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Acesso financeiro bloqueado até revisão da fronteira SQL.",
        ) from None

    ticket_value = await _provider_call(
        provider, "issue_ticket", session, scope=READ_SCOPE
    )
    if ticket_value is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sessão ausente, revogada ou fora do escopo.",
        )
    try:
        ticket = validate_signed_session_ticket(ticket_value)
    except InvalidSessionTicket:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sessão financeira inválida.",
        ) from None

    capability_value = await _provider_call(
        provider, "bind_ticket", ticket, tenant_id=tenant
    )
    if capability_value is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sessão ausente, revogada ou fora do escopo.",
        )
    try:
        capability = validate_session_capability(capability_value)
    except InvalidSessionCapability:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sessão financeira inválida.",
        ) from None

    try:
        pool = await get_db_pool()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Acesso financeiro indisponível.",
        ) from None

    async with pool.acquire() as connection:
        try:
            # Only the opaque capability is installed. No caller-supplied
            # tenant, role, or user GUC participates in this route's RLS.
            async with connection.transaction(readonly=True):
                try:
                    await install_session_capability(connection, capability)
                except InvalidSessionCapability:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Sessão financeira inválida.",
                    ) from None
                yield connection
        finally:
            try:
                await connection.execute("RESET ALL; DISCARD TEMP;")
            except Exception:
                # Do not return a connection with unknown session state to pool.
                connection.terminate()
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Conexão financeira indisponível.",
                ) from None


async def get_ledger_directory_db_connection(
    request: Request,
    session: AuthenticatedSession = Depends(get_current_session),
) -> AsyncGenerator:
    """Capability path for the read-only ledger directory when a provider exists.

    The normal application has no provider until independent key custody,
    schema review, and staging evidence are accepted. Without it, preserve the
    existing M40840-gated dependency behavior.
    """
    provider = getattr(request.app.state, PROVIDER_STATE_ATTRIBUTE, None)
    if provider is None:
        async for connection in get_rls_db_connection(session):
            yield connection
        return

    try:
        require_verified_rls_session(session)
    except UnverifiedRLSSession:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sessão financeira não verificada ou expirada.",
        ) from None
    tenant = _directory_tenant(request, session)
    async for connection in _capability_db_connection(
        request, session, provider, tenant
    ):
        yield connection
