"""M360 - 26 lançamentos sintéticos em mock, sem tocar banco operacional."""
from datetime import datetime, timezone, timedelta
from uuid import uuid4, UUID
import json
import base64
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from app.dependencies import AuthenticatedSession, get_current_session
from app.database import get_rls_db_connection
from app.main import app
from app.routers.ledger import list_ledger_account_entries_keyset
from app.ledger_keyset import encode_cursor, decode_cursor

T,A,U,OTHER = (str(uuid4()) for _ in range(4))


def actor(role="TENANT_ADMIN", tenant=T):
    return AuthenticatedSession(U,role,tenant,"ci@example.invalid","CI",role=="MASTER")


def row(i):
    return dict(id=UUID(int=1000+i),transaction_id=UUID(int=2000+i),
                transaction_date=datetime(2027,1,10,tzinfo=timezone.utc)-timedelta(minutes=i),
                description="Movimento sintetico",reference_id="CI:READ_ONLY",
                entry_type="DR",amount_cents=125)


class ReadOnly:
    def __init__(self, rows=(), exists=True):
        self.rows=list(rows)
        self.exists=exists
        self.calls=[]

    async def fetchrow(self, sql, *args):
        assert sql.strip().startswith("SELECT")
        self.calls.append((sql,args))
        return {"id":UUID(A)} if self.exists else None

    async def fetch(self, sql, *args):
        assert sql.strip().startswith("SELECT")
        assert "e.tenant_id=$1 AND e.account_id=$2" in sql
        assert "t.tenant_id=e.tenant_id" in sql
        assert "OFFSET" not in sql.upper()
        self.calls.append((sql,args))
        if len(args)==3:
            return self.rows[:args[-1]]
        key=tuple(args[2:5])
        return [r for r in self.rows if (
            r["transaction_date"],r["transaction_id"],r["id"]
        ) < key][:args[-1]]

    async def execute(self,*_):
        raise AssertionError("escrita nao autorizada")


@pytest.mark.asyncio
async def test_two_distinct_pages_of_26_entries():
    db=ReadOnly([row(i) for i in range(26)])
    first=await list_ledger_account_entries_keyset(T,A,None,25,actor(),db)
    assert first.has_more and len(first.entries)==25 and first.next_cursor
    assert first.page_size==25 and first.tenant_id==T and first.account_id==A
    assert not first.bank_reconciled and not first.financial_closing_authorized
    assert not first.complete_ledger_verified
    assert db.calls[-1][1]==(UUID(T),UUID(A),26)
    second=await list_ledger_account_entries_keyset(T,A,first.next_cursor,25,actor(),db)
    assert not second.has_more and second.next_cursor is None
    assert len(second.entries)==1
    assert {r.id for r in first.entries}.isdisjoint({r.id for r in second.entries})
    assert db.calls[-1][1][:2]==(UUID(T),UUID(A))
    assert len(db.calls)==4


@pytest.mark.asyncio
async def test_zero_one_and_missing_account():
    for records in ([],[row(0)]):
        db=ReadOnly(records)
        result=await list_ledger_account_entries_keyset(T,A,None,25,actor(),db)
        assert len(result.entries)==len(records)
        assert not result.has_more and result.next_cursor is None
    db=ReadOnly([row(0)],exists=False)
    with pytest.raises(HTTPException) as exc:
        await list_ledger_account_entries_keyset(T,A,None,25,actor(),db)
    assert exc.value.status_code==404 and len(db.calls)==1


@pytest.mark.asyncio
async def test_privileges_and_scoping_before_sql():
    for role,tenant in (("MASTER",None),("TENANT_MEMBER",T),("TENANT_ADMIN",OTHER)):
        db=ReadOnly([row(0)])
        with pytest.raises(HTTPException) as exc:
            await list_ledger_account_entries_keyset(T,A,None,25,actor(role,tenant),db)
        assert exc.value.status_code==403 and db.calls==[]


@pytest.mark.asyncio
async def test_malformed_cursor_and_invalid_input():
    good=encode_cursor(UUID(T),UUID(A),row(0))
    bad=[
        "!!!","x"*401,good+"x",
        encode_cursor(UUID(OTHER),UUID(A),row(0)),
        encode_cursor(UUID(T),UUID(OTHER),row(0)),
    ]
    for token in bad:
        db=ReadOnly()
        with pytest.raises(HTTPException) as exc:
            await list_ledger_account_entries_keyset(T,A,token,25,actor(),db)
        assert exc.value.status_code==422 and db.calls==[]
    for tenant,account,size in ((T,"bad",25),("bad",A,25),(T,A,0),(T,A,51),(T,A,True)):
        db=ReadOnly()
        with pytest.raises(HTTPException) as exc:
            await list_ledger_account_entries_keyset(tenant,account,None,size,actor(tenant=tenant),db)
        assert exc.value.status_code==422 and db.calls==[]
    assert decode_cursor(good,UUID(T),UUID(A))[1]==row(0)["transaction_id"]
    data=json.loads(base64.urlsafe_b64decode(good+"="*(-len(good)%4)))
    for patch in ({"v":True},{"v":2},{"entry":"bad"},
                  {"date":"2027-01-10T12:00:00"},{"extra":"unauthorized"}):
        changed={**data,**patch}
        token=base64.urlsafe_b64encode(json.dumps(changed,separators=(",",":"),sort_keys=True).encode()).decode().rstrip("=")
        with pytest.raises(HTTPException) as exc:
            decode_cursor(token,UUID(T),UUID(A))
        assert exc.value.status_code==422


@pytest.mark.asyncio
async def test_bad_rows_fail_closed():
    cases=[
        [row(0),row(0)],[row(1),row(0)],
        [{**row(0),"amount_cents":-1}],
        [{**row(0),"amount_cents":True}],
        [{**row(0),"entry_type":"XX"}],
        [{**row(0),"description":"bad\nline"}],
        [{**row(0),"reference_id":""}],
        [{**row(0),"id":"bad"}],
        [{**row(0),"transaction_date":None}],
        [{**row(0),"transaction_date":datetime(2027,1,10)}],
    ]
    for records in cases:
        db=ReadOnly(records)
        with pytest.raises(HTTPException) as exc:
            await list_ledger_account_entries_keyset(T,A,None,25,actor(),db)
        assert exc.value.status_code==503


def test_http_unauthenticated_query_bounds_and_no_cache():
    path=f"/api/v1/tenants/{T}/ledger/accounts/{A}/entries/keyset"
    with TestClient(app) as client:
        assert client.get(path).status_code==401
    app.dependency_overrides[get_current_session]=actor
    app.dependency_overrides[get_rls_db_connection]=lambda:ReadOnly([row(0)])
    try:
        with TestClient(app) as client:
            for query in ("?page_size=0","?page_size=51","?cursor=!!!"):
                assert client.get(path+query).status_code==422
            res=client.get(path)
            assert res.status_code==200,res.text
            assert res.json()["next_cursor"] is None
            assert res.headers["cache-control"]=="no-store"
    finally:
        app.dependency_overrides.pop(get_current_session,None)
        app.dependency_overrides.pop(get_rls_db_connection,None)
