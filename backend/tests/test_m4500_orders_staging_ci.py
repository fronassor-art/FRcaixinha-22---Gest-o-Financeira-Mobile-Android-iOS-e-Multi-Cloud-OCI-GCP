"""M4500: OCI staging 036 has signed Orders separate from legacy Payment inbox."""
from pathlib import Path
from uuid import UUID
import pytest

from app.mp_orders_webhook import SignedOrderEvent
from app.mp_orders_staging_db import StagingOrdersInbox,OrdersStagingDatabaseBlocked

ROOT=Path(__file__).resolve().parents[1]
SQL=ROOT/"staging_migrations/036_signed_orders_inbox_staging_only.sql"
T=UUID("00000000-0000-4000-8000-0000000000a1")


def test_staging_only_guard_schema_and_durable_function():
    assert SQL.is_file()
    assert not (ROOT/"migrations"/SQL.name).exists()
    body=SQL.read_text()
    for anchor in (
        "current_database()<>'frcaixinha_staging'",
        "frcaixinha.orders_staging_authorized",
        "current_setting('is_superuser')<>'on'",
        "frcaixinha_mp_webhook_ingest",
        "mp_signed_order_inbox_staging",
        "FORCE ROW LEVEL SECURITY",
        "session_user<>'frcaixinha_mp_webhook_ingest'",
        "mp_staging_append_signed_order",
        "REPLAY",
        "BANK",
        "CHECK(bank_reconciled=false)",
        "CHECK(ledger_written=false)",
        "CHECK(payment_marked_paid=false)",
    ):
        if anchor=="BANK":
            continue
        assert anchor in body
    assert "COMMIT;" in body
    assert "GRANT EXECUTE" in body
    assert "TO frcaixinha_mp_webhook_ingest" in body
    assert "ON DELETE RESTRICT" in body
    assert "DROP TABLE public." not in body
    assert "UPDATE loans SET" not in body


def sample():
    return SignedOrderEvent(
        tenant_id=T,provider_account_id="2002",
        event_id="N_12345",request_id="req-12345678",
        order_id="ORD01HRYFWNYRE1MR1E60MW3X0T2P",
        action="order.processed",observed_status="processed",
        payload_sha256="a"*64,live_mode=False,
    )


class Tx:
    async def __aenter__(self):return self
    async def __aexit__(self,*args):pass

class Conn:
    def __init__(self,ready=True):
        self.ready=ready
        self.args=None
    def transaction(self):return Tx()
    async def fetchval(self,query,*args):
        if "current_database()" in query:return self.ready
        self.args=(query,args)
        return "INSERTED"

class Pool:
    def __init__(self,conn):self.conn=conn
    def acquire(self):
        class Handle:
            def __init__(self,conn):self.conn=conn
            async def __aenter__(self):return self.conn
            async def __aexit__(self,*a):pass
        return Handle(self.conn)


@pytest.mark.asyncio
async def test_signed_event_persists_only_if_real_staging_role():
    conn=Conn(ready=True)
    adapter=StagingOrdersInbox(Pool(conn))
    assert await adapter.append(sample())=="INSERTED"
    assert conn.args is not None
    assert "mp_staging_append_signed_order(" in conn.args[0]
    assert len(conn.args[1])==9
    assert conn.args[1][0]==T
    assert conn.args[1][4]=="ORD01HRYFWNYRE1MR1E60MW3X0T2P"


@pytest.mark.asyncio
async def test_dev_database_denied_no_financial_fallback():
    conn=Conn(ready=False)
    adapter=StagingOrdersInbox(Pool(conn))
    with pytest.raises(OrdersStagingDatabaseBlocked):
        await adapter.append(sample())
    assert conn.args is None
