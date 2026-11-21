"""AI Studio M5100 — durable Orders reservation adapter, OCI STAGING ONLY.

The pool must be injected by an authorized background worker using the
unprivileged `frcaixinha_mp_financial_worker` login. No network/PSP calls or
money effects in this adapter; no transaction spans an outbound POST.
"""
from __future__ import annotations

from uuid import UUID

from .pix_automation_contract import PixPaymentCommand, FinancialOperationBlocked
from .mp_orders_api import OrdersPixCheckout

CONTRACT = "AI_STUDIO_M5100_ORDERS_STAGING_RESERVATION_V1"


class OrdersStagingBlocked(FinancialOperationBlocked):
    pass


class StagingOrdersJournal:
    """Reservation half of OrdersPaymentJournal. No real payment posting.

    A new instance is tenant+seller scoped by server-side auth. It must not
    be constructed from client-supplied tenant/account without validation.
    """

    def __init__(self, pool, *, tenant_id: UUID, provider_account_id: str):
        if (type(tenant_id) is not UUID
                or type(provider_account_id) is not str
                or not provider_account_id.isascii()
                or not provider_account_id.isdecimal()
                or not 1 <= len(provider_account_id) <= 40):
            raise OrdersStagingBlocked("Identidade de worker inválida")
        self.pool = pool
        self.tenant_id = tenant_id
        self.provider_account_id = provider_account_id

    def _check(self, command: PixPaymentCommand):
        if (type(command) is not PixPaymentCommand
                or command.obligation.tenant_id != self.tenant_id
                or command.obligation.provider_account_id != self.provider_account_id
                or command.obligation.environment != "HOMOLOGACAO"):
            raise OrdersStagingBlocked("Cobrança pertence a outra conta ou produção")

    async def _guard(self, conn):
        try:
            valid = await conn.fetchval(
                "SELECT current_database()='frcaixinha_staging' "
                "AND session_user='frcaixinha_mp_financial_worker' "
                "AND current_user='frcaixinha_mp_financial_worker' "
                "AND to_regprocedure('public.mp_orders_staging_reserve("
                "uuid,uuid,uuid,uuid,character varying,uuid,bigint,smallint,"
                "character varying,character varying,character varying,"
                "character varying,character varying,character varying)') IS NOT NULL"
            )
        except Exception:
            valid = False
        if valid is not True:
            raise OrdersStagingBlocked("Staging Orders indisponível")

    async def reserve_idempotent(self, command: PixPaymentCommand) -> str:
        self._check(command)
        p = command.obligation
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                await self._guard(conn)
                result = await conn.fetchval(
                    "SELECT public.mp_orders_staging_reserve("
                    "$1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14)",
                    p.tenant_id, p.cycle_id, p.member_id,
                    p.obligation_id, p.kind.value, p.loan_id,
                    command.amount_cents, command.attempt,
                    command.operation_id, command.external_reference,
                    command.idempotency_key, self.provider_account_id,
                    p.terms_version, p.environment,
                )
                if result not in ("NEW", "EXISTS"):
                    raise OrdersStagingBlocked("Reserva idempotente não confirmada")
                return result

    async def lookup_checkout(self, operation_id: str) -> OrdersPixCheckout | None:
        if (type(operation_id) is not str or len(operation_id) != 34
                or not operation_id.startswith("P_")
                or any(ch not in "0123456789abcdef" for ch in operation_id[2:])):
            raise OrdersStagingBlocked("ID da reserva inválido")
        async with self.pool.acquire() as conn:
            async with conn.transaction(readonly=True):
                await self._guard(conn)
                row = await conn.fetchrow(
                    "SELECT * FROM public.mp_orders_staging_get_checkout($1,$2)",
                    self.tenant_id, operation_id,
                )
        if row is None:
            return None
        if (row["operation_id"]!=operation_id
                or row["status"]!="AGUARDANDO_PROVEDOR"):
            raise OrdersStagingBlocked("Checkout persistido divergente")
        return OrdersPixCheckout(
            operation_id=operation_id,order_id=row["order_id"],
            payment_id=row["payment_id"],amount_cents=row["amount_cents"],
            status="action_required",status_detail="waiting_transfer",
            qr_code=row["qr_code"],qr_code_base64=row["qr_image"],
            ticket_url=row["ticket_url"],
        )

    async def write_checkout(
        self, command: PixPaymentCommand, checkout: OrdersPixCheckout,
    )->None:
        self._check(command)
        if (type(checkout) is not OrdersPixCheckout
                or checkout.operation_id != command.operation_id
                or checkout.amount_cents != command.amount_cents
                or checkout.status != "action_required"
                or checkout.status_detail != "waiting_transfer"
                or checkout.bank_reconciled is not False
                or checkout.ledger_written is not False
                or checkout.capital_recognized is not False):
            raise OrdersStagingBlocked("Checkout do provedor divergente")
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                await self._guard(conn)
                result = await conn.fetchval(
                    "SELECT public.mp_orders_staging_save_checkout("
                    "$1,$2,$3,$4,$5,$6,$7)",
                    self.tenant_id,command.operation_id,
                    checkout.order_id,checkout.payment_id,
                    checkout.qr_code,checkout.qr_code_base64,
                    checkout.ticket_url,
                )
                if result not in ("INSERTED","REPLAY"):
                    raise OrdersStagingBlocked("Checkout não foi persistido")

    async def mark_uncertain(self, operation_id:str)->None:
        if (type(operation_id) is not str or len(operation_id) != 34
                or not operation_id.startswith("P_")
                or any(ch not in "0123456789abcdef" for ch in operation_id[2:])):
            raise OrdersStagingBlocked("ID de reserva inválido")
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                await self._guard(conn)
                result=await conn.fetchval(
                    "SELECT public.mp_orders_staging_mark_uncertain($1,$2)",
                    self.tenant_id,operation_id,
                )
                if result not in ("UNCERTAIN","UNCHANGED"):
                    raise OrdersStagingBlocked("Estado incerto não persistido")

    async def atomic_post_once(self, *, command, bank, loan_allocation):
        # A ledger implementation will require bank-signed evidence, duplicate
        # key constraints, income/principal splits and balanced accounting.
        # Never fabricate a receipt in this reservation-only repository.
        raise OrdersStagingBlocked(
            "Escrituração financeira bloqueada sem reconciliação certificada"
        )
