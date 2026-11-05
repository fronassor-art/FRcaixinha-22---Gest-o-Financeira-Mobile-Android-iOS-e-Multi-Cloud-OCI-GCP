"""AI Studio M6600: untrusted settlement -> durable HOLD, never paid.

Only a server-bound, unprivileged staging Orders journal may append a
reconciliation hold. There is deliberately no mark-paid / release / credit
authority here. The caller must attest evidence off-band; the hash is a
fingerprint, not proof of a real bank transfer.
"""
from __future__ import annotations

from enum import Enum
from re import fullmatch

from .mp_orders_reservation import StagingOrdersJournal,OrdersStagingBlocked
from .pix_automation_contract import PixPaymentCommand

CONTRACT="AI_STUDIO_M6600_DURABLE_ORDERS_RECONCILIATION_HOLDS_V1"


class HoldReason(str,Enum):
    TIMEOUT_UNKNOWN="TIMEOUT_UNKNOWN"
    PROVIDER_MISMATCH="PROVIDER_MISMATCH"
    BANK_MISSING="BANK_MISSING"
    FEE_MISMATCH="FEE_MISMATCH"
    ORDER_REPLAY="ORDER_REPLAY"
    REVERSAL_PENDING="REVERSAL_PENDING"
    STATEMENT_DUPLICATE="STATEMENT_DUPLICATE"
    STATUS_CONFLICT="STATUS_CONFLICT"
    SELLER_REVOKED="SELLER_REVOKED"


class StagingReconciliationHolds:
    def __init__(self,journal:StagingOrdersJournal):
        if type(journal) is not StagingOrdersJournal:
            raise OrdersStagingBlocked("Serviço de retenção exige worker validado")
        self.journal=journal

    async def hold(
        self,*,command:PixPaymentCommand,reason:HoldReason,
        evidence_sha256:str,
    )->str:
        self.journal._check(command)
        if (type(reason) is not HoldReason
                or type(evidence_sha256) is not str
                or fullmatch(r"[0-9a-f]{64}",evidence_sha256) is None):
            raise OrdersStagingBlocked("Retenção sem motivo e fingerprint válido")
        async with self.journal.pool.acquire() as conn:
            async with conn.transaction():
                await self.journal._guard(conn)
                try:
                    result=await conn.fetchval(
                        "SELECT public.mp_orders_staging_record_hold($1,$2,$3,$4)",
                        self.journal.tenant_id,command.operation_id,
                        reason.value,evidence_sha256,
                    )
                except Exception as exc:
                    raise OrdersStagingBlocked(
                        "Não foi possível persistir a retenção; cobrança bloqueada"
                    ) from exc
                if result not in ("NEW","REPLAY"):
                    raise OrdersStagingBlocked("Retenção não confirmada")
                return result
