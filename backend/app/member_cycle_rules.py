"""AI Studio / M401+: avaliação PURA de membro, inadimplência e Capital-Dias V2.

Autoridade: Caderno Mestre AI Studio, 6.2-6.6, 8.6 e 10.1-10.6.
A regra especial da caixinha do proprietário depende de validação jurídica.
Nenhum evento aqui grava no DB, cobra multa, confisca principal, aciona Pix,
encerra conta ou substitui os termos aceitos por cada tenant.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from uuid import UUID
from zoneinfo import ZoneInfo

BELEM = ZoneInfo("America/Belem")
FIRST_CYCLE = date(2027, 1, 1)
LAST_CYCLE_EXCLUSIVE = date(2028, 1, 1)


@dataclass(frozen=True)
class MonthlyDueProof:
    tenant_id: UUID
    member_id: UUID
    competence: str  # AAAA-MM
    due_on: date
    amount_due_cents: int
    paid_reconciled_cents: int
    fully_settled_on: date | None  # quitação integral conciliada, não apenas Pix criado
    evidence_id: str

    def __post_init__(self):
        if type(self.tenant_id) is not UUID or type(self.member_id) is not UUID:
            raise ValueError("Identidade inválida")
        if (type(self.competence) is not str or len(self.competence) != 7
            or self.competence[4] != "-" or not self.competence[:4].isdigit()
            or not self.competence[5:].isdigit()):
            raise ValueError("Competência inválida")
        year, month = int(self.competence[:4]), int(self.competence[5:])
        if not 1 <= month <= 12 or year < 2000 or year > 2100:
            raise ValueError("Competência fora do intervalo")
        if type(self.due_on) is not date or (
            self.due_on.year, self.due_on.month, self.due_on.day
        ) != (year, month, 10):
            raise ValueError("Vencimento central dia 10 obrigatório")
        if (type(self.amount_due_cents) is not int or self.amount_due_cents <= 0
            or type(self.paid_reconciled_cents) is not int
            or not 0 <= self.paid_reconciled_cents <= self.amount_due_cents):
            raise ValueError("Centavos inválidos")
        if self.fully_settled_on is not None and type(self.fully_settled_on) is not date:
            raise ValueError("Data da quitação inválida")
        if self.fully_settled_on is not None and self.paid_reconciled_cents != self.amount_due_cents:
            raise ValueError("Quitação sem valor integral conciliado")
        if self.fully_settled_on is None and self.paid_reconciled_cents == self.amount_due_cents:
            raise ValueError("Pagamento integral exige prova da data de conciliação")
        if not isinstance(self.evidence_id, str) or not (1 <= len(self.evidence_id) <= 100):
            raise ValueError("Comprovante obrigatório")


@dataclass(frozen=True)
class CapitalMovement:
    tenant_id: UUID
    member_id: UUID
    effective_at: datetime  # instante comprovado, com fuso
    delta_cents: int  # + aporte confirmado / - restituição ou reversão comprovada
    event_id: UUID

    def __post_init__(self):
        if type(self.tenant_id) is not UUID or type(self.member_id) is not UUID:
            raise ValueError("Identidade inválida")
        if type(self.effective_at) is not datetime or (
            self.effective_at.tzinfo is None or self.effective_at.utcoffset() is None
        ):
            raise ValueError("Movimento exige timestamp com fuso")
        if type(self.delta_cents) is not int or self.delta_cents == 0:
            raise ValueError("Movimento exige centavos inteiros não nulos")
        if not isinstance(self.event_id, UUID):
            raise ValueError("Evento sem ID de auditoria")


@dataclass(frozen=True)
class ExitRequest:
    tenant_id: UUID
    member_id: UUID
    requested_on: date
    request_id: UUID
    accepted_contract_evidence: str | None = None
    authorized_exit_on: date | None = None
    obligations_reviewed: bool = False
    capital_restitution_reconciled: bool = False

    def __post_init__(self):
        if type(self.tenant_id) is not UUID or type(self.member_id) is not UUID:
            raise ValueError("Identidade inválida")
        if type(self.requested_on) is not date or type(self.request_id) is not UUID:
            raise ValueError("Solicitação formal com data e ID obrigatória")
        if type(self.obligations_reviewed) is not bool or type(self.capital_restitution_reconciled) is not bool:
            raise ValueError("Provas explícitas obrigatórias")
        if self.authorized_exit_on is not None and (
            type(self.authorized_exit_on) is not date
            or self.authorized_exit_on < self.requested_on
        ):
            raise ValueError("Encerramento retroativo não permitido")


@dataclass(frozen=True)
class MemberCycleReview:
    tenant_id: UUID
    member_id: UUID
    as_of: date
    longest_overdue_days: int
    current_consecutive_unpaid: int
    historic_three_unpaid_on: date | None
    profit_eligible: bool | None
    status: str
    principal_preserved_cents: int
    capital_days_weight: Decimal
    exit_status: str
    may_close_cycle: bool = False
    may_pay_real_money: bool = False


def _month_index(competence: str) -> int:
    return int(competence[:4]) * 12 + int(competence[5:]) - 1


def _validate_due_history(
    tenant: UUID, member: UUID, dues: tuple[MonthlyDueProof, ...]
) -> tuple[MonthlyDueProof, ...]:
    if type(dues) is not tuple or len(dues) > 120:
        raise ValueError("Histórico de contribuições inválido")
    if any(not isinstance(d, MonthlyDueProof) or d.tenant_id != tenant
           or d.member_id != member for d in dues):
        raise ValueError("Dados de outro tenant/membro")
    ordered = tuple(sorted(dues, key=lambda d: _month_index(d.competence)))
    if len({_month_index(d.competence) for d in dues}) != len(dues):
        raise ValueError("Competência duplicada")
    if len({d.evidence_id for d in dues}) != len(dues):
        raise ValueError("Comprovante duplicado")
    return ordered


def first_three_unpaid_trigger(
    tenant: UUID, member: UUID, dues: tuple[MonthlyDueProof, ...], as_of: date
) -> date | None:
    """Três competências consecutivas ainda NÃO quitadas no vencimento da terceira.

    A posterior quitação não apaga a prova histórica do fato. A saída desta
    função NÃO executa a sanção juridicamente condicionada.
    """
    if type(as_of) is not date:
        raise ValueError("Data de referência inválida")
    seq = _validate_due_history(tenant, member, dues)
    for first, second, third in zip(seq, seq[1:], seq[2:]):
        if (_month_index(second.competence) != _month_index(first.competence) + 1
                or _month_index(third.competence) != _month_index(second.competence) + 1):
            continue
        effective = third.due_on + timedelta(days=1)
        if effective > as_of:
            continue
        if all(q.fully_settled_on is None or q.fully_settled_on > third.due_on
               for q in (first, second, third)):
            return effective
    return None


def capital_days_v2(
    tenant: UUID, member: UUID, movements: tuple[CapitalMovement, ...],
    *, start: date, end_exclusive: date
) -> tuple[int, Decimal]:
    """Soma diária de capital conciliado, no fim do dia em America/Belem.

    Datas [start,end_exclusive); eventos de confirmação, estorno e devolução
    impactam somente o fim do próprio dia e dias futuros.
    """
    if (type(start) is not date or type(end_exclusive) is not date
            or not start < end_exclusive or (end_exclusive - start).days > 367):
        raise ValueError("Ciclo inválido")
    if type(movements) is not tuple or len(movements) > 25000:
        raise ValueError("Movimentos inválidos")
    seen: set[UUID] = set()
    changes: dict[date, int] = {}
    for event in movements:
        if (not isinstance(event, CapitalMovement)
                or event.tenant_id != tenant or event.member_id != member):
            raise ValueError("Evento cruzado")
        if event.event_id in seen:
            raise ValueError("Movimento duplicado")
        seen.add(event.event_id)
        day = event.effective_at.astimezone(BELEM).date()
        if day < start:
            raise ValueError("Saldo anterior deve entrar como movimento de abertura auditado")
        changes[day] = changes.get(day, 0) + event.delta_cents
    position = 0
    total = 0
    day = start
    while day < end_exclusive:
        position += changes.get(day, 0)
        if position < 0:
            raise ValueError("Restituição/reversão acima do capital confirmado")
        total += position
        day += timedelta(days=1)
    return position, Decimal(total) / Decimal(100)


def review_member_cycle(
    tenant: UUID, member: UUID, *,
    as_of: date, dues: tuple[MonthlyDueProof, ...],
    movements: tuple[CapitalMovement, ...],
    cycle_start: date, cycle_end_exclusive: date,
    owner_box: bool, legal_gate_approved: bool,
    history_attested: bool, exit_request: ExitRequest | None = None,
) -> MemberCycleReview:
    if type(tenant) is not UUID or type(member) is not UUID:
        raise ValueError("Contexto inválido")
    if (type(as_of) is not date or type(owner_box) is not bool
            or type(legal_gate_approved) is not bool
            or type(history_attested) is not bool):
        raise ValueError("Pré-condições inválidas")
    if type(cycle_start) is not date or type(cycle_end_exclusive) is not date:
        raise ValueError("Ciclo inválido")
    ordered = _validate_due_history(tenant, member, dues)
    trigger = first_three_unpaid_trigger(tenant, member, dues, as_of)
    active = [d for d in ordered if d.due_on < as_of]
    overdue = [
        (as_of-d.due_on).days for d in active
        if d.fully_settled_on is None or d.fully_settled_on > as_of
    ]
    overdue_days = max(overdue, default=0)
    streak = 0
    previous_idx = None
    for d in reversed(active):
        idx = _month_index(d.competence)
        if previous_idx is not None and idx != previous_idx-1:
            break
        if d.fully_settled_on is not None and d.fully_settled_on <= as_of:
            break
        streak += 1
        previous_idx = idx
    principal, weight = capital_days_v2(
        tenant, member, movements, start=cycle_start, end_exclusive=cycle_end_exclusive
    )
    exit_state = "NO_EXIT_REQUEST"
    if exit_request is not None:
        if not isinstance(exit_request, ExitRequest) or (exit_request.tenant_id,
                exit_request.member_id) != (tenant, member):
            raise ValueError("Saída vinculada a outra identidade")
        if exit_request.authorized_exit_on is None:
            exit_state = "REQUESTED_AWAITING_REVIEW"
        elif (not exit_request.accepted_contract_evidence
                or not exit_request.obligations_reviewed
                or not exit_request.capital_restitution_reconciled):
            exit_state = "APPROVED_BUT_SETTLEMENT_UNVERIFIED"
        else:
            exit_state = "EXIT_DOCUMENTED_RIGHTS_PRESERVED"
    if not history_attested:
        eligible, status = None, "HISTORY_NOT_ATTESTED"
    elif trigger and owner_box:
        if legal_gate_approved:
            eligible, status, weight = False, "OWNER_CYCLE_PROFIT_EXCLUDED", Decimal(0)
        else:
            eligible, status = None, "OWNER_EXCLUSION_WAITING_LEGAL_REVIEW"
    elif trigger and not owner_box:
        eligible, status = None, "TENANT_POLICY_REVIEW_REQUIRED"
    else:
        eligible, status = True, "NO_CONTRACT_TRIGGER_FOUND"
    if exit_state in ("REQUESTED_AWAITING_REVIEW", "APPROVED_BUT_SETTLEMENT_UNVERIFIED"):
        eligible, status = None, "VOLUNTARY_EXIT_UNRESOLVED"
    return MemberCycleReview(
        tenant_id=tenant, member_id=member, as_of=as_of,
        longest_overdue_days=overdue_days, current_consecutive_unpaid=streak,
        historic_three_unpaid_on=trigger, profit_eligible=eligible,
        status=status, principal_preserved_cents=principal,
        capital_days_weight=weight, exit_status=exit_state,
    )
