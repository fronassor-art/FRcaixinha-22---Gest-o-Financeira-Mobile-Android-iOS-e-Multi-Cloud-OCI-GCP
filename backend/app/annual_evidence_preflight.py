"""AI Studio M1721–M1880: prévia ANUAL de registros, não de extratos.

Não comprova banco, não confunde capital com receitas, não executa fechamento,
distribuição, débito, cobrança, desconto em restituição ou pagamentos.
Todos os documentos aqui são REFERÊNCIAS declaradas, nunca prova autenticada.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID
from zoneinfo import ZoneInfo
import re

CONTRACT = "AI_STUDIO_M1880_ANNUAL_PRECHECK_V1"
BELEM = ZoneInfo("America/Belem")
MAX_EVENTS = 1000
MAX_CENTS = 999_999_999_999
PROFIT_REVENUES = frozenset(("INTEREST_RECEIPT", "MORA_RECEIPT", "FINE_RECEIPT"))
COSTS = frozenset(("ELIGIBLE_EXPENSE", "ADMISSIBLE_LOSS", "REVENUE_REVERSAL"))
CAPITAL = frozenset(("MEMBER_QUOTA_PRINCIPAL", "LOAN_PRINCIPAL_REPAYMENT"))
KINDS = PROFIT_REVENUES | COSTS | CAPITAL


def _cents(value: int) -> int:
    if type(value) is not int or not 0 <= value <= MAX_CENTS:
        raise ValueError("Valor não auditável em centavos")
    return value


@dataclass(frozen=True)
class RegisteredAnnualEvidence:
    event_id: UUID
    tenant_id: UUID
    kind: str
    amount_cents: int
    effective_at: datetime
    ledger_reference: str
    provider_reference: str | None
    independent_review_reference: str | None
    source: str = "REGISTERED_ONLY"

    def __post_init__(self):
        if (type(self.event_id) is not UUID or type(self.tenant_id) is not UUID
                or self.kind not in KINDS
                or type(self.effective_at) is not datetime
                or self.effective_at.utcoffset() is None
                or not isinstance(self.ledger_reference, str)
                or not re.fullmatch(r"[A-Za-z0-9._:-]{8,120}", self.ledger_reference)
                or self.source != "REGISTERED_ONLY"):
            raise ValueError("Evento financeiro cadastral inválido")
        _cents(self.amount_cents)
        if not self.amount_cents:
            raise ValueError("Movimento sem valor")
        for ref in (self.provider_reference, self.independent_review_reference):
            if ref is not None and (
                not isinstance(ref, str) or
                not re.fullmatch(r"[A-Za-z0-9._:-]{8,120}", ref)
            ):
                raise ValueError("Comprovante cadastral malformado")


@dataclass(frozen=True)
class AnnualRegisteredPreflight:
    tenant_id: UUID
    start: date
    end_exclusive: date
    events_count: int
    recorded_revenue_cents: int
    recorded_expense_loss_reversal_cents: int
    recorded_net_result_cents: int
    recorded_member_capital_cents: int
    recorded_loan_principal_cents: int
    missing_provider_reference_count: int
    missing_independent_review_count: int
    declared_disputes_count: int
    status: str
    contract: str = CONTRACT
    source: str = "REGISTERED_ONLY_NOT_PROVIDER"
    simulation_only: bool = True
    bank_reconciled: bool = False
    distributable_profit_cents: None = None
    available_cash_cents: None = None
    annual_closing_authorized: bool = False
    master_saas_revenue_cents: None = None
    capital_restitution_authorized: bool = False
    pix_enabled: bool = False


def preview_registered_annual_result(
    *, tenant_id: UUID, start: date, end_exclusive: date,
    events: tuple[RegisteredAnnualEvidence, ...],
    disputed_event_ids: tuple[UUID, ...] = (),
) -> AnnualRegisteredPreflight:
    """Prova de conservação *cadastral*, nunca banco/caixa disponível.

    Datas são por America/Belem para um ciclo de duração <=367 dias.
    O código rejeita períodos/ciclos cruzados em vez de truncar histórico.
    """
    if (type(tenant_id) is not UUID or type(start) is not date
            or type(end_exclusive) is not date
            or not start < end_exclusive
            or (end_exclusive - start).days > 367
            or type(events) is not tuple or len(events) > MAX_EVENTS
            or type(disputed_event_ids) is not tuple
            or len(disputed_event_ids) > MAX_EVENTS
            or any(type(item) is not UUID for item in disputed_event_ids)):
        raise ValueError("Ciclo ou coleção inválida")
    if len(set(disputed_event_ids)) != len(disputed_event_ids):
        raise ValueError("Disputa duplicada")
    seen_events = set()
    ledger_refs = set()
    provider_refs = set()
    revenue = costs = quota = principal = 0
    missing_provider = missing_review = 0
    for event in events:
        if not isinstance(event, RegisteredAnnualEvidence) or event.tenant_id != tenant_id:
            raise ValueError("Evento de outro tenant")
        if event.event_id in seen_events or event.ledger_reference in ledger_refs:
            raise ValueError("Evento contábil duplicado")
        day = event.effective_at.astimezone(BELEM).date()
        if not start <= day < end_exclusive:
            raise ValueError("Competência fora do ciclo; período não será ajustado silenciosamente")
        seen_events.add(event.event_id)
        ledger_refs.add(event.ledger_reference)
        if event.provider_reference is None:
            missing_provider += 1
        else:
            if event.provider_reference in provider_refs:
                raise ValueError("Comprovante declarado reutilizado")
            provider_refs.add(event.provider_reference)
        if event.independent_review_reference is None:
            missing_review += 1
        if event.kind in PROFIT_REVENUES:
            revenue += event.amount_cents
        elif event.kind in COSTS:
            costs += event.amount_cents
        elif event.kind == "MEMBER_QUOTA_PRINCIPAL":
            quota += event.amount_cents
        else:
            principal += event.amount_cents
    if not set(disputed_event_ids).issubset(seen_events):
        raise ValueError("Contestação sem evento cadastrado")
    if max(revenue, costs, quota, principal, abs(revenue - costs)) > MAX_CENTS:
        raise ValueError("Agregado ultrapassa limite monetário")
    # Mesmo com 100% de referências declaradas, não existe GET autenticado,
    # extrato comprovado, política jurídica validada ou autorização de Pix.
    status = ("EVIDENCE_REFERENCES_MISSING" if missing_provider or missing_review
              else "DECLARED_REFERENCES_NEED_INDEPENDENT_VERIFICATION")
    if disputed_event_ids:
        status = "DISPUTES_REQUIRE_REVIEW"
    if not events:
        status = "NO_REGISTERED_EVENTS"
    return AnnualRegisteredPreflight(
        tenant_id, start, end_exclusive, len(events),
        revenue, costs, revenue - costs, quota, principal,
        missing_provider, missing_review,
        len(disputed_event_ids), status)
