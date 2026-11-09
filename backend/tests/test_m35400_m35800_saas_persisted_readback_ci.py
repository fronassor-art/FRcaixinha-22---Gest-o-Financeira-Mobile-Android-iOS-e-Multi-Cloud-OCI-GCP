"""M35400-M35800 CI: RLS-backed SaaS payment, frozen price and provider readback."""
from decimal import Decimal
from uuid import uuid4
import httpx
import pytest
from app.dependencies import AuthenticatedSession
from app.platform_provider_adapters import PlatformMpConfig
from app.saas_persisted_license_preflight import PAYMENT_QUERY,readback_persisted_platform_payment

CONFIG=PlatformMpConfig("CI_ONLY_PLATFORM_MP_TEST_TOKEN_12345","12345","s"*26,False)

def master(role="MASTER",verified=True,tenant=None):
    return AuthenticatedSession(str(uuid4()),role,tenant,"ci@example.invalid","CI",verified)

def sample(**kw):
    x=dict(tenant_id=uuid4(),admin_user_id=uuid4(),provider_payment_id="456789",
       platform_collector_id="12345",external_reference="saas:m35800",
       expected_amount_cents=8990,live_mode=False,payment_status="PENDING",
       currency="BRL",provider="MERCADO_PAGO",billing_period="MONTHLY",
       preparation_status="PENDING_PAYMENT",monthly_price=Decimal("89.90"),
       annual_price=Decimal("899.00"))
    x.update(kw)
    return x

class DB:
    def __init__(self,row): self.row=row;self.calls=0
    async def fetchrow(self,query,pid):
        assert query==PAYMENT_QUERY
        assert "JOIN public.saas_subscription_preparations" in query
        assert "JOIN public.platform_license_price_versions" in query
        assert "s.price_version_id=i.price_version_id" in query
        assert "i.admin_user_id=s.admin_user_id" in query
        assert "JOIN public.tenants t" in query
        assert "WHERE i.id=$1::uuid" in query
        assert "ledger_entries" not in query
        assert pid.version is not None
        self.calls+=1
        return self.row

def http_client(calls,**patch):
    payload=dict(id=456789,collector_id=12345,
        external_reference="saas:m35800",transaction_amount="89.90",
        currency_id="BRL",live_mode=False,status="approved",
        transaction_amount_refunded=0)
    payload.update(patch)
    def run(request):
        calls.append(request)
        assert request.method=="GET" and request.url.path=="/v1/payments/456789"
        assert request.url.host=="api.mercadopago.com"
        return httpx.Response(200,json=payload)
    return httpx.AsyncClient(transport=httpx.MockTransport(run))

@pytest.fixture
def gates(monkeypatch):
    for key in ("AI_STUDIO_REAL_SAAS","AI_STUDIO_LEGAL_CLEARANCE","AI_STUDIO_OPERATIONAL_REVIEW"):
        monkeypatch.setenv(key,"APPROVED")

@pytest.mark.asyncio
async def test_master_matches_db_provider_without_activating(gates):
    db=DB(sample());calls=[];payment=uuid4()
    async with http_client(calls) as c:
        a=await readback_persisted_platform_payment(
            session=master(),intent_id=payment,conn=db,config=CONFIG,client=c)
        b=await readback_persisted_platform_payment(
            session=master(),intent_id=payment,conn=db,config=CONFIG,client=c)
    assert a==b
    assert a.state=="RLS_PRICE_PROVIDER_MATCH_REVIEW_ONLY"
    assert a.matched and len(a.digest)==64 and db.calls==2 and len(calls)==2
    assert all(not getattr(a,key) for key in (
        "payment_settled","license_activated","member_activated",
        "pix_authorized","production_authorized","writes_performed"))
    assert "CI_ONLY_PLATFORM_MP_TEST_TOKEN" not in repr(a)
    assert "456789" not in repr(a)

@pytest.mark.asyncio
@pytest.mark.parametrize("session",[
    master("TENANT_ADMIN",False,str(uuid4())),master("TENANT_MEMBER",False,str(uuid4())),
    master("MASTER",False), master("MASTER",True,str(uuid4())),
    AuthenticatedSession("invalid","MASTER",None,"","",True),
])
async def test_role_rejected_before_db_and_http(session,gates):
    db=DB(sample());calls=[]
    async with http_client(calls) as c:
        a=await readback_persisted_platform_payment(
            session=session,intent_id=uuid4(),conn=db,config=CONFIG,client=c)
    assert a.state=="MASTER_SESSION_DENIED"
    assert db.calls==0 and calls==[]

@pytest.mark.asyncio
@pytest.mark.parametrize("patch,reason",[
    ({"monthly_price":Decimal("89.91")},"STORED_PRICE_VERSION_MISMATCH"),
    ({"monthly_price":Decimal("NaN")},"STORED_PRICE_VERSION_MISMATCH"),
    ({"monthly_price":89.9},"STORED_PRICE_VERSION_MISMATCH"),
    ({"expected_amount_cents":8991},"STORED_PRICE_VERSION_MISMATCH"),
    ({"billing_period":"ANNUAL","expected_amount_cents":8990},"STORED_PRICE_VERSION_MISMATCH"),
    ({"billing_period":"WEEKLY"},"INVALID_PREPARATION_SCOPE"),
    ({"provider":"FAKE"},"INVALID_PREPARATION_SCOPE"),
    ({"preparation_status":"CANCELED"},"INVALID_PREPARATION_SCOPE"),
    ({"live_mode":True},"LIVE_PROVIDER_READBACK_DISABLED"),
])
async def test_price_and_business_scope_fail_closed_before_get(patch,reason,gates):
    calls=[]
    async with http_client(calls) as c:
        a=await readback_persisted_platform_payment(
            session=master(),intent_id=uuid4(),conn=DB(sample(**patch)),config=CONFIG,client=c)
    assert a.state==reason and not a.writes_performed and calls==[]

@pytest.mark.asyncio
async def test_no_rls_row_never_reaches_provider(gates):
    calls=[]
    async with http_client(calls) as c:
        a=await readback_persisted_platform_payment(
            session=master(),intent_id=uuid4(),conn=DB(None),config=CONFIG,client=c)
    assert a.state=="RLS_PAYMENT_NOT_VISIBLE" and calls==[]

@pytest.mark.asyncio
@pytest.mark.parametrize("patch,reason",[
    ({"collector_id":99999},"PROVIDER_ID_COLLECTOR_REFERENCE_AMOUNT_OR_MODE_MISMATCH"),
    ({"transaction_amount":"89.91"},"PROVIDER_ID_COLLECTOR_REFERENCE_AMOUNT_OR_MODE_MISMATCH"),
    ({"external_reference":"saas:other"},"PROVIDER_ID_COLLECTOR_REFERENCE_AMOUNT_OR_MODE_MISMATCH"),
    ({"status":"refunded"},"PROVIDER_NOT_APPROVED_OR_REVERSED"),
    ({"transaction_amount_refunded":"0.01"},"REFUND_OR_PARTIAL_REFUND_BLOCKED"),
])
async def test_provider_mismatch_never_activates(patch,reason,gates):
    calls=[]
    async with http_client(calls,**patch) as c:
        a=await readback_persisted_platform_payment(
            session=master(),intent_id=uuid4(),conn=DB(sample()),config=CONFIG,client=c)
    assert a.state==reason and not a.production_authorized and len(calls)==1

@pytest.mark.asyncio
async def test_governance_off_blocks_external_get(monkeypatch):
    for key in ("AI_STUDIO_REAL_SAAS","AI_STUDIO_LEGAL_CLEARANCE","AI_STUDIO_OPERATIONAL_REVIEW"):
        monkeypatch.delenv(key,raising=False)
    calls=[]
    async with http_client(calls) as c:
        a=await readback_persisted_platform_payment(
            session=master(),intent_id=uuid4(),conn=DB(sample()),config=CONFIG,client=c)
    assert a.state=="AUTHENTICATED_GET_UNAVAILABLE_OR_BLOCKED" and calls==[]

def test_source_module_never_writes_or_routes():
    from pathlib import Path
    root=Path(__file__).resolve().parents[2]
    code=(root/"backend/app/saas_persisted_license_preflight.py").read_text()
    assert "APIRouter" not in code and "INSERT INTO " not in code
    assert "UPDATE public." not in code and "DELETE FROM " not in code
    assert "get_rls_db_connection" in code and "review_platform_saas_payment_get" in code
