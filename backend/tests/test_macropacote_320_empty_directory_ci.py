"""M320: diretório contábil sem saldos, autorizado e com dados sintéticos."""
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException

from app.dependencies import AuthenticatedSession
from app.routers.ledger import (
    _validate_directory_accounts, list_ledger_account_directory,
)

TENANT=str(uuid4())
OTHER=str(uuid4())
USER=str(uuid4())


def session(role="TENANT_ADMIN", tenant=TENANT):
    return AuthenticatedSession(USER,role,tenant,"ci@example.invalid","CI",role=="MASTER")


def account(**changed):
    row={
        "id":uuid4(), "tenant_id":UUID(TENANT),
        "account_code":"1.1.1", "account_name":"Caixa contábil sintético",
        "account_type":"ASSET",
    }
    return {**row,**changed}


class ReadOnly:
    def __init__(self, rows):
        self.rows=rows
        self.calls=[]

    async def fetch(self, sql, *args):
        assert sql.lstrip().startswith("SELECT")
        self.calls.append((sql,args))
        return self.rows

    async def execute(self, *_):
        raise AssertionError("Nunca gravar em banco")


@pytest.mark.asyncio
async def test_directory_with_zero_transactions_and_one_account():
    db=ReadOnly([account()])
    result=await list_ledger_account_directory(TENANT,session(),db)
    assert result.source=="POSTGRESQL_RLS"
    assert result.scope=="TENANT_ADMIN_READ_ONLY"
    assert result.tenant_id==TENANT
    assert result.accounts[0].account_code=="1.1.1"
    assert result.balance_values_hidden is True
    assert result.complete_ledger_verified is False
    assert result.bank_reconciled is False
    assert result.financial_closing_authorized is False
    assert result.accounts[0].model_dump()=={
        "id":str(db.rows[0]["id"]),
        "account_code":"1.1.1",
        "account_name":"Caixa contábil sintético",
        "account_type":"ASSET",
    }
    assert "balance" not in str(result.model_dump()["accounts"]).lower()
    assert len(db.calls)==1
    sql,args=db.calls[0]
    assert "SELECT id, tenant_id, account_code, account_name, account_type" in sql
    assert "balance_cents" not in sql
    assert "FROM public.ledger_accounts" in sql
    assert "WHERE tenant_id=$1" in sql
    assert "ORDER BY account_code ASC, id ASC" in sql
    assert "LIMIT 501" in sql
    assert args==(UUID(TENANT),)


@pytest.mark.asyncio
async def test_empty_directory_never_invents_accounts():
    result=await list_ledger_account_directory(TENANT,session(),ReadOnly([]))
    assert result.accounts==[]


@pytest.mark.asyncio
async def test_master_member_cross_tenant_rejected_without_query():
    for role,tenant in (("MASTER",None),("TENANT_MEMBER",TENANT),
                        ("TENANT_ADMIN",OTHER)):
        db=ReadOnly([account()])
        with pytest.raises(HTTPException) as error:
            await list_ledger_account_directory(TENANT,session(role,tenant),db)
        assert error.value.status_code==403
        assert db.calls==[]


@pytest.mark.asyncio
async def test_invalid_tenant_fails_without_query():
    db=ReadOnly([account()])
    with pytest.raises(HTTPException) as error:
        await list_ledger_account_directory("not-a-uuid",session(tenant="not-a-uuid"),db)
    assert error.value.status_code==422 and db.calls==[]


@pytest.mark.asyncio
async def test_fail_closed_on_duplicates_cross_tenant_and_bad_data():
    row=account()
    cases=[
        [row,row],
        [row,account(account_code="1.1.1")],
        [account(tenant_id=UUID(OTHER))],
        [account(tenant_id="invalid")],
        [account(id="invalid")],
        [account(account_code="1; DROP")],
        [account(account_name="")],
        [account(account_name="invalid\nline")],
        [account(account_type="")],
        [account(account_type="ASSET\n")],
        [account(account_code="x"*25)],
        [account(account_name="x"*161)],
        [account(account_type="x"*49)],
        [account() for _ in range(501)],
    ]
    for rows in cases:
        db=ReadOnly(rows)
        with pytest.raises(HTTPException) as error:
            await list_ledger_account_directory(TENANT,session(),db)
        assert error.value.status_code==503
        assert len(db.calls)==1


def test_validator_does_not_query_database():
    row=account()
    assert len(_validate_directory_accounts([row],UUID(TENANT)))==1
