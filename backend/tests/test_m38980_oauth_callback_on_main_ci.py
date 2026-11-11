"""M38980: same FR Finance FastAPI OAuth callback never enables Pix or leaks tokens."""
from __future__ import annotations

from fastapi.testclient import TestClient
import pytest

from app.main import app
from app.routers.mercado_pago_oauth import OAuthCallbackBinding, OAuthCallbackReceipt

STATE = "A" * 44
CODE = "CI_SYNTHETIC_CODE"


@pytest.fixture(autouse=True)
def reset_binding():
    if hasattr(app.state, "mp_oauth_callback_runtime"):
        delattr(app.state, "mp_oauth_callback_runtime")
    yield
    if hasattr(app.state, "mp_oauth_callback_runtime"):
        delattr(app.state, "mp_oauth_callback_runtime")


def binding(complete=None, **kw):
    async def mock_complete(**kwargs):
        return OAuthCallbackReceipt(True, True, True, True, False)
    flags = {
        "original_database_verified": True,
        "durable_pkce_state_verified": True,
        "vault_store_verified": True,
        "seller_registry_verified": True,
        "callback_https_registered": True,
        "sandbox_only": True,
    }
    flags.update(kw)
    return OAuthCallbackBinding(complete=complete or mock_complete, **flags)


def test_only_one_callback_registered_on_original_fastapi():
    paths = [r.path for r in app.routes]
    assert paths.count("/api/v1/mercadopago/oauth/callback") == 1
    assert paths.count("/integrations/mercadopago/orders") == 1


def test_callback_requires_https_even_when_worker_not_configured():
    with TestClient(app, base_url="http://testserver") as c:
        result = c.get("/api/v1/mercadopago/oauth/callback",
                       params={"state":STATE, "code":CODE})
    assert result.status_code == 403


@pytest.mark.parametrize("params", [
    {"state": "short", "code": CODE},
    {"state": STATE, "code": "bad white space"},
    {"state": STATE},
    {"code": CODE},
    {"state": STATE, "code": CODE, "token": "SENSITIVE"},
])
def test_bad_or_extra_callback_params_rejected_without_token_exchange(params):
    with TestClient(app, base_url="https://testserver") as c:
        r = c.get("/api/v1/mercadopago/oauth/callback", params=params)
    assert r.status_code == 400


def test_replay_ambiguous_params_blocked():
    with TestClient(app, base_url="https://testserver") as c:
        r = c.get("/api/v1/mercadopago/oauth/callback",
                  params=[("state", STATE), ("state", STATE), ("code", CODE)])
    assert r.status_code == 400


def test_valid_callback_without_existing_binding_is_503():
    with TestClient(app, base_url="https://testserver") as c:
        r = c.get("/api/v1/mercadopago/oauth/callback",
                  params={"state":STATE, "code":CODE})
    assert r.status_code == 503
    assert STATE not in r.text
    assert CODE not in r.text


@pytest.mark.parametrize("flag", [
    "original_database_verified",
    "durable_pkce_state_verified",
    "vault_store_verified",
    "seller_registry_verified",
    "callback_https_registered",
])
def test_each_unattested_provider_gate_blocks_before_worker(flag):
    called = []
    async def complete(**kwargs):
        called.append(kwargs)
        return OAuthCallbackReceipt(True, True, True, True, False)
    app.state.mp_oauth_callback_runtime = binding(complete=complete, **{flag: False})
    with TestClient(app, base_url="https://testserver") as c:
        r = c.get("/api/v1/mercadopago/oauth/callback",
                  params={"state":STATE, "code":CODE})
    assert r.status_code == 503
    assert called == []


@pytest.mark.parametrize("bad", [
    OAuthCallbackReceipt(False, True, True, True, False),
    OAuthCallbackReceipt(True, False, True, True, False),
    OAuthCallbackReceipt(True, True, False, True, False),
    OAuthCallbackReceipt(True, True, True, False, False),
    OAuthCallbackReceipt(True, True, True, True, True),
    None, True,
])
def test_no_false_seller_link_or_money_if_callback_receipt_is_incomplete(bad):
    async def complete(**kwargs):
        return bad
    app.state.mp_oauth_callback_runtime = binding(complete=complete)
    with TestClient(app, base_url="https://testserver") as c:
        r = c.get("/api/v1/mercadopago/oauth/callback",
                  params={"state":STATE, "code":CODE})
    assert r.status_code == 503


def test_valid_synthetic_callback_only_claims_sandbox_connection():
    called = []
    async def complete(**kwargs):
        called.append(kwargs)
        return OAuthCallbackReceipt(True, True, True, True, False)
    app.state.mp_oauth_callback_runtime = binding(complete=complete)
    with TestClient(app, base_url="https://testserver") as c:
        r = c.get("/api/v1/mercadopago/oauth/callback",
                  params={"state":STATE, "code":CODE})
    assert r.status_code == 200
    assert called == [{"state": STATE, "authorization_code": CODE}]
    assert r.json() == {
        "status": "SANDBOX_CONNECT_CONFIRMED",
        "real_payments_enabled": False,
        "pix_inbound_enabled": False,
        "pix_outbound_enabled": False,
    }
    assert STATE not in r.text
    assert CODE not in r.text


def test_provider_exception_is_generic_without_access_token_leaks():
    async def complete(**kwargs):
        raise ValueError("SENSITIVE_CLIENT_SECRET")
    app.state.mp_oauth_callback_runtime = binding(complete=complete)
    with TestClient(app, base_url="https://testserver") as c:
        r = c.get("/api/v1/mercadopago/oauth/callback",
                  params={"state":STATE, "code":CODE})
    assert r.status_code == 503
    assert "SENSITIVE_CLIENT_SECRET" not in r.text
