"""M5100: per-tenant Orders reservation repository; mock DB, no real cash."""
from datetime import date
from uuid import UUID

import pytest

from app.mp_orders_api import OrdersPixCheckout
from app.mp_orders_reservation import (
    StagingOrdersJournal, OrdersStagingBlocked, CONTRACT,
)
from app.pix_automation_contract import (
    PaymentObligation, ObligationKind, build_pix_command,
)
from app.mp_orders_workflow import OrdersCollectionAutomation

T=UUID("00000000-0000-4000-8000-0000000000a1")
OTHER=UUID("00000000-0000-4000-8000-0000000000b1")
C=UUID("00000000-0000-4000-8000-0000000000a2")
M=UUID("00000000-0000-4000-8000-0000000000a3")
O=UUID("00000000-0000-4000-8000-0000000000a4")
ORD="ORD01HRYFWNYRE1MR1E60MW3X0T2P"
PAY="PAY01HRYFXQ53Q3JPEC48MYWMR0TE"


def command(*,tenant=T,provider="2002",attempt=1):
    return build_pix_command(
        PaymentObligation(
            tenant_id=tenant,cycle_id=C,member_id=M,
            obligation_id=O,kind=ObligationKind.CONTRIBUTION,
            expected_cents=15000,already_paid_cents=0,
            due_date=date(2027,1,10),terms_version="policy_2027_1",
            provider_account_id=provider,environment="HOMOLOGACAO",
        ),attempt=attempt,
    )


def checkout(cmd):
    return OrdersPixCheckout(
        operation_id=cmd.operation_id,order_id=ORD,payment_id=PAY,
        amount_cents=cmd.amount_cents,
        status="action_required",status_detail="waiting_transfer",
        qr_code="00020126SANDBOX",qr_code_base64=None,ticket_url=None,
    )


class TX:
    async def __aenter__(self):return self
    async def __aexit__(self,*args):return None

class DB:
    def __init__(self,ready=True):
        self.ready=ready
        self.calls=[]
        self.operations={}
        self.unknown=set()
    def transaction(self,readonly=False):return TX()
    async def fetchval(self,sql,*params):
        self.calls.append(("fetchval",sql,params))
        if "current_database()" in sql:return self.ready
        if "mp_orders_staging_reserve(" in sql:
            key=params[8]
            if key in self.operations:return "EXISTS"
            self.operations[key]=None
            return "NEW"
        if "mp_orders_staging_save_checkout(" in sql:
            operation=params[1]
            self.operations[operation]={
                "operation_id":operation,"order_id":params[2],
                "payment_id":params[3],"amount_cents":15000,
                "status":"AGUARDANDO_PROVEDOR",
                "qr_code":params[4],"qr_image":params[5],
                "ticket_url":params[6],
            }
            return "INSERTED"
        if "mp_orders_staging_mark_uncertain(" in sql:
            self.unknown.add(params[1])
            return "UNCERTAIN"
        raise AssertionError("Unsupported SQL")
    async def fetchrow(self,sql,*params):
        self.calls.append(("fetchrow",sql,params))
        assert "mp_orders_staging_get_checkout(" in sql
        return self.operations.get(params[1])


class Pool:
    def __init__(self,conn):self.conn=conn
    def acquire(self):
        class A:
            def __init__(self,conn):self.conn=conn
            async def __aenter__(self):return self.conn
            async def __aexit__(self,*args):return None
        return A(self.conn)


@pytest.mark.asyncio
async def test_new_reservation_uses_exact_tenant_and_idempotency_key():
    db=DB()
    journal=StagingOrdersJournal(Pool(db),tenant_id=T,provider_account_id="2002")
    cmd=command(attempt=2)
    assert cmd.attempt==2
    assert await journal.reserve_idempotent(cmd)=="NEW"
    call=next(x for x in db.calls if "mp_orders_staging_reserve(" in x[1])
    assert call[2][0]==T
    assert call[2][6]==cmd.amount_cents
    assert call[2][7]==2
    assert call[2][8]==cmd.operation_id
    assert call[2][10]==cmd.idempotency_key
    assert call[2][11]=="2002"


@pytest.mark.asyncio
async def test_order_checkout_writes_and_reads_by_tenant():
    db=DB()
    journal=StagingOrdersJournal(Pool(db),tenant_id=T,provider_account_id="2002")
    cmd=command()
    assert await journal.reserve_idempotent(cmd)=="NEW"
    await journal.write_checkout(cmd,checkout(cmd))
    assert await journal.reserve_idempotent(cmd)=="EXISTS"
    received=await journal.lookup_checkout(cmd.operation_id)
    assert received.operation_id==cmd.operation_id
    assert received.order_id==ORD
    assert not received.bank_reconciled and not received.ledger_written
    await journal.mark_uncertain(cmd.operation_id)
    assert cmd.operation_id in db.unknown


@pytest.mark.asyncio
@pytest.mark.parametrize("bad",[
    lambda:command(tenant=OTHER),
    lambda:command(provider="9999"),
])
async def test_different_tenant_and_merchant_rejected_before_sql(bad):
    db=DB()
    journal=StagingOrdersJournal(Pool(db),tenant_id=T,provider_account_id="2002")
    with pytest.raises(OrdersStagingBlocked):
        await journal.reserve_idempotent(bad())
    assert not db.calls


@pytest.mark.asyncio
async def test_wrong_database_or_role_blocked():
    db=DB(ready=False)
    journal=StagingOrdersJournal(Pool(db),tenant_id=T,provider_account_id="2002")
    with pytest.raises(OrdersStagingBlocked):
        await journal.reserve_idempotent(command())
    assert not any("mp_orders_staging_reserve(" in x[1] for x in db.calls)


@pytest.mark.asyncio
async def test_bank_posting_intentionally_not_implemented():
    db=DB()
    journal=StagingOrdersJournal(Pool(db),tenant_id=T,provider_account_id="2002")
    with pytest.raises(OrdersStagingBlocked):
        await journal.atomic_post_once(command=command(),bank=None,loan_allocation=None)
    assert db.calls==[]
    assert CONTRACT=="AI_STUDIO_M5100_ORDERS_STAGING_RESERVATION_V1"


class Provider:
    def __init__(self):self.count=0
    async def create(self,*,command,payer_email):
        self.count+=1
        return checkout(command)


@pytest.mark.asyncio
async def test_full_synthetic_create_uses_one_psp_post():
    db=DB()
    provider=Provider()
    journal=StagingOrdersJournal(Pool(db),tenant_id=T,provider_account_id="2002")
    run=OrdersCollectionAutomation(provider=provider,journal=journal,statements=None)
    a=await run.create(command=command(),payer_email="member@example.invalid")
    b=await run.create(command=command(),payer_email="member@example.invalid")
    assert provider.count==1
    assert a==b


@pytest.mark.asyncio
async def test_provider_timeout_marked_uncertain_and_does_not_repost():
    db=DB()
    class ProviderFails:
        def __init__(self):self.count=0
        async def create(self,*,command,payer_email):
            self.count+=1
            raise TimeoutError("Test timeout ambiguous")
    provider=ProviderFails()
    journal=StagingOrdersJournal(Pool(db),tenant_id=T,provider_account_id="2002")
    run=OrdersCollectionAutomation(provider=provider,journal=journal,statements=None)
    with pytest.raises(TimeoutError):
        await run.create(command=command(),payer_email="member@example.invalid")
    assert command().operation_id in db.unknown
    with pytest.raises(Exception):
        await run.create(command=command(),payer_email="member@example.invalid")
    assert provider.count==1
