"""AI Studio: cobrança de parcela de CRÉDITO em atraso — apenas cálculo puro.

Caderno Mestre 8.6: parcela mais antiga; juros remuneratórios vencidos,
mora simples 20%/30 na caixinha do proprietário; multa única R$10 por
obrigação; principal só diminui após imputação; sem juros futuros.
NÃO reutilizar para cobrar multa sobre contribuição de cota sem política
específica, aceita, com prova legal. Sem escrita, Pix, saque ou mutação DB.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID


@dataclass(frozen=True)
class LoanArrearsPolicy:
    monthly_mora: Decimal
    fine_cents: int
    contract_revision: str

    def __post_init__(self):
        if (type(self.monthly_mora) is not Decimal or
            not self.monthly_mora.is_finite() or not Decimal("0") <= self.monthly_mora <= Decimal("1")):
            raise ValueError("Taxa não contratada")
        if type(self.fine_cents) is not int or self.fine_cents < 0:
            raise ValueError("Multa inválida")
        if not isinstance(self.contract_revision,str) or len(self.contract_revision) < 8:
            raise ValueError("Versão aceita exigida")


@dataclass(frozen=True)
class LoanInstallmentState:
    tenant_id: UUID
    installment_id: UUID
    due_on: date
    overdue_principal_cents: int
    overdue_interest_cents: int
    mora_accrued_cents: int
    fine_outstanding_cents: int
    fine_charged_once: bool

    def __post_init__(self):
        if type(self.tenant_id) is not UUID or type(self.installment_id) is not UUID:
            raise ValueError("Identidade inválida")
        if type(self.due_on) is not date:
            raise ValueError("Data inválida")
        if any(type(x) is not int or x < 0 for x in (
            self.overdue_principal_cents,self.overdue_interest_cents,
            self.mora_accrued_cents,self.fine_outstanding_cents)):
            raise ValueError("Centavos inválidos")
        if type(self.fine_charged_once) is not bool:
            raise ValueError("Histórico da multa obrigatório")


@dataclass(frozen=True)
class LoanArrearsQuote:
    installment_id: UUID
    elapsed_days: int
    interest_cents: int
    mora_cents: int
    fine_cents: int
    principal_cents: int
    total_due_cents: int


@dataclass(frozen=True)
class AppliedLoanPayment:
    installment_id: UUID
    paid_interest_cents: int
    paid_mora_cents: int
    paid_fine_cents: int
    paid_principal_cents: int
    remaining_cents: int
    new_overdue_principal_cents: int


def quote_loan_arrears(
    state: LoanInstallmentState, as_of: date,
    policy: LoanArrearsPolicy,
) -> LoanArrearsQuote:
    if type(as_of) is not date or not isinstance(policy, LoanArrearsPolicy):
        raise ValueError("Data ou política inválida")
    days=max(0,(as_of-state.due_on).days)
    fine=state.fine_outstanding_cents
    if days and not state.fine_charged_once and (
        state.overdue_principal_cents or state.overdue_interest_cents
    ):
        fine=policy.fine_cents
    if not days and not state.fine_charged_once and fine:
        raise ValueError("Multa antes do vencimento")
    # A mora preexistente é preservada; esta simulação calcula somente o
    # intervalo incremental sobre o principal vencido atual, sem anatocismo.
    additional=int((Decimal(state.overdue_principal_cents)*
                    policy.monthly_mora*Decimal(days)/Decimal(30)).
                   quantize(Decimal("1"),rounding=ROUND_HALF_UP))
    mora=state.mora_accrued_cents+additional
    total=state.overdue_interest_cents+mora+fine+state.overdue_principal_cents
    return LoanArrearsQuote(state.installment_id,days,
        state.overdue_interest_cents,mora,fine,state.overdue_principal_cents,total)


def apply_partial_loan_payment(
    quote: LoanArrearsQuote, paid_cents: int
) -> AppliedLoanPayment:
    if type(paid_cents) is not int or paid_cents <= 0 or paid_cents > quote.total_due_cents:
        raise ValueError("Pagamento deve ser positivo e não pode exceder dívida exigível")
    remaining=paid_cents
    paid={}
    for part,due in (
        ("interest",quote.interest_cents),
        ("mora",quote.mora_cents),
        ("fine",quote.fine_cents),
        ("principal",quote.principal_cents),
    ):
        amount=min(remaining,due)
        paid[part]=amount
        remaining-=amount
    if remaining or sum(paid.values()) != paid_cents:
        raise AssertionError("Imputação não conserva centavos")
    return AppliedLoanPayment(quote.installment_id,
        paid["interest"],paid["mora"],paid["fine"],paid["principal"],
        quote.total_due_cents-paid_cents,quote.principal_cents-paid["principal"])


def ordered_loan_debt(
    tenant_id: UUID, rows: tuple[LoanInstallmentState,...]
) -> tuple[LoanInstallmentState,...]:
    if type(rows) is not tuple or len(rows)>120:
        raise ValueError("Lista inválida")
    ids=set()
    for row in rows:
        if not isinstance(row,LoanInstallmentState) or row.tenant_id!=tenant_id:
            raise ValueError("Parcela de outro tenant")
        if row.installment_id in ids:
            raise ValueError("Parcela duplicada")
        ids.add(row.installment_id)
    return tuple(sorted(rows,key=lambda row:(row.due_on,str(row.installment_id))))
