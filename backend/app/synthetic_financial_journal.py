"""M1721–M1880: diário sintético encadeado, offline e SEM efeitos.

Hash-chain demonstra somente consistência interna de fixtures. SHA-256 não
autentica banco, provedor, assinatura, titularidade ou prova jurídica.
Nunca escrever no livro-razão real, liberar Pix, lucro ou restituição.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import hmac
import json
import re
from uuid import UUID

from .financial_cashboxes import CashboxRoute, DuePayment
from .financial_sandbox_reconciliation import SandboxIntent

CONTRACT = "AI_STUDIO_M1880_SYNTHETIC_JOURNAL_V1"
MAX_EVENTS = 1000
MAX_INTENTS = 500
MAX_CENTS = 999_999_999_999
ZERO_HASH = "0" * 64
PROVIDER_SOURCE = "SYNTHETIC_GET_FIXTURE"
KINDS = frozenset(("APPROVED", "REFUNDED", "CHARGEBACK", "DISPUTE_OPEN"))
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_ID = re.compile(r"[0-9]{1,40}\Z")
_OP = re.compile(r"[A-Za-z0-9._:-]{1,100}\Z")


def _cents(value: int) -> int:
    if type(value) is not int or not 0 <= value <= MAX_CENTS:
        raise ValueError("Centavos inválidos no diário")
    return value


@dataclass(frozen=True)
class LabJournalEvent:
    event_id: UUID
    sequence: int
    operation_key: str
    provider_payment_id: str
    collector_id: str
    tenant_id: UUID | None
    kind: str
    amount_cents: int
    occurred_at: datetime
    source: str = PROVIDER_SOURCE

    def __post_init__(self):
        if (type(self.event_id) is not UUID
                or type(self.sequence) is not int or self.sequence < 1
                or not isinstance(self.operation_key, str)
                or not _OP.fullmatch(self.operation_key)
                or not isinstance(self.provider_payment_id, str)
                or not _ID.fullmatch(self.provider_payment_id)
                or not isinstance(self.collector_id, str)
                or not _ID.fullmatch(self.collector_id)
                or (self.tenant_id is not None and type(self.tenant_id) is not UUID)
                or self.kind not in KINDS
                or self.source != PROVIDER_SOURCE
                or type(self.occurred_at) is not datetime
                or self.occurred_at.utcoffset() is None):
            raise ValueError("Evento sintético sem identidade ou sequência auditável")
        _cents(self.amount_cents)
        if ((self.kind == "DISPUTE_OPEN" and self.amount_cents != 0)
                or (self.kind != "DISPUTE_OPEN" and self.amount_cents == 0)):
            raise ValueError("Evento sem valor adequado para o tipo")


@dataclass(frozen=True)
class LabJournalLink:
    event: LabJournalEvent
    previous_hash: str
    event_hash: str


@dataclass(frozen=True)
class LabOperationPosition:
    operation_key: str
    provider_payment_id: str
    collector_id: str
    tenant_id: UUID | None
    approved_cents: int
    refunded_cents: int
    chargeback_cents: int
    unreversed_cents: int
    disputed: bool
    status: str
    synthetic_only: bool = True
    bank_reconciled: bool = False


@dataclass(frozen=True)
class LabJournalAudit:
    route: CashboxRoute
    chain_head: str
    event_count: int
    approved_cents: int
    refunded_cents: int
    chargeback_cents: int
    unreversed_cents: int
    blocked_count: int
    positions: tuple[LabOperationPosition, ...]
    status: str
    source: str = PROVIDER_SOURCE
    contract: str = CONTRACT
    synthetic_only: bool = True
    chain_is_provenance: bool = False
    bank_reconciled: bool = False
    capital_confirmed_cents: None = None
    financial_closing_authorized: bool = False
    real_payments_enabled: bool = False
    payout_authorized: bool = False
    ledger_written: bool = False


def _event_bytes(event: LabJournalEvent) -> bytes:
    # Canonicalização estável entre Python 3.10+; não usa floats nem timezone local.
    utc = event.occurred_at.astimezone(timezone.utc).isoformat(timespec="microseconds")
    record = {
        "event_id": str(event.event_id),
        "sequence": event.sequence,
        "operation_key": event.operation_key,
        "provider_payment_id": event.provider_payment_id,
        "collector_id": event.collector_id,
        "tenant_id": str(event.tenant_id) if event.tenant_id else None,
        "kind": event.kind,
        "amount_cents": event.amount_cents,
        "occurred_at_utc": utc,
        "source": event.source,
        "contract": CONTRACT,
    }
    return json.dumps(record, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True).encode("ascii")


def _hash_link(previous: str, event: LabJournalEvent) -> str:
    return hashlib.sha256(
        b"frcaixinha-ai-studio-synthetic-ledger-v1\0"
        + previous.encode("ascii") + b"\0" + _event_bytes(event)
    ).hexdigest()


def seal_synthetic_journal(events: tuple[LabJournalEvent, ...]) -> tuple[LabJournalLink, ...]:
    """Gera encadeamento determinístico; NÃO assina, autentica ou persiste."""
    if type(events) is not tuple or len(events) > MAX_EVENTS:
        raise ValueError("Tamanho do diário inválido")
    head = ZERO_HASH
    links = []
    for n, event in enumerate(events, start=1):
        if not isinstance(event, LabJournalEvent) or event.sequence != n:
            raise ValueError("A sequência deve ser contínua desde 1")
        digest = _hash_link(head, event)
        links.append(LabJournalLink(event, head, digest))
        head = digest
    return tuple(links)


def audit_synthetic_journal(
    *, route: CashboxRoute, intents: tuple[SandboxIntent, ...],
    links: tuple[LabJournalLink, ...],
) -> LabJournalAudit:
    """Reexecuta e verifica a cadeia por CAIXA, sem confiar em fixtures externas.

    A ordem nunca é corrigida por sorting; gaps, replay e divergências rejeitam
    todo o relatório. Até a posição APPROVED permanece somente sintética.
    """
    if (not isinstance(route, CashboxRoute)
            or type(intents) is not tuple or len(intents) > MAX_INTENTS
            or type(links) is not tuple or len(links) > MAX_EVENTS):
        raise ValueError("Diário excede os limites")
    seen_keys = set()
    seen_idempotency = set()
    seen_payments = set()
    seen_refs = set()
    operations: dict[str, DuePayment] = {}
    for intent in intents:
        if not isinstance(intent, SandboxIntent):
            raise ValueError("Intenção não é sandbox")
        p = intent.payment
        if p.route != route:
            raise ValueError("Tentativa de misturar caixas ou tenants")
        if (intent.operation_key in seen_keys
                or intent.idempotency_key in seen_idempotency
                or p.provider_payment_id in seen_payments
                or p.external_reference in seen_refs):
            raise ValueError("Duplicidade de identidade de intenção")
        seen_keys.add(intent.operation_key)
        seen_idempotency.add(intent.idempotency_key)
        seen_payments.add(p.provider_payment_id)
        seen_refs.add(p.external_reference)
        operations[intent.operation_key] = p
    seen_events = set()
    positions = {name: {
        "approved": 0, "refunded": 0, "chargeback": 0,
        "disputed": False, "approved_once": False, "last_at": None
    } for name in operations}
    head = ZERO_HASH
    for n, link in enumerate(links, start=1):
        if not isinstance(link, LabJournalLink) or not isinstance(link.event, LabJournalEvent):
            raise ValueError("Ligação do diário malformada")
        e = link.event
        if (e.sequence != n or e.event_id in seen_events
                or not isinstance(link.previous_hash, str)
                or not isinstance(link.event_hash, str)
                or not _HASH.fullmatch(link.previous_hash)
                or not _HASH.fullmatch(link.event_hash)
                or not hmac.compare_digest(link.previous_hash, head)
                or not hmac.compare_digest(link.event_hash, _hash_link(head, e))):
            raise ValueError("Sequência, replay ou hash do diário inválido")
        head = link.event_hash
        seen_events.add(e.event_id)
        expected = operations.get(e.operation_key)
        if (expected is None or e.provider_payment_id != expected.provider_payment_id
                or e.collector_id != route.collector_id
                or e.tenant_id != route.tenant_id):
            raise ValueError("Evento órfão ou de outro caixa")
        state = positions[e.operation_key]
        if state["last_at"] is not None and e.occurred_at < state["last_at"]:
            raise ValueError("Reordenação temporal para a operação")
        state["last_at"] = e.occurred_at
        if e.kind == "APPROVED":
            if state["approved_once"] or e.amount_cents != expected.amount_cents:
                raise ValueError("Crédito duplicado ou divergente")
            state["approved_once"] = True
            state["approved"] = e.amount_cents
        else:
            if not state["approved_once"]:
                raise ValueError("Estorno ou contestação sem crédito original")
            if e.kind == "DISPUTE_OPEN":
                if state["disputed"]:
                    raise ValueError("Contestação repetida")
                state["disputed"] = True
            elif e.kind == "REFUNDED":
                state["refunded"] += e.amount_cents
            elif e.kind == "CHARGEBACK":
                if state["chargeback"]:
                    raise ValueError("Chargeback repetido")
                state["chargeback"] += e.amount_cents
                state["disputed"] = True
            if state["refunded"] + state["chargeback"] > state["approved"]:
                raise ValueError("Reversões excedem o crédito original")
    report_positions = []
    for name in sorted(operations):
        p = operations[name]
        state = positions[name]
        remain = state["approved"] - state["refunded"] - state["chargeback"]
        if not state["approved_once"]:
            status = "NO_SYNTHETIC_APPROVAL"
        elif state["disputed"]:
            status = "DISPUTE_HOLD"
        elif state["refunded"] == state["approved"]:
            status = "FULLY_REFUNDED"
        elif state["refunded"]:
            status = "PARTIALLY_REFUNDED"
        else:
            status = "APPROVED_FIXTURE_ONLY"
        report_positions.append(LabOperationPosition(
            name, p.provider_payment_id, route.collector_id, route.tenant_id,
            state["approved"], state["refunded"], state["chargeback"],
            remain, state["disputed"], status))
    positions_tuple = tuple(report_positions)
    gross = sum(p.approved_cents for p in positions_tuple)
    refunded = sum(p.refunded_cents for p in positions_tuple)
    charged = sum(p.chargeback_cents for p in positions_tuple)
    remain = sum(p.unreversed_cents for p in positions_tuple)
    if any(v > MAX_CENTS for v in (gross, refunded, charged, remain)):
        raise ValueError("Limite de somatórios excedido")
    if remain != gross - refunded - charged:
        raise AssertionError("Conservação de centavos violada")
    blocked = sum(p.status != "APPROVED_FIXTURE_ONLY" for p in positions_tuple)
    return LabJournalAudit(
        route=route, chain_head=head, event_count=len(links),
        approved_cents=gross, refunded_cents=refunded,
        chargeback_cents=charged, unreversed_cents=remain,
        blocked_count=blocked, positions=positions_tuple,
        status=("REVIEW_REQUIRED" if not positions_tuple or blocked
                else "SYNTHETIC_CHAIN_MATCH_ONLY"))


@dataclass(frozen=True)
class ExitEvidenceGate:
    tenant_id: UUID
    membership_id: UUID
    capital_registered_cents: int
    loan_due_registered_cents: int
    disputed_registered_cents: int
    confirmed_payout_cents: None
    candidate_restitution_cents: None
    status: str
    independent_reconciliation_verified: bool = False
    rights_preserved: bool = True
    automatic_setoff_allowed: bool = False
    payment_authorized: bool = False


def preview_exit_evidence_gate(
    *, tenant_id: UUID, membership_id: UUID, registered_capital_cents: int,
    registered_loan_due_cents: int, disputed_cents: int, reviewer_refs: tuple[str, ...],
) -> ExitEvidenceGate:
    """Declarações não são autenticação de prova; valor líquido permanece nulo."""
    if type(tenant_id) is not UUID or type(membership_id) is not UUID:
        raise ValueError("Identidade de saída inválida")
    for value in (registered_capital_cents, registered_loan_due_cents, disputed_cents):
        _cents(value)
    if (type(reviewer_refs) is not tuple or len(reviewer_refs) > 3
            or any(not isinstance(ref, str) or not 8 <= len(ref) <= 120
                   for ref in reviewer_refs)
            or len(set(reviewer_refs)) != len(reviewer_refs)):
        raise ValueError("Referências de revisão inválidas")
    return ExitEvidenceGate(
        tenant_id, membership_id, registered_capital_cents,
        registered_loan_due_cents, disputed_cents, None, None,
        ("INDEPENDENT_EVIDENCE_PENDING" if len(reviewer_refs) < 3
         else "DECLARED_REFERENCES_REQUIRE_EXTERNAL_VERIFICATION"))
