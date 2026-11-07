"""M22900: Orders GET must never self-attest independent bank settlement."""
from dataclasses import replace
from datetime import datetime,tzinfo
import pytest
from app.mp_orders_settlement import correlate_three_source,IndependentOrdersSettlementService
from app.mp_orders_workflow import validate_orders_independent_settlement
from app.pix_automation_contract import FinancialOperationBlocked
from test_m5200_orders_three_source_ci import command,provider_read,statement
from test_m4600_orders_workflow_ci import bank as bank_proof

@pytest.mark.parametrize("flag",["bank_reconciled","ledger_written","financial_effect_applied"])
def test_processed_get_does_not_claim_bank(flag):
    forged=provider_read(**{flag:True})
    with pytest.raises(FinancialOperationBlocked):
        correlate_three_source(command=command(),authenticated_order=forged,statement=statement())
    with pytest.raises(FinancialOperationBlocked):
        validate_orders_independent_settlement(command(),forged,bank_proof(command()))

@pytest.mark.parametrize("flag",["bank_reconciled","ledger_written","financial_effect_applied"])
@pytest.mark.asyncio
async def test_bad_provider_get_cannot_contact_statement_reader(flag):
    class Never:
        async def fetch(self,**kwargs):pytest.fail("bank lookup must not occur")
    result=await IndependentOrdersSettlementService(Never()).verify(
        command=command(),authenticated_order=provider_read(**{flag:True}))
    assert result is None

class NoOffset(tzinfo):
    def utcoffset(self,dt):return None
    def dst(self,dt):return None
    def tzname(self,dt):return "unknown"

@pytest.mark.parametrize("bad",[
    {"settled_at":datetime(2027,1,10,14,30,tzinfo=NoOffset())},
    {"fetched_at":datetime(2027,1,10,14,30,tzinfo=NoOffset())},
    {"settled_at":datetime(2027,1,10,14,30)},
    {"fetched_at":datetime(2027,1,10,14,30)},
    {"gross_cents":True},{"fee_cents":True},
    {"net_cents":14700.0},{"gross_cents":"15000"},
])
def test_wrong_timezone_or_cents_fails_closed(bad):
    with pytest.raises(FinancialOperationBlocked):
        correlate_three_source(command=command(),authenticated_order=provider_read(),statement=statement(**bad))

@pytest.mark.asyncio
async def test_workflow_rejects_fake_ledger_written_without_posting():
    from app.mp_orders_workflow import OrdersCollectionAutomation
    from test_m4600_orders_workflow_ci import Provider,Journal,Statement,command as cmd_fn,prepare_persisted_checkout
    class Fake(Provider):
        async def get(self,*,command,order_id):
            return replace(await super().get(command=command,order_id=order_id),ledger_written=True)
    journal=Journal();cmd=cmd_fn()
    await prepare_persisted_checkout(journal,cmd)
    flow=OrdersCollectionAutomation(provider=Fake(),journal=journal,statements=Statement())
    with pytest.raises(FinancialOperationBlocked):
        await flow.reconcile(command=cmd,order_id="ORD01HRYFWNYRE1MR1E60MW3X0T2P")
    assert journal.posts=={}
