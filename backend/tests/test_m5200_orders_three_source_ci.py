"""M5200: reject fake settlement, cross-tenant, fee mismatch and stale reads."""
from dataclasses import replace
from datetime import date,datetime,timedelta,timezone
from uuid import UUID
import pytest

from app.pix_automation_contract import (
    PaymentObligation,ObligationKind,build_pix_command,FinancialOperationBlocked,
)
from app.mp_orders_api import OrdersReadReport
from app.mp_orders_settlement import (
    CONTRACT,AuthenticatedSettlementRow,
    correlate_three_source,IndependentOrdersSettlementService,
)

T=UUID("00000000-0000-4000-8000-0000000000a1")
OTHER=UUID("00000000-0000-4000-8000-0000000000b1")
C=UUID("00000000-0000-4000-8000-0000000000a2")
M=UUID("00000000-0000-4000-8000-0000000000a3")
O=UUID("00000000-0000-4000-8000-0000000000a4")
ORD="ORD01HRYFWNYRE1MR1E60MW3X0T2P"
PAY="PAY01HRYFXQ53Q3JPEC48MYWMR0TE"
AT=datetime(2027,1,10,14,30,tzinfo=timezone.utc)


def command():
    return build_pix_command(PaymentObligation(
        tenant_id=T,cycle_id=C,member_id=M,obligation_id=O,
        kind=ObligationKind.CONTRIBUTION,
        expected_cents=15000,already_paid_cents=0,
        due_date=date(2027,1,10),terms_version="policy-2027-01",
        provider_account_id="2002",environment="HOMOLOGACAO",
    ))


def provider_read(**updates):
    args=dict(order_id=ORD,payment_id=PAY,
              status="processed",status_detail="accredited",
              payment_status="processed",payment_detail="accredited",
              provider_response_structure_verified=True,
              ready_for_independent_settlement_lookup=True)
    args.update(updates)
    return OrdersReadReport(**args)


def statement(**updates):
    args=dict(
        tenant_id=T,collector_id="2002",
        order_id=ORD,payment_id=PAY,
        external_reference=command().external_reference,
        statement_reference="SETTLEMENT_BANK_2027_0001",
        statement_source_hash="a"*64,
        currency="BRL",gross_cents=15000,fee_cents=300,net_cents=14700,
        settlement_state="SETTLED",
        settled_at=AT,fetched_at=AT+timedelta(minutes=5),
        authenticated_provider_identity=True,
        authenticated_statement_transport=True,
        independently_settled=True,
    )
    args.update(updates)
    return AuthenticatedSettlementRow(**args)


def test_three_source_is_only_evidence_not_journal_write():
    report=correlate_three_source(
        command=command(),authenticated_order=provider_read(),
        statement=statement())
    assert report.account_id=="2002"
    assert report.order_id==ORD and report.payment_id==PAY
    assert report.amount_cents==15000
    assert report.bank_statement_hash=="a"*64
    assert report.bank_settlement_attested is True
    assert report.independent_statement_source is True
    assert CONTRACT=="AI_STUDIO_M5200_ORDERS_THREE_SOURCE_SETTLEMENT_V1"


@pytest.mark.parametrize("bad",[
    {"tenant_id":OTHER},
    {"collector_id":"3003"},
    {"order_id":"ORD01ANOTHERPAYMENT0000000000"},
    {"payment_id":"PAY01ANOTHERPAYMENT0000000000"},
    {"external_reference":"other-ref"},
    {"statement_reference":"bad"},
    {"statement_source_hash":"0"*63},
    {"currency":"USD"},
    {"gross_cents":14999},
    {"fee_cents":15001},
    {"fee_cents":-1},
    {"net_cents":14999},
    {"settlement_state":"APPROVED"},
    {"settled_at":AT+timedelta(hours=1)},
    {"authenticated_provider_identity":False},
    {"authenticated_statement_transport":False},
    {"independently_settled":False},
    {"source_kind":"USER_PROVIDED_CSV_UNVERIFIED"},
])
def test_foreign_untrusted_or_incorrect_statement_denied(bad):
    with pytest.raises(FinancialOperationBlocked):
        correlate_three_source(command=command(),
            authenticated_order=provider_read(),statement=statement(**bad))


@pytest.mark.parametrize("bad",[
    {"status":"action_required","status_detail":"waiting_transfer",
     "payment_status":"action_required","payment_detail":"waiting_transfer",
     "ready_for_independent_settlement_lookup":False},
    {"payment_status":"action_required"},
    {"provider_response_structure_verified":False},
    {"order_id":"ORD01OTHERORDER00000000000"},
    {"payment_id":"PAY01OTHERPAYMENT0000000000"},
])
def test_wrong_provider_get_blocks_statement(bad):
    with pytest.raises(FinancialOperationBlocked):
        correlate_three_source(command=command(),
            authenticated_order=provider_read(**bad),statement=statement())


@pytest.mark.asyncio
async def test_no_bank_statement_is_not_a_payment():
    class Bank:
        def __init__(self):self.calls=[]
        async def fetch(self,**kwargs):
            self.calls.append(kwargs)
            return None
    b=Bank()
    service=IndependentOrdersSettlementService(b)
    assert await service.verify(
        command=command(),authenticated_order=provider_read()) is None
    assert b.calls[0]["provider_account_id"]=="2002"
    assert b.calls[0]["tenant_id"]==T
    assert b.calls[0]["order_id"]==ORD


@pytest.mark.asyncio
async def test_unprocessed_order_must_not_fetch_statement():
    class Never:
        async def fetch(self,**kwargs):
            raise AssertionError("No authenticated fetch should occur")
    result=await IndependentOrdersSettlementService(Never()).verify(
        command=command(),
        authenticated_order=provider_read(
            ready_for_independent_settlement_lookup=False))
    assert result is None


@pytest.mark.asyncio
async def test_trusted_bank_worker_can_produce_only_structural_evidence():
    class Bank:
        async def fetch(self,**kwargs):
            return statement()
    report=await IndependentOrdersSettlementService(Bank()).verify(
        command=command(),authenticated_order=provider_read())
    assert report.bank_statement_reference=="SETTLEMENT_BANK_2027_0001"
    assert report.bank_settled_at==AT
