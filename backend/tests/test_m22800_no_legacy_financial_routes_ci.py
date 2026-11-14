"""M22800: public financial routes cannot be activated by deleting a guard."""
import inspect
import pytest
from fastapi import HTTPException

from app.routers.contributions import pay_contribution
from app.routers.closings import close_cycle, capital_days_weight
from app.dependencies import AuthenticatedSession

def actor(role="TENANT_ADMIN"):
    return AuthenticatedSession("synthetic-user",role,"tenant",
                                "synthetic@example.invalid","CI",False)


@pytest.mark.asyncio
async def test_public_payment_503_without_database_writes():
    class Database:
        async def execute(self,*args): pytest.fail("database write denied")
        async def fetchrow(self,*args): pytest.fail("database read denied")
    with pytest.raises(HTTPException) as exc:
        await pay_contribution("tenant","contribution",None,actor(),Database())
    assert exc.value.status_code==503


@pytest.mark.asyncio
async def test_close_503_without_database_writes():
    class Database:
        async def execute(self,*args):pytest.fail("database write denied")
        async def fetchrow(self,*args):pytest.fail("database read denied")
    with pytest.raises(HTTPException) as exc:
        await close_cycle("tenant",None,actor(),Database())
    assert exc.value.status_code==503


def test_direct_financial_route_has_no_unreachable_mutation():
    for route in (pay_contribution,close_cycle):
        source=inspect.getsource(route)
        assert "raise HTTPException(" in source
        assert "status_code=503" in source
        assert "await conn.execute(" not in source
        assert "UPDATE cycles" not in source
        assert "INSERT INTO pix_payment_intents" not in source
        assert "capital_recognized=True" not in source


def test_member_cannot_close_cycle():
    import asyncio
    async def run():
        with pytest.raises(HTTPException) as exc:
            await close_cycle("tenant",None,actor("TENANT_MEMBER"),None)
        assert exc.value.status_code==403
    asyncio.run(run())


def test_closing_weight_helper_preserved_for_contract_unit_tests():
    from datetime import date
    from decimal import Decimal
    assert capital_days_weight(Decimal("100"),date(2027,1,10),
                               date(2027,12,31))==Decimal("35500.0000")
