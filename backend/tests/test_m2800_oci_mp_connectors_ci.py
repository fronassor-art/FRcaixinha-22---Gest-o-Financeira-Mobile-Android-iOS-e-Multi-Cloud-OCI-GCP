"""M2800 tests: OAuth HTTP mock and injected OCI SDK fake; never real network."""
import base64
import json
from types import SimpleNamespace
from uuid import UUID

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.oci_secret_bridge import (
    CONTRACT, SecretValue, VaultUnavailable,
    build_instance_principal_secrets_client, get_current_secret,
)
from app.mp_oauth_connect_preflight import prepare_oauth_draft
from app.mp_connect_http_runtime import (
    OAuthConnectionBlocked, exchange_sandbox_authorization_code,
    refresh_sandbox_seller_token,
)

TENANT=UUID("00000000-0000-4000-8000-0000000000a1")
ACTOR=UUID("00000000-0000-4000-8000-0000000000a9")
SECRET_ID="ocid1.secret.oc1.sa-saopaulo-1.abcdefghijklmnopqrstuvwxyz"
APP_SECRET="TEST-SERVER-SECRET-NOT-REAL-2026"
PAYLOAD={
    "access_token":"TEST_SANDBOX_ACCESS_TOKEN_123456",
    "refresh_token":"TEST_SANDBOX_REFRESH_TOKEN_123456",
    "token_type":"bearer",
    "expires_in":15552000,
    "scope":"read offline_access",
    "user_id":2002,
    "live_mode":False,
}


def draft():
    return prepare_oauth_draft(
        tenant_id=TENANT,initiated_by=ACTOR,client_id="123456",
        registered_redirect_uri="https://app.example.invalid/connect/callback",
        now_epoch=1800000000,
    )


def secret_response(value):
    encoded=base64.b64encode(value.encode()).decode()
    return SimpleNamespace(data=SimpleNamespace(
        secret_bundle_content=SimpleNamespace(content=encoded,content_type="BASE64"),
    ))


class FakeOCI:
    def __init__(self,value="secret-unittest"):
        self.value=value
        self.calls=[]
    def get_secret_bundle(self,id,stage):
        self.calls.append((id,stage))
        return secret_response(self.value)


def test_oci_get_current_secret_strips_no_secrets_into_repr():
    client=FakeOCI("CI-MOCK-APP-SECRET")
    result=get_current_secret(secret_ocid=SECRET_ID,client=client)
    assert client.calls==[(SECRET_ID,"CURRENT")]
    assert result.secret=="CI-MOCK-APP-SECRET"
    assert "CI-MOCK-APP-SECRET" not in repr(result)
    assert "redacted" in repr(result)


@pytest.mark.parametrize("id",[
    "", "ocid1.user.oc1.test", "../../tmp/private",
    "ocid1.secret.short", " ocid1.secret.oc1.sa-saopaulo-1.abcde ",
])
def test_bad_oci_ocids_rejected_before_call(id):
    f=FakeOCI()
    with pytest.raises(VaultUnavailable):
        get_current_secret(secret_ocid=id,client=f)
    assert not f.calls


@pytest.mark.parametrize("value",["", "\x00secret","💥"*9000])
def test_invalid_secret_values_fail_closed(value):
    with pytest.raises(VaultUnavailable):
        get_current_secret(secret_ocid=SECRET_ID,client=FakeOCI(value))


def test_oci_real_client_opt_in_not_enabled():
    with pytest.raises(VaultUnavailable):
        build_instance_principal_secrets_client(region="sa-saopaulo-1")
    with pytest.raises(VaultUnavailable):
        build_instance_principal_secrets_client(region="wrong region",enabled=True)


def authorized_handler(req):
    assert req.method=="POST"
    assert str(req.url)=="https://api.mercadopago.com/oauth/token"
    assert req.headers["content-type"]=="application/json"
    b=json.loads(req.content)
    assert b["client_id"]=="123456"
    assert b["client_secret"]==APP_SECRET
    assert b["test_token"]=="true"
    assert b["grant_type"] in ("authorization_code","refresh_token")
    if b["grant_type"]=="authorization_code":
        assert b["code_verifier"]
        assert b["redirect_uri"]=="https://app.example.invalid/connect/callback"
    return httpx.Response(200,json=PAYLOAD)


async def exchange(**kw):
    d=kw.pop("draft",draft())
    return await exchange_sandbox_authorization_code(
        draft=d,returned_state=kw.pop("returned_state",d.state),
        code=kw.pop("code","TG-CI-AUTH-CODE-123"),
        client_secret=kw.pop("client_secret",APP_SECRET),
        expected_seller_id=kw.pop("expected_seller_id","2002"),
        consumed_by_durable_store=kw.pop("consumed_by_durable_store",True),
        transport=kw.pop("transport",httpx.MockTransport(authorized_handler)),
        **kw,
    )


@pytest.mark.asyncio
async def test_real_oauth_request_builder_and_sandbox_token_parsing():
    result=await exchange()
    assert result.seller_id=="2002"
    assert result.live_mode is False
    assert result.access_token==PAYLOAD["access_token"]
    assert PAYLOAD["access_token"] not in repr(result)
    assert PAYLOAD["refresh_token"] not in str(result)


@pytest.mark.asyncio
@pytest.mark.parametrize("change",[
    {"consumed_by_durable_store":False},
    {"returned_state":"some-wrong-state"},
    {"expected_seller_id":"invalid"},
    {"client_secret":"short"},
    {"code":"code with spaces"},
    {"transport":object()},
])
async def test_oauth_rejects_bad_inputs(change):
    with pytest.raises(OAuthConnectionBlocked):
        await exchange(**change)


@pytest.mark.asyncio
async def test_real_network_disabled_by_default():
    with pytest.raises(OAuthConnectionBlocked):
        await exchange(transport=None)


@pytest.mark.asyncio
@pytest.mark.parametrize("change",[
    {"user_id":3003}, {"live_mode":True},
    {"token_type":"Bearer"}, {"expires_in":0},
    {"expires_in":15552001},
    {"scope":""}, {"refresh_token":"short"},
])
async def test_untrusted_oauth_token_response_rejected(change):
    data={**PAYLOAD,**change}
    with pytest.raises(OAuthConnectionBlocked):
        await exchange(transport=httpx.MockTransport(
            lambda req:httpx.Response(200,json=data)))


@pytest.mark.asyncio
@pytest.mark.parametrize("content",[
    b"{bad json", b'{"user_id":2002,"user_id":3003}',
    b"[]" , b'{"live_mode":NaN}', b"x"*32769,
])
async def test_invalid_or_oversized_oauth_response_rejected(content):
    with pytest.raises(OAuthConnectionBlocked):
        await exchange(transport=httpx.MockTransport(
            lambda req:httpx.Response(200,content=content)))


@pytest.mark.asyncio
@pytest.mark.parametrize("status",[301,302,400,401,429,500])
async def test_oauth_error_status_never_returns_sensitive_data(status):
    with pytest.raises(OAuthConnectionBlocked) as error:
        await exchange(transport=httpx.MockTransport(
            lambda req:httpx.Response(status,content=APP_SECRET.encode())))
    assert APP_SECRET not in str(error.value)


@pytest.mark.asyncio
async def test_refresh_token_and_no_automatic_payment():
    result=await refresh_sandbox_seller_token(
        client_id="123456",client_secret=APP_SECRET,expected_seller_id="2002",
        refresh_token="TEST_REFRESHTOKEN_FOR_MOCK_2026",
        seller_binding_confirmed=True,
        transport=httpx.MockTransport(authorized_handler),
    )
    assert result.seller_id=="2002"
    assert result.live_mode is False
    assert result.access_token==PAYLOAD["access_token"]
    with pytest.raises(OAuthConnectionBlocked):
        await refresh_sandbox_seller_token(
            client_id="123456",client_secret=APP_SECRET,expected_seller_id="2002",
            refresh_token="TEST_REFRESHTOKEN_FOR_MOCK_2026",
            seller_binding_confirmed=False,
            transport=httpx.MockTransport(authorized_handler),
        )


def test_m2800_contract_is_dormant():
    with TestClient(app) as c:
        response=c.get("/api/health/features/m2800")
    assert response.status_code==200
    d=response.json()
    assert d["contract"]==CONTRACT
    assert d["workstream"]=="AI_STUDIO"
    assert d["oci_sdk_adapter_in_code"] is True
    assert d["mp_oauth_https_adapter_in_code"] is True
    for key in (
        "oci_staging_deployed","oci_vault_connected","mp_app_registered",
        "mp_oauth_exchange_active","webhook_receiver_registered",
        "bank_reconciled","ledger_written","financial_closing_authorized",
        "real_payments_enabled"):
        assert d[key] is False
