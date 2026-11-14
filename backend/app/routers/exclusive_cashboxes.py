"""FR Finance M39090: exclusive financial panels, READ ONLY.

Master platform SaaS and tenant-admin own remuneration are distinct legal
cashboxes. This initial endpoint returns only authenticated, RLS-scoped,
server-counted *evidence metadata*, never financial balances. No SQL writes,
new tables, Pix, transfers, reconciled statements or fabricated zero balances.
"""
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Response

from ..database import get_rls_db_connection
from ..dependencies import (
    AuthenticatedSession, get_current_session, require_master,
    require_tenant_access,
)

master_router = APIRouter(prefix="/master", tags=["Caixa exclusivo Master — consulta"])
tenant_router = APIRouter(prefix="/tenants/{tenant_id}", tags=["Caixa exclusivo do administrador — consulta"])


def _count(value: object) -> int:
    if type(value) is not int or not 0 <= value <= 1000000000:
        raise HTTPException(503, "Contagem financeira indisponível para auditoria.")
    return value


def _disallow_financial_caching(response: Response) -> None:
    """Never cache financial evidence after role switch or logout."""
    response.headers["Cache-Control"] = "private, no-store, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Vary"] = "Authorization"


@master_router.get("/exclusive-cashbox")
async def master_exclusive_cashbox(
    response: Response,
    session: AuthenticatedSession = Depends(require_master),
    conn=Depends(get_rls_db_connection),
):
    """Master: ONLY SaaS billing evidence, not members' money or tenants' ledgers."""
    _disallow_financial_caching(response)
    intents = _count(await conn.fetchval(
        "SELECT count(*)::int FROM public.saas_payment_intents"))
    preparations = _count(await conn.fetchval(
        "SELECT count(*)::int FROM public.saas_subscription_preparations"))
    return {
        "source": "POSTGRESQL_RLS",
        "scope": "MASTER_PLATFORM_SAAS_ONLY",
        "tenant_id": None,
        "cashbox": "PLATFORM_SAAS",
        "payment_intents_count": intents,
        "subscription_preparations_count": preparations,
        "settled_balance_cents": None,
        "bank_reconciled": False,
        "transfer_enabled": False,
        "real_payments_enabled": False,
        "status": "AWAITING_PROVIDER_RECONCILIATION",
    }


@tenant_router.get("/admin-exclusive-cashbox")
async def tenant_admin_exclusive_cashbox(
    tenant_id: UUID,
    response: Response,
    session: AuthenticatedSession = Depends(get_current_session),
    conn=Depends(get_rls_db_connection),
):
    """Only original tenant owner; never expose another tenant or member capital."""
    _disallow_financial_caching(response)
    require_tenant_access(str(tenant_id), session)
    if session.role != "TENANT_ADMIN":
        raise HTTPException(403, "Caixa exclusivo restrito ao administrador da caixinha.")
    try:
        actor = UUID(str(session.user_id))
    except (TypeError, ValueError, AttributeError) as exc:
        raise HTTPException(403, "Identidade da sessão inválida.") from exc
    owner = await conn.fetchval(
        "SELECT admin_user_id FROM public.tenants "
        "WHERE id=$1 AND status='ATIVO'", tenant_id,
    )
    if owner != actor:
        raise HTTPException(403, "Somente o administrador titular pode consultar o próprio caixa.")
    # A count is evidence of ledger records, not proof of available cash,
    # individual administrator remuneration, completed closing, or bank deposits.
    entries = _count(await conn.fetchval(
        "SELECT count(*)::int FROM public.ledger_transactions "
        "WHERE tenant_id=$1", tenant_id,
    ))
    return {
        "source": "POSTGRESQL_RLS",
        "scope": "TENANT_ADMIN_OWN_REMUNERATION_ONLY",
        "tenant_id": str(tenant_id),
        "cashbox": "TENANT_ADMIN_REMUNERATION",
        "ledger_transactions_count": entries,
        "administrator_profit_share_pct": "15.00",
        "members_profit_share_pct": "85.00",
        "settled_balance_cents": None,
        "bank_reconciled": False,
        "closing_authorized": False,
        "transfer_enabled": False,
        "real_payments_enabled": False,
        "status": "AWAITING_CLOSING_AND_RECONCILIATION",
    }
