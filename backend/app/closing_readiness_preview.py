"""FRcaixinha AI Studio: pré-condições sintéticas, SEM AUTORIZAR fechamento.

Este módulo não consulta banco, não processa pagamentos, não persiste aceites
e não substitui conciliação bancária ou auditoria independente.
"""
from dataclasses import dataclass

EVIDENCE_FIELDS = (
    "bank_reconciliation_verified",
    "ledger_balanced",
    "contract_version_valid",
    "annual_consent_verified",
    "capital_days_audited",
    "delinquency_classification_audited",
    "backup_restoration_exercised",
    "independent_approval_granted",
)


@dataclass(frozen=True)
class ClosingReadinessPreview:
    state: str
    evidence_marked: tuple[str, ...]
    evidence_pending: tuple[str, ...]
    bank_reconciled: bool
    financial_closing_authorized: bool
    cycle_liquidated: bool


def evaluate_closing_readiness_synthetic(evidence: dict[str, bool]) -> ClosingReadinessPreview:
    """Modela checklist simulado; flags de entrada NÃO provam evidências reais."""
    if type(evidence) is not dict or set(evidence) != set(EVIDENCE_FIELDS):
        raise ValueError("Checklist de fechamento incompleto ou inesperado.")
    if any(type(evidence[k]) is not bool for k in EVIDENCE_FIELDS):
        raise ValueError("Checklist exige indicadores booleanos explícitos.")
    marked = tuple(k for k in EVIDENCE_FIELDS if evidence[k])
    pending = tuple(k for k in EVIDENCE_FIELDS if not evidence[k])
    return ClosingReadinessPreview(
        state="SIMULATION_ONLY_NOT_AUTHORIZED",
        evidence_marked=marked,
        evidence_pending=pending,
        bank_reconciled=False,
        financial_closing_authorized=False,
        cycle_liquidated=False,
    )
