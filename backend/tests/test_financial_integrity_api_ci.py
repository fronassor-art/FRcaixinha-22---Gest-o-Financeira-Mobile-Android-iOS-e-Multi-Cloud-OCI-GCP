"""M601–M760: endpoints reais de auditoria — permissão + SQL somente leitura."""
from datetime import date
from decimal import Decimal
from uuid import UUID
import pytest
from fastapi import HTTPException

from app.dependencies import AuthenticatedSession
from app.routers.financial_integrity_previews import get_tenant_financial_integrity_preview

T=UUID(int=10001)
B=UUID(int=10002)
CID=UUID(int=10003)
ADMIN=UUID(int=10004)
MEM=UUID(int=10005)
PAY=UUID(int=10006)
TX=UUID(int=10007)
POL=UUID(int=10008)


def session(role="TENANT_ADMIN",tenant=T):
    return AuthenticatedSession(str(ADMIN),role,
        str(tenant) if tenant else None,"admin@example.invalid",
        "Fictício",role=="MASTER")


class ReadDB:
    def __init__(self, *, paid=True, missing_cycle=False):
        self.paid=paid
        self.missing_cycle=missing_cycle
        self.calls=[]
    async def fetchrow(self,query,*args):
        self.calls.append(("fetchrow",query,args))
        assert "FROM public.cycles" in query
        assert args==(T,2027)
        if self.missing_cycle:
            return None
        return dict(id=CID,year=2027,status="ABERTO",
                    start_date=date(2027,1,1),end_date=date(2027,12,31))
    async def fetch(self,query,*args):
        self.calls.append(("fetch",query,args))
        assert args[0]==T
        if "FROM public.memberships" in query:
            return [
              dict(id=MEM,tenant_id=T,user_id=ADMIN,role="TENANT_MEMBER",status="ATIVA"),
              dict(id=ADMIN,tenant_id=T,user_id=ADMIN,role="TENANT_ADMIN",status="ATIVA")]
        if "FROM public.contributions" in query:
            return [dict(id=PAY,tenant_id=T,cycle_id=CID,membership_id=MEM,
                competence="2027-01",amount_due=Decimal("150.00"),
                amount_paid=Decimal("150.00") if self.paid else Decimal("0.00"),
                payment_status="QUITADA" if self.paid else "PENDENTE")]
        if "FROM public.policies" in query:
            return [dict(id=POL,tenant_id=T,cycle_id=CID,version=1,
                         admin_pct=Decimal("15.00"),member_pct=Decimal("85.00"),
                         contribution_per_quota=Decimal("150.00"),status="ACTIVE")]
        if "FROM public.ledger_accounts" in query:
            return [dict(account_code=x) for x in
                    ("1.1.1","1.2.1","2.1.1","2.2.1","4.1.1")]
        if "FROM public.ledger_transactions" in query:
            if not self.paid:return []
            return [dict(id=TX,tenant_id=T,reference_id=str(PAY),
                         entries=2,dr_entries=1,cr_entries=1,
                         dr_cents=15000,cr_cents=15000,
                         cash_dr_cents=15000,capital_cr_cents=15000,
                         invalid_entries=0)]
        raise AssertionError("Query não auditada")
    async def execute(self,*_):
        raise AssertionError("Tentativa inesperada de escrita")


@pytest.mark.asyncio
async def test_authenticated_admin_gets_registered_not_bank_reconciled():
    db=ReadDB()
    r=await get_tenant_financial_integrity_preview(T,2027,session(),db)
    assert r.source=="POSTGRESQL_RLS_REGISTERED_NOT_BANK_RECONCILED"
    assert r.scope=="TENANT_ADMIN_READ_ONLY"
    assert r.status=="REGISTERED_INTEGRITY_ONLY"
    assert r.findings==()
    assert r.member_role_links==1 and r.admin_role_links==1
    assert r.members_distinct==1 and r.members_links==2
    assert r.registered_paid_cents==r.linked_payment_cents==15000
    assert r.ledger_dr_cents==r.ledger_cr_cents==15000
    assert r.quota_value_cents==15000
    assert (r.admin_percent,r.member_percent)==("15.00","85.00")
    assert r.no_bank_evidence and not r.bank_reconciled
    assert r.cash_available_cents is None
    assert r.master_saas_revenue_cents is None
    assert not r.transfer_authorized
    assert not r.closing_authorized
    assert len(db.calls)==6
    assert all(k=="fetchrow" or k=="fetch" for k,_,__ in db.calls)


@pytest.mark.asyncio
async def test_empty_ledger_for_zero_payments_is_not_a_failure_but_no_cash_proof():
    db=ReadDB(paid=False)
    r=await get_tenant_financial_integrity_preview(T,2027,session(),db)
    assert r.status=="REGISTERED_INTEGRITY_ONLY"
    assert r.ledger_transactions==0
    assert r.registered_paid_cents==0 and r.registered_open_cents==15000
    assert not r.bank_reconciled


@pytest.mark.asyncio
async def test_master_member_cross_tenant_rejected_without_sql():
    for user in (session("MASTER",None),session("TENANT_MEMBER"),
                 session("TENANT_ADMIN",B)):
        db=ReadDB()
        with pytest.raises(HTTPException) as exc:
            await get_tenant_financial_integrity_preview(T,2027,user,db)
        assert exc.value.status_code==403
        assert db.calls==[]


@pytest.mark.asyncio
async def test_missing_cycle_and_invalid_year_blocked():
    db=ReadDB(missing_cycle=True)
    with pytest.raises(HTTPException) as err:
        await get_tenant_financial_integrity_preview(T,2027,session(),db)
    assert err.value.status_code==404
    db2=ReadDB()
    with pytest.raises(HTTPException) as err:
        await get_tenant_financial_integrity_preview(T,2101,session(),db2)
    assert err.value.status_code==422
    assert db2.calls==[]


@pytest.mark.asyncio
async def test_bound_more_than_500_members_fails_closed():
    class Many(ReadDB):
        async def fetch(self,query,*args):
            if "FROM public.memberships" in query:
                return [dict(id=UUID(int=i+1),tenant_id=T,
                  user_id=UUID(int=i+1),role="TENANT_MEMBER",status="ATIVA")
                  for i in range(501)]
            return await super().fetch(query,*args)
    with pytest.raises(HTTPException) as err:
        await get_tenant_financial_integrity_preview(T,2027,session(),Many())
    assert err.value.status_code==503


@pytest.mark.asyncio
async def test_member_overpayment_fails_closed():
    class Overpay(ReadDB):
        async def fetch(self,query,*args):
            if "FROM public.contributions" in query:
                return [dict(id=PAY,tenant_id=T,cycle_id=CID,membership_id=MEM,
                    competence="2027-01",amount_due=Decimal("150.00"),
                    amount_paid=Decimal("151.00"),payment_status="QUITADA")]
            return await super().fetch(query,*args)
    with pytest.raises(HTTPException) as exc:
        await get_tenant_financial_integrity_preview(
            T,2027,session(),Overpay())
    assert exc.value.status_code==503


def test_route_is_get_only_and_session_protected():
    from app.main import app
    matches=[route for route in app.routes
      if getattr(route,"path","").endswith("/financial-integrity/preview")]
    assert len(matches)==1
    assert matches[0].methods=={"GET"}
