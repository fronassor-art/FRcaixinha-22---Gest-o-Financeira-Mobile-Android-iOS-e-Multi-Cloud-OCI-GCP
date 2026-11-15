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


# M39910 — HISTÓRICO DOCUMENTAL, NÃO EXTRATO FINANCEIRO.
# Retorna apenas categorias/status/horários já registrados, sem dinheiro,
# valores, referências externas, CPF, nome, identificador de pagador ou saldo.
from datetime import datetime, timezone
from collections.abc import Mapping

_PAYMENT_STATES = frozenset(("PENDING", "APPROVED", "REJECTED", "CANCELED", "REFUNDED"))
_PREPARATION_STATES = frozenset(("PENDING_PAYMENT", "PAUSED_NO_PAYMENT", "CANCELED"))
_HISTORY_LIMIT = 10


def _history_record(row: Mapping, category: str, allowed: frozenset[str]) -> dict:
    try:
        event_id = row["id"]
        when = row["created_at"]
        if type(event_id) is not UUID or type(when) is not datetime or (
            when.tzinfo is None or when.utcoffset() is None
        ):
            raise ValueError("Invalid documentary event")
        state = row["status"] if category != "TENANT_COLLECTIVE_LEDGER" else "RECORDED_NOT_REMUNERATION"
        if type(state) is not str or state not in allowed:
            raise ValueError("Invalid documentary status")
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        raise HTTPException(503, "Histórico documental não comprovado.") from exc
    return {
        "id": str(event_id), "occurred_at": when.astimezone(timezone.utc).isoformat(),
        "category": category, "state": state, "amount_cents": None,
        "settlement_verified": False,
    }


def _history_response(scope: str, tenant_id: UUID | None, entries: list[dict]) -> dict:
    return {
        "source": "POSTGRESQL_RLS", "scope": scope,
        "tenant_id": str(tenant_id) if tenant_id is not None else None,
        "entries": entries, "available_balance_cents": None,
        "cash_movement_verified": False, "transfer_enabled": False,
        "status": "DOCUMENTARY_ONLY_NOT_RECONCILED",
    }


@master_router.get("/exclusive-cashbox/history")
async def master_exclusive_cashbox_history(
    response: Response,
    session: AuthenticatedSession = Depends(require_master),
    conn=Depends(get_rls_db_connection),
):
    """Limited SaaS event history; approved intent is NOT bank reconciliation."""
    _disallow_financial_caching(response)
    intents = await conn.fetch(
        "SELECT id,created_at,status FROM public.saas_payment_intents "
        "ORDER BY created_at DESC,id DESC LIMIT 10"
    )
    preparations = await conn.fetch(
        "SELECT id,created_at,status FROM public.saas_subscription_preparations "
        "ORDER BY created_at DESC,id DESC LIMIT 10"
    )
    if len(intents) > _HISTORY_LIMIT or len(preparations) > _HISTORY_LIMIT:
        raise HTTPException(503, "Histórico documental excedeu o limite.")
    records = [
        _history_record(r, "SAAS_INTENT", _PAYMENT_STATES) for r in intents
    ] + [
        _history_record(r, "SAAS_PREPARATION", _PREPARATION_STATES)
        for r in preparations
    ]
    # Stable sort with bounded output. Never include amount/tenant identity.
    records.sort(key=lambda x: (x["occurred_at"], x["id"]), reverse=True)
    return _history_response("MASTER_PLATFORM_SAAS_ONLY", None,
                             records[:_HISTORY_LIMIT])


@tenant_router.get("/admin-exclusive-cashbox/history")
async def tenant_admin_exclusive_cashbox_history(
    tenant_id: UUID,
    response: Response,
    session: AuthenticatedSession = Depends(get_current_session),
    conn=Depends(get_rls_db_connection),
):
    """Collective ledger evidence only, never personal admin remuneration."""
    _disallow_financial_caching(response)
    require_tenant_access(str(tenant_id), session)
    if session.role != "TENANT_ADMIN":
        raise HTTPException(403, "Histórico restrito ao administrador titular.")
    try:
        actor = UUID(str(session.user_id))
    except (TypeError, ValueError, AttributeError) as exc:
        raise HTTPException(403, "Identidade inválida.") from exc
    owner = await conn.fetchval(
        "SELECT admin_user_id FROM public.tenants "
        "WHERE id=$1 AND status='ATIVO'", tenant_id,
    )
    if owner != actor:
        raise HTTPException(403, "Somente administrador titular autorizado.")
    rows = await conn.fetch(
        "SELECT id,created_at FROM public.ledger_transactions "
        "WHERE tenant_id=$1 ORDER BY created_at DESC,id DESC LIMIT 10",
        tenant_id,
    )
    if len(rows) > _HISTORY_LIMIT:
        raise HTTPException(503, "Histórico documental excedeu o limite.")
    records = [
        _history_record(r, "TENANT_COLLECTIVE_LEDGER",
                        frozenset(("RECORDED_NOT_REMUNERATION",)))
        for r in rows
    ]
    return _history_response("TENANT_ADMIN_COLLECTIVE_REFERENCE_ONLY",
                             tenant_id, records)


# M39960 — VIEWER AUTHENTICATION READINESS ONLY (NOT A REVIEW SIGNATURE).
# The session provenance is generated exclusively by get_current_session.
# No claim of documentary approval, balance, payout, or fulfilled 2-person review.
from ..exclusive_cashbox_review_readiness import (
    ReviewReadinessDenied, verify_review_readiness,
)
from ..exclusive_cashbox_provenance import PLATFORM_MASTER, TENANT_ADMIN_OWN


def _readiness_response(scope: str, tenant_id: UUID | None) -> dict:
    """Public-facing minimum: never return user/session IDs or expiry times."""
    return {
        "source": "POSTGRES_TOKEN_HASH_REFRESH",
        "scope": scope,
        "tenant_id": str(tenant_id) if tenant_id is not None else None,
        "state": "SESSION_BOUND_VIEW_ONLY",
        "session_bound": True,
        "owner_verified_for_view": tenant_id is not None,
        "document_authenticated": False,
        "independent_reviewers_verified": False,
        "documentary_review_authorized": False,
        "bank_reconciled": False,
        "journal_posted": False,
        "payment_enabled": False,
        "payout_enabled": False,
        "available_balance_cents": None,
    }


@master_router.get("/exclusive-cashbox/review-readiness")
async def master_exclusive_cashbox_review_readiness(
    response: Response,
    session: AuthenticatedSession = Depends(require_master),
):
    """Read-only master session scope check; no tenant ledger or DB query."""
    _disallow_financial_caching(response)
    try:
        verify_review_readiness(
            session, requested_scope=PLATFORM_MASTER, requested_tenant_id=None,
        )
    except ReviewReadinessDenied as exc:
        raise HTTPException(403, "Sessão Master não verificável para consulta.") from exc
    return _readiness_response("MASTER_PLATFORM_SAAS_ONLY", None)


@tenant_router.get("/admin-exclusive-cashbox/review-readiness")
async def tenant_admin_exclusive_cashbox_review_readiness(
    tenant_id: UUID,
    response: Response,
    session: AuthenticatedSession = Depends(get_current_session),
    conn=Depends(get_rls_db_connection),
):
    """Read-only viewer check: token-bound session AND active tenant ownership."""
    _disallow_financial_caching(response)
    require_tenant_access(str(tenant_id), session)
    try:
        verify_review_readiness(
            session,
            requested_scope=TENANT_ADMIN_OWN,
            requested_tenant_id=tenant_id,
        )
    except ReviewReadinessDenied as exc:
        raise HTTPException(403, "Sessão de administrador não verificável.") from exc
    owner = await conn.fetchval(
        "SELECT admin_user_id FROM public.tenants "
        "WHERE id=$1 AND status='ATIVO'", tenant_id,
    )
    if owner != UUID(session.user_id):
        raise HTTPException(403, "Somente o administrador titular ativo pode consultar.")
    return _readiness_response("TENANT_ADMIN_OWN_REMUNERATION_ONLY", tenant_id)
