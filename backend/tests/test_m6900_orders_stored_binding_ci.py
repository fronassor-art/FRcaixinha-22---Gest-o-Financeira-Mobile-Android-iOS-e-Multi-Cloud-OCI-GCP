"""M6900: Orders GET must match a previously persisted tenant checkout."""
from dataclasses import replace
from datetime import date,datetime,timezone
from uuid import UUID,uuid4
import pytest

from app.mp_orders_api import OrdersPixCheckout,OrdersReadReport
from app.mp_orders_workflow import (
    OrdersCollectionAutomation,OrdersSettlementEvidence,
    OrdersPaymentReceipt,validate_orders_independent_settlement,
)
from app.pix_automation_contract import (
    PaymentObligation,ObligationKind,build_pix_command,
    FinancialOperationBlocked,
)

T=UUID("00000000-0000-4000-8000-0000000000a1")
C=UUID("00000000-0000-4000-8000-0000000000a2")
M=UUID("00000000-0000-4000-8000-0000000000a3")
O=UUID("00000000-0000-4000-8000-0000000000a4")
ORD="ORD01HRYFWNYRE1MR1E60MW3X0T2P"
PAY="PAY01HRYFXQ53Q3JPEC48MYWMR0TE"


def cmd():
    return build_pix_command(PaymentObligation(
        tenant_id=T,cycle_id=C,member_id=M,obligation_id=O,
        kind=ObligationKind.CONTRIBUTION,expected_cents=15000,
        already_paid_cents=0,due_date=date(2027,1,10),
        terms_version="policy-2027-1",
        provider_account_id="2002",environment="HOMOLOGACAO",
    ))


def checkout(command=None,**overrides):
    command=command or cmd()
    val=dict(operation_id=command.operation_id,order_id=ORD,payment_id=PAY,
        amount_cents=command.amount_cents,
        status="action_required",status_detail="waiting_transfer",
        qr_code="00020126SANDBOX",qr_code_base64=None,ticket_url=None)
    val.update(overrides)
    return OrdersPixCheckout(**val)


def report(**overrides):
    d=dict(order_id=ORD,payment_id=PAY,
        status="processed",status_detail="accredited",
        payment_status="processed",payment_detail="accredited",
        provider_response_structure_verified=True,
        ready_for_independent_settlement_lookup=True)
    d.update(overrides)
    return OrdersReadReport(**d)


def bank():
    return OrdersSettlementEvidence(
        tenant_id=T,account_id="2002",
        operation_id=cmd().operation_id,
        external_reference=cmd().external_reference,
        order_id=ORD,payment_id=PAY,amount_cents=15000,
        bank_statement_reference="BANK_SETTLEMENT_TEST_2027",
        bank_statement_hash="a"*64,
        bank_settled_at=datetime(2027,1,10,15,tzinfo=timezone.utc),
        bank_settlement_attested=True,
        account_binding_attested=True,
        independent_statement_source=True)


class Provider:
    def __init__(self,response=None,created=None):
        self.reads=0
        self.posted=0
        self.response=response or report()
        self.created=created
    async def get(self,*,command,order_id):
        self.reads+=1
        return self.response
    async def create(self,*,command,payer_email):
        self.posted+=1
        return self.created or checkout(command)


class Journal:
    def __init__(self,known=None):
        self.known=known
        self.posts=0
        self.reservations=0
    async def lookup_checkout(self,operation):
        return self.known
    async def reserve_idempotent(self,command):
        self.reservations+=1
        return "NEW"
    async def write_checkout(self,command,value):
        self.known=value
    async def mark_uncertain(self,operation):pass
    async def atomic_post_once(self,**kwargs):
        self.posts+=1
        return OrdersPaymentReceipt(
            receipt_id=uuid4(),tenant_id=T,
            order_id=ORD,payment_id=PAY,
            operation_id=cmd().operation_id,obligation_id=O,
            amount_cents=15000,ledger_transaction_id=uuid4(),
            statement_reference="BANK_SETTLEMENT_TEST_2027",
            bank_reconciled=True)


class Settlement:
    def __init__(self):self.calls=0
    async def fetch_and_attest(self,*,command,verified_get):
        self.calls+=1
        return bank()


def run(known=None,provider_response=None):
    j=Journal(known=known)
    p=Provider(response=provider_response)
    s=Settlement()
    return OrdersCollectionAutomation(
        provider=p,journal=j,statements=s),p,j,s


@pytest.mark.asyncio
async def test_no_reservation_blocks_before_provider_or_bank():
    workflow,p,j,s=run()
    with pytest.raises(FinancialOperationBlocked):
        await workflow.reconcile(command=cmd(),order_id=ORD)
    assert p.reads==0 and j.posts==0 and s.calls==0


@pytest.mark.asyncio
@pytest.mark.parametrize("poison",[
    {"operation_id":"P_"+"b"*32},
    {"order_id":"ORD01ANOTHERORDER00000000000"},
    {"amount_cents":10000},
    {"bank_reconciled":True},
    {"ledger_written":True},
])
async def test_poisoned_durable_checkout_blocks_before_get(poison):
    data=checkout(**poison)
    workflow,p,j,s=run(known=data)
    with pytest.raises(FinancialOperationBlocked):
        await workflow.reconcile(command=cmd(),order_id=ORD)
    assert p.reads==0 and j.posts==0 and s.calls==0


@pytest.mark.asyncio
async def test_provider_payment_id_must_match_stored_checkout():
    workflow,p,j,s=run(known=checkout(),
        provider_response=report(payment_id="PAY01WRONGPAYMENT000000000000"))
    with pytest.raises(FinancialOperationBlocked):
        await workflow.reconcile(command=cmd(),order_id=ORD)
    assert p.reads==1 and j.posts==0 and s.calls==0


@pytest.mark.parametrize("poison",[
    {"status":"action_required"},
    {"status_detail":"waiting_transfer"},
    {"payment_status":"action_required"},
    {"payment_detail":"waiting_transfer"},
    {"provider_response_structure_verified":False},
    {"ready_for_independent_settlement_lookup":False},
])
def test_unprocessed_order_cannot_validate_bank_even_with_attested_flags(poison):
    with pytest.raises(FinancialOperationBlocked):
        validate_orders_independent_settlement(cmd(),report(**poison),bank())


@pytest.mark.asyncio
async def test_proven_order_still_reaches_only_mock_journal():
    workflow,p,j,s=run(known=checkout())
    receipt=await workflow.reconcile(command=cmd(),order_id=ORD)
    assert receipt.operation_id==cmd().operation_id
    assert p.reads==1 and j.posts==1 and s.calls==1


@pytest.mark.asyncio
async def test_provider_create_response_claiming_ledger_effect_is_rejected():
    forged=checkout(ledger_written=True)
    j=Journal()
    p=Provider(created=forged)
    workflow=OrdersCollectionAutomation(
        provider=p,journal=j,statements=Settlement())
    with pytest.raises(FinancialOperationBlocked):
        await workflow.create(command=cmd(),payer_email="member@example.invalid")
    assert p.posted==1
    assert j.known is None


@pytest.mark.asyncio
async def test_authoritative_get_cannot_follow_bare_external_order_id():
    workflow,p,j,s=run(known=checkout())
    with pytest.raises(FinancialOperationBlocked):
        await workflow.reconcile(command=cmd(),order_id="ORD01OTHERORDER0000000000")
    assert p.reads==0
