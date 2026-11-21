"""FR Caixinha AI Studio: fronteiras de tesouraria e rateio financeiro SEM I/O.

Duas tesourarias independentes: PLATAFORMA (mensalidade SaaS) e TENANT
(cotas/credito/receita da própria caixinha). Nenhum cálculo confirma Pix,
cria saldo, autoriza fechamento, transfere dinheiro ou concede empréstimo.

Usar somente com valores/audit evidenciados; nesta etapa é PREVIEW sintética.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Mapping
from uuid import UUID

from .mercado_pago_safety import ExpectedPayment, matches_approved_payment

PLATFORM_SAAS = "PLATFORM_SAAS"
TENANT_CONTRIBUTION = "TENANT_CONTRIBUTION"
TENANT_LOAN_REPAYMENT = "TENANT_LOAN_REPAYMENT"
_ALLOWED = {PLATFORM_SAAS, TENANT_CONTRIBUTION, TENANT_LOAN_REPAYMENT}


@dataclass(frozen=True)
class CashboxRoute:
    """Identidade do destino; token secreto NÃO faz parte do modelo."""
    purpose: str
    collector_id: str
    tenant_id: UUID | None

    def __post_init__(self):
        if self.purpose not in _ALLOWED:
            raise ValueError("Finalidade de recebimento desconhecida")
        if not isinstance(self.collector_id, str) or not (
            self.collector_id.isascii() and self.collector_id.isdecimal()
            and 1 <= len(self.collector_id) <= 40
        ):
            raise ValueError("Conta recebedora inválida")
        if self.purpose == PLATFORM_SAAS and self.tenant_id is not None:
            raise ValueError("Tesouraria da plataforma não tem tenant")
        if self.purpose != PLATFORM_SAAS and type(self.tenant_id) is not UUID:
            raise ValueError("Recebimento de membro exige tenant vinculado")


@dataclass(frozen=True)
class DuePayment:
    route: CashboxRoute
    external_reference: str
    provider_payment_id: str
    amount_cents: int
    live_mode: bool

    def __post_init__(self):
        if type(self.amount_cents) is not int or not 1 <= self.amount_cents <= 999999999999:
            raise ValueError("Valor precisa estar em centavos positivos")
        if type(self.live_mode) is not bool:
            raise ValueError("Ambiente deve ser declarado explicitamente")
        if not isinstance(self.external_reference, str) or not (
            1 <= len(self.external_reference) <= 100
        ):
            raise ValueError("Referência de obrigação inválida")
        if not isinstance(self.provider_payment_id, str) or not (
            self.provider_payment_id.isascii()
            and self.provider_payment_id.isdecimal()
            and 1 <= len(self.provider_payment_id) <= 40
        ):
            raise ValueError("ID do provedor inválido")
        if self.route.purpose == PLATFORM_SAAS:
            if not self.external_reference.startswith("saas:"):
                raise ValueError("Assinatura deve ter referência saas")
        else:
            if not self.external_reference.startswith(f"tenant:{self.route.tenant_id}:"):
                raise ValueError("Obrigação deve declarar o tenant recebedor")


def validate_payment_against_cashbox(
    expected: DuePayment, provider_response: Mapping[str, object],
    *, platform_collector_id: str, tenant_collectors: Mapping[UUID, str]
) -> bool:
    """Compara resposta de consulta autenticada; NÃO altera dinheiro/saldo.

    Não aceitar objeto de webhook como resposta autoritativa. O chamador é
    responsável pela obtenção GET segura, autenticação e prevenção de replay.
    """
    route = expected.route
    if not isinstance(provider_response, Mapping):
        return False
    if (not isinstance(platform_collector_id, str) or
        not platform_collector_id.isascii() or
        not platform_collector_id.isdecimal()):
        return False
    if route.purpose == PLATFORM_SAAS:
        if route.collector_id != platform_collector_id:
            return False
        if route.collector_id in tenant_collectors.values():
            return False
    else:
        if route.tenant_id not in tenant_collectors:
            return False
        if tenant_collectors[route.tenant_id] != route.collector_id:
            return False
        if route.collector_id == platform_collector_id:
            return False
    return matches_approved_payment(
        ExpectedPayment(
            provider_payment_id=expected.provider_payment_id,
            collector_id=route.collector_id,
            external_reference=expected.external_reference,
            amount_cents=expected.amount_cents,
            live_mode=expected.live_mode,
        ), provider_response,
    )


def _weight_units(weight: Decimal) -> int:
    if type(weight) is not Decimal or not weight.is_finite() or weight < 0:
        raise ValueError("Capital-Dias requer Decimal não negativo")
    units = weight * Decimal(10000)
    if units != units.to_integral_value():
        raise ValueError("Capital-Dias admite no máximo quatro decimais")
    return int(units)


@dataclass(frozen=True)
class MemberCapitalDays:
    tenant_id: UUID
    membership_id: UUID
    weight: Decimal
    eligible: bool

    def __post_init__(self):
        if type(self.tenant_id) is not UUID or type(self.membership_id) is not UUID:
            raise ValueError("Tenant/membership inválido")
        if type(self.eligible) is not bool:
            raise ValueError("Elegibilidade explícita obrigatória")
        _weight_units(self.weight)


@dataclass(frozen=True)
class ProfitPreview:
    tenant_id: UUID
    net_profit_cents: int
    administrator_share_cents: int
    members_pool_cents: int
    shares_cents: tuple[tuple[UUID, int], ...]
    simulation_only: bool = True
    closing_authorized: bool = False
    bank_reconciled: bool = False


def simulate_annual_profit_split(
    tenant_id: UUID, net_profit_cents: int,
    members: tuple[MemberCapitalDays, ...],
) -> ProfitPreview:
    """15% administração da PRÓPRIA caixinha; 85% membros.

    Capital de cotas não é lucro. Maior resto em CENTAVOS e desempate UUID.
    Total dos shares deve ser exatamente o pool. Zero lucro: nenhum rateio.
    """
    if type(tenant_id) is not UUID or type(net_profit_cents) is not int or (
        net_profit_cents < 0 or net_profit_cents > 999999999999
    ):
        raise ValueError("Lucro líquido não auditado ou inválido")
    if type(members) is not tuple or len(members) > 5000:
        raise ValueError("Coleção de membros inválida")
    seen: set[UUID] = set()
    eligible: list[tuple[UUID, int]] = []
    for member in members:
        if not isinstance(member, MemberCapitalDays) or member.tenant_id != tenant_id:
            raise ValueError("Rateio entre tenants é proibido")
        if member.membership_id in seen:
            raise ValueError("Membro repetido")
        seen.add(member.membership_id)
        w = _weight_units(member.weight)
        if member.eligible and w:
            eligible.append((member.membership_id, w))
    try:
        admin_cents = int((Decimal(net_profit_cents) * Decimal("0.15")).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP))
    except (InvalidOperation, ArithmeticError) as exc:
        raise ValueError("Falha numérica") from exc
    pool = net_profit_cents - admin_cents
    weight_total = sum(w for _, w in eligible)
    if pool and not weight_total:
        raise ValueError("Pool sem membro elegível: manter bloqueado")
    base: dict[UUID, int] = {member.membership_id: 0 for member in members}
    if weight_total:
        fractions: list[tuple[int, str, UUID]] = []
        for mid, weight in eligible:
            share, remainder = divmod(pool * weight, weight_total)
            base[mid] = share
            fractions.append((-remainder, str(mid), mid))
        residual = pool - sum(base.values())
        for _, _, mid in sorted(fractions)[:residual]:
            base[mid] += 1
    shares = tuple(sorted(base.items(), key=lambda x: str(x[0])))
    if (admin_cents + sum(v for _, v in shares) != net_profit_cents or
        any(v < 0 for _, v in shares)):
        raise AssertionError("Quebra de conservação de centavos")
    return ProfitPreview(
        tenant_id=tenant_id, net_profit_cents=net_profit_cents,
        administrator_share_cents=admin_cents,
        members_pool_cents=pool, shares_cents=shares,
    )
