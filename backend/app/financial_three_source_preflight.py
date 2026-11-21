"""AI Studio M2041-M2200: pré-conciliação de 3 fontes SINTÉTICAS, sem I/O.

Não consulta provedor, extrato ou banco, não confirma liquidação. Confronta
apenas intenção, resposta de GET SIMULADA e extrato sintético independente.
Nenhuma prévia libera capital, juros, fechamento, empréstimos, Pix ou estorno.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping
from uuid import UUID
import re

from .financial_cashboxes import (
    CashboxRoute, DuePayment, validate_payment_against_cashbox,
)
from .financial_sandbox_reconciliation import (
    SandboxIntent, ProviderFixture, MAX_CENTS, MAX_OPERATIONS, PROVIDER_SOURCE,
)

CONTRACT = "AI_STUDIO_M2200_THREE_SOURCE_SYNTHETIC_V1"
SETTLEMENT_SOURCE = "SYNTHETIC_SETTLEMENT_STATEMENT_FIXTURE"
ACCOUNTING_SOURCE = "SYNTHETIC_ACCOUNTING_PLAN_FIXTURE"
MAX_TOTAL = MAX_CENTS
REF_RE = re.compile(r"[A-Za-z0-9._:-]{8,120}\Z")
PAYMENT_RE = re.compile(r"[0-9]{1,40}\Z")
APPROVED = "approved"
SETTLED = "synthetic_settled"
EVENT_STATUSES = frozenset((APPROVED, "pending", "rejected",
                             "refunded", "charged_back", "in_mediation"))


def _cents(value: int) -> int:
    if type(value) is not int or not 0 <= value <= MAX_CENTS:
        raise ValueError("Centavos fora do limite ou tipo inválido")
    return value


def _identifier(value: str, pattern: re.Pattern[str]) -> str:
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise ValueError("Identidade sintética inválida")
    return value


@dataclass(frozen=True)
class SettlementFixture:
    payment_id: str
    tenant_id: UUID | None
    collector_id: str
    external_reference: str
    gross_cents: int
    fee_cents: int
    net_cents: int
    statement_reference: str
    settled_at: datetime
    status: str = SETTLED
    currency: str = "BRL"
    live_mode: bool = False
    source: str = SETTLEMENT_SOURCE

    def __post_init__(self) -> None:
        _identifier(self.payment_id, PAYMENT_RE)
        _identifier(self.collector_id, PAYMENT_RE)
        _identifier(self.statement_reference, REF_RE)
        if (self.tenant_id is not None and type(self.tenant_id) is not UUID
                or not isinstance(self.external_reference, str)
                or not 1 <= len(self.external_reference) <= 100
                or not re.fullmatch(r"[A-Za-z0-9._:-]+", self.external_reference)
                or type(self.settled_at) is not datetime
                or self.settled_at.utcoffset() is None
                or self.currency != "BRL"
                or self.status not in (SETTLED, "synthetic_pending", "synthetic_disputed")
                or self.live_mode is not False
                or self.source != SETTLEMENT_SOURCE):
            raise ValueError("Extrato sintético sem contexto ou proveniência")
        for amount in (self.gross_cents, self.fee_cents, self.net_cents):
            _cents(amount)
        if (self.gross_cents <= 0
                or self.fee_cents > self.gross_cents
                or self.net_cents != self.gross_cents - self.fee_cents):
            raise ValueError("Bruto - taxa deve equivaler exatamente ao líquido")


@dataclass(frozen=True)
class AccountingFixture:
    payment_id: str
    tenant_id: UUID | None
    collector_id: str
    external_reference: str
    debit_cents: int
    credit_cents: int
    ledger_reference: str
    effective_at: datetime
    source: str = ACCOUNTING_SOURCE

    def __post_init__(self) -> None:
        _identifier(self.payment_id, PAYMENT_RE)
        _identifier(self.collector_id, PAYMENT_RE)
        _identifier(self.ledger_reference, REF_RE)
        if (self.tenant_id is not None and type(self.tenant_id) is not UUID
                or not isinstance(self.external_reference, str)
                or not re.fullmatch(r"[A-Za-z0-9._:-]{1,100}", self.external_reference)
                or type(self.effective_at) is not datetime
                or self.effective_at.utcoffset() is None
                or self.source != ACCOUNTING_SOURCE):
            raise ValueError("Plano contábil sintético inválido")
        _cents(self.debit_cents)
        _cents(self.credit_cents)
        if self.debit_cents != self.credit_cents or self.debit_cents == 0:
            raise ValueError("Plano sintético exige partidas dobradas iguais")


@dataclass(frozen=True)
class ThreeSourceFinding:
    operation_key: str
    provider_payment_id: str
    tenant_id: UUID | None
    collector_id: str
    expected_gross_cents: int
    synthetic_net_cents: int | None
    synthetic_fee_cents: int | None
    finding: str
    can_mark_paid: bool = field(default=False, init=False)
    bank_reconciled: bool = field(default=False, init=False)
    financial_effect_applied: bool = field(default=False, init=False)
    ledger_written: bool = field(default=False, init=False)


@dataclass(frozen=True)
class ThreeSourceReport:
    items: tuple[ThreeSourceFinding, ...]
    orphan_provider_ids: tuple[str, ...]
    orphan_settlement_ids: tuple[str, ...]
    orphan_accounting_ids: tuple[str, ...]
    total_expected_cents: int
    total_synthetic_gross_cents: int
    total_synthetic_fees_cents: int
    total_synthetic_net_cents: int
    status: str
    contract: str = CONTRACT
    all_sources_synthetic: bool = field(default=True, init=False)
    settlement_is_bank_proof: bool = field(default=False, init=False)
    accounting_is_posted_ledger: bool = field(default=False, init=False)
    bank_reconciled: bool = field(default=False, init=False)
    real_payments_enabled: bool = field(default=False, init=False)
    financial_effect_applied: bool = field(default=False, init=False)
    financial_closing_authorized: bool = field(default=False, init=False)
    capital_confirmed_cents: None = field(default=None, init=False)
    payout_authorized: bool = field(default=False, init=False)


def _fixtures_by_id(rows: tuple, cls: type, attribute: str, refs: str | None) -> dict[str, Any]:
    if type(rows) is not tuple or len(rows) > MAX_OPERATIONS:
        raise ValueError("Coleção de fixtures acima do limite")
    result = {}
    seen_refs = set()
    for row in rows:
        if not isinstance(row, cls):
            raise ValueError("Fixture de origem incompatível")
        key = getattr(row, attribute)
        if key in result:
            raise ValueError("Identificador do provedor duplicado")
        if refs:
            ref = getattr(row, refs)
            if ref in seen_refs:
                raise ValueError("Referência documental reutilizada")
            seen_refs.add(ref)
        result[key] = row
    return result


def preview_three_source_evidence(
    *, intents: tuple[SandboxIntent, ...],
    provider_get_fixtures: tuple[ProviderFixture, ...],
    settlement_fixtures: tuple[SettlementFixture, ...],
    accounting_fixtures: tuple[AccountingFixture, ...],
    platform_collector_id: str,
    tenant_collectors: Mapping[UUID, str],
    as_of: datetime,
) -> ThreeSourceReport:
    """Conservação de centavos e identidades. Todos os registros são SIMULADOS.

    Nenhum booleano pode ser usado como prova de banco: os dados são fixtures
    locais, mesmo quando quatro registros combinam exatamente entre si.
    """
    if (type(as_of) is not datetime or as_of.utcoffset() is None
            or type(intents) is not tuple or len(intents) > MAX_OPERATIONS
            or not isinstance(tenant_collectors, Mapping)
            or len(tenant_collectors) > MAX_OPERATIONS
            or not isinstance(platform_collector_id, str)
            or not PAYMENT_RE.fullmatch(platform_collector_id)):
        raise ValueError("Contexto de pré-conciliação inválido")
    receivers = [platform_collector_id]
    for tenant_id, collector in tenant_collectors.items():
        if type(tenant_id) is not UUID:
            raise ValueError("Tenant inválido")
        receivers.append(_identifier(collector, PAYMENT_RE))
    if len(receivers) != len(set(receivers)):
        raise ValueError("Conta recebedora compartilhada por caixas")

    by_key: dict[str, SandboxIntent] = {}
    by_id: dict[str, SandboxIntent] = {}
    idempotency = set()
    external_refs = set()
    total_expected = 0
    for intent in intents:
        if not isinstance(intent, SandboxIntent):
            raise ValueError("Somente intenção de sandbox")
        p = intent.payment
        route = p.route
        if (route.collector_id != (
                platform_collector_id if route.tenant_id is None
                else tenant_collectors.get(route.tenant_id))
                or intent.operation_key in by_key
                or p.provider_payment_id in by_id
                or intent.idempotency_key in idempotency
                or (route.collector_id, p.external_reference) in external_refs):
            raise ValueError("Identidade, caixa ou idempotência conflitante")
        by_key[intent.operation_key] = intent
        by_id[p.provider_payment_id] = intent
        idempotency.add(intent.idempotency_key)
        external_refs.add((route.collector_id, p.external_reference))
        total_expected += p.amount_cents
    if total_expected > MAX_TOTAL:
        raise ValueError("Total de obrigações fora do limite")

    provider = _fixtures_by_id(provider_get_fixtures, ProviderFixture,
                                "provider_payment_id", None)
    settled = _fixtures_by_id(settlement_fixtures, SettlementFixture,
                               "payment_id", "statement_reference")
    accounting = _fixtures_by_id(accounting_fixtures, AccountingFixture,
                                  "payment_id", "ledger_reference")

    findings = []
    gross_total = fee_total = net_total = 0
    for key in sorted(by_key):
        op = by_key[key]
        p = op.payment
        pid = p.provider_payment_id
        pv = provider.get(pid)
        st = settled.get(pid)
        ac = accounting.get(pid)
        reason = "SYNTHETIC_CROSS_SOURCE_MATCH_ONLY"
        if pv is None:
            reason = "MISSING_GET_FIXTURE"
        elif (pv.source != PROVIDER_SOURCE
                or str(pv.payload.get("id", "")) != pid
                or pv.payload.get("status") != APPROVED
                or not validate_payment_against_cashbox(
                    p, pv.payload,
                    platform_collector_id=platform_collector_id,
                    tenant_collectors=tenant_collectors)):
            reason = "PROVIDER_FIXTURE_MISMATCH_OR_NOT_APPROVED"
        elif st is None:
            reason = "MISSING_SETTLEMENT_FIXTURE"
        elif (st.status != SETTLED or st.payment_id != pid
              or st.tenant_id != p.route.tenant_id
              or st.collector_id != p.route.collector_id
              or st.external_reference != p.external_reference
              or st.gross_cents != p.amount_cents
              or st.settled_at > as_of):
            reason = "SETTLEMENT_FIXTURE_MISMATCH_OR_PENDING"
        elif ac is None:
            reason = "MISSING_ACCOUNTING_FIXTURE"
        elif (ac.payment_id != pid or ac.tenant_id != p.route.tenant_id
              or ac.collector_id != p.route.collector_id
              or ac.external_reference != p.external_reference
              or ac.debit_cents != p.amount_cents
              or ac.effective_at > as_of):
            reason = "ACCOUNTING_FIXTURE_MISMATCH"
        if reason == "SYNTHETIC_CROSS_SOURCE_MATCH_ONLY":
            gross_total += st.gross_cents
            fee_total += st.fee_cents
            net_total += st.net_cents
        findings.append(ThreeSourceFinding(
            key, pid, p.route.tenant_id, p.route.collector_id,
            p.amount_cents, st.net_cents if st else None,
            st.fee_cents if st else None, reason,
        ))
    totals = (gross_total, fee_total, net_total)
    if any(value > MAX_TOTAL for value in totals) or gross_total != fee_total + net_total:
        raise ValueError("Quebra de conservação agregada em centavos")
    orphans_provider = tuple(sorted(set(provider)-set(by_id)))
    orphans_settlement = tuple(sorted(set(settled)-set(by_id)))
    orphans_accounting = tuple(sorted(set(accounting)-set(by_id)))
    status = ("SYNTHETIC_CROSS_SOURCE_MATCH_ONLY" if intents
              and not (orphans_provider or orphans_settlement or orphans_accounting)
              and all(item.finding == "SYNTHETIC_CROSS_SOURCE_MATCH_ONLY"
                      for item in findings)
              else "REVIEW_REQUIRED")
    return ThreeSourceReport(
        tuple(findings), orphans_provider, orphans_settlement,
        orphans_accounting, total_expected, gross_total, fee_total,
        net_total, status,
    )
