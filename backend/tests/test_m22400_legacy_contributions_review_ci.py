"""M22400: historical R$100 review without SQL mutations or unverified credit."""
import pytest
from uuid import UUID
from decimal import Decimal
from fastapi import HTTPException

from app.dependencies import AuthenticatedSession
from app.routers.cycle_contribution_price import legacy_contributions_review

T=UUID("00000000-0000-4000-8000-0000000000a1")
C=UUID("00000000-0000-4000-8000-0000000000b1")
U=UUID("00000000-0000-4000-8000-0000000000c1")


class Fake:
    def __init__(self,rows):
        self.rows=rows
        self.queries=[]
    async def fetchrow(self,sql,*values):
        self.queries.append(sql)
        assert values==(C,T)
        return {"id":C,"year":2027}
    async def fetch(self,sql,*values):
        self.queries.append(sql)
        assert values==(T,C)
        return self.rows

def user(role="TENANT_ADMIN",tenant=str(T)):
    return AuthenticatedSession(str(U),role,tenant,
                                "synthetic@example.invalid","Synthetic",False)

def rec(due="100.00",paid="0.00",status="PENDENTE",n=12):
    return {"amount_due":Decimal(due),"amount_paid":Decimal(paid),
            "payment_status":status,"registered_count":n}

@pytest.mark.asyncio
async def test_legacy_12_months_100_brl_preserved():
    db=Fake([rec()])
    report=await legacy_contributions_review(T,C,user(),db)
    assert report["legacy_registered_contributions"]==12
    assert report["legacy_due_cents"]==120000
    assert report["legacy_open_recorded_cents"]==120000
    assert report["minimum_new_quota_cents"]==15000
    assert report["requires_administrator_review"] is True
    assert report["price_adjustment_authorized"] is False
    assert report["historical_obligations_changed"] is False
    assert report["bank_reconciled"] is False
    assert all(sql.startswith("SELECT ") for sql in db.queries)

@pytest.mark.asyncio
async def test_empty_legacy_history_reports_no_auto_adjustment():
    report=await legacy_contributions_review(T,C,user(),Fake([]))
    assert report["requires_administrator_review"] is False
    assert report["legacy_due_cents"]==0

@pytest.mark.asyncio
@pytest.mark.parametrize("role,tenant",[
    ("TENANT_MEMBER",str(T)),("MASTER",None),
    ("TENANT_ADMIN",str(UUID("00000000-0000-4000-8000-0000000000a2"))),
])
async def test_foreign_roles_cannot_review(role,tenant):
    with pytest.raises(HTTPException) as caught:
        await legacy_contributions_review(T,C,user(role,tenant),Fake([rec()]))
    assert caught.value.status_code==403

@pytest.mark.asyncio
@pytest.mark.parametrize("row",[
    rec("149.999"),rec("0.00"),rec("150.00"),
    rec("100.00","101.00"),rec("100.00","0.00","DESCONHECIDA"),
    rec(n=0),rec(n=True),rec(n=1000001),
])
async def test_inconsistent_legacy_is_blocked(row):
    with pytest.raises(HTTPException) as caught:
        await legacy_contributions_review(T,C,user(),Fake([row]))
    assert caught.value.status_code==503

@pytest.mark.asyncio
async def test_more_than_200_groups_requires_pagination():
    with pytest.raises(HTTPException) as caught:
        await legacy_contributions_review(T,C,user(),Fake([rec()]*201))
    assert caught.value.status_code==503
