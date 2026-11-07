"""M23000: reject unsafe callback URLs before allocating PKCE state."""
import pytest
from uuid import UUID
from app.mp_oauth_connect_preflight import prepare_oauth_draft, precheck_oauth_callback

TENANT=UUID("00000000-0000-4000-8000-0000000000a1")
ADMIN=UUID("00000000-0000-4000-8000-0000000000a9")

def new(uri):
    return prepare_oauth_draft(
        tenant_id=TENANT,initiated_by=ADMIN,client_id="123456",
        registered_redirect_uri=uri,now_epoch=1800000000)

@pytest.mark.parametrize("uri",[
    "https://localhost/callback",
    "https://localhost.local/callback",
    "https://merchant.internal/callback",
    "https://merchant.local/callback",
    "https://example/callback",
    "https://127.0.0.1/callback",
    "https://192.0.2.1/callback",
    "https://[2001:db8::1]/callback",
    "https://example.com:443/callback",
    "https://example.com:8443/callback",
    "https://-example.com/callback",
    "https://example-.com/callback",
    "https://app.example.com?state=1",
    "https://admin:secret@app.example.com/callback",
    "https://app.example.com/callback#state",
    "http://app.example.com/callback",
    "https://app.example.com",
    "https://app.example.com.\u002Fcallback",
])
def test_uri_rejected_at_draft_creation(uri):
    with pytest.raises(ValueError):
        new(uri)

def test_valid_public_sandbox_uri_keeps_pkce_unchanged():
    x=new("https://app.example.invalid/connect/callback")
    assert x.redirect_uri=="https://app.example.invalid/connect/callback"
    assert "code_verifier" not in x.authorization_url
    assert x.live_mode is False
    assert precheck_oauth_callback(
        draft=x,tenant_id=TENANT,initiated_by=ADMIN,
        provided_state=x.state,code="TG-M23000-CODE",
        redirect_uri=x.redirect_uri,now_epoch=1800000020,
        already_consumed=False)
