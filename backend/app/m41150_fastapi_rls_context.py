"""M41150/M41160/M41170: FastAPI capability path for six read-only ledger routes.

The capability provider is deliberately absent from the default application.
No legacy GUC-based database fallback is allowed. When the optional provider is
absent, the ledger routes fail closed with HTTP 503. A provider must independently
validate the server session, issue a one-use signed ticket, and bind it to a
short-lived capability.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime
import inspect
import os
import re
from typing import AsyncGenerator, Protocol
from uuid import UUID, uuid4

from fastapi import Depends, HTTPException, Request, status

from .database import get_db_pool
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
    """Runtime-supplied issuer/binder; no signing key is held by this module.

    M41230: binding requires issuer authorization of the exact target transaction.
    Independent real issuer/process custody is pending; no provider is enabled.
    """

    async def issue_ticket(
        self, session: AuthenticatedSession, *, scope: str, request_nonce: UUID
    ) -> object: ...

    async def bind_ticket(
        self, ticket: str, *, tenant_id: UUID, backend_pid: int,
        virtual_xid: str, transaction_started_at: datetime, target_challenge: str,
    ) -> object: ...


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


def _ledger_tenant(request: Request, session: AuthenticatedSession) -> UUID:
    if getattr(session, "role", None) != "TENANT_ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Livro-razão exclusivo do administrador.",
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


async def _require_bound_read_claims(connection: object, expected: tuple) -> None:
    """Compare SQL's verified claims, not the opaque token's shape.

    The fixed SQL interface is the existing disposable prototype contract.
    Missing function/privilege or malformed results never fall back.
    """
    try:
        rows = await connection.fetch(
            "SELECT user_id, role_name, tenant_id, scope_name, session_id, request_nonce "
            "FROM m41050.current_claims_v4()"
        )
        if not isinstance(rows, list):
            raise TypeError("M41190_INVALID_SQL_CLAIMS")
        if len(rows) != 1:
            matches = False
        else:
            row = rows[0]
            matches = (
                row["user_id"], row["role_name"],
                row["tenant_id"], row["scope_name"], row["session_id"],
                row["request_nonce"],
            ) == expected
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Autorização financeira indisponível.",
        ) from None
    if not matches:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sessão financeira inválida.",
        )


async def _read_transaction_identity(connection: object) -> tuple[int, str, datetime]:
    """Read server-owned identity of the current top-level transaction."""
    try:
        row = await connection.fetchrow(
            "SELECT pg_catalog.pg_backend_pid() AS backend_pid, "
            "l.virtualxid AS virtual_xid, "
            "pg_catalog.transaction_timestamp() AS transaction_started_at "
            "FROM pg_catalog.pg_locks AS l "
            "WHERE l.pid=pg_catalog.pg_backend_pid() "
            "AND l.locktype='virtualxid' AND l.mode='ExclusiveLock' "
            "AND l.granted AND l.virtualxid=l.virtualtransaction"
        )
        pid, vxid, started = row["backend_pid"], row["virtual_xid"], row["transaction_started_at"]
        if (type(pid) is not int or pid <= 0 or type(vxid) is not str
                or re.fullmatch(r"[0-9]+/[0-9]+", vxid) is None
                or not isinstance(started, datetime) or started.utcoffset() is None):
            raise ValueError("M41220_INVALID_TRANSACTION_IDENTITY")
        return pid, vxid, started
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Autorização financeira indisponível.",
        ) from None


async def _read_target_challenge(connection: object, ticket: str, tenant: UUID) -> str:
    """Require a transaction-local SQL proof; never synthesize or fall back."""
    try:
        value = await connection.fetchval(
            "SELECT m41050.read_target_challenge($1,$2)", ticket, tenant
        )
        return validate_signed_session_ticket(value)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Autorização financeira indisponível.",
        ) from None


@asynccontextmanager
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

    # Fresh server nonce, never supplied by a header, body or query parameter.
    # The issuer signs this nonce and SQL copies it from the consumed ticket.
    request_nonce = uuid4()
    expected_claims = (
        UUID(session.user_id), session.role, tenant, READ_SCOPE,
        UUID(session.verified_session_id), request_nonce,
    )

    # M40840 stays authoritative: provider presence never enables production.
    try:
        require_nonproduction_financial_sql(os.environ)
    except FinancialSQLReleaseBlocked:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Acesso financeiro bloqueado até revisão da fronteira SQL.",
        ) from None

    ticket_value = await _provider_call(
        provider, "issue_ticket", session, scope=READ_SCOPE,
        request_nonce=request_nonce,
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

    try:
        require_verified_rls_session(session)
    except UnverifiedRLSSession:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sessão financeira não verificada ou expirada.",
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
                backend_pid, virtual_xid, transaction_started_at = await _read_transaction_identity(connection)
                target_challenge = await _read_target_challenge(connection, ticket, tenant)
                capability_value = await _provider_call(
                    provider, "bind_ticket", ticket, tenant_id=tenant,
                    backend_pid=backend_pid, virtual_xid=virtual_xid,
                    transaction_started_at=transaction_started_at,
                    target_challenge=target_challenge,
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
                    await install_session_capability(connection, capability)
                except InvalidSessionCapability:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Sessão financeira inválida.",
                    ) from None
                await _require_bound_read_claims(connection, expected_claims)
                try:
                    require_verified_rls_session(session)
                except UnverifiedRLSSession:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Sessão financeira não verificada ou expirada.",
                    ) from None
                yield connection
        finally:
            try:
                await connection.execute("RESET ALL; DISCARD TEMP;")
            except BaseException as exc:
                # Cancellation during reset is also an unknown session state.
                connection.terminate()
                if not isinstance(exc, Exception):
                    raise
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Conexão financeira indisponível.",
                ) from None


async def get_ledger_readonly_db_connection(
    request: Request,
    session: AuthenticatedSession = Depends(get_current_session),
) -> AsyncGenerator:
    """Capability path for ledger reads; absent provider fails closed (M41170)."""
    provider = getattr(request.app.state, PROVIDER_STATE_ATTRIBUTE, None)
    if provider is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Acesso ao livro-razão indisponível.",
        )

    try:
        require_verified_rls_session(session)
    except UnverifiedRLSSession:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sessão financeira não verificada ou expirada.",
        ) from None
    tenant = _ledger_tenant(request, session)
    # Propagate the consumer's exception into the transaction before release.
    async with _capability_db_connection(
        request, session, provider, tenant
    ) as connection:
        yield connection
