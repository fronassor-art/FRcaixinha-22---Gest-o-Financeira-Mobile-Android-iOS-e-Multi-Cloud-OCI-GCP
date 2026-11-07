"""FR Caixinha AI Studio M1401: obrigações cadastrais de membro.

Confronta contribuições e cronogramas de empréstimos registrados, com
centavos inteiros e segregação por tenant/ciclo. Não atesta Pix, não calcula
mora ou multa sem prova e NÃO estabelece restituição líquida/pagamento.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID

MAX_ROWS = 500
MAX_CENTS = 999_999_999_999
ACTIVE_LOAN = frozenset({"DESEMBOLSADO", "INADIMPLENTE"})
DRAFT_LOAN = frozenset({"SOLICITADO", "APROVADO", "RESERVADO"})
ALL_LOAN = ACTIVE_LOAN | DRAFT_LOAN | {"QUITADO"}
CONTRIBUTION_STATUS = frozenset({"PENDENTE", "PARCIAL", "QUITADA"})
INSTALLMENT_STATUS = frozenset({"PENDENTE", "PARCIAL", "VENCIDA", "QUITADA"})


def _cents(v: int) -> int:
    if type(v) is not int or not 0 <= v <= MAX_CENTS:
        raise ValueError("Centavos inválidos ou fora do limite")
    return v


def _identity(v: UUID) -> UUID:
    if type(v) is not UUID:
        raise ValueError("Identificador obrigatório")
    return v


@dataclass(frozen=True)
class ContributionRecord:
    id: UUID
    tenant_id: UUID
    cycle_id: UUID
    membership_id: UUID
    competence: str
    due_on: date
    due_cents: int
    paid_cents: int
    status: str

    def __post_init__(self):
        for key in ("id", "tenant_id", "cycle_id", "membership_id"):
            _identity(getattr(self, key))
        if type(self.due_on) is not date:
            raise ValueError("Data de vencimento inválida")
        if (not isinstance(self.competence, str)
            or len(self.competence) != 7 or self.competence[4] != "-"
            or not (self.competence[:4]+self.competence[5:]).isdigit()
            or not 1 <= int(self.competence[5:]) <= 12
            or (self.due_on.year, self.due_on.month) !=
                (int(self.competence[:4]), int(self.competence[5:]))):
            raise ValueError("Competência/vencimento incoerente")
        if _cents(self.due_cents) == 0 or _cents(self.paid_cents) > self.due_cents:
            raise ValueError("Contribuição fora do limite")
        if self.status not in CONTRIBUTION_STATUS:
            raise ValueError("Situação inválida")
        expected = ("QUITADA" if self.paid_cents == self.due_cents
                    else "PENDENTE" if self.paid_cents == 0 else "PARCIAL")
        if self.status != expected:
            raise ValueError("Estado não coincide com os valores cadastrados")


@dataclass(frozen=True)
class LoanRecord:
    id: UUID
    tenant_id: UUID
    cycle_id: UUID
    membership_id: UUID
    status: str
    disbursed_at: datetime | None

    def __post_init__(self):
        for key in ("id", "tenant_id", "cycle_id", "membership_id"):
            _identity(getattr(self, key))
        if self.status not in ALL_LOAN:
            raise ValueError("Empréstimo com estado desconhecido")
        if self.disbursed_at is not None and (
            type(self.disbursed_at) is not datetime
            or self.disbursed_at.utcoffset() is None
        ):
            raise ValueError("Desembolso precisa ter instante com fuso")
        if self.status in ACTIVE_LOAN and self.disbursed_at is None:
            raise ValueError("Empréstimo ativo sem data de desembolso")
        if self.status in DRAFT_LOAN and self.disbursed_at is not None:
            raise ValueError("Proposta de empréstimo com desembolso incompatível")


@dataclass(frozen=True)
class InstallmentRecord:
    id: UUID
    tenant_id: UUID
    loan_id: UUID
    number: int
    due_on: date
    principal_cents: int
    interest_cents: int
    total_cents: int
    paid_principal_cents: int
    paid_interest_cents: int
    paid_mora_cents: int
    paid_fine_cents: int
    status: str

    def __post_init__(self):
        for key in ("id", "tenant_id", "loan_id"):
            _identity(getattr(self, key))
        if type(self.number) is not int or not 1 <= self.number <= 120:
            raise ValueError("Número de parcela inválido")
        if type(self.due_on) is not date:
            raise ValueError("Vencimento da parcela inválido")
        for field in (
            "principal_cents", "interest_cents", "total_cents",
            "paid_principal_cents", "paid_interest_cents",
            "paid_mora_cents", "paid_fine_cents",
        ):
            _cents(getattr(self, field))
        if (self.total_cents <= 0 or
            self.principal_cents + self.interest_cents != self.total_cents or
            self.paid_principal_cents > self.principal_cents or
            self.paid_interest_cents > self.interest_cents or
            self.status not in INSTALLMENT_STATUS):
            raise ValueError("Cronograma ou imputação inconsistente")
        paid = self.paid_principal_cents + self.paid_interest_cents
        remaining = self.total_cents-paid
        if ((self.status == "QUITADA") != (remaining == 0)):
            raise ValueError("Estado da parcela divergente")
        if self.status == "PENDENTE" and paid:
            raise ValueError("Parcela pendente com pagamento imputado")
        if self.status == "PARCIAL" and not paid:
            raise ValueError("Parcela parcial sem amortização identificada")


@dataclass(frozen=True)
class MemberObligationSnapshot:
    tenant_id: UUID
    cycle_id: UUID
    membership_id: UUID
    cycle_year: int
    as_of: date
    contribution_count: int
    contribution_due_cents: int
    contribution_paid_recorded_cents: int
    contribution_open_cents: int
    contribution_now_open_cents: int
    contribution_overdue_count: int
    loan_proposal_count: int
    loan_active_count: int
    loan_closed_count: int
    loan_unscheduled_count: int
    installment_count: int
    loan_now_principal_cents: int
    loan_now_interest_cents: int
    loan_future_principal_cents: int
    loan_future_interest_cents: int
    loan_overdue_installment_count: int
    registered_now_open_cents: int
    status: str
    bank_reconciled: bool = False
    capital_reconciled_cents: None = None
    net_exit_restitution_cents: None = None
    accrued_mora_cents: None = None
    accrued_fine_cents: None = None
    profit_eligible: None = None
    sanction_applied: bool = False
    closing_authorized: bool = False
    payout_authorized: bool = False


def audit_member_obligations(
    tenant_id: UUID, cycle_id: UUID, membership_id: UUID, cycle_year: int,
    as_of: date, contributions: tuple[ContributionRecord, ...],
    loans: tuple[LoanRecord, ...],
    installments: tuple[InstallmentRecord, ...],
) -> MemberObligationSnapshot:
    for value in (tenant_id, cycle_id, membership_id):
        _identity(value)
    if type(cycle_year) is not int or not 2020 <= cycle_year <= 2100:
        raise ValueError("Ano inválido")
    if type(as_of) is not date or not 2020 <= as_of.year <= 2100:
        raise ValueError("Data de análise inválida")
    if any(type(rows) is not tuple or len(rows) > MAX_ROWS
           for rows in (contributions, loans, installments)):
        raise ValueError("Relatório excede limite sem paginação")

    due = paid = open_now = overdue_count = 0
    seen_contrib: set[UUID] = set()
    seen_competence: set[str] = set()
    for c in contributions:
        if (not isinstance(c, ContributionRecord) or
            (c.tenant_id, c.cycle_id, c.membership_id) !=
            (tenant_id, cycle_id, membership_id) or
            c.due_on.year != cycle_year):
            raise ValueError("Contribuição de outra identidade ou exercício")
        if c.id in seen_contrib or c.competence in seen_competence:
            raise ValueError("Contribuição duplicada")
        seen_contrib.add(c.id); seen_competence.add(c.competence)
        due += c.due_cents
        paid += c.paid_cents
        open_cents=c.due_cents-c.paid_cents
        if c.due_on <= as_of:
            open_now += open_cents
        if c.due_on < as_of and open_cents:
            overdue_count += 1

    loan_map: dict[UUID, LoanRecord] = {}
    proposal = active = closed = 0
    for loan in loans:
        if (not isinstance(loan, LoanRecord) or
            (loan.tenant_id, loan.cycle_id, loan.membership_id) !=
            (tenant_id, cycle_id, membership_id) or loan.id in loan_map):
            raise ValueError("Empréstimo duplicado ou de outra identidade")
        loan_map[loan.id] = loan
        if loan.status in DRAFT_LOAN:
            proposal += 1
        elif loan.status in ACTIVE_LOAN:
            active += 1
        else:
            closed += 1

    principal_now = interest_now = principal_future = interest_future = 0
    overdue_installments = 0
    seen_installments: set[UUID] = set()
    seen_numbers: set[tuple[UUID, int]] = set()
    scheduled_loans: set[UUID] = set()
    for item in installments:
        if (not isinstance(item, InstallmentRecord) or
            item.tenant_id != tenant_id or item.loan_id not in loan_map):
            raise ValueError("Parcela sem empréstimo próprio")
        pair = item.loan_id, item.number
        if item.id in seen_installments or pair in seen_numbers:
            raise ValueError("Parcela duplicada")
        seen_installments.add(item.id); seen_numbers.add(pair)
        loan = loan_map[item.loan_id]
        scheduled_loans.add(loan.id)
        remaining_principal = item.principal_cents-item.paid_principal_cents
        remaining_interest = item.interest_cents-item.paid_interest_cents
        if loan.status == "QUITADO" and (remaining_principal or remaining_interest):
            raise ValueError("Empréstimo quitado ainda apresenta parcelas abertas")
        # Propostas não desembolsadas podem ter cronograma hipotético,
        # porém NÃO são dívida exigível nem juros cobrados.
        if loan.status not in ACTIVE_LOAN:
            continue
        if item.due_on <= as_of:
            principal_now += remaining_principal
            interest_now += remaining_interest
        else:
            principal_future += remaining_principal
            interest_future += remaining_interest
        if item.due_on < as_of and (remaining_principal or remaining_interest):
            overdue_installments += 1

    unscheduled = len({loan.id for loan in loans if loan.status in ACTIVE_LOAN}
                      -scheduled_loans)
    if any(n > MAX_CENTS for n in (
        due, paid, due-paid, open_now, principal_now, interest_now,
        principal_future, interest_future,
        open_now+principal_now+interest_now,
    )):
        raise ValueError("Valor agregado excede capacidade representável")
    status=("INCOMPLETE_REGISTERED_LOAN_SCHEDULE" if unscheduled
            else "REGISTERED_ONLY_NOT_RECONCILED")
    return MemberObligationSnapshot(
        tenant_id,cycle_id,membership_id,cycle_year,as_of,
        len(contributions),due,paid,due-paid,open_now,overdue_count,
        proposal,active,closed,unscheduled,len(installments),
        principal_now,interest_now,principal_future,interest_future,
        overdue_installments,open_now+principal_now+interest_now,status,
    )
