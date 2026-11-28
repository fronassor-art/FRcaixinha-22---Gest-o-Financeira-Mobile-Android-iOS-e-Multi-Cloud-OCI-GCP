"""M40750: OAuth token POST is mock-only, irrespective of approval flags.

CI tests use synthetic tokens; never access Mercado Pago or any local DB.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

import httpx
import pytest

from app.mp_connect_http_runtime import (
    OAuthConnectionBlocked,
    _send_token_post,
)

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "backend/app/mp_connect_http_runtime.py"
PIX_SOURCE = ROOT / "backend/app/mp_pix_execution.py"
WORKFLOW = ROOT / ".github/workflows/frfinance-m40750-oauth-egress-no-go-ci.yml"
DOC = ROOT / "docs/FR_FINANCE_M40750_OAUTH_REAL_NETWORK_NO_GO.md"
BODY = {"client_id": "123456", "grant_type": "authorization_code", "test_token": "true"}
VALID = {
    "user_id": 2002,
    "live_mode": False,
    "token_type": "bearer",
    "expires_in": 900,
    "scope": "read offline_access",
    "access_token": "SYNTHETIC_OAUTH_ACCESS_2026",
    "refresh_token": "SYNTHETIC_OAUTH_REFRESH_2026",
}


def run(transport, approved=False):
    return asyncio.run(_send_token_post(
        body=BODY, seller_id="2002", transport=transport,
        real_https_authorized=approved,
    ))


@pytest.mark.parametrize("approved", [False, True])
def test_default_transport_denied_even_if_live_flag_true(approved):
    with pytest.raises(OAuthConnectionBlocked, match="M40750_OAUTH_REAL_HTTPS_BLOCKED"):
        run(None, approved)


@pytest.mark.parametrize("approved", [False, True])
def test_real_http_transport_denied_without_send(approved):
    transport = httpx.AsyncHTTPTransport()
    try:
        with pytest.raises(OAuthConnectionBlocked, match="M40750_OAUTH_REAL_HTTPS_BLOCKED"):
            run(transport, approved)
    finally:
        asyncio.run(transport.aclose())


def test_custom_transport_denied_without_egress():
    class ExternalCapable(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request):
            raise AssertionError("External transport unexpectedly invoked")

    with pytest.raises(OAuthConnectionBlocked):
        run(ExternalCapable(), True)


def test_mock_transport_subclass_denied():
    class SubclassedMock(httpx.MockTransport):
        pass
    transport = SubclassedMock(lambda request: httpx.Response(200, json=VALID))
    with pytest.raises(OAuthConnectionBlocked):
        run(transport, True)


def test_untyped_or_nontransport_denied():
    with pytest.raises(OAuthConnectionBlocked):
        run(object(), True)


@pytest.mark.parametrize("approved", [False, True])
def test_exact_mock_preserves_sandbox_oauth_parsing(approved):
    seen = []
    def handler(request):
        seen.append((request.method, str(request.url), request.headers.get("content-type")))
        return httpx.Response(200, json=VALID)
    token = run(httpx.MockTransport(handler), approved)
    assert token.seller_id == "2002"
    assert token.live_mode is False
    assert token.scope == "read offline_access"
    assert "SYNTHETIC_OAUTH_ACCESS" not in repr(token)
    assert seen == [("POST", "https://api.mercadopago.com/oauth/token", "application/json")]


def test_mock_rejects_wrong_account():
    def handler(request):
        return httpx.Response(200, json={**VALID, "user_id": 3003})
    with pytest.raises(OAuthConnectionBlocked):
        run(httpx.MockTransport(handler), True)


def test_source_guard_and_pix_guard_are_both_present():
    oauth = SOURCE.read_text(encoding="utf-8")
    pix = PIX_SOURCE.read_text(encoding="utf-8")
    assert 'type(transport) is not httpx.MockTransport' in oauth
    assert "M40750_OAUTH_REAL_HTTPS_BLOCKED" in oauth
    assert "if transport is None and real_https_authorized is not True" not in oauth
    assert "M40740_REDE_FINANCEIRA_REAL_BLOQUEADA" in pix
    assert pix.count("type(transport) is not httpx.MockTransport") == 2


def test_workflow_and_document_keep_production_blocked():
    yaml = WORKFLOW.read_text(encoding="utf-8")
    document = DOC.read_text(encoding="utf-8")
    for marker in (
        "PIX_REAL: 'OFF'", "PAGAMENTOS_REAIS: 'OFF'",
        "ATIVACAO_REAL: 'OFF'", "permissions:", "contents: read",
        "test_m40750_oauth_egress_no_go_ci.py",
    ):
        assert marker in yaml
    for forbidden in ("DATABASE_URL:", "postgres:18", "pg_ctl", "kubectl", "ssh ",
                      "workflow_dispatch:"):
        assert forbidden not in yaml
    for marker in ("M40730", "M40740", "GUC", "NO-GO", "PRODUCTION=BLOCKED"):
        assert marker in document
