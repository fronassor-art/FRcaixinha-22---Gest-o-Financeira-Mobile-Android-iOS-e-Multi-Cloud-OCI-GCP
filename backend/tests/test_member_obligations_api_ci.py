"""M1401 — FastAPI de obrigações: RLS, autenticação e consultas sem mutação."""
from datetime import date,datetime,timezone
from decimal import Decimal
from uuid import UUID
import pytest
from fastapi import HTTPException

from app.dependencies import AuthenticatedSession
from app.routers.member_obligations import (
    get_my_member_obligations,get_admin_member_obligations,
    _snapshot, _cents,
)

T=UUID(int=7401)
B=UUID(int=7402)
C=UUID(int=7403)
M=UUID(int=7404)
U=UUID(int=7405)
L=UUID(int=7406)
I=UUID(int=7407)
P=UUID(int=7408)


def session(role="TENANT_MEMBER",tenant=T):
    return AuthenticatedSession(
        str(U),role,str(tenant) if tenant is not None else None,
        "synthetic@example.invalid","CI USER",role=="MASTER",
    )


class ReadOnlyDB:
    def __init__(self,active=False):
        self.calls=[]
        self.active=active
    async def fetchrow(self,sql,*args):
        self.calls.append(("fetchrow",sql,args))
        if "FROM public.cycles" in sql:
            return {"id":C}
        if "FROM public.memberships" in sql:
            return {"id":M}
        raise AssertionError("Unexpected fetchrow: "+sql)
    async def fetch(self,sql,*args):
        self.calls.append(("fetch",sql,args))
        assert args==(T,C,M)
        if "FROM public.contributions" in sql:
            return [dict(id=P,tenant_id=T,cycle_id=C,membership_id=M,
                competence="2027-02",due_date=date(2027,2,10),
                amount_due=Decimal("150.00"),
                amount_paid=Decimal("75.00"),
                payment_status="PARCIAL")]
        if "FROM public.loans" in sql and "JOIN" not in sql:
            return [dict(id=L,tenant_id=T,cycle_id=C,
                borrower_membership_id=M,
                status="DESEMBOLSADO" if self.active else "SOLICITADO",
                disbursed_at=(datetime(2027,1,20,tzinfo=timezone.utc)
                              if self.active else None))]
        if "FROM public.loan_installments" in sql:
            return [dict(
                id=I,tenant_id=T,loan_id=L,installment_number=1,
                due_date=date(2027,2,10),
                principal_due=Decimal("80.00"),
                interest_due=Decimal("20.00"),
                total_due=Decimal("100.00"),
                paid_principal=Decimal("0.00"),
                paid_interest=Decimal("0.00"),
                paid_mora=Decimal("0.00"),paid_fine=Decimal("0.00"),
                status="PENDENTE",
            )]
        raise AssertionError("Unexpected query: "+sql)
    async def execute(self,*_):
        raise AssertionError("Não se permite escrita SQL em prévia")


@pytest.mark.asyncio
async def test_member_only_self_receives_registered_obligations():
    db=ReadOnlyDB()
    result=await get_my_member_obligations(T,2027,date(2027,2,11),session(),db)
    assert result.tenant_id==str(T)
    assert result.membership_id==str(M)
    assert result.scope=="SELF_READ_ONLY"
    assert result.source=="POSTGRESQL_RLS_REGISTERED_NOT_BANK_RECONCILED"
    assert result.contribution_due_cents==15000
    assert result.contribution_paid_recorded_cents==7500
    assert result.contribution_open_cents==7500
    assert result.contribution_now_open_cents==7500
    assert result.contribution_overdue_count==1
    assert result.loan_proposal_count==1
    assert result.loan_now_principal_cents==0
    assert result.registered_now_open_cents==7500
    assert result.net_exit_restitution_cents is None
    assert result.capital_reconciled_cents is None
    assert result.profit_eligible is None
    assert not result.payout_authorized
    assert all(call[0] in ("fetch","fetchrow") for call in db.calls)


@pytest.mark.asyncio
async def test_admin_preview_uses_tenant_and_member_without_master_access():
    db=ReadOnlyDB(active=True)
    result=await get_admin_member_obligations(
        T,2027,M,date(2027,2,11),session("TENANT_ADMIN"),db,
    )
    assert result.scope=="TENANT_ADMIN_READ_ONLY"
    assert result.loan_proposal_count==0
    assert result.loan_active_count==1
    assert result.loan_now_principal_cents==8000
    assert result.loan_now_interest_cents==2000
    assert result.registered_now_open_cents==17500
    assert not result.bank_reconciled
    assert not result.closing_authorized


@pytest.mark.asyncio
async def test_master_and_cross_tenant_forbidden_before_any_db_query():
    for actor in (session("MASTER",None),session("TENANT_MEMBER",B),
                  session("TENANT_ADMIN",B)):
        db=ReadOnlyDB()
        with pytest.raises(HTTPException) as exc:
            await get_admin_member_obligations(
                T,2027,M,date(2027,2,11),actor,db,
            )
        assert exc.value.status_code==403
        assert db.calls==[]


@pytest.mark.asyncio
async def test_member_cannot_choose_admin_requested_membership():
    db=ReadOnlyDB()
    with pytest.raises(HTTPException) as exc:
        await get_admin_member_obligations(
            T,2027,M,date(2027,2,11),session(),db
        )
    assert exc.value.status_code==403
    assert db.calls==[]


@pytest.mark.asyncio
async def test_admin_cannot_use_member_endpoint():
    db=ReadOnlyDB()
    with pytest.raises(HTTPException) as exc:
        await get_my_member_obligations(
            T,2027,date(2027,2,11),session("TENANT_ADMIN"),db)
    assert exc.value.status_code==403
    assert db.calls==[]


@pytest.mark.asyncio
async def test_missing_membership_rejects_instead_of_forging_money():
    class Missing(ReadOnlyDB):
        async def fetchrow(self,sql,*args):
            if "FROM public.memberships" in sql:
                return None
            return await super().fetchrow(sql,*args)
    with pytest.raises(HTTPException) as exc:
        await get_my_member_obligations(
            T,2027,date(2027,2,11),session(),Missing()
        )
    assert exc.value.status_code==404


@pytest.mark.asyncio
async def test_missing_cycle_rejects():
    class Missing(ReadOnlyDB):
        async def fetchrow(self,sql,*args):
            if "FROM public.cycles" in sql:
                return None
            return await super().fetchrow(sql,*args)
    with pytest.raises(HTTPException) as exc:
        await get_my_member_obligations(
            T,2027,date(2027,2,11),session(),Missing()
        )
    assert exc.value.status_code==404


@pytest.mark.asyncio
async def test_invalid_year_and_date_fail_before_read():
    for year,asof in ((2019,date(2027,2,11)),(2101,date(2027,2,11)),
                       (2027,date(2101,1,1))):
        db=ReadOnlyDB()
        with pytest.raises(HTTPException) as exc:
            await get_my_member_obligations(T,year,asof,session(),db)
        assert exc.value.status_code==422
        assert db.calls==[]


@pytest.mark.asyncio
async def test_response_blocks_inaccurate_paid_registration():
    class Overpaid(ReadOnlyDB):
        async def fetch(self,sql,*args):
            rows=await super().fetch(sql,*args)
            if "FROM public.contributions" in sql:
                return [dict(rows[0],amount_paid=Decimal("151.00"))]
            return rows
    with pytest.raises(HTTPException) as exc:
        await get_my_member_obligations(
            T,2027,date(2027,2,11),session(),Overpaid()
        )
    assert exc.value.status_code==503


@pytest.mark.asyncio
async def test_more_than_500_rows_cannot_be_silently_truncated():
    class Many(ReadOnlyDB):
        async def fetch(self,sql,*args):
            if "FROM public.loan_installments" in sql:
                return [dict(id=UUID(int=n+100),
                    tenant_id=T,loan_id=L,installment_number=n+1,
                    due_date=date(2027,2,10),
                    principal_due=Decimal("80"),interest_due=Decimal("20"),
                    total_due=Decimal("100"),paid_principal=Decimal(0),
                    paid_interest=Decimal(0),paid_mora=Decimal(0),paid_fine=Decimal(0),
                    status="PENDENTE") for n in range(501)]
            return await super().fetch(sql,*args)
    with pytest.raises(HTTPException) as exc:
        await get_my_member_obligations(
            T,2027,date(2027,2,11),session(),Many()
        )
    assert exc.value.status_code==503


def test_money_precision_accepts_only_decimal_exact_cents():
    assert _cents(Decimal("150.00"))==15000
    for value in (Decimal("1.001"),Decimal("-1"),Decimal("NaN"),
                  Decimal("Infinity"),1.00,True):
        with pytest.raises(ValueError):
            _cents(value)


def test_route_registration_get_only():
    from app.main import app
    routes=[r for r in app.routes
            if "/member-obligations/" in getattr(r,"path","")]
    assert len(routes)==2
    assert all(r.methods=={"GET"} for r in routes)
    assert {r.name for r in routes}=={
        "get_my_member_obligations","get_admin_member_obligations"
    }
