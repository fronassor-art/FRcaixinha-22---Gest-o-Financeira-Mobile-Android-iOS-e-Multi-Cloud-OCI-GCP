"""M39081 — campaigns require an ABERTO cycle within its real date interval.

Uses fake RLS DB, never the phone's PostgreSQL or any external provider.
"""
import asyncio
from datetime import date, timedelta
from uuid import UUID

import pytest
from fastapi import HTTPException

from backend.app.routers.special_credit import _cycle


TENANT = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
CYCLE = UUID("aaaacccc-aaaa-4aaa-8aaa-aaaaaaaaaaaa")


class Cursor:
    def __init__(self, date_state="current"):
        self.date_state = date_state
        self.query = None
        self.tenant = None

    async def fetchrow(self, query, tenant):
        self.query = query
        self.tenant = tenant
        assert "start_date<=CURRENT_DATE" in query
        assert "end_date>=CURRENT_DATE" in query
        assert "status='ABERTO'" in query
        assert "FROM public.cycles WHERE tenant_id=$1" in query
        if self.date_state != "current":
            # PostgreSQL enforces dates: future/expired/closed cycles have no row.
            return None
        return {"id": CYCLE, "end_date": date.today() + timedelta(days=40)}


@pytest.mark.parametrize("state", ["future", "expired", "closed", "absent"])
def test_no_future_or_expired_cycle_can_authorize_member_grants(state):
    db = Cursor(state)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(_cycle(db, TENANT))
    assert exc.value.status_code == 409
    assert "vigente" in str(exc.value.detail)
    assert db.tenant == TENANT


def test_current_open_cycle_can_be_used_in_synthetic_flow():
    db = Cursor("current")
    row = asyncio.run(_cycle(db, TENANT))
    assert row["id"] == CYCLE
    assert row["end_date"] > date.today()


def test_current_cycle_gate_not_satisfied_by_next_year_preview():
    from backend.app.routers import cycle_contribution_price as opening
    # Cycle opening is a separate authorized write. Neither preview nor
    # having status ABERTO lets credit campaigns start before start_date.
    import inspect
    source = inspect.getsource(opening.opening_preview)
    assert "date(payload.year,1,1)" in source
    assert "FR_FINANCE_CYCLE_OPEN_ENABLED" in source
    assert "preconditions_satisfied" in source
    cycle_source = inspect.getsource(_cycle)
    assert "start_date<=CURRENT_DATE" in cycle_source


def test_read_only_preflight_and_nothing_real_activated():
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    preflight = (root/"backend/scripts/frfinance_m39080_credit_campaign_cycle_readonly.py").read_text()
    contract = (root/"backend/app/routers/special_credit.py").read_text()
    assert "CURRENT_DATE" in preflight
    assert "M39080_DATABASE_WRITES=NONE" in preflight
    assert "real_credit_enabled\": False" in contract
    assert "pix_real_enabled\": False" in contract
    assert "'BLOCKED_EXTERNAL'" in contract
