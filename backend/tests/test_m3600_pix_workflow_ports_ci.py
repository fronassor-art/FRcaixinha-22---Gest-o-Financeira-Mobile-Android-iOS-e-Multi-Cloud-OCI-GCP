"""M3600 workflows: only trusted server ports; no local money."""
from dataclasses import dataclass
from datetime import date,datetime,timezone
from uuid import UUID,uuid4
import pytest

from app.pix_automation_contract import (
    ObligationKind, PaymentObligation, ConfirmedCollection,
    PaymentReceipt,RegisteredPixDestination,LoanDisbursement,
    LoanDueComponents,build_pix_command,build_disbursement_order,
    PayoutState,FinancialOperationBlocked,
)
from app.mp_pix_execution import (
    CreatedPix,VerifiedProviderRead,SentPayout,ProviderCredentials,PixRecipient,
)
from app.pix_automation_workflows import (
    CollectionAutomation,PayoutAutomation,ProviderPayoutProof,CONTRACT,
)

T=UUID("00000000-0000-4000-8000-0000000000a1")
C=UUID("00000000-0000-4000-8000-0000000000a2")
M=UUID("00000000-0000-4000-8000-0000000000a3")
O=UUID("00000000-0000-4000-8000-0000000000a4")
L=UUID("00000000-0000-4000-8000-0000000000a5")
D=UUID("00000000-0000-4000-8000-0000000000a6")


def obligation(kind=ObligationKind.CONTRIBUTION):
    return PaymentObligation(
        tenant_id=T,cycle_id=C,member_id=M,obligation_id=O,
        kind=kind,loan_id=L if kind is ObligationKind.LOAN_INSTALLMENT else None,
        expected_cents=20000,already_paid_cents=0,
        due_date=date(2027,1,10),terms_version="2027-accepted-v1",
        provider_account_id="2002",environment="HOMOLOGACAO",
    )


def credentials():
    return ProviderCredentials(
        account_id="2002",access_token="TEST_SANDBOX_TOKEN_123456",
        account_binding_verified=True,capability_in=True,capability_out=True,
        provider_profile_verified=True,
    )


class CollectionDb:
    def __init__(self):
        self.reserve_count=0
        self.records={}
        self.uncertain=set()
        self.posts={}
        self.allocation=None
    async def reserve_collection(self,command):
        key=command.operation_id
        if key in self.records:
            return "EXISTS"
        self.records[key]=None
        self.reserve_count+=1
        return "NEW"
    async def stored_checkout(self,operation_id):
        return self.records[operation_id]
    async def record_checkout(self,command,checkout):
        self.records[command.operation_id]=checkout
    async def mark_collection_uncertain(self,operation_id):
        self.uncertain.add(operation_id)
    async def atomic_post_collection(self,command,evidence,allocation):
        self.allocation=allocation
        if command.operation_id not in self.posts:
            self.posts[command.operation_id]=PaymentReceipt(
                receipt_id=uuid4(),operation_id=command.operation_id,
                payment_id=evidence.provider_payment_id,tenant_id=T,
                obligation_id=O,amount_cents=command.amount_cents,
                paid_at=datetime(2027,1,10,tzinfo=timezone.utc),
                ledger_transaction_id=uuid4(),
                statement_reference=evidence.bank_statement_ref,
            )
        return self.posts[command.operation_id]


class Provider:
    def __init__(self):
        self.calls=0
        self.fail=False
        self.approved=True
    async def create(self,*,command,payer_email,credentials):
        self.calls+=1
        if self.fail:
            raise TimeoutError("test")
        return CreatedPix(command.operation_id,"900001",command.amount_cents,
                          "pending","000201-SANDBOX-NOT-PAYABLE")
    async def read(self,*,operation,payment_id,credentials):
        return VerifiedProviderRead(payment_id,"approved" if self.approved else "pending",
                                    self.approved)


class Bank:
    def __init__(self):
        self.ready=False
    async def verify(self,*,command,provider):
        if not self.ready:
            return None
        return ConfirmedCollection(
            tenant_id=T,operation_id=command.operation_id,
            provider_payment_id=provider.payment_id,
            provider_account_id="2002",
            external_reference=command.external_reference,
            paid_cents=command.amount_cents,
            bank_statement_ref="BANK_PROOF_2027_001",
            provider_get_verified=True,settlement_record_verified=True,
            currency="BRL",live_mode=False,obligation=command.obligation,
        )


@pytest.mark.asyncio
async def test_repeated_pix_click_uses_one_provider_post_and_same_qr():
    db=CollectionDb();provider=Provider()
    work=CollectionAutomation(db,provider,Bank())
    first=await work.start(obligation=obligation(),
         payer_email="ci@example.invalid",credentials=credentials())
    second=await work.start(obligation=obligation(),
         payer_email="ci@example.invalid",credentials=credentials())
    assert first==second
    assert provider.calls==1
    assert db.reserve_count==1
    assert not first.bank_reconciled


@pytest.mark.asyncio
async def test_timeout_leaves_operation_ambiguous_no_second_post():
    db=CollectionDb();provider=Provider();provider.fail=True
    work=CollectionAutomation(db,provider,Bank())
    with pytest.raises(TimeoutError):
        await work.start(obligation=obligation(),
         payer_email="ci@example.invalid",credentials=credentials())
    assert len(db.uncertain)==1
    with pytest.raises(FinancialOperationBlocked):
        await work.start(obligation=obligation(),
         payer_email="ci@example.invalid",credentials=credentials())
    assert provider.calls==1


@pytest.mark.asyncio
async def test_provider_approved_without_bank_proof_never_generates_receipt():
    db=CollectionDb();provider=Provider();bank=Bank()
    work=CollectionAutomation(db,provider,bank)
    b=build_pix_command(obligation())
    r=await work.reconcile(command=b,payment_id="900001",credentials=credentials())
    assert r is None
    assert not db.posts
    bank.ready=True
    provider.approved=False
    r=await work.reconcile(command=b,payment_id="900001",credentials=credentials())
    assert r is None
    assert not db.posts


@pytest.mark.asyncio
async def test_conciliated_loan_200_allocates_40_interest_160_principal_once():
    db=CollectionDb();provider=Provider();bank=Bank();bank.ready=True
    work=CollectionAutomation(db,provider,bank)
    b=build_pix_command(obligation(ObligationKind.LOAN_INSTALLMENT))
    due=LoanDueComponents(O,T,L,4000,0,0,16000)
    r=await work.reconcile(command=b,payment_id="900001",
                           credentials=credentials(),loan_due=due)
    assert r.amount_cents==20000
    assert db.allocation.paid_interest==4000
    assert db.allocation.paid_principal==16000
    second=await work.reconcile(command=b,payment_id="900001",
                           credentials=credentials(),loan_due=due)
    assert second.receipt_id==r.receipt_id
    assert len(db.posts)==1


class PayoutDb:
    def __init__(self):
        self.orders={}
        self.uncertain=set()
        self.posts=[]
    async def reserve_payout(self,order):
        if order.loan_id in self.orders:
            return "EXISTS"
        self.orders[order.loan_id]=None
        return "NEW"
    async def stored_payout(self,loan_id):
        return self.orders[loan_id]
    async def record_sent_payout(self,order,sent):
        self.orders[order.loan_id]=sent
    async def mark_payout_uncertain(self,loan_id):
        self.uncertain.add(loan_id)
    async def post_confirmed_payout(self,order,provider_id,effective_at,
                                    reference,installment_schedule):
        self.posts.append((order,provider_id,effective_at,reference,installment_schedule))


def payout():
    dest=RegisteredPixDestination(
        tenant_id=T,member_id=M,destination_id=D,masked_key="***1234",
        fingerprint="a"*64,verified_owner=True,consent_active=True,
    )
    l=LoanDisbursement(
        tenant_id=T,cycle_id=C,loan_id=L,member_id=M,principal_cents=50000,
        destination=dest,approved=True,reservation_confirmed=True,
        adequate_reconciled_cash=True,consent_valid=True,
        environment="HOMOLOGACAO",financial_role="TENANT_ADMIN",
        provider_out_capability=True,
    )
    r=PixRecipient(
        destination_id=str(D),key_type="PIX_CODE",
        pix_key="123e4567-e89b-12d3-a456-426614174000",
        identification_type="CPF",identification_number="12345678901",
        key_ownership_verified=True,
    )
    return l,r


class PayoutProvider:
    def __init__(self):
        self.calls=0
        self.fail=False
    async def submit(self,*,order,recipient,credentials):
        self.calls+=1
        if self.fail:
            raise TimeoutError("ci")
        return SentPayout(order.business_operation_id,"ABCD","approved")


class Proof:
    def __init__(self):
        self.complete=False
    async def verify_final(self,*,order,sent,credentials):
        return ProviderPayoutProof(
            provider_payout_id=sent.provider_payout_id,
            business_operation_id=order.business_operation_id,
            state="processed" if self.complete else "approved",
            proof_reference="BANK_OUT_PROOF_2027",
            recipient_destination_id=order.destination_id,
            account_id=credentials.account_id,
            amount_cents=order.amount_cents,
            final_settlement_verified=self.complete,
            effective_at=datetime(2027,1,28,tzinfo=timezone.utc) if self.complete else None,
        )


@pytest.mark.asyncio
async def test_admin_one_loan_one_payout_and_no_late_repeat():
    db=PayoutDb();p=PayoutProvider();v=Proof()
    work=PayoutAutomation(db,p,v)
    loan,recipient=payout()
    first=await work.authorize_and_send(loan=loan,recipient=recipient,
                                       credentials=credentials())
    second=await work.authorize_and_send(loan=loan,recipient=recipient,
                                       credentials=credentials())
    assert first==second
    assert p.calls==1
    assert first.financial_state is PayoutState.PENDING_RECONCILIATION
    order=build_disbursement_order(loan)
    pending=await work.reconcile_disbursement(
        order=order,sent=first,credentials=credentials(),
        loan_principal="500.00",rate="0.20",installments=5,
        cycle_start=date(2027,1,1),cycle_end=date(2027,12,31),
        tenant_timezone="America/Belem",
    )
    assert pending is PayoutState.PENDING_RECONCILIATION
    assert not db.posts
    v.complete=True
    confirmed=await work.reconcile_disbursement(
        order=order,sent=first,credentials=credentials(),
        loan_principal="500.00",rate="0.20",installments=5,
        cycle_start=date(2027,1,1),cycle_end=date(2027,12,31),
        tenant_timezone="America/Belem",
    )
    assert confirmed is PayoutState.CONFIRMED
    assert len(db.posts)==1
    schedule=db.posts[0][-1]
    assert schedule[0].due_date=="2027-02-10"
    assert schedule[0].is_cents_adjusted is False
    assert sum(x.amortization_portion for x in schedule)==500


@pytest.mark.asyncio
async def test_outbound_provider_timeout_fails_closed_without_second_order():
    db=PayoutDb();p=PayoutProvider();p.fail=True
    loan,recipient=payout()
    work=PayoutAutomation(db,p,Proof())
    with pytest.raises(TimeoutError):
        await work.authorize_and_send(loan=loan,recipient=recipient,
                                      credentials=credentials())
    assert L in db.uncertain
    with pytest.raises(FinancialOperationBlocked):
        await work.authorize_and_send(loan=loan,recipient=recipient,
                                      credentials=credentials())
    assert p.calls==1
