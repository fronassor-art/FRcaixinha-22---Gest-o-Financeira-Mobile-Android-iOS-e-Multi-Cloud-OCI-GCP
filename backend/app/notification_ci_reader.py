"""M18000 — executable CI-only notification read/receipt adapter.

Never imported by the HTTP router; no application runtime DB credentials
are read here. The test supplies synthetic session-scoped role app
connections, ephemeral secret, and synthetic events in frcaixinha_staging.
It is NOT production authentication or a live inbox implementation.
"""
from __future__ import annotations
import os
from datetime import datetime
from uuid import UUID
import asyncpg

from .notification_inbox_page_boundary import (
    RecipientScope, decode_cursor, preview_notification_page,
)
from .notifications_policy import NoticeRole
from .pix_automation_contract import FinancialOperationBlocked


def _ensure_ci_context(connection: asyncpg.Connection) -> None:
    if (
        os.getenv("GITHUB_ACTIONS") != "true"
        or os.getenv("FRCAIXINHA_CI_ISOLATED") != "1"
        or os.getenv("CI_MP_NOTIFICATION_APP_URL") not in (
            "postgresql://frcaixinha_ci:ci-test-only@127.0.0.1:5432/frcaixinha_staging",
            "postgresql://frcaixinha_pg18_app:ci-test-only@127.0.0.1:5432/frcaixinha_staging",
        )
        or connection is None
        or connection.is_closed()
    ):
        raise FinancialOperationBlocked("Gateway de inbox permitido apenas na CI isolada")


async def _bind_ci_context(
    conn: asyncpg.Connection, scope: RecipientScope
) -> None:
    db, user = await conn.fetchrow("SELECT current_database(),session_user")
    if db != "frcaixinha_staging" or user not in (
        "frcaixinha_ci", "frcaixinha_pg18_app",
    ):
        raise FinancialOperationBlocked("Papel ou banco incorreto para inbox sintética")
    # Transaction-local: override any stale/forged GUCs on a reused socket.
    await conn.execute("SELECT set_config('app.current_user_id',$1,true)",
                       str(scope.user_id))
    await conn.execute("SELECT set_config('app.current_role',$1,true)",
                       scope.role.value)
    await conn.execute("SELECT set_config('app.current_tenant_id',$1,true)",
                       str(scope.tenant_id) if scope.tenant_id else "")
    await conn.execute(
        "SELECT set_config('frcaixinha.notifications_staging_ci','1',true)"
    )


async def read_disposable_notification_page(
    conn: asyncpg.Connection,
    scope: RecipientScope,
    *,
    secret: bytes,
    now: datetime,
    limit: int = 20,
    after: str | None = None,
):
    _ensure_ci_context(conn)
    # Validate request and cursor before making any SQL query.
    if type(limit) is not int or not 1 <= limit <= 50:
        raise FinancialOperationBlocked("Limite de página inválido")
    marker = (decode_cursor(after,scope,secret=secret,now=now)
              if after is not None else None)
    # First call fails before DB when scope or secret are not valid.
    preview_notification_page((),scope,secret=secret,now=now,limit=limit)
    async with conn.transaction():
        await _bind_ci_context(conn,scope)
        data = await conn.fetch(
            "SELECT id,tenant_id,recipient_user_id,recipient_role,kind,"
            "title,message,created_at,read_at "
            "FROM public.notification_inbox_staging "
            "WHERE recipient_user_id=$1::uuid "
            "AND recipient_role=$2::varchar "
            "AND tenant_id IS NOT DISTINCT FROM $3::uuid "
            "AND ($4::timestamptz IS NULL OR "
            "(created_at,id)<($4::timestamptz,$5::uuid)) "
            "ORDER BY created_at DESC,id DESC LIMIT $6",
            scope.user_id,scope.role.value,scope.tenant_id,
            marker[0] if marker else None,marker[1] if marker else None,
            limit+1,
        )
        # asyncpg can return its own pgproto.UUID class, which is not
        # exactly uuid.UUID. Explicitly normalize only the three UUID
        # columns, preserving the strict page validator (no relaxed types).
        normalized = []
        for row in data:
            item = dict(row)
            for key in ("id", "tenant_id", "recipient_user_id"):
                raw = item[key]
                if raw is None:
                    if key != "tenant_id":
                        raise FinancialOperationBlocked("UUID nulo no registro")
                    continue
                try:
                    value = UUID(str(raw))
                except (ValueError, TypeError, AttributeError) as exc:
                    raise FinancialOperationBlocked("UUID não canônico do banco") from exc
                if value.int == 0 or str(value) != str(raw):
                    raise FinancialOperationBlocked("UUID adulterado no banco")
                item[key] = value
            normalized.append(item)
        return preview_notification_page(
            tuple(normalized),scope,secret=secret,
            now=now,limit=limit,after=after
        )


async def mark_disposable_notification_read(
    conn: asyncpg.Connection,
    scope: RecipientScope,
    notice_id: UUID,
) -> str:
    _ensure_ci_context(conn)
    if type(notice_id) is not UUID or notice_id.int == 0:
        raise FinancialOperationBlocked("ID de notificação inválido")
    # Fail closed on bad role, no DB side effects.
    preview_notification_page(
        (),scope,secret=b"CI_VALIDATION_ONLY_KEY_M18000_LENGTH_38",
        now=datetime.now().astimezone(),limit=1,
    )
    async with conn.transaction():
        await _bind_ci_context(conn,scope)
        result = await conn.fetchval(
            "SELECT public.notification_mark_read_staging_ci($1::uuid)",notice_id
        )
        if result not in ("READ","ALREADY_READ","NOT_FOUND"):
            raise FinancialOperationBlocked("Resposta inesperada da leitura sintética")
        return result
