"""FR Finance M39940: independent evidence SHAPE gate for candidate journals.

No I/O, SQL, provider authentication, persisted idempotency, role verification,
tax verification, release, payout or posting. A matching evidence document is
NOT a verified event. Source documents are treated as untrusted caller input.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
import re
from uuid import UUID

from .exclusive_cashbox_journal_preflight import JournalCandidate
from .exclusive_cashbox_provenance import (
    PLATFORM_MASTER, TENANT_ADMIN_OWN, TENANT_COLLECTIVE, EVENT_SCOPE,
)

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_PROVIDER_ID = re.compile(r"^[0-9]{1,40}$")
_REFERENCE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{5,119}$")
_MAX_CENTS = 999_999_999_999

# Domain and event-to-document type are centrally fixed (no caller overrides).
_DOCUMENT_BY_EVENT = {
    "SAAS_SETTLEMENT": "PROVIDER_SETTLEMENT",
    "PLATFORM_OPERATING_EXPENSE": "FISCAL_EXPENSE",
    "ADMIN_CLOSING_REMUNERATION": "ANNUAL_CLOSING",
    "ADMIN_OWN_EXPENSE": "FISCAL_EXPENSE",
    "MEMBER_CONTRIBUTION": "PROVIDER_SETTLEMENT",
    "TENANT_LOAN_REPAYMENT": "PROVIDER_SETTLEMENT",
    "TENANT_OPERATING_EXPENSE": "FISCAL_EXPENSE",
}
assert set(_DOCUMENT_BY_EVENT) == set(EVENT_SCOPE)

@dataclass(frozen=True)
class EvidenceDraft:
    """Unverified and non-authoritative data from a candidate paper trail."""
    scope: str
    tenant_id: UUID | None
    event_type: str
    journal_fingerprint: str
    evidence_reference: str
    document_kind: str
    document_digest: str
    obligation_amount_cents: int
    preparer_id: UUID
    proposed_reviewer_id: UUID
    provider_payment_id: str | None = None
    provider_collector_id: str | None = None
    provider_observed_at: datetime | None = None
    expense_reference: str | None = None
    cycle_id: UUID | None = None
    policy_id: UUID | None = None
    net_profit_cents: int | None = None
    closing_year: int | None = None


@dataclass(frozen=True)
class EvidencePreflight:
    scope: str
    tenant_id: UUID | None
    journal_fingerprint: str
    state: str = "DOCUMENTARY_CANDIDATE_NOT_AUTHENTICATED"
    document_authenticated: bool = False
    amount_reconciled: bool = False
    actor_authorized: bool = False
    independent_review_verified: bool = False
    original_db_posted: bool = False
    payout_authorized: bool = False
    outstanding_gates: tuple[str, ...] = (
        "SOURCE_AUTHENTICITY_UNATTESTED",
        "ROLE_AND_OWNERSHIP_UNATTESTED",
        "INDEPENDENT_REVIEW_UNATTESTED",
        "TRANSACTIONAL_IDEMPOTENCY_UNATTESTED",
        "PERIOD_AND_ACCOUNTING_RECONCILIATION_UNATTESTED",
        "POSTING_AND_WITHDRAWAL_DISABLED",
    )


def _strict_cents(value: object, *, positive: bool = True) -> int:
    if type(value) is not int or not (1 if positive else 0) <= value <= _MAX_CENTS:
        raise ValueError("Centavos inválidos em documento não verificado")
    return value


def _utc_aware(value: object) -> bool:
    if type(value) is not datetime:
        return False
    return value.tzinfo is not None and value.utcoffset() is not None


def preflight_cashbox_evidence(
    journal: JournalCandidate, evidence: EvidenceDraft,
) -> EvidencePreflight:
    """Only structural consistency; never assert actual authentication.

    The proof digest, provider fields, people and cycle metadata are supplied
    claims, *not* verified records. Even passing all checks cannot post money.
    """
    if type(journal) is not JournalCandidate or type(evidence) is not EvidenceDraft:
        raise ValueError("Tipos de registros documentais inválidos")
    if journal.scope not in (PLATFORM_MASTER, TENANT_ADMIN_OWN, TENANT_COLLECTIVE):
        raise ValueError("Escopo financeiro inválido")
    if evidence.event_type not in _DOCUMENT_BY_EVENT or (
        journal.event_type != evidence.event_type or
        journal.scope != evidence.scope or journal.tenant_id != evidence.tenant_id or
        journal.evidence_reference != evidence.evidence_reference or
        journal.fingerprint != evidence.journal_fingerprint
    ):
        raise ValueError("Documento de outro lançamento, evento ou caixa")
    if evidence.document_kind != _DOCUMENT_BY_EVENT[evidence.event_type]:
        raise ValueError("Natureza documental incompatível com evento")
    if not isinstance(evidence.document_digest,str) or (
        _SHA256.fullmatch(evidence.document_digest) is None
    ):
        raise ValueError("Digest documental inválido")
    if type(evidence.preparer_id) is not UUID or (
        type(evidence.proposed_reviewer_id) is not UUID or
        evidence.preparer_id == evidence.proposed_reviewer_id
    ):
        raise ValueError("Revisão independente proposta exige IDs distintos")
    if _strict_cents(evidence.obligation_amount_cents) != sum(
        line.amount_cents for line in journal.lines if line.side == "DR"
    ):
        raise ValueError("Documento e partidas não conferem em centavos")
    if evidence.document_kind == "PROVIDER_SETTLEMENT":
        if not (
            isinstance(evidence.provider_payment_id,str)
            and _PROVIDER_ID.fullmatch(evidence.provider_payment_id)
            and isinstance(evidence.provider_collector_id,str)
            and _PROVIDER_ID.fullmatch(evidence.provider_collector_id)
            and _utc_aware(evidence.provider_observed_at)
        ):
            raise ValueError("Identidade técnica do provedor incompleta")
        if any(x is not None for x in (
            evidence.expense_reference, evidence.cycle_id,
            evidence.policy_id, evidence.net_profit_cents,
            evidence.closing_year,
        )):
            raise ValueError("Documento de pagamento misturado com fechamento/despesa")
    elif evidence.document_kind == "FISCAL_EXPENSE":
        if (not isinstance(evidence.expense_reference,str) or
            _REFERENCE.fullmatch(evidence.expense_reference) is None):
            raise ValueError("Despesa não possui referência documental válida")
        if any(x is not None for x in (
            evidence.provider_payment_id, evidence.provider_collector_id,
            evidence.provider_observed_at, evidence.cycle_id,
            evidence.policy_id, evidence.net_profit_cents,
            evidence.closing_year,
        )):
            raise ValueError("Despesa não pode herdar estado de pagamento/fechamento")
    else:
        # Annual closing is an untrusted *proposal*; neither the policy row nor
        # the profit can be authenticated without a future audited DB workflow.
        if journal.scope != TENANT_ADMIN_OWN:
            raise ValueError("Rateio individual não pertence ao caixa Master/coletivo")
        if (type(evidence.cycle_id) is not UUID or
            type(evidence.policy_id) is not UUID or
            type(evidence.closing_year) is not int or
            not 2000 <= evidence.closing_year <= 2100):
            raise ValueError("Ciclo e política versionada não comprovados")
        net = _strict_cents(evidence.net_profit_cents)
        tentative_admin_share = int((Decimal(net) * Decimal("0.15")).quantize(
            Decimal("1"),rounding=ROUND_HALF_UP))
        if tentative_admin_share != evidence.obligation_amount_cents:
            raise ValueError("Prévia administrativa não corresponde a 15%")
        if any(x is not None for x in (
            evidence.provider_payment_id, evidence.provider_collector_id,
            evidence.provider_observed_at, evidence.expense_reference,
        )):
            raise ValueError("Rateio não é comprovante de pagamento ou despesa")

    # An all-fields-complete draft still does not establish server-verified
    # ownership, reconciled provider receipt, closing signature or bank funds.
    return EvidencePreflight(
        scope=journal.scope,tenant_id=journal.tenant_id,
        journal_fingerprint=journal.fingerprint,
    )
