"""M22700: tenant OAuth sandbox response and callback security gates."""
from dataclasses import replace
from urllib.parse import parse_qs,urlsplit
from uuid import UUID
import httpx
import pytest

from app.mp_oauth_connect_preflight import prepare_oauth_draft,precheck_oauth_callback
from app.mp_connect_http_runtime import (
    OAuthConnectionBlocked,exchange_sandbox_authorization_code,
)
from test_m2800_oci_mp_connectors_ci import APP_SECRET,PAYLOAD

TENANT=UUID("00000000-0000-4000-8000-0000000000a1")
SECOND=UUID("00000000-0000-4000-8000-0000000000a2")
ADMIN=UUID("00000000-0000-4000-8000-0000000000a9")
SECOND_ADMIN=UUID("00000000-0000-4000-8000-0000000000a8")
NOW=1800000000

def draft(tenant=TENANT,admin=ADMIN):
    return prepare_oauth_draft(
        tenant_id=tenant,initiated_by=admin,
        client_id="123456",registered_redirect_uri="https://app.example.invalid/mp/callback",
        now_epoch=NOW,
    )

@pytest.mark.parametrize("scope",[
    "read","write","offline_access","read write",
    "write offline_access","read read offline_access",
    "read offline_access bogus","read  offline_access",
    "read\\noffline_access", "read offline_access offline_access",
])
@pytest.mark.asyncio
async def test_seller_oauth_refuses_incomplete_or_duplicate_scope(scope):
    d=draft()
    data={**PAYLOAD,"scope":scope}
    called=[]
    def handler(req):
        called.append(req)
        return httpx.Response(200,json=data)
    with pytest.raises(OAuthConnectionBlocked):
        await exchange_sandbox_authorization_code(
            draft=d,returned_state=d.state,code="TG-M22700-CODE",
            client_secret=APP_SECRET,expected_seller_id="2002",
            consumed_by_durable_store=True,
            transport=httpx.MockTransport(handler),
        )
    assert len(called)==1

@pytest.mark.asyncio
async def test_full_seller_scope_validates_without_enabling_payments():
    d=draft()
    result=await exchange_sandbox_authorization_code(
        draft=d,returned_state=d.state,code="TG-M22700-CODE",
        client_secret=APP_SECRET,expected_seller_id="2002",
        consumed_by_durable_store=True,
        transport=httpx.MockTransport(lambda _:httpx.Response(200,json={
            **PAYLOAD,"scope":"read write offline_access",
        })),
    )
    assert result.live_mode is False
    assert "offline_access" in result.scope
    assert "TEST_SANDBOX" not in repr(result)

def test_multi_tenant_pkce_state_and_actor_isolation():
    a,b=draft(),draft(SECOND,SECOND_ADMIN)
    assert a.state!=b.state
    assert a.code_verifier!=b.code_verifier
    assert "code_verifier" not in a.authorization_url
    assert "offline_access" not in a.authorization_url  # permissions in MP app config
    assert parse_qs(urlsplit(a.authorization_url).query)["code_challenge_method"]==["S256"]
    kw={"provided_state":a.state,"code":"TG-M22700-CODE","redirect_uri":a.redirect_uri,
        "now_epoch":NOW+5,"already_consumed":False}
    assert precheck_oauth_callback(draft=a,tenant_id=TENANT,initiated_by=ADMIN,**kw)
    assert not precheck_oauth_callback(draft=a,tenant_id=SECOND,initiated_by=ADMIN,**kw)
    assert not precheck_oauth_callback(draft=a,tenant_id=TENANT,initiated_by=SECOND_ADMIN,**kw)
    assert not precheck_oauth_callback(draft=b,tenant_id=SECOND,initiated_by=SECOND_ADMIN,**kw)
    assert not precheck_oauth_callback(draft=a,tenant_id=TENANT,initiated_by=ADMIN,
                                      **{**kw,"already_consumed":True})
    assert not precheck_oauth_callback(draft=a,tenant_id=TENANT,initiated_by=ADMIN,
                                      **{**kw,"now_epoch":NOW+601})

@pytest.mark.asyncio
@pytest.mark.parametrize("redirect",[
 "https://localhost/callback","https://127.0.0.1/callback",
 "https://merchant.internal/callback","https://merchant.local/callback",
 "https://site.example.invalid:8443/callback","https://a/callback",
])
async def test_crafted_draft_redirect_cannot_bypass_token_exchange(redirect):
    d=replace(draft(),redirect_uri=redirect)
    called=[]
    with pytest.raises(OAuthConnectionBlocked):
        await exchange_sandbox_authorization_code(
            draft=d,returned_state=d.state,code="TG-M22700-CODE",
            client_secret=APP_SECRET,expected_seller_id="2002",
            consumed_by_durable_store=True,
            transport=httpx.MockTransport(lambda r:(called.append(r),
                                         httpx.Response(200,json=PAYLOAD))[1]),
        )
    assert called==[]
