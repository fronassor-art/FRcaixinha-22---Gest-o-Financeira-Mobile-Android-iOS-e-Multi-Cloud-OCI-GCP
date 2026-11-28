"""FR Finance M39900 — pure three-cashbox provenance fence, no IO.

The platform Master owns only platform SaaS proceeds/expenses. Each tenant's
collective funds and its administrator's own remuneration are separate.
This classifier cannot approve closing, recognize revenue, post journal lines,
create expenses, reconcile provider receipts or authorize payment/withdrawal.
"""
from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

PLATFORM_MASTER = "PLATFORM_MASTER"
TENANT_ADMIN_OWN = "TENANT_ADMIN_OWN"
TENANT_COLLECTIVE = "TENANT_COLLECTIVE"

EVENT_SCOPE = {
    "SAAS_SETTLEMENT": PLATFORM_MASTER,
    "PLATFORM_OPERATING_EXPENSE": PLATFORM_MASTER,
    "ADMIN_CLOSING_REMUNERATION": TENANT_ADMIN_OWN,
    "ADMIN_OWN_EXPENSE": TENANT_ADMIN_OWN,
    "MEMBER_CONTRIBUTION": TENANT_COLLECTIVE,
    "TENANT_LOAN_REPAYMENT": TENANT_COLLECTIVE,
    "TENANT_OPERATING_EXPENSE": TENANT_COLLECTIVE,
}


@dataclass(frozen=True)
class CashboxSourceReview:
    scope: str
    event_type: str
    tenant_id: UUID | None
    evidence_state: str = "SOURCE_CLASSIFIED_ONLY"
    posting_authorized: bool = False
    withdrawal_authorized: bool = False
    reconciled_balance_cents: None = None


def classify_cashbox_source(
    event_type: str, scope: str, tenant_id: UUID | None,
) -> CashboxSourceReview:
    """Classify an intended event without validating a financial transaction.

    Only explicit event families are accepted. A platform event cannot acquire a
    tenant, and a tenant event must belong to one UUID. Authorization, member
    eligibility, tenant ownership, accounting proof and reconciled amounts
    MUST be independently verified before a future posting API is considered.
    """
    if not isinstance(event_type, str) or event_type not in EVENT_SCOPE:
        raise ValueError("Tipo de evento financeiro não autorizado")
    if not isinstance(scope, str) or scope != EVENT_SCOPE[event_type]:
        raise ValueError("Transferência ou mistura entre caixas proibida")
    if scope == PLATFORM_MASTER:
        if tenant_id is not None:
            raise ValueError("Receita/despesa SaaS não usa tenant")
    elif type(tenant_id) is not UUID:
        raise ValueError("Caixa da caixinha exige tenant UUID explícito")
    return CashboxSourceReview(
        scope=scope, event_type=event_type, tenant_id=tenant_id,
    )
