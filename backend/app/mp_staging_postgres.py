"""M2900: staging PostgreSQL adapter for verified webhook inbox ONLY.

Requires an explicitly provisioned 'frcaixinha_staging' database and migration
034, and the dedicated unprivileged webhook login. Never targets Termux 5433.
"""
from __future__ import annotations

import re
from uuid import UUID

from .mp_webhook_staging_runtime import SellerContext, SignedWebhookRecord

_DIGITS=re.compile(r"[0-9]{1,40}\Z")


class StagingInboxUnavailable(RuntimeError):
    pass


class StagingPostgresInbox:
    def __init__(self, pool):
        self.pool=pool

    async def _ensure_staging(self,conn):
        try:
            result=await conn.fetchval(
                "SELECT current_database()='frcaixinha_staging' "
                "AND current_user='frcaixinha_mp_webhook_ingest' "
                "AND to_regclass('public.mp_signed_webhook_inbox_staging') IS NOT NULL"
            )
        except Exception:
            result=False
        if result is not True:
            raise StagingInboxUnavailable("Staging webhook database unavailable")

    async def resolve_seller(self,seller_id: str):
        if type(seller_id) is not str or not _DIGITS.fullmatch(seller_id):
            return None
        async with self.pool.acquire() as conn:
            await self._ensure_staging(conn)
            row=await conn.fetchrow(
                "SELECT tenant_id,seller_id,webhook_secret_ocid "
                "FROM public.mp_staging_resolve_seller($1::varchar)",seller_id,
            )
        if row is None:
            return None
        return SellerContext(
            UUID(str(row["tenant_id"])),str(row["seller_id"]),
            str(row["webhook_secret_ocid"]),True,
        )

    async def append(self,event: SignedWebhookRecord) -> str:
        if type(event) is not SignedWebhookRecord:
            raise StagingInboxUnavailable("Staging webhook event invalid")
        async with self.pool.acquire() as conn:
            await self._ensure_staging(conn)
            async with conn.transaction():
                outcome=await conn.fetchval(
                    "SELECT public.mp_staging_append_signed_webhook("
                    "$1::uuid,$2::varchar,$3::varchar,$4::varchar,$5::varchar,"
                    "$6::varchar,$7::varchar,$8::varchar,$9::boolean)",
                    event.tenant_id,event.seller_id,event.notification_id,
                    event.request_id,event.resource_id,event.event_type,
                    event.action,event.payload_sha256,event.live_mode,
                )
        if outcome not in ("INSERTED","REPLAY"):
            raise StagingInboxUnavailable("Staging inbox error")
        return outcome
