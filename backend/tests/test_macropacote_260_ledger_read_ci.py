"""Macropacote 260: somente SELECT sintético; nunca acessa PG operacional."""
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.dependencies import AuthenticatedSession
from app.routers.ledger import (
    MAX_LEDGER_ACCOUNTS,
    MAX_LEDGER_TRANSACTIONS,
    MAX_LEDGER_ENTRIES_PER_TRANSACTION,
    _require_ledger_bound,
    list_ledger_accounts,
    list_ledger_transactions,
)

T = str(uuid4())
OUTSIDER = str(uuid4())
ACTOR = str(uuid4())


def session(role="TENANT_ADMIN", tenant=T):
    return AuthenticatedSession(ACTOR, role, tenant, "ci@example.invalid", "CI", role == "MASTER")


class ReadOnly:
    def __init__(self, results):
        self.results = list(results)
        self.calls = []

    async def fetch(self, sql, *args):
        assert sql.lstrip().startswith("SELECT")
        self.calls.append((sql, args))
        assert self.results, "Consulta inesperada"
        return self.results.pop(0)

    async def execute(self, *args):
        raise AssertionError("Escrita proibida")

    async def fetchrow(self, *args):
        raise AssertionError("Consulta extra proibida")


def test_cap_definitions_and_fail_closed():
    assert (MAX_LEDGER_ACCOUNTS, MAX_LEDGER_TRANSACTIONS, MAX_LEDGER_ENTRIES_PER_TRANSACTION) == (500, 500, 100)
    assert len(_require_ledger_bound(list(range(500)), 500)) == 500
    assert len(_require_ledger_bound(list(range(100)), 100)) == 100
    for size, limit in ((501, 500), (101, 100)):
        with pytest.raises(HTTPException) as err:
            _require_ledger_bound(list(range(size)), limit)
        assert err.value.status_code == 503
        assert "pagina" in err.value.detail.lower()


@pytest.mark.asyncio
async def test_accounts_limit_fails_closed_without_truncating():
    db = ReadOnly([[{} for _ in range(501)]])
    with pytest.raises(HTTPException) as err:
        await list_ledger_accounts(T, session(), db)
    assert err.value.status_code == 503
    assert len(db.calls) == 1
    sql, args = db.calls[0]
    assert "WHERE tenant_id = $1" in sql
    assert "ORDER BY account_code ASC" in sql
    assert "LIMIT 501" in sql


@pytest.mark.asyncio
async def test_transactions_limit_fails_closed_before_entry_queries():
    db = ReadOnly([[{} for _ in range(501)]])
    with pytest.raises(HTTPException) as err:
        await list_ledger_transactions(T, session(), db)
    assert err.value.status_code == 503
    assert len(db.calls) == 1
    assert "ORDER BY transaction_date DESC, id DESC" in db.calls[0][0]
    assert "LIMIT 501" in db.calls[0][0]


@pytest.mark.asyncio
async def test_entry_limit_and_tenant_join_fail_closed():
    tx = {
        "id": uuid4(), "tenant_id": __import__("uuid").UUID(T),
        "transaction_date": datetime(2027, 1, 10, tzinfo=timezone.utc),
        "description": "CI", "reference_id": "CI:ONLY",
    }
    db = ReadOnly([[tx], [{} for _ in range(101)]])
    with pytest.raises(HTTPException) as err:
        await list_ledger_transactions(T, session(), db)
    assert err.value.status_code == 503
    assert len(db.calls) == 2
    sql, args = db.calls[1]
    assert "a.tenant_id = e.tenant_id" in sql
    assert "e.transaction_id = $1 AND e.tenant_id = $2" in sql
    assert "LIMIT 101" in sql


@pytest.mark.asyncio
async def test_empty_rows_return_empty_not_synthetic_data():
    db1 = ReadOnly([[]])
    db2 = ReadOnly([[]])
    assert await list_ledger_accounts(T, session(), db1) == []
    assert await list_ledger_transactions(T, session(), db2) == []
    assert len(db1.calls) == len(db2.calls) == 1


@pytest.mark.asyncio
async def test_master_member_other_tenant_rejected_without_db_calls():
    for role, tenant in (("MASTER", None), ("TENANT_MEMBER", T), ("TENANT_ADMIN", OUTSIDER)):
        for route in (list_ledger_accounts, list_ledger_transactions):
            db = ReadOnly([])
            with pytest.raises(HTTPException) as err:
                await route(T, session(role, tenant), db)
            assert err.value.status_code == 403
            assert db.calls == []
