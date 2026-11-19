"""M40740: no real provider network from the Pix adapter until explicit source review.

Pure offline AST execution: never import app/start service, connect DB or perform real HTTP.
"""
from __future__ import annotations

import ast
import asyncio
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[2]
ADAPTER = ROOT / "backend/app/mp_pix_execution.py"
WORKFLOW = ROOT / ".github/workflows/frfinance-m40740-pix-network-no-go-ci.yml"
DOC = ROOT / "docs/FR_FINANCE_M40740_PIX_REAL_NETWORK_NO_GO.md"


class ProviderRequestBlocked(RuntimeError):
    pass


class ProviderOutcomeUnknown(ProviderRequestBlocked):
    pass


def isolated_functions():
    """Execute ONLY two selected functions, without app imports or network."""
    code = ADAPTER.read_text(encoding="utf-8")
    tree = ast.parse(code)
    nodes = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
             and n.name in {"_client", "_send"}]
    assert {n.name for n in nodes} == {"_client", "_send"}
    scope = {"httpx": httpx, "ProviderRequestBlocked": ProviderRequestBlocked,
             "ProviderOutcomeUnknown": ProviderOutcomeUnknown}
    exec(compile(ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])),
                 str(ADAPTER), "exec"), scope)
    return code, scope


def request():
    return httpx.Request("POST", "https://api.mercadopago.com/v1/payments")


@pytest.mark.parametrize("approved", [False, True])
def test_no_default_live_network_even_when_previously_approved(approved):
    _, f = isolated_functions()
    with pytest.raises(ProviderRequestBlocked):
        asyncio.run(f["_send"](request(), transport=None, approved_network=approved))
    with pytest.raises(ProviderRequestBlocked):
        f["_client"](None)


def test_refuses_real_httpx_transport_before_sending():
    _, f = isolated_functions()
    transport = httpx.AsyncHTTPTransport()
    try:
        with pytest.raises(ProviderRequestBlocked):
            asyncio.run(f["_send"](request(), transport=transport, approved_network=True))
        with pytest.raises(ProviderRequestBlocked):
            f["_client"](transport)
    finally:
        asyncio.run(transport.aclose())


def test_refuses_custom_transport_before_any_egress():
    class NetworkCapable(httpx.AsyncBaseTransport):
        async def handle_async_request(self, req):
            raise AssertionError("Unexpected egress attempted")
    _, f = isolated_functions()
    with pytest.raises(ProviderRequestBlocked):
        asyncio.run(f["_send"](request(), transport=NetworkCapable(), approved_network=True))
    with pytest.raises(ProviderRequestBlocked):
        f["_client"](NetworkCapable())


def test_refuses_mock_subclass_with_overridden_network_behavior():
    class CustomMock(httpx.MockTransport):
        pass
    _, f = isolated_functions()
    transport = CustomMock(lambda req: httpx.Response(200))
    with pytest.raises(ProviderRequestBlocked):
        asyncio.run(f["_send"](request(), transport=transport, approved_network=True))


@pytest.mark.parametrize("approved", [False, True])
def test_exact_mock_transport_still_works_without_network(approved):
    _, f = isolated_functions()
    calls = []
    def handler(req):
        calls.append((req.method, req.url.host))
        return httpx.Response(202, json={"status": "synthetic"})
    response = asyncio.run(f["_send"](
        request(), transport=httpx.MockTransport(handler), approved_network=approved
    ))
    assert response.status_code == 202
    assert response.json() == {"status": "synthetic"}
    assert calls == [("POST", "api.mercadopago.com")]


def test_wrong_domain_remains_blocked_even_with_mock():
    _, f = isolated_functions()
    mock = httpx.MockTransport(lambda req: httpx.Response(200))
    bad = httpx.Request("POST", "https://example.com/v1/payments")
    with pytest.raises(ProviderRequestBlocked):
        asyncio.run(f["_send"](bad, transport=mock, approved_network=True))


def test_both_adapter_entry_points_are_locked_in_source():
    source, _ = isolated_functions()
    assert 'type(transport) is not httpx.MockTransport' in source
    assert source.count("type(transport) is not httpx.MockTransport") == 2
    assert "M40740_REDE_FINANCEIRA_REAL_BLOQUEADA" in source
    assert "def _client(transport):" in source
    assert "async def _send(" in source


def test_ci_is_offline_and_cannot_start_services():
    yaml = WORKFLOW.read_text(encoding="utf-8")
    doc = DOC.read_text(encoding="utf-8")
    for marker in ("PIX_REAL: 'OFF'", "PAGAMENTOS_REAIS: 'OFF'",
                   "ATIVACAO_REAL: 'OFF'", "pytest",
                   "test_m40740_pix_network_no_go_ci.py"):
        assert marker in yaml
    for marker in ("ssh ", "pg_ctl", "kubectl", "psql ",
                   "workflow_dispatch:", "DATABASE_URL:"):
        assert marker not in yaml
    for marker in ("M40730", "GUC", "NO-GO", "PRODUCTION=BLOCKED"):
        assert marker in doc
