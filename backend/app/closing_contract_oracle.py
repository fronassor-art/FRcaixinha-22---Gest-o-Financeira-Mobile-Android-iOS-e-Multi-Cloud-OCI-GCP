"""AI Studio M401+: oráculo PURO do encerramento anual, sem liquidação Pix.

Caderno Mestre 10.1–10.8. A base de distribuição NÃO inclui cotas nem
empréstimos. Rateio usa Capital-Dias V2 e carteira técnica segregada.
Este cálculo não altera saldo, marca pagamento ou concede autorização legal.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID
from zoneinfo import ZoneInfo

from .member_cycle_rules import MemberCycleReview

BELEM = ZoneInfo("America/Belem")
KINDS = {"REALIZED_REVENUE", "ELIGIBLE_EXPENSE", "ADMISSIBLE_LOSS",
         "APPROVED_ADJUSTMENT", "CAPITAL_PRINCIPAL"}


@dataclass(frozen=True)
class FinancialEvidence:
    tenant_id: UUID
    event_id: UUID
    kind: str
    amount_cents: int
    effective_at: datetime
    confirmed_and_reconciled: bool
    documentary_proof: str

    def __post_init__(self):
        if type(self.tenant_id) is not UUID or type(self.event_id) is not UUID:
            raise ValueError("Evento sem identidade")
        if self.kind not in KINDS or type(self.amount_cents) is not int or self.amount_cents < 0:
            raise ValueError("Tipo ou valor inválido")
        if type(self.effective_at) is not datetime or self.effective_at.utcoffset() is None:
            raise ValueError("Data com fuso obrigatória")
        if type(self.confirmed_and_reconciled) is not bool:
            raise ValueError("Prova de conciliação inválida")
        if not isinstance(self.documentary_proof, str) or len(self.documentary_proof) < 5:
            raise ValueError("Documento identificável obrigatório")


@dataclass(frozen=True)
class MemberClosingShare:
    member_id: UUID
    eligible: bool
    capital_days: Decimal
    base_cents: int
    technical_bonus_cent: int
    final_cents: int


@dataclass(frozen=True)
class AnnualClosingPreview:
    tenant_id: UUID
    cycle_year: int
    realized_revenue_cents: int
    eligible_costs_cents: int
    net_result_cents: int
    distributable_profit_cents: int
    admin_remuneration_cents: int
    member_pool_cents: int
    member_shares: tuple[MemberClosingShare, ...]
    technical_wallet_before_allocation_cents: int
    technical_wallet_after_allocation_cents: int
    reserved_undistributed_cents: int
    status: str
    simulation_only: bool = True
    bank_reconciled: bool = False
    financial_closing_authorized: bool = False
    pix_enabled: bool = False


def _pct(value: Decimal) -> int:
    if type(value) is not Decimal or not value.is_finite():
        raise ValueError("Percentual contratual exige Decimal")
    scaled = value * 100
    if scaled != scaled.to_integral_value() or not 0 <= scaled <= 10000:
        raise ValueError("Percentual fora da escala de duas casas")
    return int(scaled)


def simulate_contract_closing(
    *, tenant_id: UUID, cycle_year: int,
    admin_percent: Decimal, member_percent: Decimal,
    fixed_cycle_policy_version: str,
    evidence: tuple[FinancialEvidence, ...],
    reviews: tuple[MemberCycleReview, ...],
    contract_compliant: bool,
) -> AnnualClosingPreview:
    """Simulação resistente a resultados inventados ou reclassificação de capital.

    Uma evidência após 31/12 ou não conciliada NÃO ingressa silenciosamente
    no lucro. A simulação não pode distribuir se existir revisão pendente.
    """
    if type(tenant_id) is not UUID or type(cycle_year) is not int or not 2026 <= cycle_year <= 2100:
        raise ValueError("Tenant/ano inválido")
    admin_basis, member_basis = _pct(admin_percent), _pct(member_percent)
    if admin_basis + member_basis != 10000:
        raise ValueError("Percentuais devem totalizar 100%")
    if not isinstance(fixed_cycle_policy_version, str) or len(fixed_cycle_policy_version) < 8:
        raise ValueError("Versão documental do ciclo não identificada")
    if type(contract_compliant) is not bool:
        raise ValueError("Conformidade contratual precisa ser explícita")
    if type(evidence) is not tuple or len(evidence) > 50000:
        raise ValueError("Eventos inválidos")
    if type(reviews) is not tuple or len(reviews) > 5000:
        raise ValueError("Membros inválidos")
    seen_events: set[UUID] = set()
    revenue = 0
    costs = 0
    pending_evidence = False
    first = date(cycle_year, 1, 1)
    end = date(cycle_year+1, 1, 1)
    for event in evidence:
        if not isinstance(event, FinancialEvidence) or event.tenant_id != tenant_id:
            raise ValueError("Evento de outro tenant")
        if event.event_id in seen_events:
            raise ValueError("Duplicata de lançamento financeiro")
        seen_events.add(event.event_id)
        day = event.effective_at.astimezone(BELEM).date()
        if not (first <= day < end) or not event.confirmed_and_reconciled:
            pending_evidence = True
            continue
        if event.kind == "REALIZED_REVENUE":
            revenue += event.amount_cents
        elif event.kind in ("ELIGIBLE_EXPENSE", "ADMISSIBLE_LOSS", "APPROVED_ADJUSTMENT"):
            costs += event.amount_cents
        # CAPITAL_PRINCIPAL is intentionally excluded from profit.
    member_ids: set[UUID] = set()
    unresolved = False
    for row in reviews:
        if not isinstance(row, MemberCycleReview) or row.tenant_id != tenant_id:
            raise ValueError("Membro de outro tenant")
        if row.member_id in member_ids:
            raise ValueError("Vínculo repetido")
        member_ids.add(row.member_id)
        if row.profit_eligible is None or row.exit_status in (
            "REQUESTED_AWAITING_REVIEW", "APPROVED_BUT_SETTLEMENT_UNVERIFIED"
        ):
            unresolved = True
        if (row.capital_days_weight < 0 or not row.capital_days_weight.is_finite()
                or (row.profit_eligible is False and row.capital_days_weight != 0)):
            raise ValueError("Elegibilidade/peso inconsistentes")
    net = revenue-costs
    profit = max(net, 0)
    # Contrato e conciliação são pré-condições para uma distribuição calculável.
    gated = not contract_compliant or pending_evidence or unresolved
    if gated:
        return AnnualClosingPreview(
            tenant_id, cycle_year, revenue, costs, net, profit,
            0, 0, (), 0, 0, profit, "PENDING_REVIEW_OR_RECONCILIATION"
        )
    admin = (Decimal(profit) * Decimal(admin_basis) / Decimal(10000)).quantize(
        Decimal("1"), rounding=ROUND_HALF_UP
    )
    admin_cents = int(admin)
    pool = profit - admin_cents
    weights = [(row.member_id, row.capital_days_weight) for row in reviews
               if row.profit_eligible and row.capital_days_weight > 0]
    total_weight = sum((w for _, w in weights), Decimal(0))
    base_cents: dict[UUID, int] = {row.member_id: 0 for row in reviews}
    bonus: dict[UUID, int] = {row.member_id: 0 for row in reviews}
    remainders = []
    wallet = 0
    retained = 0
    status = "SIMULATED_NOT_AUTHORIZED"
    if pool and total_weight == 0:
        retained = pool
        status = "NO_ELIGIBLE_MEMBERS_RESERVE_PENDING"
    elif pool and total_weight:
        for mid, weight in weights:
            exact = Decimal(pool) * weight / total_weight
            truncated = int(exact)
            base_cents[mid] = truncated
            remainders.append((-(exact-Decimal(truncated)), str(mid), mid))
        wallet = pool-sum(base_cents.values())
        for _, _, mid in sorted(remainders)[:wallet]:
            bonus[mid] += 1
    shares = tuple(sorted((
        MemberClosingShare(row.member_id, bool(row.profit_eligible),
                           row.capital_days_weight, base_cents[row.member_id],
                           bonus[row.member_id],
                           base_cents[row.member_id]+bonus[row.member_id])
        for row in reviews
    ), key=lambda v: str(v.member_id)))
    awarded = sum(x.final_cents for x in shares)
    if admin_cents+awarded+retained != profit:
        raise AssertionError("Diferença de centavos na apuração")
    if not retained and wallet != sum(x.technical_bonus_cent for x in shares):
        raise AssertionError("Carteira técnica não foi integralmente atribuída")
    return AnnualClosingPreview(
        tenant_id, cycle_year, revenue, costs, net, profit, admin_cents, pool,
        shares, wallet, 0, retained, status
    )
