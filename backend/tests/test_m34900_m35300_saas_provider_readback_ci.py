"""M34900-M35300 provider GET + SaaS readback: simulated HTTP only."""
from __future__ import annotations
from dataclasses import replace
from decimal import Decimal
from uuid import uuid4
import json
import re

import httpx
import pytest

from app.saas_platform_payment_readback import (
    SaaSPlatformPaymentRecord, review_platform_saas_payment_get,
)
from app.platform_provider_adapters import (
    PlatformMpConfig, ProviderUnavailable, fetch_authoritative_saas_payment,
)

TOKEN="TEST_ONLY_PLATFORM_READBACK_NEVER_LIVE_CI"
CONFIG=PlatformMpConfig(TOKEN,"12345","S"*32,False)


@pytest.fixture
def gates(monkeypatch):
    for key in ("AI_STUDIO_REAL_SAAS","AI_STUDIO_LEGAL_CLEARANCE",
                "AI_STUDIO_OPERATIONAL_REVIEW"):
        monkeypatch.setenv(key,"APPROVED")


def intent():
    return SaaSPlatformPaymentRecord(
        tenant_id=uuid4(),admin_user_id=uuid4(),provider_payment_id="456789",
        platform_collector_id="12345",external_reference="saas:ci-m35300",
        expected_amount_cents=8990,live_mode=False,status="PENDING",
    )


def response(**updates):
    item={
        "id":456789,"status":"approved","currency_id":"BRL",
        "live_mode":False,"collector_id":12345,
        "external_reference":"saas:ci-m35300",
        "transaction_amount":"89.90","transaction_amount_refunded":0,
    }
    item.update(updates)
    return item


def mock_http(handler):
    def run(request):
        assert request.method=="GET"
        assert request.url.scheme=="https"
        assert request.url.host=="api.mercadopago.com"
        assert request.url.path=="/v1/payments/456789"
        assert request.headers["authorization"]=="Bearer "+TOKEN
        return handler(request)
    return httpx.MockTransport(run)


@pytest.mark.asyncio
async def test_valid_provider_get_is_only_a_candidate(gates):
    calls=[]
    async with httpx.AsyncClient(transport=mock_http(
        lambda req: (calls.append(req.method) or httpx.Response(200,json=response()))
    )) as client:
        result=await review_platform_saas_payment_get(record=intent(),config=CONFIG,client=client)
    assert calls==["GET"]
    assert result.state=="READBACK_MATCH_REVIEW_ONLY"
    assert result.matching_fields is True
    assert re.fullmatch(r"[0-9a-f]{64}",result.evidence_sha256)
    assert all(getattr(result,key) is False for key in (
        "payment_marked_paid","entitlement_created","membership_created",
        "quota_created","ledger_written","pix_authorized",
        "production_activation_authorized","writes_performed",
    ))
    assert TOKEN not in repr(result)
    assert "456789" not in repr(result)


@pytest.mark.asyncio
@pytest.mark.parametrize("change,expected_state",[
    ({"id":"987654"},"AUTHENTICATED_GET_UNAVAILABLE_OR_BLOCKED"),
    ({"collector_id":99999},"PROVIDER_ID_COLLECTOR_REFERENCE_AMOUNT_OR_MODE_MISMATCH"),
    ({"external_reference":"saas:other"},"PROVIDER_ID_COLLECTOR_REFERENCE_AMOUNT_OR_MODE_MISMATCH"),
    ({"transaction_amount":"89.91"},"PROVIDER_ID_COLLECTOR_REFERENCE_AMOUNT_OR_MODE_MISMATCH"),
    ({"transaction_amount":"NaN"},"PROVIDER_ID_COLLECTOR_REFERENCE_AMOUNT_OR_MODE_MISMATCH"),
    ({"currency_id":"USD"},"PROVIDER_ID_COLLECTOR_REFERENCE_AMOUNT_OR_MODE_MISMATCH"),
    ({"live_mode":True},"PROVIDER_ID_COLLECTOR_REFERENCE_AMOUNT_OR_MODE_MISMATCH"),
    ({"status":"pending"},"PROVIDER_NOT_APPROVED_OR_REVERSED"),
    ({"status":"refunded"},"PROVIDER_NOT_APPROVED_OR_REVERSED"),
    ({"status":"charged_back"},"PROVIDER_NOT_APPROVED_OR_REVERSED"),
    ({"transaction_amount_refunded":"0.01"},"REFUND_OR_PARTIAL_REFUND_BLOCKED"),
    ({"transaction_amount_refunded":"89.90"},"REFUND_OR_PARTIAL_REFUND_BLOCKED"),
    ({"transaction_amount_refunded":"NaN"},"REFUND_OR_PARTIAL_REFUND_BLOCKED"),
    ({"transaction_amount_refunded":-1},"REFUND_OR_PARTIAL_REFUND_BLOCKED"),
    ({"transaction_amount_refunded":False},"REFUND_OR_PARTIAL_REFUND_BLOCKED"),
    ({"transaction_amount_refunded":None},"READBACK_MATCH_REVIEW_ONLY"),
])
async def test_mismatch_never_enables_license(change,expected_state,gates):
    async with httpx.AsyncClient(transport=mock_http(
        lambda _:httpx.Response(200,json=response(**change))
    )) as client:
        result=await review_platform_saas_payment_get(record=intent(),config=CONFIG,client=client)
    assert result.state==expected_state
    assert result.production_activation_authorized is False
    assert result.payment_marked_paid is False
    assert result.writes_performed is False


@pytest.mark.asyncio
@pytest.mark.parametrize("http_status,body",[
    (401,b'{"message":"unauthorized"}'),
    (403,b'{"message":"denied"}'),
    (404,b'{"message":"missing"}'),
    (429,b'{"message":"rate_limit"}'),
    (500,b'{"message":"server_error"}'),
    (302,b'{"status":"approved"}'),
    (200,b'not json'),
    (200,b'{"id":456789,"status":"approved","status":"refunded"}'),
    (200,b'{"id":456789,"status":NaN}'),
    (200,b" "*65537),
])
async def test_non_authoritative_or_ambiguous_get_blocked(http_status,body,gates):
    async with httpx.AsyncClient(transport=mock_http(
        lambda _:httpx.Response(http_status,content=body)
    )) as client:
        result=await review_platform_saas_payment_get(record=intent(),config=CONFIG,client=client)
    assert result.state=="AUTHENTICATED_GET_UNAVAILABLE_OR_BLOCKED"
    assert result.matching_fields is False
    assert result.production_activation_authorized is False


@pytest.mark.asyncio
async def test_duplicate_nested_key_rejected(gates):
    body=(b'{"id":456789,"status":"approved","currency_id":"BRL",'
          b'"live_mode":false,"collector_id":12345,'
          b'"external_reference":"saas:ci-m35300","transaction_amount":89.90,'
          b'"additional_info":{"status":"approved","status":"refunded"}}')
    async with httpx.AsyncClient(transport=mock_http(
        lambda _:httpx.Response(200,content=body)
    )) as client:
        result=await review_platform_saas_payment_get(record=intent(),config=CONFIG,client=client)
    assert result.state=="AUTHENTICATED_GET_UNAVAILABLE_OR_BLOCKED"


@pytest.mark.asyncio
@pytest.mark.parametrize("record_changes",[
    {"provider_payment_id":"../../admin"},
    {"platform_collector_id":"99999"},
    {"external_reference":"pix:tenant-finance"},
    {"expected_amount_cents":0},
    {"expected_amount_cents":True},
    {"live_mode":True},
    {"status":"REFUNDED"},
    {"currency":"USD"},
    {"source":"WEBHOOK_JSON"},
])
async def test_invalid_persisted_scope_does_not_hit_provider(record_changes,gates):
    calls=[]
    async with httpx.AsyncClient(transport=mock_http(
        lambda _: (calls.append(1) or httpx.Response(200,json=response()))
    )) as client:
        result=await review_platform_saas_payment_get(
            record=replace(intent(),**record_changes),config=CONFIG,client=client)
    assert result.state=="PLATFORM_RECORD_OR_CREDENTIAL_SCOPE_DENIED"
    assert calls==[]


@pytest.mark.asyncio
async def test_disarmed_environment_blocks_before_get(monkeypatch):
    for key in ("AI_STUDIO_REAL_SAAS","AI_STUDIO_LEGAL_CLEARANCE",
                "AI_STUDIO_OPERATIONAL_REVIEW"):
        monkeypatch.delenv(key,raising=False)
    calls=[]
    async with httpx.AsyncClient(transport=mock_http(
        lambda _: (calls.append(1) or httpx.Response(200,json=response()))
    )) as client:
        result=await review_platform_saas_payment_get(
            record=intent(),config=CONFIG,client=client)
    assert result.state=="AUTHENTICATED_GET_UNAVAILABLE_OR_BLOCKED"
    assert calls==[]


@pytest.mark.asyncio
async def test_transport_failure_is_closed(gates):
    def broken(_):
        raise httpx.ConnectTimeout("mock timeout")
    async with httpx.AsyncClient(transport=mock_http(broken)) as client:
        result=await review_platform_saas_payment_get(
            record=intent(),config=CONFIG,client=client)
    assert result.state=="AUTHENTICATED_GET_UNAVAILABLE_OR_BLOCKED"
    assert result.entitlement_created is False


@pytest.mark.asyncio
async def test_adapter_returns_exact_decimal_from_authenticated_json(gates):
    async with httpx.AsyncClient(transport=mock_http(
        lambda _:httpx.Response(200,content=json.dumps(response(
            transaction_amount=89.90,
        )).encode())
    )) as client:
        raw=await fetch_authoritative_saas_payment(
            config=CONFIG,payment_id="456789",client=client)
    assert raw["transaction_amount"]==Decimal("89.9")
    assert type(raw["transaction_amount"]) is Decimal


def test_module_is_not_a_public_endpoint_or_financial_worker():
    from pathlib import Path
    root=Path(__file__).resolve().parents[2]
    source=(root/"backend/app/saas_platform_payment_readback.py").read_text()
    assert "INSERT INTO " not in source
    assert "UPDATE public." not in source
    assert "DELETE FROM " not in source
    assert "create_platform_pix" not in source
    assert "matches_approved_payment" in source
    assert "fetch_authoritative_saas_payment" in source
    assert "production_activation_authorized: bool = False" in source
