"""M4900: approval is administrative ONLY; installments after actual payout."""
from uuid import UUID
import pytest
from fastapi import HTTPException

from app.dependencies import AuthenticatedSession
from app.routers import loans

TENANT="00000000-0000-4000-8000-0000000000a1"
OTHER="00000000-0000-4000-8000-0000000000b1"
LOAN="00000000-0000-4000-8000-0000000000a2"
ACTOR="00000000-0000-4000-8000-0000000000a3"
MEMBER="00000000-0000-4000-8000-0000000000a4"


def session(role="TENANT_ADMIN",tenant=TENANT):
    return AuthenticatedSession(ACTOR,role,tenant,"admin@example.invalid","Admin",False)


class Conn:
    def __init__(self,*,status="SOLICITADO",is_admin=False,
                 borrower_is_admin=False,installments=0):
        self.status=status
        self.is_admin=is_admin
        self.borrower_is_admin=borrower_is_admin
        self.installments=installments
        self.executed=[]
    async def fetchrow(self,query,*values):
        assert "FOR UPDATE" in query
        assert values==(UUID(LOAN),UUID(TENANT))
        return {
            "id":UUID(LOAN),"tenant_id":UUID(TENANT),
            "status":self.status,"is_admin_loan":self.is_admin,
            "borrower_membership_id":UUID(MEMBER),
        }
    async def fetchval(self,query,*values):
        if "SELECT EXISTS" in query:
            return self.borrower_is_admin
        if "COUNT(*)" in query and "loan_installments" in query:
            return self.installments
        raise AssertionError("Unexpected query")
    async def execute(self,query,*params):
        self.executed.append((query,params))


@pytest.mark.asyncio
async def test_admin_approval_has_no_installments_or_ledger(monkeypatch):
    async def read(tenant,loan,session,conn):
        assert tenant==TENANT
        return {"status":"APROVADO","installments":[]}
    monkeypatch.setattr(loans,"_read_loan_result",read)
    conn=Conn()
    result=await loans.approve_loan(TENANT,LOAN,session(),conn)
    assert result["status"]=="APROVADO"
    assert result["installments"]==[]
    sql="\n".join(x[0] for x in conn.executed)
    assert "UPDATE loans SET status='APROVADO'" in sql
    assert "APROVACAO_CREDITO_SEM_DESEMBOLSO" in sql
    for forbidden in ("INSERT INTO loan_installments",
                      "INSERT INTO ledger_entries",
                      "INSERT INTO ledger_transactions",
                      "disbursed_at", "DESEMBOLSADO",
                      "money_out", "mercadopago"):
        assert forbidden not in sql


@pytest.mark.asyncio
@pytest.mark.parametrize("conn",[
    Conn(status="APROVADO"),Conn(status="DESEMBOLSADO"),
    Conn(is_admin=True),Conn(borrower_is_admin=True),
    Conn(installments=6),
])
async def test_invalid_preconditions_never_write_credit(conn):
    with pytest.raises(HTTPException):
        await loans.approve_loan(TENANT,LOAN,session(),conn)
    assert not conn.executed


@pytest.mark.asyncio
@pytest.mark.parametrize("actor",[
    session("MASTER"),session("TENANT_MEMBER"),session("TENANT_ADMIN",OTHER),
])
async def test_approval_prohibits_master_member_other_tenant(actor):
    conn=Conn()
    with pytest.raises(HTTPException) as exc:
        await loans.approve_loan(TENANT,LOAN,actor,conn)
    assert exc.value.status_code==403
    assert not conn.executed


def test_legacy_loan_money_routes_remain_fail_closed():
    from pathlib import Path
    src=Path(loans.__file__).read_text()
    blocks={
        'async def disburse_loan(':'raise HTTPException(status_code=503',
        'async def repay_loan_installment(':'raise HTTPException(status_code=503',
        'async def settle_loan_early(':'raise HTTPException(status_code=503',
    }
    for anchor,stop in blocks.items():
        assert anchor in src
        assert stop in src.split(anchor,1)[1][:1500]
