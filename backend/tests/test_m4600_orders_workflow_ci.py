"""M4600 server-only Orders workflow mocks, no real bank or money."""
from datetime import date,datetime,timezone
from uuid import UUID,uuid4
import pytest

from app.mp_orders_api import OrdersPixCheckout,OrdersReadReport
from app.mp_orders_workflow import (
    CONTRACT,OrdersSettlementEvidence,OrdersPaymentReceipt,
    OrdersCollectionAutomation,validate_orders_independent_settlement,
)
from app.pix_automation_contract import (
    PaymentObligation,ObligationKind,FinancialOperationBlocked,
    LoanDueComponents,build_pix_command,apply_loan_installment,
)

T=UUID("00000000-0000-4000-8000-0000000000a1")
M=UUID("00000000-0000-4000-8000-0000000000a2")
C=UUID("00000000-0000-4000-8000-0000000000a3")
O=UUID("00000000-0000-4000-8000-0000000000a4")
L=UUID("00000000-0000-4000-8000-0000000000a5")
ORD="ORD01HRYFWNYRE1MR1E60MW3X0T2P"
PAY="PAY01HRYFXQ53Q3JPEC48MYWMR0TE"


def command(kind=ObligationKind.CONTRIBUTION):
    return build_pix_command(PaymentObligation(
        tenant_id=T,member_id=M,cycle_id=C,
        obligation_id=O,kind=kind,expected_cents=15000,
        already_paid_cents=0,due_date=date(2027,1,10),
        terms_version="accepted-terms-2027-1",
        provider_account_id="2002",environment="HOMOLOGACAO",
        loan_id=L if kind is ObligationKind.LOAN_INSTALLMENT else None,
    ))


def result(cmd):
    return OrdersPixCheckout(
        operation_id=cmd.operation_id,order_id=ORD,payment_id=PAY,
        amount_cents=cmd.amount_cents,status="action_required",
        status_detail="waiting_transfer",
        qr_code="00020126SANDBOX-NOT-PAYABLE",
        qr_code_base64="ZmFrZQ==",ticket_url=None,
    )


def read(ready=True):
    return OrdersReadReport(
        order_id=ORD,payment_id=PAY,
        status="processed" if ready else "action_required",
        status_detail="accredited" if ready else "waiting_transfer",
        payment_status="processed" if ready else "action_required",
        payment_detail="accredited" if ready else "waiting_transfer",
        provider_response_structure_verified=True,
        ready_for_independent_settlement_lookup=ready,
    )


def bank(cmd):
    return OrdersSettlementEvidence(
        tenant_id=T,account_id="2002",operation_id=cmd.operation_id,
        external_reference=cmd.external_reference,
        order_id=ORD,payment_id=PAY,amount_cents=cmd.amount_cents,
        bank_statement_reference="BANK_STAGING_TEST_2027",
        bank_statement_hash="a"*64,
        bank_settled_at=datetime(2027,1,10,tzinfo=timezone.utc),
        bank_settlement_attested=True,account_binding_attested=True,
        independent_statement_source=True,
    )


class Provider:
    def __init__(self):
        self.posts=0
        self.timeout=False
        self.ready=True
    async def create(self,*,command,payer_email):
        self.posts+=1
        if self.timeout:raise TimeoutError("CI ambiguous")
        return result(command)
    async def get(self,*,command,order_id):
        assert order_id==ORD
        return read(self.ready)


class Journal:
    def __init__(self):
        self.checkout={}
        self.uncertain=set()
        self.posts={}
        self.allocation=None
    async def reserve_idempotent(self,cmd):
        if cmd.operation_id in self.checkout:return "EXISTS"
        self.checkout[cmd.operation_id]=None
        return "NEW"
    async def lookup_checkout(self,key):return self.checkout[key]
    async def write_checkout(self,cmd,value):self.checkout[cmd.operation_id]=value
    async def mark_uncertain(self,key):self.uncertain.add(key)
    async def atomic_post_once(self,*,command,bank,loan_allocation):
        self.allocation=loan_allocation
        if command.operation_id not in self.posts:
            self.posts[command.operation_id]=OrdersPaymentReceipt(
                receipt_id=uuid4(),tenant_id=T,
                order_id=ORD,payment_id=PAY,
                operation_id=command.operation_id,obligation_id=O,
                amount_cents=command.amount_cents,
                ledger_transaction_id=uuid4(),
                statement_reference=bank.bank_statement_reference,
                bank_reconciled=True,
            )
        return self.posts[command.operation_id]


async def prepare_persisted_checkout(journal,cmd):
    assert await journal.reserve_idempotent(cmd)=="NEW"
    await journal.write_checkout(cmd,result(cmd))


class Statement:
    def __init__(self):self.available=False
    async def fetch_and_attest(self,*,command,verified_get):
        return bank(command) if self.available else None


@pytest.mark.asyncio
async def test_create_by_tenant_is_idempotent_no_double_order():
    provider=Provider();journal=Journal()
    run=OrdersCollectionAutomation(provider=provider,journal=journal,statements=Statement())
    a=await run.create(command=command(),payer_email="ci@example.invalid")
    b=await run.create(command=command(),payer_email="ci@example.invalid")
    assert a==b
    assert provider.posts==1
    assert not a.capital_recognized


@pytest.mark.asyncio
async def test_timeout_ambiguous_never_auto_reposts():
    provider=Provider();provider.timeout=True
    journal=Journal()
    run=OrdersCollectionAutomation(provider=provider,journal=journal,statements=Statement())
    with pytest.raises(TimeoutError):
        await run.create(command=command(),payer_email="ci@example.invalid")
    assert command().operation_id in journal.uncertain
    with pytest.raises(FinancialOperationBlocked):
        await run.create(command=command(),payer_email="ci@example.invalid")
    assert provider.posts==1


@pytest.mark.asyncio
async def test_webhook_or_provider_get_is_not_bank_reconciliation():
    provider=Provider();journal=Journal();statement=Statement()
    run=OrdersCollectionAutomation(provider=provider,journal=journal,statements=statement)
    await prepare_persisted_checkout(journal,command())
    assert await run.reconcile(command=command(),order_id=ORD) is None
    assert not journal.posts
    statement.available=True
    provider.ready=False
    assert await run.reconcile(command=command(),order_id=ORD) is None
    assert not journal.posts


@pytest.mark.asyncio
async def test_synthetic_three_source_commit_contract_idempotent():
    provider=Provider();journal=Journal();statement=Statement()
    statement.available=True
    run=OrdersCollectionAutomation(provider=provider,journal=journal,statements=statement)
    await prepare_persisted_checkout(journal,command())
    receipt=await run.reconcile(command=command(),order_id=ORD)
    assert receipt.bank_reconciled
    assert receipt.order_id==ORD
    assert receipt.payment_id==PAY
    assert receipt.amount_cents==15000
    duplicate=await run.reconcile(command=command(),order_id=ORD)
    assert duplicate.receipt_id==receipt.receipt_id
    assert len(journal.posts)==1


@pytest.mark.asyncio
async def test_loan_payment_requires_interest_principal_allocation():
    provider=Provider();journal=Journal();statement=Statement()
    statement.available=True
    run=OrdersCollectionAutomation(provider=provider,journal=journal,statements=statement)
    loan=command(ObligationKind.LOAN_INSTALLMENT)
    await prepare_persisted_checkout(journal,loan)
    with pytest.raises(FinancialOperationBlocked):
        await run.reconcile(command=loan,order_id=ORD)
    split=apply_loan_installment(
        LoanDueComponents(O,T,L,3000,0,0,12000),
        confirmed_cents=15000)
    await run.reconcile(command=loan,order_id=ORD,loan_allocation=split)
    assert journal.allocation.paid_interest==3000
    assert journal.allocation.paid_principal==12000
    assert journal.allocation.revenue_cents==3000


@pytest.mark.parametrize("mutation",[
    {"account_id":"3003"},{"tenant_id":uuid4()},
    {"amount_cents":14999},{"order_id":"ORD01ANOTHERORDER000000000000"},
    {"payment_id":"PAY01ANOTHERPAY000000000000"},
    {"bank_statement_hash":"bad"},
    {"bank_settlement_attested":False},
    {"independent_statement_source":False},
    {"account_binding_attested":False},
])
def test_no_forged_bank_proof_authorizes_posting(mutation):
    from dataclasses import replace
    cmd=command()
    with pytest.raises(FinancialOperationBlocked):
        validate_orders_independent_settlement(
            cmd,read(),replace(bank(cmd),**mutation),
        )


def test_orders_workflow_documented_contract():
    assert CONTRACT=="AI_STUDIO_M4600_ORDERS_CONCILIATION_WORKFLOW_PORTS_V1"
