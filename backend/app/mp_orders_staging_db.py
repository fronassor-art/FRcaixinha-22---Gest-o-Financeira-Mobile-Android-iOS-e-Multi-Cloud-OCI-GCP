"""M4500: durable signed Orders inbox PostgreSQL staging adapter.

No standalone connection string; pool comes exclusively from OCI staging
service and narrowly scoped role. No SQL on member-controlled identifiers
except parameterized values. No ledger, settlement, or money writes.
"""
from __future__ import annotations

from .mp_orders_webhook import SignedOrderEvent


class OrdersStagingDatabaseBlocked(RuntimeError):
    pass


class StagingOrdersInbox:
    def __init__(self,pool):
        self.pool=pool

    @staticmethod
    async def _guard(conn):
        try:
            ok=await conn.fetchval(
                "SELECT current_database()='frcaixinha_staging' "
                "AND current_user='frcaixinha_mp_webhook_ingest' "
                "AND to_regclass('public.mp_signed_order_inbox_staging') IS NOT NULL "
                "AND has_function_privilege(current_user,"
                "'public.mp_staging_append_signed_order(uuid,varchar,varchar,"
                "varchar,varchar,varchar,varchar,varchar,boolean)','EXECUTE')"
            )
        except Exception:
            ok=False
        if ok is not True:
            raise OrdersStagingDatabaseBlocked("Orders inbox OCI staging indisponível")

    async def append(self,event:SignedOrderEvent)->str:
        if type(event) is not SignedOrderEvent or event.bank_reconciled or event.ledger_written:
            raise OrdersStagingDatabaseBlocked("Evento Orders não verificado")
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                await self._guard(conn)
                result=await conn.fetchval(
                    "SELECT public.mp_staging_append_signed_order("
                    "$1,$2,$3,$4,$5,$6,$7,$8,$9)",
                    event.tenant_id,event.provider_account_id,
                    event.event_id,event.request_id,event.order_id,
                    event.action,event.observed_status,
                    event.payload_sha256,event.live_mode,
                )
                if result not in ("INSERTED","REPLAY"):
                    raise OrdersStagingDatabaseBlocked("Persistência Orders não confirmada")
                return result
