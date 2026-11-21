"""AI Studio — Pix IN/OUT workflow orchestrator; server-only dependency injection.

The app is the command/control plane. Mercado Pago is payment rail; never
let client confirm payment. The repository holds immutable state and performs
atomic ledger posting; external calls NEVER happen inside a DB transaction.
Runtime connectors are not installed until OCI and PSP authorization.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol
from uuid import UUID

from .mp_pix_execution import (
    ProviderCredentials, PixRecipient, CreatedPix, VerifiedProviderRead,
    SentPayout, ProviderOutcomeUnknown,
)
from .pix_automation_contract import (
    FinancialOperationBlocked, PaymentObligation, PixPaymentCommand,
    ConfirmedCollection, PaymentReceipt, LoanDueComponents, LoanAllocation,
    LoanDisbursement, DisbursementOrder, PayoutState,
    build_pix_command, build_disbursement_order, eligible_for_atomic_posting,
    apply_loan_installment, payout_state_after_provider,
)

CONTRACT = "AI_STUDIO_M3600_PIX_FINANCIAL_WORKFLOW_PORTS_V1"


class CollectionPort(Protocol):
    async def create(self,*,command:PixPaymentCommand,payer_email:str,
                     credentials:ProviderCredentials)->CreatedPix: ...
    async def read(self,*,operation:PixPaymentCommand,payment_id:str,
                   credentials:ProviderCredentials)->VerifiedProviderRead: ...


class DisbursementPort(Protocol):
    async def submit(self,*,order:DisbursementOrder,recipient:PixRecipient,
                     credentials:ProviderCredentials)->SentPayout: ...


class SettlementPort(Protocol):
    async def verify(self,*,command:PixPaymentCommand,
                     provider:VerifiedProviderRead)->ConfirmedCollection | None: ...


class CollectionRepository(Protocol):
    async def reserve_collection(self,command:PixPaymentCommand)->str: ...
    async def stored_checkout(self,operation_id:str)->CreatedPix | None: ...
    async def record_checkout(self,command:PixPaymentCommand,
                              checkout:CreatedPix)->None: ...
    async def mark_collection_uncertain(self,operation_id:str)->None: ...
    async def atomic_post_collection(self,command:PixPaymentCommand,
                                     evidence:ConfirmedCollection,
                                     allocation:LoanAllocation | None)->PaymentReceipt: ...


class DisbursementRepository(Protocol):
    async def reserve_payout(self,order:DisbursementOrder)->str: ...
    async def stored_payout(self,loan_id:UUID)->SentPayout | None: ...
    async def record_sent_payout(self,order:DisbursementOrder,
                                 sent:SentPayout)->None: ...
    async def mark_payout_uncertain(self,loan_id:UUID)->None: ...
    async def post_confirmed_payout(
        self,order:DisbursementOrder,provider_payout_id:str,
        effective_at:datetime,proof_reference:str,
        installment_schedule:tuple,
    )->None: ...


@dataclass(frozen=True)
class ProviderPayoutProof:
    provider_payout_id: str
    business_operation_id: str
    state: str
    proof_reference: str
    recipient_destination_id: UUID
    account_id: str
    amount_cents: int
    final_settlement_verified: bool
    effective_at: datetime | None


class PayoutVerificationPort(Protocol):
    async def verify_final(self,*,order:DisbursementOrder,
                           sent:SentPayout,
                           credentials:ProviderCredentials)->ProviderPayoutProof: ...


class CollectionAutomation:
    def __init__(self,repository:CollectionRepository,
                 provider:CollectionPort,settlement:SettlementPort):
        self.repository=repository
        self.provider=provider
        self.settlement=settlement

    async def start(
        self,*,obligation:PaymentObligation,payer_email:str,
        credentials:ProviderCredentials,amount_cents:int|None=None,
        attempt:int=1,
    )->CreatedPix:
        """One DB reservation per operation before any provider POST.

        Never automatically retry a TIMEOUT. Duplicate calls may only return
        the stored checkout; uncertain status needs provider reconciliation.
        """
        command=build_pix_command(obligation,
            requested_cents=amount_cents,attempt=attempt)
        state=await self.repository.reserve_collection(command)
        if state=="EXISTS":
            known=await self.repository.stored_checkout(command.operation_id)
            if type(known) is CreatedPix:
                return known
            raise FinancialOperationBlocked("Cobrança em confirmação externa")
        if state!="NEW":
            raise FinancialOperationBlocked("Cobrança não pode ser criada")
        try:
            checkout=await self.provider.create(
                command=command,payer_email=payer_email,
                credentials=credentials,
            )
            if (type(checkout) is not CreatedPix
                    or checkout.operation_id!=command.operation_id
                    or checkout.amount_cents!=command.amount_cents
                    or checkout.capital_recognized is not False
                    or checkout.ledger_written is not False):
                raise FinancialOperationBlocked("Retorno de Pix incompatível")
            await self.repository.record_checkout(command,checkout)
            return checkout
        except Exception:
            await self.repository.mark_collection_uncertain(command.operation_id)
            raise

    async def reconcile(
        self,*,command:PixPaymentCommand,payment_id:str,
        credentials:ProviderCredentials,
        loan_due:LoanDueComponents|None=None,
    )->PaymentReceipt | None:
        """From durable trusted worker after signed inbox event or poll.

        The callback/client MUST NOT pass settlement evidence or decide paid.
        """
        verified=await self.provider.read(
            operation=command,payment_id=payment_id,
            credentials=credentials,
        )
        if type(verified) is not VerifiedProviderRead:
            raise FinancialOperationBlocked("Consulta de PSP inválida")
        if not verified.verified_approved:
            return None
        bank_proof=await self.settlement.verify(
            command=command,provider=verified,
        )
        if bank_proof is None:
            return None
        eligible_for_atomic_posting(command,bank_proof)
        allocation=None
        if command.obligation.kind.value=="LOAN_INSTALLMENT":
            if (type(loan_due) is not LoanDueComponents
                    or loan_due.installment_id!=command.obligation.obligation_id
                    or loan_due.tenant_id!=command.obligation.tenant_id
                    or loan_due.loan_id!=command.obligation.loan_id):
                raise FinancialOperationBlocked("Amortização de outro contrato")
            allocation=apply_loan_installment(
                loan_due,confirmed_cents=command.amount_cents,
            )
        # Repo must lock operation and obligation, check bank proof signature
        # from trusted source, post balanced entries ONCE, create receipt.
        receipt=await self.repository.atomic_post_collection(
            command,bank_proof,allocation,
        )
        if (type(receipt) is not PaymentReceipt
                or receipt.operation_id!=command.operation_id
                or receipt.tenant_id!=command.obligation.tenant_id
                or receipt.amount_cents!=command.amount_cents):
            raise FinancialOperationBlocked("Comprovante divergente do ledger")
        return receipt


class PayoutAutomation:
    def __init__(self,repository:DisbursementRepository,
                 provider:DisbursementPort,verification:PayoutVerificationPort):
        self.repository=repository
        self.provider=provider
        self.verification=verification

    async def authorize_and_send(
        self,*,loan:LoanDisbursement,recipient:PixRecipient,
        credentials:ProviderCredentials,
    )->SentPayout:
        """Admin-approved disbursement; one loan one immutable payout order."""
        order=build_disbursement_order(loan)
        if recipient.destination_id!=str(order.destination_id):
            raise FinancialOperationBlocked("Conta de crédito não corresponde ao membro")
        state=await self.repository.reserve_payout(order)
        if state=="EXISTS":
            known=await self.repository.stored_payout(order.loan_id)
            if type(known) is SentPayout:
                return known
            raise FinancialOperationBlocked("Transferência pendente de conciliação")
        if state!="NEW":
            raise FinancialOperationBlocked("Reserva de crédito indisponível")
        try:
            sent=await self.provider.submit(
                order=order,recipient=recipient,credentials=credentials,
            )
            if (type(sent) is not SentPayout
                    or sent.business_operation_id!=order.business_operation_id
                    or sent.money_transferred_confirmed is not False
                    or sent.ledger_written is not False):
                raise FinancialOperationBlocked("Ordem de saque incompatível")
            await self.repository.record_sent_payout(order,sent)
            return sent
        except Exception:
            await self.repository.mark_payout_uncertain(order.loan_id)
            raise

    async def reconcile_disbursement(
        self,*,order:DisbursementOrder,sent:SentPayout,
        credentials:ProviderCredentials,
        loan_principal: str,rate: str,installments: int,
        cycle_start: date,cycle_end: date,
        tenant_timezone: str,
    )->PayoutState:
        """Creates definitive Price schedule ONLY after externally proven Pix.

        Dates are derived from the actual confirmed disbursement date.
        """
        proof=await self.verification.verify_final(
            order=order,sent=sent,credentials=credentials,
        )
        if (type(proof) is not ProviderPayoutProof
                or proof.provider_payout_id!=sent.provider_payout_id
                or proof.business_operation_id!=order.business_operation_id
                or proof.recipient_destination_id!=order.destination_id
                or proof.amount_cents!=order.amount_cents
                or proof.account_id!=credentials.account_id):
            raise FinancialOperationBlocked("Prova de desembolso divergente")
        state=payout_state_after_provider(
            state=sent.financial_state,external_status=proof.state,
            authentic_final_evidence=proof.final_settlement_verified,
        )
        if state is not PayoutState.CONFIRMED:
            return state
        if (type(proof.effective_at) is not datetime
                or proof.effective_at.tzinfo is None
                or type(proof.proof_reference) is not str
                or len(proof.proof_reference)<8):
            raise FinancialOperationBlocked("Desembolso sem data/prova")
        from .loan_payout_price import confirmed_price_schedule
        sched=confirmed_price_schedule(
            principal=loan_principal,monthly_rate=rate,
            installments=installments,
            effective_at=proof.effective_at,
            tenant_timezone=tenant_timezone,
            cycle_start=cycle_start,cycle_end=cycle_end,
            expected_payout_cents=order.amount_cents,
        )
        await self.repository.post_confirmed_payout(
            order,proof.provider_payout_id,proof.effective_at,
            proof.proof_reference,tuple(sched.schedule),
        )
        return state
