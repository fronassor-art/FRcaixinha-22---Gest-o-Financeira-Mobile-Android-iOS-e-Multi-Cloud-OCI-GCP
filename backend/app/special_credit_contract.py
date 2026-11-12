"""FR Finance AI Studio — pure, fail-closed special-credit contract.

This module never approves/disburses a loan and never sends marketing.
The exception grants the right to REQUEST simulation, not financial authority.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Iterable

CENT = Decimal("0.01")
CHANNELS = ("PUSH", "EMAIL", "WHATSAPP", "SMS")
GRANT_STATES = ("ACTIVE", "REVOKED", "EXPIRED")
RECIPIENT_STATES = ("PENDING", "INTERESTED", "DECLINED")


class SpecialCreditDenied(ValueError):
    """A documented business or safety precondition was not satisfied."""


def amount_brl(value: object) -> Decimal:
    """Exact centavos; float/bool/NaN/infinite/over-precision are forbidden."""
    if isinstance(value, (float, bool)) or value is None:
        raise SpecialCreditDenied("Valor monetário inválido.")
    try:
        raw = Decimal(str(value))
        if not raw.is_finite() or raw <= 0 or raw != raw.quantize(CENT):
            raise SpecialCreditDenied("Valor deve ser positivo e expresso em centavos.")
        if raw >= Decimal("10000000000000"):
            raise SpecialCreditDenied("Valor excede o tipo monetário da persistência.")
        return raw
    except (InvalidOperation, OverflowError, ValueError) as exc:
        raise SpecialCreditDenied("Valor monetário inválido.") from exc


def valid_expiry(expires_at: datetime, *, now: datetime | None = None) -> datetime:
    if expires_at.tzinfo is None or expires_at.utcoffset() is None:
        raise SpecialCreditDenied("Validade exige data com fuso.")
    moment = now or datetime.now(timezone.utc)
    if moment.tzinfo is None or moment.utcoffset() is None:
        raise SpecialCreditDenied("Relógio sem fuso.")
    if expires_at <= moment:
        raise SpecialCreditDenied("Autorização vencida.")
    return expires_at


def validate_exception(
    *,
    tenant_id: str,
    member_tenant_id: str,
    member_status: str,
    cycle_status: str,
    amount: object,
    expires_at: datetime,
    reason: str,
    now: datetime | None = None,
) -> Decimal:
    if not tenant_id or tenant_id != member_tenant_id:
        raise SpecialCreditDenied("Membro fora da caixinha.")
    if member_status != "ATIVA" or cycle_status != "ABERTO":
        raise SpecialCreditDenied("Membro ou ciclo inelegível.")
    if not isinstance(reason, str) or len(reason.strip()) < 20 or len(reason) > 2000:
        raise SpecialCreditDenied("Justificativa de risco obrigatória (20–2000 caracteres).")
    valid_expiry(expires_at, now=now)
    return amount_brl(amount)


def request_is_permitted(
    *,
    grant_status: str,
    valid_until: datetime,
    requested: object,
    granted_limit: object,
    member_active: bool,
    cycle_open: bool,
    now: datetime | None = None,
) -> bool:
    """A grant only waives the *ordinary amount ceiling*, nothing else.

    It NEVER asserts affordability, guarantee, loan approval, liquidity,
    contract validity, collateral, or outbound Pix permission.
    """
    if grant_status != "ACTIVE" or not member_active or not cycle_open:
        return False
    try:
        valid_expiry(valid_until, now=now)
        return amount_brl(requested) <= amount_brl(granted_limit)
    except SpecialCreditDenied:
        return False


def channel_permissions(opted_in: Iterable[str], *, verified: Iterable[str] = ()) -> dict[str, bool]:
    """Marketing fails closed: explicit opt-in PLUS verified channel required."""
    allowed, confirmed = set(opted_in), set(verified)
    return {channel: channel in allowed and channel in confirmed for channel in CHANNELS}


def public_push_preview() -> dict[str, str]:
    """Locked-screen safe: no member name, amount, indebtedness, or loan data."""
    return {
        "title": "FR Finance • Nova oportunidade",
        "body": "Você tem uma nova mensagem na área Minhas Oportunidades.",
    }


def external_dispatch_allowed(*, feature_enabled: bool, production: bool,
                              authorization_real: bool, provider_verified: bool,
                              channel_opt_in: bool) -> bool:
    """Must have a separate real-environment authorization, never inferred from CI."""
    return all((feature_enabled, production, authorization_real,
                provider_verified, channel_opt_in))
