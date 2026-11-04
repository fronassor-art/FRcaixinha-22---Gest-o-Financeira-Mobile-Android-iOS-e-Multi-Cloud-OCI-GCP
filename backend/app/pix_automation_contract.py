"""FR Caixinha AI Studio — motor Pix de obrigações e crédito.

Contrato 6.2–6.4, 8.2–8.8, 9.1–9.9, 16.2; sem dinheiro real.
As rotinas NÃO leem a rede nem alteram banco. Precisam de provas
autoritativas e repositório com transação serializável para efeito financeiro.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from hashlib import sha256
import re
from typing import Mapping
from uuid import UUID

CONTRACT = "AI_STUDIO_M3400_PIX_LOAN_AUTOMATION_DOMAIN_V1"
_MAX_CENTS = 999_999_999_999
_REF = re.compile(r"[A-Za-z0-9_-]{8,64}\Z")
_MP = re.compile(r"[0-9]{1,40}\Z")


class FinancialOperationBlocked(ValueError):
    """Never reveal Pix keys, token, account number or private identifiers."""


class ObligationKind(str, Enum):
    CONTRIBUTION = "CONTRIBUTION"
    LOAN_INSTALLMENT = "LOAN_INSTALLMENT"


class PaymentState(str, Enum):
    PENDING = "PENDENTE"
    WAITING_PROVIDER = "AGUARDANDO_PROVEDOR"
    PENDING_RECONCILIATION = "PENDENTE_CONCILIACAO"
    SETTLED = "LIQUIDADO_CONCILIADO"
    REVERSED = "REVERTIDO"
    FAILED = "FALHOU"


class PayoutState(str, Enum):
    REQUESTED = "SOLICITADO"
    RESERVED = "RESERVADO"
    SENT = "ENVIADO"
    PENDING_RECONCILIATION = "PENDENTE_CONCILIACAO"
    CONFIRMED = "CONFIRMADO"
    FAILED = "FALHOU"
    CANCELLED_PROVEN = "CANCELADO_COMPROVADO"


def _cents(n: int, *, zero: bool = False) -> int:
    if type(n) is not int or not (0 if zero else 1) <= n <= _MAX_CENTS:
        raise FinancialOperationBlocked("Valor monetario invalido")
    return n


def decimal_brl(cents: int) -> str:
    """Exactly two decimals; never float in the authoritative backend."""
    return format(Decimal(_cents(cents,zero=True)) / Decimal(100), ".2f")


def amount_cents(amount: str) -> int:
    if type(amount) is not str or not re.fullmatch(r"[0-9]{1,10}\.[0-9]{2}", amount):
        raise FinancialOperationBlocked("Valor BRL requer dois decimais")
    cents=Decimal(amount)*100
    return _cents(int(cents))


@dataclass(frozen=True)
class PaymentObligation:
    tenant_id: UUID
    cycle_id: UUID
    member_id: UUID
    obligation_id: UUID
    kind: ObligationKind
    expected_cents: int
    already_paid_cents: int
    due_date: date
    terms_version: str
    provider_account_id: str
    environment: str
    loan_id: UUID | None = None

    def __post_init__(self):
        if (any(type(x) is not UUID for x in (
                self.tenant_id,self.cycle_id,self.member_id,self.obligation_id))
            or type(self.kind) is not ObligationKind
            or type(self.due_date) is not date
            or type(self.terms_version) is not str
            or not re.fullmatch(r"[A-Za-z0-9._:-]{8,100}",self.terms_version)
            or type(self.provider_account_id) is not str
            or not _MP.fullmatch(self.provider_account_id)
            or self.environment not in ("HOMOLOGACAO","PRODUCAO")
            or (self.kind is ObligationKind.LOAN_INSTALLMENT) != (type(self.loan_id) is UUID)):
            raise FinancialOperationBlocked("Obrigacao sem identidade ou contrato valido")
        _cents(self.expected_cents)
        _cents(self.already_paid_cents,zero=True)
        if self.already_paid_cents > self.expected_cents:
            raise FinancialOperationBlocked("Saldo de obrigacao inconsistente")

    @property
    def open_cents(self) -> int:
        return self.expected_cents-self.already_paid_cents


@dataclass(frozen=True)
class PixPaymentCommand:
    obligation: PaymentObligation
    amount_cents: int
    operation_id: str
    external_reference: str
    idempotency_key: str

    def __post_init__(self):
        _cents(self.amount_cents)
        if self.amount_cents > self.obligation.open_cents:
            raise FinancialOperationBlocked("Pix excede saldo pendente")
        if (not _REF.fullmatch(self.external_reference)
                or not _REF.fullmatch(self.idempotency_key)
                or not _REF.fullmatch(self.operation_id)):
            raise FinancialOperationBlocked("Referencia Pix invalida")


def build_pix_command(
    obligation: PaymentObligation, *, requested_cents: int | None = None,
    attempt: int = 1,
) -> PixPaymentCommand:
    """No PII or changing clock; the same economic attempt retains its key.

    New attempts allowed only after an authoritative failure/cancellation has
    been proven; the repository, not a client, controls the attempt counter.
    """
    if type(obligation) is not PaymentObligation:
        raise FinancialOperationBlocked("Obrigacao inexistente")
    if obligation.open_cents <= 0:
        raise FinancialOperationBlocked("Obrigacao ja quitada")
    if type(attempt) is not int or not 1 <= attempt <= 999:
        raise FinancialOperationBlocked("Tentativa Pix invalida")
    amount=obligation.open_cents if requested_cents is None else requested_cents
    _cents(amount)
    if amount > obligation.open_cents:
        raise FinancialOperationBlocked("Pagamento excede saldo aberto")
    source="|".join((
        "FRC_PIX_V1",str(obligation.tenant_id),
        str(obligation.cycle_id),str(obligation.member_id),
        str(obligation.obligation_id),obligation.kind.value,
        str(amount),obligation.terms_version,str(attempt),
    ))
    fingerprint=sha256(source.encode("ascii")).hexdigest()
    return PixPaymentCommand(
        obligation=obligation,amount_cents=amount,
        operation_id="P_"+fingerprint[:32],
        external_reference="FRC_"+fingerprint[:40],
        idempotency_key="pix_"+fingerprint[:40],
    )


@dataclass(frozen=True)
class LoanDueComponents:
    installment_id: UUID
    tenant_id: UUID
    loan_id: UUID
    interest_cents: int
    mora_cents: int
    fine_cents: int
    principal_cents: int

    def __post_init__(self):
        if any(type(x) is not UUID for x in (
                self.installment_id,self.tenant_id,self.loan_id)):
            raise FinancialOperationBlocked("Parcela sem identificacao")
        for x in (self.interest_cents,self.mora_cents,
                  self.fine_cents,self.principal_cents):
            _cents(x,zero=True)

    @property
    def total(self):
        return sum((self.interest_cents,self.mora_cents,
                    self.fine_cents,self.principal_cents))


@dataclass(frozen=True)
class LoanAllocation:
    paid_interest: int
    paid_mora: int
    paid_fine: int
    paid_principal: int
    remaining_interest: int
    remaining_mora: int
    remaining_fine: int
    remaining_principal: int

    @property
    def revenue_cents(self):
        return self.paid_interest+self.paid_mora+self.paid_fine

    @property
    def applied_cents(self):
        return self.revenue_cents+self.paid_principal

    @property
    def is_fully_paid(self):
        return not any((self.remaining_interest,self.remaining_mora,
                        self.remaining_fine,self.remaining_principal))


def apply_loan_installment(
    due: LoanDueComponents, *, confirmed_cents: int,
) -> LoanAllocation:
    """Clause 8.6: interest -> simple mora -> one-time fine -> principal.

    Caller must select the OLDEST matured installment and calculate legal
    charges from immutable agreed terms before calling. No client amount
    or signed webhook alone is payment confirmation.
    """
    if type(due) is not LoanDueComponents:
        raise FinancialOperationBlocked("Parcela invalida")
    remaining=_cents(confirmed_cents)
    if remaining > due.total:
        raise FinancialOperationBlocked("Pagamento excede componentes devidos")
    paid=[]
    unpaid=[]
    for component in (due.interest_cents,due.mora_cents,
                      due.fine_cents,due.principal_cents):
        allocated=min(remaining,component)
        remaining-=allocated
        paid.append(allocated)
        unpaid.append(component-allocated)
    if remaining:
        raise FinancialOperationBlocked("Imputacao contabil inconsistente")
    result=LoanAllocation(*paid,*unpaid)
    if result.applied_cents != confirmed_cents:
        raise FinancialOperationBlocked("Total de parcela nao preservado")
    return result


@dataclass(frozen=True,repr=False)
class RegisteredPixDestination:
    """Server-side beneficiary record; no plaintext key in repr/logs.

    Key is released by encrypted evidence store only for a verified provider
    API call; frontend receives only masked_key and destination reference.
    """
    tenant_id: UUID
    member_id: UUID
    destination_id: UUID
    masked_key: str
    fingerprint: str
    verified_owner: bool
    consent_active: bool
    revoked: bool = False

    def __repr__(self) -> str:
        return "RegisteredPixDestination(redacted=True)"

    def __post_init__(self):
        if (any(type(x) is not UUID for x in (
                self.tenant_id,self.member_id,self.destination_id))
                or type(self.masked_key) is not str
                or not 3 <= len(self.masked_key) <= 80
                or type(self.fingerprint) is not str
                or not re.fullmatch("[a-f0-9]{64}",self.fingerprint)):
            raise FinancialOperationBlocked("Destino Pix nao verificado")


@dataclass(frozen=True)
class LoanDisbursement:
    tenant_id: UUID
    cycle_id: UUID
    loan_id: UUID
    member_id: UUID
    principal_cents: int
    destination: RegisteredPixDestination
    approved: bool
    reservation_confirmed: bool
    adequate_reconciled_cash: bool
    consent_valid: bool
    environment: str
    financial_role: str
    provider_out_capability: bool

    def __post_init__(self):
        if any(type(x) is not UUID for x in (
                self.tenant_id,self.cycle_id,self.loan_id,self.member_id)):
            raise FinancialOperationBlocked("Credito sem identidade")
        _cents(self.principal_cents)


@dataclass(frozen=True)
class DisbursementOrder:
    tenant_id: UUID
    loan_id: UUID
    member_id: UUID
    destination_id: UUID
    amount_cents: int
    business_operation_id: str
    idempotency_key: str
    status: PayoutState = PayoutState.RESERVED
    money_transferred: bool = False


def build_disbursement_order(loan: LoanDisbursement) -> DisbursementOrder:
    if (type(loan) is not LoanDisbursement
            or loan.financial_role != "TENANT_ADMIN"
            or loan.approved is not True
            or loan.reservation_confirmed is not True
            or loan.adequate_reconciled_cash is not True
            or loan.consent_valid is not True
            or loan.provider_out_capability is not True
            or loan.environment not in ("HOMOLOGACAO","PRODUCAO")
            or loan.destination.tenant_id != loan.tenant_id
            or loan.destination.member_id != loan.member_id
            or loan.destination.verified_owner is not True
            or loan.destination.consent_active is not True
            or loan.destination.revoked is not False):
        raise FinancialOperationBlocked("Desembolso sem aprovacao, saldo ou destino")
    source="|".join(("FRC_LOAN_DISBURSE_V1",str(loan.tenant_id),
                     str(loan.cycle_id),str(loan.loan_id),
                     str(loan.member_id),str(loan.destination.destination_id),
                     str(loan.principal_cents)))
    digest=sha256(source.encode("ascii")).hexdigest()
    return DisbursementOrder(
        tenant_id=loan.tenant_id,loan_id=loan.loan_id,
        member_id=loan.member_id,destination_id=loan.destination.destination_id,
        amount_cents=loan.principal_cents,
        business_operation_id="L_"+digest[:40],
        idempotency_key="payout_"+digest[:40],
    )


def payout_state_after_provider(*, state: PayoutState,
                                external_status: str | None,
                                authentic_final_evidence: bool) -> PayoutState:
    """A payout 'approved' may still be pending processing, never settled."""
    if type(state) is not PayoutState or state not in (
            PayoutState.RESERVED,PayoutState.SENT,
            PayoutState.PENDING_RECONCILIATION):
        raise FinancialOperationBlocked("Estado de transferencia invalido")
    if external_status == "approved" or external_status in (
            None,"pending","in_process"):
        return PayoutState.PENDING_RECONCILIATION
    if external_status == "processed" and authentic_final_evidence is True:
        return PayoutState.CONFIRMED
    if external_status == "failed" and authentic_final_evidence is True:
        return PayoutState.FAILED
    raise FinancialOperationBlocked("Payout nao liquidado comprovadamente")


@dataclass(frozen=True)
class ConfirmedCollection:
    tenant_id: UUID
    operation_id: str
    provider_payment_id: str
    provider_account_id: str
    external_reference: str
    paid_cents: int
    bank_statement_ref: str
    provider_get_verified: bool
    settlement_record_verified: bool
    currency: str
    live_mode: bool
    obligation: PaymentObligation

    def __post_init__(self):
        if not _MP.fullmatch(self.provider_payment_id):
            raise FinancialOperationBlocked("Prova de pagamento invalida")


def eligible_for_atomic_posting(
    command: PixPaymentCommand, evidence: ConfirmedCollection,
) -> bool:
    """True is only a prerequisite, never a database write or bank proof.

    The evidence fields MUST originate from server-side provider and
    independently authenticated settlement adapters, never from client JSON.
    """
    if type(command) is not PixPaymentCommand or type(evidence) is not ConfirmedCollection:
        raise FinancialOperationBlocked("Prova de operacao invalida")
    if (evidence.tenant_id != command.obligation.tenant_id
            or evidence.obligation != command.obligation
            or evidence.operation_id != command.operation_id
            or evidence.external_reference != command.external_reference
            or evidence.paid_cents != command.amount_cents
            or evidence.provider_account_id != command.obligation.provider_account_id
            or evidence.currency != "BRL"
            or evidence.provider_get_verified is not True
            or evidence.settlement_record_verified is not True
            or evidence.live_mode is not (command.obligation.environment=="PRODUCAO")
            or type(evidence.bank_statement_ref) is not str
            or not _REF.fullmatch(evidence.bank_statement_ref)):
        raise FinancialOperationBlocked("Prova externa divergente ou incompleta")
    return True


@dataclass(frozen=True)
class PaymentReceipt:
    receipt_id: UUID
    operation_id: str
    payment_id: str
    tenant_id: UUID
    obligation_id: UUID
    amount_cents: int
    paid_at: datetime
    ledger_transaction_id: UUID
    statement_reference: str
    status: str = "CONFIRMADO_CONCILIADO"


def make_receipt(
    *, command: PixPaymentCommand, evidence: ConfirmedCollection,
    committed_ledger_transaction_id: UUID,
    receipt_id: UUID, committed_at: datetime,
) -> PaymentReceipt:
    eligible_for_atomic_posting(command,evidence)
    if (type(receipt_id) is not UUID
            or type(committed_ledger_transaction_id) is not UUID
            or type(committed_at) is not datetime
            or committed_at.tzinfo is None):
        raise FinancialOperationBlocked("Comprovante exige commit autoritativo")
    return PaymentReceipt(
        receipt_id=receipt_id, operation_id=command.operation_id,
        payment_id=evidence.provider_payment_id,
        tenant_id=command.obligation.tenant_id,
        obligation_id=command.obligation.obligation_id,
        amount_cents=command.amount_cents, paid_at=committed_at,
        ledger_transaction_id=committed_ledger_transaction_id,
        statement_reference=evidence.bank_statement_ref,
    )
