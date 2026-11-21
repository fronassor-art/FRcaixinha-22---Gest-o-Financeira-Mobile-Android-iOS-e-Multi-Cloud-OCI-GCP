"""M3800: real scoped user journeys without bank/provider writes."""
from uuid import UUID
from datetime import date
from decimal import Decimal
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from app.main import app
from app.dependencies import AuthenticatedSession,get_current_session
from app.routers.pix_automation import contribution_quote,installment_quote,payout_preview

T="00000000-0000-4000-8000-0000000000a1"
U="00000000-0000-4000-8000-0000000000a3"
X="00000000-0000-4000-8000-0000000000b1"
O="00000000-0000-4000-8000-0000000000a4"
L="00000000-0000-4000-8000-0000000000a5"


def session(role="TENANT_MEMBER",user_id=U):
    return AuthenticatedSession(user_id,role,T if role!="MASTER" else None,
            "ci@example.invalid","CI",role=="MASTER")


class DB:
    def __init__(self,row):
        self.row=row
        self.calls=0
    async def fetchrow(self,query,*args):
        self.calls+=1
        return self.row


def test_capabilities_and_money_post_gate():
    app.dependency_overrides[get_current_session]=lambda:session()
    try:
        with TestClient(app) as c:
            prefix=f"/api/v1/tenants/{T}/financial-automation"
            cap=c.get(prefix+"/capabilities")
            assert cap.status_code==200
            assert cap.json()["pix_collection_enabled"] is False
            assert cap.json()["pix_payout_enabled"] is False
            assert c.post(prefix+f"/contributions/{O}/pix").status_code==503
            assert c.post(prefix+f"/loans/{L}/installments/{O}/pix").status_code==503
            assert c.post(prefix+f"/loans/{L}/payout").status_code==403
    finally:
        app.dependency_overrides.clear()


def test_master_has_no_access_to_member_finance():
    app.dependency_overrides[get_current_session]=lambda:session("MASTER")
    try:
        with TestClient(app) as c:
            assert c.get(f"/api/v1/tenants/{T}/financial-automation/capabilities").status_code==403
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_january_150_member_quote_is_authoritative_read_only():
    row=dict(id=UUID(O),cycle_id=UUID(O),competence="2027-01",
             due_date=date(2027,1,10),amount_due=Decimal("150.00"),
             amount_paid=Decimal("0.00"),payment_status="PENDENTE",
             user_id=UUID(U))
    db=DB(row)
    r=await contribution_quote(T,O,session(),db)
    assert (r["open_cents"],r["paid_cents"])==(15000,0)
    assert not r["pix_payable"]
    with pytest.raises(HTTPException):
        await contribution_quote(T,O,session(user_id=X),db)


@pytest.mark.asyncio
async def test_200_installment_read_preserves_separate_interest_and_principal():
    row=dict(id=UUID(O),installment_number=1,due_date=date(2027,1,10),
             status="PENDENTE",interest_due=Decimal("40.00"),
             principal_due=Decimal("160.00"),
             paid_interest=Decimal("0.00"),paid_principal=Decimal("0.00"),
             user_id=UUID(U))
    r=await installment_quote(T,L,O,session(),DB(row))
    assert r["base_open_cents"]==20000
    assert r["interest_open_cents"]==4000
    assert r["principal_open_cents"]==16000
    assert not r["pix_payable"]


@pytest.mark.asyncio
async def test_approved_loan_is_not_an_executed_payout():
    row=dict(id=UUID(L),principal=Decimal("500.00"),status="APROVADO",
             user_id=UUID(U))
    r=await payout_preview(T,L,session("TENANT_ADMIN"),DB(row))
    assert r["principal_cents"]==50000
    assert r["destination_registered"] is False
    assert r["external_transfer_confirmed"] is False


def test_staging_diagnostics_never_claim_real_money():
    with TestClient(app) as c:
        a=c.get("/api/health/features/m3700")
        b=c.get("/api/health/features/m3800")
    assert a.status_code==b.status_code==200
    assert a.json()["staging_migration_applied"] is False
    assert b.json()["member_pix_workflow_code_present"] is True
    assert b.json()["real_payments_enabled"] is False
