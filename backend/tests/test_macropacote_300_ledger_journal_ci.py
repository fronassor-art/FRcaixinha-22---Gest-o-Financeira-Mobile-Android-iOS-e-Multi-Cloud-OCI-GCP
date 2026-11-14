"""FR Caixinha M300 — paginação de conta contábil; testes apenas sintéticos."""
from datetime import datetime, timezone
from uuid import uuid4, UUID

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.dependencies import AuthenticatedSession
from app.routers.ledger import list_ledger_account_entries
from app.main import app

T = str(uuid4())
A = str(uuid4())
U = str(uuid4())
OTHER = str(uuid4())


def actor(role="TENANT_ADMIN", tenant=T):
    return AuthenticatedSession(U, role, tenant, "ci@example.invalid", "CI", role == "MASTER")


def entry(**changes):
    value = {
        "id": uuid4(), "transaction_id": uuid4(),
        "transaction_date": datetime(2027, 1, 10, tzinfo=timezone.utc),
        "description": "Movimento sintético",
        "reference_id": "CI:READ_ONLY",
        "entry_type": "DR",
        "amount_cents": 125,
    }
    return {**value, **changes}


class ReadOnly:
    def __init__(self, exists=True, rows=None):
        self.exists = exists
        self.rows = [] if rows is None else rows
        self.calls = []

    async def fetchrow(self, sql, *params):
        assert sql.lstrip().startswith("SELECT")
        self.calls.append((sql, params))
        return {"id": UUID(A)} if self.exists else None

    async def fetch(self, sql, *params):
        assert sql.lstrip().startswith("SELECT")
        self.calls.append((sql, params))
        return self.rows

    async def execute(self, *_):
        raise AssertionError("No database mutation allowed")


@pytest.mark.asyncio
async def test_page_is_tenant_scoped_bounded_and_not_financially_authorized():
    db = ReadOnly(rows=[entry(), entry(), entry()])
    result = await list_ledger_account_entries(
        T, A, page=2, page_size=2, session=actor(), conn=db,
    )
    assert result.tenant_id == T and result.account_id == A
    assert result.page == 2 and result.page_size == 2
    assert result.has_more is True and len(result.entries) == 2
    assert result.entries[0].amount_cents == 125
    assert str(result.entries[0].amount_brl) == "1.25"
    assert not result.complete_ledger_verified
    assert not result.bank_reconciled
    assert not result.financial_closing_authorized
    assert len(db.calls) == 2
    account_sql, account_args = db.calls[0]
    assert "tenant_id=$1 AND id=$2" in account_sql
    assert account_args == (UUID(T), UUID(A))
    journal_sql, journal_args = db.calls[1]
    assert "e.tenant_id=$1 AND e.account_id=$2" in journal_sql
    assert "t.tenant_id=e.tenant_id" in journal_sql
    assert "ORDER BY t.transaction_date DESC, t.id DESC, e.id DESC" in journal_sql
    assert journal_args == (UUID(T), UUID(A), 3, 2)


@pytest.mark.asyncio
async def test_empty_page_and_missing_account_are_distinct():
    db = ReadOnly(rows=[])
    res = await list_ledger_account_entries(T, A, 1, 25, actor(), db)
    assert res.entries == [] and res.has_more is False
    assert res.complete_ledger_verified is False
    missing = ReadOnly(exists=False)
    with pytest.raises(HTTPException) as err:
        await list_ledger_account_entries(T, A, 1, 25, actor(), missing)
    assert err.value.status_code == 404 and len(missing.calls) == 1


@pytest.mark.asyncio
async def test_master_member_and_other_tenant_fail_before_sql():
    for role, tenant in (("MASTER", None), ("TENANT_MEMBER", T), ("TENANT_ADMIN", OTHER)):
        db = ReadOnly()
        with pytest.raises(HTTPException) as err:
            await list_ledger_account_entries(T, A, 1, 25, actor(role, tenant), db)
        assert err.value.status_code == 403 and db.calls == []


@pytest.mark.asyncio
async def test_invalid_ids_and_pages_fail_before_sql():
    for tenant, account, page, size in (
        (T, "bad", 1, 25), ("bad", A, 1, 25),
        (T, A, 0, 25), (T, A, 1001, 25),
        (T, A, 1, 0), (T, A, 1, 51),
        (T, A, 1.5, 25), (T, A, 1, True),
    ):
        db = ReadOnly()
        with pytest.raises(HTTPException) as err:
            await list_ledger_account_entries(tenant, account, page, size, actor(tenant=tenant), db)
        assert err.value.status_code == 422
        assert db.calls == []


@pytest.mark.asyncio
async def test_malformed_entries_fail_closed():
    row = entry()
    cases = [
        [row, row], [entry(amount_cents=-1)],
        [entry(amount_cents=0)],
        [entry(amount_cents=1.5)],
        [entry(amount_cents=True)],
        [entry(amount_cents=100000000001)],
        [entry(entry_type="ZZ")], [entry(description="")],
        [entry(reference_id="")], [entry(id="bad")],
        [entry(transaction_id=None)],
        [entry(transaction_date=None)],
    ]
    for rows in cases:
        db = ReadOnly(rows=rows)
        with pytest.raises(HTTPException) as err:
            await list_ledger_account_entries(T, A, 1, 25, actor(), db)
        assert err.value.status_code == 503


def test_api_query_limits_422_without_authenticated_data():
    # FastAPI must reject invalid paging parameters before touching the DB.
    from app.dependencies import get_current_session
    from app.database import get_rls_db_connection
    app.dependency_overrides[get_current_session] = actor
    app.dependency_overrides[get_rls_db_connection] = lambda: ReadOnly()
    try:
        with TestClient(app) as client:
            for query in ("?page=0", "?page_size=51", "?page=1001"):
                response = client.get(
                    f"/api/v1/tenants/{T}/ledger/accounts/{A}/entries" + query
                )
                assert response.status_code == 422, response.text
    finally:
        app.dependency_overrides.pop(get_current_session, None)
        app.dependency_overrides.pop(get_rls_db_connection, None)
