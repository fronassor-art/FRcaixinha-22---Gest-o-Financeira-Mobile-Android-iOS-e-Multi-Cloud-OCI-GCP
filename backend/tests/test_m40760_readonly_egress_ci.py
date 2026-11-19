"""M40760: readonly provider gateway must deny live and custom transports.

No real network, no PostgreSQL, no FastAPI startup, no external provider.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from uuid import UUID

import httpx
import pytest

from app.mp_readonly_gateway import preview_sandbox_provider_get
from app.mercado_pago_safety import ExpectedPayment

ROOT = Path(__file__).resolve().parents[2]
GATEWAY = ROOT / "backend/app/mp_readonly_gateway.py"
PIX = ROOT / "backend/app/mp_pix_execution.py"
OAUTH = ROOT / "backend/app/mp_connect_http_runtime.py"
WORKFLOW = ROOT / ".github/workflows/frfinance-m40760-readonly-egress-no-go-ci.yml"
DOC = ROOT / "docs/FR_FINANCE_M40760_READONLY_PROVIDER_NO_NETWORK.md"

TENANT = UUID("00000000-0000-4000-8000-0000000000a1")
EXPECTED = ExpectedPayment("900001", "2002", "tenant:test", 15000, False)
TOKEN = "M40760_OFFLINE_TEST_ACCESS_TOKEN_NEVER_REAL"


async def fetch(transport):
    return await preview_sandbox_provider_get(
        tenant_id=TENANT,
        expected=EXPECTED,
        bound_seller_id="2002",
        seller_authorization_checked=True,
        access_token=TOKEN,
        transport=transport,
    )


def test_refuse_missing_transport_without_network():
    with pytest.raises(ValueError, match="GET sandbox"):
        asyncio.run(fetch(None))


def test_refuse_real_async_http_transport_without_network():
    transport = httpx.AsyncHTTPTransport()
    try:
        with pytest.raises(ValueError, match="GET sandbox"):
            asyncio.run(fetch(transport))
    finally:
        asyncio.run(transport.aclose())


def test_refuse_custom_transport_before_send():
    class NetworkCapable(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request):
            raise AssertionError("Network-capable custom transport executed")

    with pytest.raises(ValueError, match="GET sandbox"):
        asyncio.run(fetch(NetworkCapable()))


def test_refuse_mock_subclass_for_type_exactness():
    class SubclassedMock(httpx.MockTransport):
        pass

    t = SubclassedMock(lambda req: httpx.Response(200, json={"status": "pending"}))
    with pytest.raises(ValueError, match="GET sandbox"):
        asyncio.run(fetch(t))


def test_mock_get_remains_synthetic_and_unsettled():
    observed = []
    def response(request):
        observed.append((request.method, str(request.url)))
        return httpx.Response(200, json={
            "id": 900001,
            "collector_id": 2002,
            "external_reference": "tenant:test",
            "transaction_amount": "150.00",
            "currency_id": "BRL",
            "status": "approved",
            "live_mode": False,
        })
    result = asyncio.run(fetch(httpx.MockTransport(response)))
    assert result.finding == "APPROVED_SANDBOX_UNSETTLED"
    assert result.bank_reconciled is False
    assert result.payment_marked_paid is False
    assert result.ledger_written is False
    assert result.financial_closing_authorized is False
    assert result.payout_authorized is False
    assert observed == [("GET", "https://api.mercadopago.com/v1/payments/900001")]


def test_mock_rejects_wrong_seller_without_recognizing_payment():
    t = httpx.MockTransport(lambda req: httpx.Response(200, json={
        "id": 900001, "collector_id": 3003,
        "external_reference": "tenant:test",
        "transaction_amount": "150.00",
        "currency_id": "BRL", "status": "approved", "live_mode": False,
    }))
    result = asyncio.run(fetch(t))
    assert result.finding == "PROVIDER_FIELDS_MISMATCH"
    assert result.payment_marked_paid is False


def test_three_adapter_guards_present():
    gateway = GATEWAY.read_text(encoding="utf-8")
    pix = PIX.read_text(encoding="utf-8")
    oauth = OAUTH.read_text(encoding="utf-8")
    assert "type(transport) is not httpx.MockTransport" in gateway
    assert pix.count("type(transport) is not httpx.MockTransport") == 2
    assert "M40740_REDE_FINANCEIRA_REAL_BLOQUEADA" in pix
    assert "M40750_OAUTH_REAL_HTTPS_BLOCKED" in oauth


def test_ci_local_egress_disabled_and_documented_no_go():
    yaml = WORKFLOW.read_text(encoding="utf-8")
    doc = DOC.read_text(encoding="utf-8")
    for label in ("PIX_REAL: 'OFF'", "PAGAMENTOS_REAIS: 'OFF'",
                  "ATIVACAO_REAL: 'OFF'", "test_m40760_readonly_egress_ci.py"):
        assert label in yaml
    for forbidden in ("DATABASE_URL:", "pg_ctl", "kubectl", "ssh ",
                      "workflow_dispatch:"):
        assert forbidden not in yaml
    for marker in ("M40730", "M40740", "M40750", "GUC", "PRODUCTION=BLOCKED"):
        assert marker in doc
