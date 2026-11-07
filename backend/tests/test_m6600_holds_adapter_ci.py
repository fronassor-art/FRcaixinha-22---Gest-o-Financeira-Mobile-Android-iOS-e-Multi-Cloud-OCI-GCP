"""M6600 staging reconciliation holds are scoped, append-only and fail-closed."""
from datetime import date
from uuid import UUID
import pytest

from app.mp_orders_holds import (
    CONTRACT,HoldReason,StagingReconciliationHolds,
)
from app.mp_orders_reservation import StagingOrdersJournal,OrdersStagingBlocked
from app.pix_automation_contract import (
    ObligationKind,PaymentObligation,build_pix_command,
)

T=UUID("00000000-0000-4000-8000-0000000000a1")
OTHER=UUID("00000000-0000-4000-8000-0000000000b1")
C=UUID("00000000-0000-4000-8000-0000000000a2")
M=UUID("00000000-0000-4000-8000-0000000000a3")
O=UUID("00000000-0000-4000-8000-0000000000a4")


def cmd(tenant=T,account="2002"):
    return build_pix_command(PaymentObligation(
        tenant_id=tenant,cycle_id=C,member_id=M,obligation_id=O,
        kind=ObligationKind.CONTRIBUTION,
        expected_cents=15000,already_paid_cents=0,
        due_date=date(2027,1,10),terms_version="policy-2027-1",
        provider_account_id=account,environment="HOMOLOGACAO",
    ))


class Tx:
    async def __aenter__(self):return self
    async def __aexit__(self,*exc):return None


class Db:
    def __init__(self):
        self.calls=[]
        self.readiness=True
        self.fail=False
        self.holds={}
    def transaction(self):return Tx()
    async def fetchval(self,sql,*params):
        self.calls.append((sql,params))
        if "SELECT current_database()" in sql:
            return self.readiness
        assert "SELECT public.mp_orders_staging_record_hold(" in sql
        if self.fail:raise RuntimeError("database unavailable")
        tenant,operation,reason,fingerprint=params
        key=(tenant,operation,reason)
        if key in self.holds:
            if self.holds[key]!=fingerprint:raise ValueError("conflict")
            return "REPLAY"
        self.holds[key]=fingerprint
        return "NEW"


class Pool:
    def __init__(self,db):self.db=db
    def acquire(self):
        class Acq:
            def __init__(self,db):self.db=db
            async def __aenter__(self):return self.db
            async def __aexit__(self,*args):return None
        return Acq(self.db)


def service(db=None):
    db=db or Db()
    journal=StagingOrdersJournal(
        Pool(db),tenant_id=T,provider_account_id="2002")
    return StagingReconciliationHolds(journal),db


@pytest.mark.asyncio
async def test_hold_and_replay_same_operation_has_no_payment_effect():
    holds,db=service()
    a=await holds.hold(command=cmd(),reason=HoldReason.BANK_MISSING,
                       evidence_sha256="a"*64)
    b=await holds.hold(command=cmd(),reason=HoldReason.BANK_MISSING,
                       evidence_sha256="a"*64)
    assert (a,b)==("NEW","REPLAY")
    assert len(db.holds)==1
    args=[p for sql,p in db.calls
          if "SELECT public.mp_orders_staging_record_hold(" in sql]
    assert args[0]==(T,cmd().operation_id,"BANK_MISSING","a"*64)
    assert not hasattr(holds,"mark_paid")
    assert not hasattr(holds,"write_ledger")
    assert CONTRACT=="AI_STUDIO_M6600_DURABLE_ORDERS_RECONCILIATION_HOLDS_V1"


@pytest.mark.asyncio
@pytest.mark.parametrize("bad",[
    {"tenant":OTHER,"account":"2002"},
    {"tenant":T,"account":"3003"},
])
async def test_mismatched_tenant_or_seller_denied_before_database(bad):
    holds,db=service()
    with pytest.raises(OrdersStagingBlocked):
        await holds.hold(command=cmd(**bad),
                         reason=HoldReason.BANK_MISSING,
                         evidence_sha256="a"*64)
    assert not db.calls


@pytest.mark.asyncio
@pytest.mark.parametrize("reason,sha",[
    ("BANK_MISSING","a"*64),
    (HoldReason.BANK_MISSING,"a"*63),
    (HoldReason.BANK_MISSING,"g"*64),
    (HoldReason.BANK_MISSING,"A"*64),
    (HoldReason.BANK_MISSING,""),
])
async def test_invalid_reason_or_hash_is_blocked(reason,sha):
    holds,db=service()
    with pytest.raises(OrdersStagingBlocked):
        await holds.hold(command=cmd(),reason=reason,
                         evidence_sha256=sha)
    assert not db.calls


@pytest.mark.asyncio
async def test_database_unavailable_never_confirms_incident():
    db=Db()
    db.readiness=False
    holds,_=service(db)
    with pytest.raises(OrdersStagingBlocked):
        await holds.hold(command=cmd(),reason=HoldReason.TIMEOUT_UNKNOWN,
                         evidence_sha256="a"*64)
    assert not db.holds


@pytest.mark.asyncio
async def test_database_failure_keeps_financially_blocked():
    db=Db()
    db.fail=True
    holds,_=service(db)
    with pytest.raises(OrdersStagingBlocked):
        await holds.hold(command=cmd(),reason=HoldReason.PROVIDER_MISMATCH,
                         evidence_sha256="a"*64)
    assert not db.holds


@pytest.mark.asyncio
async def test_conflicting_replay_is_never_replaced():
    holds,db=service()
    await holds.hold(command=cmd(),reason=HoldReason.FEE_MISMATCH,
                     evidence_sha256="a"*64)
    with pytest.raises(OrdersStagingBlocked):
        await holds.hold(command=cmd(),reason=HoldReason.FEE_MISMATCH,
                         evidence_sha256="b"*64)
    assert list(db.holds.values())==["a"*64]
