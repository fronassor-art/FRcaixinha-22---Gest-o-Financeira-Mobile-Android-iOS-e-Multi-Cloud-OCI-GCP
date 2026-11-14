"""M2600: HTTP local mock only; no provider network, paid or ledger writes."""
import json
from uuid import UUID

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.mp_readonly_gateway import preview_sandbox_provider_get, CONTRACT
from app.mercado_pago_safety import ExpectedPayment

T = UUID("00000000-0000-4000-8000-0000000000a1")
E = ExpectedPayment("900001","2002","tenant:contribution-001",15000,False)
TOKEN = "sandbox-fixture-token-never-real-2026"
BODY = {
    "id":900001,"collector_id":2002,"external_reference":"tenant:contribution-001",
    "transaction_amount":150,"currency_id":"BRL","status":"approved","live_mode":False
}


async def noop(seconds):
    assert 0 <= seconds <= 4


def transport(fn):
    return httpx.MockTransport(fn)


async def get(t, **overrides):
    options = dict(
        tenant_id=T, expected=E, bound_seller_id="2002",
        seller_authorization_checked=True, access_token=TOKEN,
        transport=t, sleep=noop,
    )
    options.update(overrides)
    return await preview_sandbox_provider_get(**options)


def response(req, data=BODY):
    assert req.method=="GET"
    assert str(req.url)=="https://api.mercadopago.com/v1/payments/900001"
    assert req.headers["authorization"]=="Bearer "+TOKEN
    return httpx.Response(200,json=data)


@pytest.mark.asyncio
async def test_approved_sandbox_is_not_paid():
    result=await get(transport(response))
    assert result.finding=="APPROVED_SANDBOX_UNSETTLED"
    assert result.attempts==1
    assert not any(getattr(result,key) for key in (
        "bank_reconciled","payment_marked_paid","ledger_written",
        "financial_closing_authorized","payout_authorized"))
    assert TOKEN not in repr(result)


@pytest.mark.asyncio
@pytest.mark.parametrize("bad",[
    {"tenant_id":"x"},{"bound_seller_id":"3003"},
    {"seller_authorization_checked":False},{"access_token":"short"},
    {"access_token":"long-token-with-space invalid"},
    {"expected":ExpectedPayment("900001","2002",E.external_reference,15000,True)},
    {"expected":ExpectedPayment("900001","2002",E.external_reference,0,False)},
    {"expected":ExpectedPayment("x-invalid","2002",E.external_reference,15000,False)},
])
async def test_no_call_on_scope_mismatch(bad):
    seen=[]
    def handler(req):
        seen.append(1)
        return httpx.Response(200,json=BODY)
    with pytest.raises(ValueError):
        await get(transport(handler),**bad)
    assert seen==[]


@pytest.mark.asyncio
@pytest.mark.parametrize("change",[
    {"id":900002},{"collector_id":3003},
    {"external_reference":"tenant:unrelated"},
    {"transaction_amount":"149.99"},{"transaction_amount":True},
    {"transaction_amount":"150.001"},{"live_mode":True},{"currency_id":"USD"},
])
async def test_provider_mismatch(change):
    payload={**BODY,**change}
    r=await get(transport(lambda req: response(req,payload)))
    assert r.finding=="PROVIDER_FIELDS_MISMATCH"
    assert r.payment_marked_paid is False


@pytest.mark.asyncio
@pytest.mark.parametrize("status",["pending","in_process","refunded",
    "charged_back","in_mediation","cancelled","rejected"])
async def test_other_status_does_not_confirm(status):
    r=await get(transport(lambda req:response(req,{**BODY,"status":status})))
    assert r.finding=="NON_APPROVED_OR_REVERSAL"
    assert not r.bank_reconciled


@pytest.mark.asyncio
async def test_429_backoff_and_retry():
    calls=[]
    delay=[]
    async def sleeper(x): delay.append(x)
    def fn(req):
        calls.append(1)
        if len(calls)<3:
            return httpx.Response(429,headers={"retry-after":"2"})
        return response(req)
    r=await get(transport(fn),sleep=sleeper)
    assert len(calls)==3 and delay==[2.0,2.0]
    assert r.finding=="APPROVED_SANDBOX_UNSETTLED"


@pytest.mark.asyncio
async def test_429_exhaustion():
    calls=[]
    def fn(req):
        calls.append(1)
        return httpx.Response(429,headers={"retry-after":"99"})
    r=await get(transport(fn))
    assert len(calls)==3 and r.finding=="RATE_LIMIT_OR_OUTAGE"
    assert not r.payment_marked_paid


@pytest.mark.asyncio
async def test_timeouts_bounded():
    calls=[]
    def fn(req):
        calls.append(1)
        raise httpx.ConnectTimeout("Sensitive exception; never return")
    r=await get(transport(fn))
    assert len(calls)==3
    assert r.finding=="UNAVAILABLE"
    assert TOKEN not in repr(r)


@pytest.mark.asyncio
@pytest.mark.parametrize("code",[301,302,401,403,404,422,500])
async def test_other_http_fail_closed(code):
    seen=[]
    def fn(req):
        seen.append(1)
        return httpx.Response(code,headers={"location":"https://untrusted.invalid"})
    r=await get(transport(fn))
    assert len(seen)==1 and r.finding=="UNEXPECTED_HTTP_STATUS"


@pytest.mark.asyncio
@pytest.mark.parametrize("content,reason",[
    (b"X"*65537,"OVERSIZE_BODY"),
    (b"bad-json","INVALID_JSON"),
    (b'{"status":"approved","status":"pending"}',"INVALID_JSON"),
    (b'{"status":NaN}',"INVALID_JSON"),
    (b'{"status":"unknown"}',"INVALID_PROVIDER_STATUS"),
])
async def test_malformed_responses(content,reason):
    r=await get(transport(lambda req:httpx.Response(200,content=content)))
    assert r.finding==reason
    assert not r.ledger_written


def test_m2600_health_no_money():
    with TestClient(app) as c:
        d=c.get("/api/health/features/m2600").json()
    assert d["contract"]==CONTRACT
    assert d["workstream"]=="AI_STUDIO"
    assert d["gateway_unwired"] is True
    assert d["oci_staging_deployed"] is False
    for key in ("provider_connected","bank_reconciled",
                "real_payments_enabled","ledger_written",
                "financial_closing_authorized"):
        assert d[key] is False
