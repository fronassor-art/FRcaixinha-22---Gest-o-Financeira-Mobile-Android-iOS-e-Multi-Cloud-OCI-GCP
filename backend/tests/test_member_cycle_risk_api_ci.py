"""M531 — prévia registrada de membro via FastAPI, segurança e sem dinheiro real."""
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

import pytest
from fastapi import HTTPException

from app.dependencies import AuthenticatedSession
from app.routers.member_cycle_previews import (
    get_my_cycle_risk_preview,
    get_admin_member_cycle_risk_preview,
)

T=UUID("00000000-0000-4000-8000-0000000000a1")
X=UUID("00000000-0000-4000-8000-0000000000b1")
U=UUID("00000000-0000-4000-8000-0000000000a2")
M=UUID("00000000-0000-4000-8000-0000000000a3")
C=UUID("00000000-0000-4000-8000-0000000000a4")


def actor(role="TENANT_MEMBER", tenant=T):
    return AuthenticatedSession(str(U),role,str(tenant) if tenant else None,
      "teste@example.invalid","Pessoa Fictícia",role=="MASTER")


def recorded(n,paid=False,partial=False):
    return dict(
        id=UUID(int=100+n), competence=f"2027-{n:02d}",
        due_date=date(2027,n,10),
        amount_due=Decimal("150.00"),
        amount_paid=Decimal("150.00") if paid else (
            Decimal("75.00") if partial else Decimal("0.00")),
        payment_status="QUITADA" if paid else ("PARCIAL" if partial else "PENDENTE"),
        paid_at=datetime(2027,n,10,12,tzinfo=timezone.utc) if paid or partial else None,
    )


class ReadOnlyDB:
    def __init__(self, rows, *, member_exists=True, cycle_exists=True):
        self.rows=rows
        self.calls=[]
        self.member_exists=member_exists
        self.cycle_exists=cycle_exists
    async def fetchrow(self, sql, *params):
        self.calls.append(("fetchrow",sql,params))
        if "FROM public.cycles" in sql:
            return {"id":C,"start_date":date(2027,1,1),
                    "end_date":date(2027,12,31),"is_owner_box":True} if self.cycle_exists else None
        if "FROM public.memberships m" in sql:
            return {"id":M} if self.member_exists else None
        raise AssertionError("Consulta não homologada")
    async def fetch(self,sql,*params):
        self.calls.append(("fetch",sql,params))
        assert "WHERE c.tenant_id=$1 AND c.cycle_id=$2 AND c.membership_id=$3" in sql
        assert params == (T,C,M)
        return self.rows
    async def execute(self,*args):
        raise AssertionError("Consulta de risco nunca pode escrever no PostgreSQL")


@pytest.mark.asyncio
async def test_member_reads_only_own_unverified_cycle_without_closing():
    db=ReadOnlyDB([recorded(1,paid=True),recorded(2,partial=True),
                   recorded(3),recorded(4)])
    out=await get_my_cycle_risk_preview(T,2027,date(2027,5,1),actor(),db)
    assert out.source=="POSTGRESQL_RLS_REGISTERED_NOT_BANK_RECONCILED"
    assert out.membership_id==str(M)
    assert out.scope=="SELF_READ_ONLY"
    assert out.owner_box
    assert out.potential_three_unpaid_trigger_date==date(2027,4,11)
    assert out.registered_contributions_count==4
    assert out.registered_due_cents==60000
    assert out.registered_paid_cents==22500
    assert out.registered_open_cents==37500
    assert out.currently_unpaid_consecutive_months==3
    assert out.longest_registered_overdue_days>0
    assert out.registered_three_competence_review_candidate is True
    assert out.requires_independent_review is True
    assert out.membership_profit_eligible is None
    assert out.reconciled_principal_cents is None
    assert out.capital_days_weight is None
    assert not out.contractual_effect_applied
    assert not out.bank_reconciled
    assert not out.real_financial_operations_enabled
    assert not out.financial_closing_authorized
    assert all("UPDATE" not in c[1] and "INSERT" not in c[1] and
               "DELETE" not in c[1] for c in db.calls)


@pytest.mark.asyncio
async def test_admin_can_view_member_in_own_tenant_but_not_as_member_self():
    db=ReadOnlyDB([recorded(1),recorded(2),recorded(3)])
    admin=actor("TENANT_ADMIN")
    r=await get_admin_member_cycle_risk_preview(
        T,2027,M,date(2027,3,11),admin,db)
    assert r.scope=="TENANT_ADMIN_READ_ONLY"
    assert r.potential_three_unpaid_trigger_date==date(2027,3,11)
    assert r.membership_profit_eligible is None
    assert "AND m.user_id=$3" not in db.calls[1][1]
    with pytest.raises(HTTPException) as err:
        await get_my_cycle_risk_preview(T,2027,date(2027,3,11),admin,ReadOnlyDB([]))
    assert err.value.status_code==403


@pytest.mark.asyncio
async def test_member_cannot_use_admin_member_selector():
    db=ReadOnlyDB([])
    with pytest.raises(HTTPException) as err:
        await get_admin_member_cycle_risk_preview(
            T,2027,M,date(2027,3,11),actor(),db)
    assert err.value.status_code==403
    assert db.calls==[]


@pytest.mark.asyncio
async def test_master_and_cross_tenant_rejected_without_any_sql():
    for session in (
        actor("MASTER",None),
        actor("TENANT_ADMIN",X),
        actor("TENANT_MEMBER",X)
    ):
        db=ReadOnlyDB([])
        with pytest.raises(HTTPException) as err:
            await get_admin_member_cycle_risk_preview(
                T,2027,M,date(2027,3,11),session,db)
        assert err.value.status_code==403
        assert db.calls==[]


@pytest.mark.asyncio
async def test_missing_cycle_or_membership_is_safe_404():
    for key in ("cycle_exists","member_exists"):
        db=ReadOnlyDB([],**{key:False})
        with pytest.raises(HTTPException) as err:
            await get_my_cycle_risk_preview(
                T,2027,date(2027,3,11),actor(),db)
        assert err.value.status_code==404


@pytest.mark.asyncio
async def test_registered_partial_still_not_eligible_profit_or_verified_capital():
    db=ReadOnlyDB([recorded(1,partial=True),recorded(2),recorded(3)])
    r=await get_admin_member_cycle_risk_preview(
        T,2027,M,date(2027,3,11),actor("TENANT_ADMIN"),db)
    assert r.registered_paid_cents==7500
    assert r.potential_three_unpaid_trigger_date==date(2027,3,11)
    assert r.membership_profit_eligible is None


@pytest.mark.asyncio
async def test_unpaid_over_90_days_not_replaced_by_three_month_rule():
    db=ReadOnlyDB([recorded(1)])
    r=await get_admin_member_cycle_risk_preview(
        T,2027,M,date(2027,4,11),actor("TENANT_ADMIN"),db)
    assert r.longest_registered_overdue_days==91
    assert r.potential_three_unpaid_trigger_date is None
    assert r.registered_ninety_day_review_candidate is True
    assert r.registered_three_competence_review_candidate is False
    assert r.requires_independent_review is True


@pytest.mark.asyncio
async def test_invalid_status_or_evidence_fails_closed():
    bad=[
        dict(recorded(1,paid=True),paid_at=None),
        dict(recorded(1),amount_paid=Decimal("150.00")),
        dict(recorded(1),amount_due=Decimal("0.00")),
        dict(recorded(1),amount_paid=Decimal("-1.00")),
        dict(recorded(1),payment_status="DESCONHECIDO"),
        dict(recorded(1),amount_due=Decimal("NaN")),
    ]
    for rows in bad:
        db=ReadOnlyDB([rows])
        with pytest.raises(HTTPException) as err:
            await get_admin_member_cycle_risk_preview(
                T,2027,M,date(2027,4,11),actor("TENANT_ADMIN"),db)
        assert err.value.status_code==503


@pytest.mark.asyncio
async def test_history_limit_and_invalid_year_rejected():
    db=ReadOnlyDB([recorded(1)]*121)
    with pytest.raises(HTTPException) as err:
        await get_admin_member_cycle_risk_preview(
            T,2027,M,date(2027,4,11),actor("TENANT_ADMIN"),db)
    assert err.value.status_code==503
    db2=ReadOnlyDB([])
    with pytest.raises(HTTPException) as err:
        await get_admin_member_cycle_risk_preview(
            T,2101,M,date(2027,4,11),actor("TENANT_ADMIN"),db2)
    assert err.value.status_code==422
    assert db2.calls==[]


def test_routes_are_registered_with_auth_and_no_post_methods():
    from app.main import app
    routes=[(getattr(r,"path",""),getattr(r,"methods",set())) for r in app.routes]
    targets=[(p,m) for p,m in routes if "/member-risk/" in p]
    assert len(targets)==2
    assert all(methods=={"GET"} for _,methods in targets)
    assert any(p.endswith("/me") for p,_ in targets)
    assert any(p.endswith("/members/{member_id}") for p,_ in targets)
