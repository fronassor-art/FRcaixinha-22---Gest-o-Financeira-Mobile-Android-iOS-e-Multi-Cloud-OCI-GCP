"""AI Studio M1561+: laboratório DETERMINÍSTICO de conciliação, sem I/O.

Não conecta ao Mercado Pago, não consulta PostgreSQL, não aceita recibos como
prova bancária, não executa Pix e não modifica qualquer lançamento. Uma
resposta de fixture "approved" NUNCA libera fechamento ou capital.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, Mapping
from uuid import UUID
import re

from .financial_cashboxes import (
    CashboxRoute, DuePayment, PLATFORM_SAAS, validate_payment_against_cashbox,
)
from .loan_arrears_contract import (
    LoanArrearsPolicy, LoanInstallmentState, quote_loan_arrears,
    apply_partial_loan_payment, ordered_loan_debt,
)
from .mercado_pago_safety import ExpectedPayment, matches_full_refund, verify_webhook_signature

LAB_CONTRACT = "AI_STUDIO_M1720_SYNTHETIC_FINANCE_V1"
MAX_OPERATIONS = 500
MAX_CENTS = 999_999_999_999
PROVIDER_SOURCE = "SYNTHETIC_GET_FIXTURE"
PROVIDER_STATES = frozenset((
    "pending", "in_process", "approved", "rejected", "cancelled",
    "refunded", "charged_back", "in_mediation",
))
ACTIVE_LOAN_STATES = frozenset(("DESEMBOLSADO", "INADIMPLENTE"))
PROPOSAL_STATES = frozenset(("SOLICITADO", "APROVADO", "RESERVADO"))


def _money(value: int, *, positive: bool = False) -> int:
    if type(value) is not int or not (1 if positive else 0) <= value <= MAX_CENTS:
        raise ValueError("Centavos inválidos ou acima do limite auditável")
    return value


@dataclass(frozen=True)
class SandboxIntent:
    operation_key: str
    payment: DuePayment
    idempotency_key: str

    def __post_init__(self) -> None:
        if not isinstance(self.payment, DuePayment) or self.payment.live_mode is not False:
            raise ValueError("Somente operações declaradamente sandbox")
        if not isinstance(self.operation_key, str) or not re.fullmatch(
            r"[A-Za-z0-9._:-]{1,100}", self.operation_key
        ):
            raise ValueError("Chave de operação inválida")
        if not isinstance(self.idempotency_key, str) or not re.fullmatch(
            r"[A-Za-z0-9_-]{8,64}", self.idempotency_key
        ):
            raise ValueError("Idempotência explícita e estável exigida")


@dataclass(frozen=True)
class ProviderFixture:
    provider_payment_id: str
    payload: Mapping[str, Any]
    source: str = PROVIDER_SOURCE

    def __post_init__(self) -> None:
        if (not isinstance(self.provider_payment_id, str)
                or not re.fullmatch(r"[0-9]{1,40}", self.provider_payment_id)
                or not isinstance(self.payload, Mapping)
                or self.source != PROVIDER_SOURCE):
            raise ValueError("Fixture GET inválida ou origem não sintética")


@dataclass(frozen=True)
class WebhookFixture:
    request_id: str
    resource_id: str
    signature: str
    received_at: datetime

    def __post_init__(self) -> None:
        if (not isinstance(self.request_id, str) or not 1 <= len(self.request_id) <= 120
                or any(c in self.request_id for c in "\r\n;")
                or not isinstance(self.resource_id, str)
                or not re.fullmatch(r"[0-9]{1,40}", self.resource_id)
                or not isinstance(self.signature, str)
                or len(self.signature) > 256
                or type(self.received_at) is not datetime
                or self.received_at.utcoffset() is None):
            raise ValueError("Notificação sintética malformada")


@dataclass(frozen=True)
class PaymentSimulation:
    operation_key: str
    provider_payment_id: str
    purpose: str
    tenant_id: UUID | None
    amount_cents: int
    finding: str
    registered_as_paid: bool = False
    bank_reconciled: bool = False
    ledger_written: bool = False


@dataclass(frozen=True)
class SandboxReconciliationReport:
    items: tuple[PaymentSimulation, ...]
    provider_orphans: tuple[str, ...]
    webhook_findings: tuple[str, ...]
    accepted_webhook_count: int
    rejected_webhook_count: int
    replayed_webhook_count: int
    status: str
    lab_contract: str = LAB_CONTRACT
    simulation_only: bool = True
    bank_reconciled: bool = False
    real_payments_enabled: bool = False
    ledger_written: bool = False
    closing_authorized: bool = False
    payout_authorized: bool = False


def _validate_receivers(platform_collector_id: str, tenants: Mapping[UUID, str]) -> None:
    if (not isinstance(platform_collector_id, str)
            or not re.fullmatch(r"[0-9]{1,40}", platform_collector_id)
            or not isinstance(tenants, Mapping) or len(tenants) > MAX_OPERATIONS):
        raise ValueError("Mapa de recebedores inválido")
    collectors = [platform_collector_id]
    for tenant_id, collector in tenants.items():
        if (type(tenant_id) is not UUID or not isinstance(collector, str)
                or not re.fullmatch(r"[0-9]{1,40}", collector)):
            raise ValueError("Conta de tenant inválida")
        collectors.append(collector)
    if len(collectors) != len(set(collectors)):
        raise ValueError("Recebedor compartilhado entre caixas ou tenants")


def _matching_identity(expected: DuePayment, payload: Mapping[str, Any],
                       platform: str, tenants: Mapping[UUID, str]) -> bool:
    """Verifica campos invariantes via validador existente, sem afirmar liquidação."""
    if not isinstance(payload.get("status"), str) or payload["status"] not in PROVIDER_STATES:
        return False
    # Somente cópia temporária para reaproveitar validação da identidade/valor;
    # o status original determina os bloqueios, nunca é alterado no input.
    candidate = dict(payload)
    candidate["status"] = "approved"
    return validate_payment_against_cashbox(
        expected, candidate, platform_collector_id=platform, tenant_collectors=tenants,
    )


def _webhook_checks(notices: tuple[WebhookFixture, ...], *, secret: str,
                    now: datetime, known_ids: set[str]) -> tuple[tuple[str, ...], int, int, int]:
    if type(notices) is not tuple or len(notices) > MAX_OPERATIONS:
        raise ValueError("Excesso de notificações")
    if not isinstance(secret, str) or not 20 <= len(secret) <= 256:
        raise ValueError("Segredo sintético obrigatório")
    seen: dict[str, str] = {}
    findings: list[str] = []
    accepted = rejected = replayed = 0
    for notice in notices:
        if not isinstance(notice, WebhookFixture):
            raise ValueError("Notificação inválida")
        previous = seen.get(notice.request_id)
        if previous is not None:
            replayed += 1
            findings.append("WEBHOOK_REPLAY" if previous == notice.resource_id
                            else "WEBHOOK_ID_CONFLICT")
            continue
        seen[notice.request_id] = notice.resource_id
        pieces = [x.strip() for x in notice.signature.split(",")]
        ts_fields = [x[3:] for x in pieces if x.startswith("ts=")]
        ts_valid = (len(ts_fields) == 1 and ts_fields[0].isascii()
                    and ts_fields[0].isdigit() and len(ts_fields[0]) in (10, 13))
        issued = (int(ts_fields[0]) / (1000 if len(ts_fields[0]) == 13 else 1)
                  if ts_valid else None)
        received = notice.received_at.timestamp()
        valid = (issued is not None
                 and abs(now.timestamp() - issued) <= 300
                 and abs(received - issued) <= 300
                 and notice.resource_id in known_ids
                 and verify_webhook_signature(
                     secret=secret, signature=notice.signature,
                     request_id=notice.request_id, resource_id=notice.resource_id))
        if valid:
            accepted += 1
        else:
            rejected += 1
            findings.append("WEBHOOK_INVALID_OR_UNMATCHED")
    return tuple(findings), accepted, rejected, replayed


def preview_sandbox_reconciliation(
    *, intents: tuple[SandboxIntent, ...], fixtures: tuple[ProviderFixture, ...],
    webhooks: tuple[WebhookFixture, ...], platform_collector_id: str,
    tenant_collectors: Mapping[UUID, str], synthetic_webhook_secret: str,
    as_of: datetime,
) -> SandboxReconciliationReport:
    """Somente fixtures locais: aprovação simulada nunca é prova de banco."""
    if (type(as_of) is not datetime or as_of.utcoffset() is None
            or type(intents) is not tuple or len(intents) > MAX_OPERATIONS
            or type(fixtures) is not tuple or len(fixtures) > MAX_OPERATIONS):
        raise ValueError("Laboratório exige data com fuso e coleções limitadas")
    _validate_receivers(platform_collector_id, tenant_collectors)
    keys: set[str] = set()
    idempotency: set[str] = set()
    refs: set[tuple[str, str]] = set()
    payments: set[str] = set()
    for intent in intents:
        if not isinstance(intent, SandboxIntent):
            raise ValueError("Intenção não sintética")
        p = intent.payment
        uniqueness = (p.route.collector_id, p.external_reference)
        if (intent.operation_key in keys or intent.idempotency_key in idempotency
                or uniqueness in refs or p.provider_payment_id in payments):
            raise ValueError("Duplicidade de intenção, referência ou idempotência")
        keys.add(intent.operation_key)
        idempotency.add(intent.idempotency_key)
        refs.add(uniqueness)
        payments.add(p.provider_payment_id)
    observations: dict[str, ProviderFixture] = {}
    for fixture in fixtures:
        if not isinstance(fixture, ProviderFixture):
            raise ValueError("Observação não sintética")
        if fixture.provider_payment_id in observations:
            raise ValueError("Resposta duplicada; nenhuma conciliação")
        observations[fixture.provider_payment_id] = fixture
    findings, accepted, rejected, replayed = _webhook_checks(
        webhooks, secret=synthetic_webhook_secret, now=as_of, known_ids=payments)
    items: list[PaymentSimulation] = []
    for intent in sorted(intents, key=lambda i: i.operation_key):
        expected = intent.payment
        fixture = observations.get(expected.provider_payment_id)
        if fixture is None:
            finding = "NO_SYNTHETIC_GET"
        else:
            payload = fixture.payload
            if str(payload.get("id", "")) != fixture.provider_payment_id or not (
                _matching_identity(expected, payload, platform_collector_id, tenant_collectors)
            ):
                finding = "PROVIDER_IDENTITY_OR_AMOUNT_MISMATCH"
            elif payload["status"] == "approved":
                finding = "APPROVED_FIXTURE_ONLY"
            elif payload["status"] == "refunded":
                expected_payment = ExpectedPayment(
                    expected.provider_payment_id, expected.route.collector_id,
                    expected.external_reference, expected.amount_cents, False)
                finding = ("FULL_REFUND_FIXTURE_ONLY" if matches_full_refund(
                    expected_payment, payload) else "REFUND_NOT_FULLY_ATTESTED")
            elif payload["status"] in ("charged_back", "in_mediation"):
                finding = "DISPUTE_OR_CHARGEBACK_HOLD"
            else:
                finding = "PROVIDER_" + payload["status"].upper()
        items.append(PaymentSimulation(
            intent.operation_key, expected.provider_payment_id,
            expected.route.purpose, expected.route.tenant_id,
            expected.amount_cents, finding))
    orphans = tuple(sorted(set(observations) - payments))
    status = ("REVIEW_REQUIRED" if (not intents or orphans or rejected or replayed
              or any(x.finding not in ("APPROVED_FIXTURE_ONLY", "FULL_REFUND_FIXTURE_ONLY")
                     for x in items)) else "SYNTHETIC_MATCH_ONLY")
    return SandboxReconciliationReport(
        items=tuple(items), provider_orphans=orphans, webhook_findings=findings,
        accepted_webhook_count=accepted, rejected_webhook_count=rejected,
        replayed_webhook_count=replayed, status=status)


@dataclass(frozen=True)
class InstallmentAllocationPreview:
    installment_id: UUID
    interest_cents: int
    mora_cents: int
    fine_cents: int
    principal_cents: int
    applied_cents: int


@dataclass(frozen=True)
class LoanAllocationPreview:
    allocations: tuple[InstallmentAllocationPreview, ...]
    input_payment_cents: int
    applied_cents: int
    unapplied_cents: int
    future_installment_count: int
    status: str
    simulation_only: bool = True
    principal_amortized_in_ledger: bool = False
    bank_reconciled: bool = False
    payout_authorized: bool = False


def preview_loan_allocation(
    *, tenant_id: UUID, loan_status: str, installment_rows: tuple[LoanInstallmentState, ...],
    amount_cents: int, as_of: date, policy: LoanArrearsPolicy,
) -> LoanAllocationPreview:
    """Ordem de vencimento: remuneratórios > mora > multa > principal.

    Não imputa juros futuros, não contabiliza antecipação, não executa quitação.
    Mora segue a prévia do oráculo existente; não é cobrança autorizada.
    """
    if (type(tenant_id) is not UUID or type(as_of) is not date
            or not isinstance(policy, LoanArrearsPolicy)
            or loan_status not in (ACTIVE_LOAN_STATES | PROPOSAL_STATES)):
        raise ValueError("Crédito, data ou política inválida")
    _money(amount_cents)
    rows = ordered_loan_debt(tenant_id, installment_rows)
    if loan_status in PROPOSAL_STATES:
        return LoanAllocationPreview((), amount_cents, 0, amount_cents,
                                     len(rows), "PROPOSAL_NOT_COLLECTIBLE")
    available = amount_cents
    allocations: list[InstallmentAllocationPreview] = []
    future = 0
    for row in rows:
        if row.due_on > as_of:
            future += 1
            continue
        quote = quote_loan_arrears(row, as_of, policy)
        if not available or not quote.total_due_cents:
            continue
        share = min(available, quote.total_due_cents)
        applied = apply_partial_loan_payment(quote, share)
        allocations.append(InstallmentAllocationPreview(
            row.installment_id, applied.paid_interest_cents,
            applied.paid_mora_cents, applied.paid_fine_cents,
            applied.paid_principal_cents, share))
        available -= share
    done = amount_cents - available
    if done != sum(x.applied_cents for x in allocations):
        raise AssertionError("Quebra de conservação de centavos")
    return LoanAllocationPreview(
        tuple(allocations), amount_cents, done, available, future,
        "SURPLUS_REQUIRES_REVIEW" if available else "SYNTHETIC_ALLOCATION_ONLY")


@dataclass(frozen=True)
class ExitRestitutionReadiness:
    tenant_id: UUID
    membership_id: UUID
    registered_capital_cents: int
    registered_due_loan_cents: int
    disputed_cents: int
    evidence_complete: bool
    status: str
    net_exit_restitution_cents: None = None
    bank_reconciled: bool = False
    setoff_authorized: bool = False
    rights_preserved: bool = True
    payout_authorized: bool = False


def preview_exit_restitution_readiness(
    *, tenant_id: UUID, membership_id: UUID, registered_capital_cents: int,
    registered_due_loan_cents: int, disputed_cents: int,
    has_bank_proof: bool, has_final_contract_decision: bool,
    independent_review_complete: bool,
) -> ExitRestitutionReadiness:
    """Checklist de provas, NÃO cálculo de restituição líquida.

    Nenhum saldo registrado é equiparado a extrato; disputa não sofre desconto
    automático, mesmo que as três declarações booleanas sejam True.
    """
    if type(tenant_id) is not UUID or type(membership_id) is not UUID:
        raise ValueError("Contexto do membro inválido")
    for x in (registered_capital_cents, registered_due_loan_cents, disputed_cents):
        _money(x)
    for flag in (has_bank_proof, has_final_contract_decision, independent_review_complete):
        if type(flag) is not bool:
            raise ValueError("Declaração de prova precisa ser booleana")
    complete = (has_bank_proof and has_final_contract_decision
                and independent_review_complete and disputed_cents == 0)
    return ExitRestitutionReadiness(
        tenant_id, membership_id, registered_capital_cents,
        registered_due_loan_cents, disputed_cents, complete,
        "DECLARED_PRECONDITIONS_NOT_VERIFIED" if complete
        else "EVIDENCE_OR_DISPUTE_PENDING")
