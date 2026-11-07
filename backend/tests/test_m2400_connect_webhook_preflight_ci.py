"""M2400: bordas OAuth PKCE/seller e webhook puras, sem internet."""
import hashlib
import hmac
import json
from dataclasses import replace
from urllib.parse import parse_qs, urlsplit
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.mp_oauth_connect_preflight import (
    CONTRACT, prepare_oauth_draft, precheck_oauth_callback,
    review_seller_token_metadata,
)
from app.mp_webhook_envelope_preflight import preview_signed_sandbox_webhook

T = UUID("00000000-0000-4000-8000-0000000000a1")
OTHER = UUID("00000000-0000-4000-8000-0000000000b1")
ACTOR = UUID("00000000-0000-4000-8000-0000000000a9")
NOW = 1800000000
NOW_MS = NOW * 1000
SECRET = b"ci-only-m2400-webhook-secret-abcde"
REDIRECT = "https://app.example.invalid/connect/callback"


def draft():
    return prepare_oauth_draft(tenant_id=T, initiated_by=ACTOR, client_id="123456",
                               registered_redirect_uri=REDIRECT, now_epoch=NOW)


def callback(d, **kw):
    args = dict(
        draft=d, tenant_id=T, initiated_by=ACTOR, provided_state=d.state,
        code="TG-Test-Code-123", redirect_uri=REDIRECT, now_epoch=NOW+20,
        already_consumed=False,
    )
    args.update(kw)
    return precheck_oauth_callback(**args)


def test_oauth_generates_pkce_and_no_secret_in_repr():
    d = draft()
    assert len(d.state) >= 32
    assert 43 <= len(d.code_verifier) <= 128
    assert "OAuthDraft(redacted=True" in repr(d)
    url = urlsplit(d.authorization_url)
    assert url.scheme == "https"
    assert url.hostname == "auth.mercadopago.com"
    query = parse_qs(url.query)
    assert query["state"] == [d.state]
    assert query["client_id"] == ["123456"]
    assert query["redirect_uri"] == [REDIRECT]
    assert query["code_challenge_method"] == ["S256"]
    assert query["code_challenge"] == [d.pkce_challenge]
    assert d.state != draft().state
    assert callback(d) is True


@pytest.mark.parametrize("args", [
    {"tenant_id": OTHER}, {"initiated_by": OTHER},
    {"provided_state": "invalid"},
    {"code": ""}, {"code": "a"*513}, {"code": "a;b"},
    {"now_epoch": NOW-1}, {"now_epoch": NOW+601},
    {"already_consumed": True},
    {"redirect_uri": "https://attacker.invalid/callback"},
    {"now_epoch": True},
])
def test_oauth_callbacks_fail_closed(args):
    assert callback(draft(), **args) is False


@pytest.mark.parametrize("uri", [
    "http://example.com/callback",
    "https://localhost/callback",
    "https://127.0.0.1/callback",
    "https://user:password@example.com/callback",
    "https://example.com/callback?tenant=1",
    "https://example.com/callback#x",
    "file:///tmp/x",
    "https://example.com:8443/callback",
    "",
])
def test_oauth_redirect_is_static_https(uri):
    with pytest.raises(ValueError):
        prepare_oauth_draft(tenant_id=T, initiated_by=ACTOR, client_id="123",
                            registered_redirect_uri=uri, now_epoch=NOW)


def test_seller_metadata_cannot_activate_provider_or_bank():
    payload = {"user_id": 2002, "live_mode": False, "token_type": "bearer",
               "expires_in": 15552000, "access_token": "dummy-never-saved"}
    r = review_seller_token_metadata(
        tenant_id=T, expected_seller_id="2002", token_metadata=payload)
    assert r.sandbox_metadata_consistent
    assert r.provider_connected is False
    assert r.payment_authorized is False
    assert r.bank_reconciled is False
    assert "dummy-never-saved" not in repr(r)


@pytest.mark.parametrize("changes", [
    {"user_id": 3003}, {"user_id": "2003"},
    {"live_mode": True}, {"live_mode": "false"},
    {"token_type": "Bearer"}, {"expires_in": 0},
    {"expires_in": 15552001}, {"expires_in": 1.0},
])
def test_seller_metadata_rejects_mismatch(changes):
    payload = {"user_id": 2002, "live_mode": False,
               "token_type": "bearer", "expires_in": 1000}
    payload.update(changes)
    assert not review_seller_token_metadata(
        tenant_id=T, expected_seller_id="2002",
        token_metadata=payload).sandbox_metadata_consistent


def envelope(**change):
    value = {"id": 123, "user_id": 2002, "live_mode": False,
             "type": "payment", "action": "payment.updated",
             "data": {"id": "90001"}}
    value.update(change)
    return json.dumps(value, separators=(",", ":")).encode()


def signed(id="90001", req="request-abc", ts=NOW_MS, secret=SECRET):
    manifest = f"id:{id};request-id:{req};ts:{ts};".encode()
    return f"ts={ts},v1={hmac.new(secret, manifest, hashlib.sha256).hexdigest()}"


def preview(**kw):
    args = dict(raw_json=envelope(), signed_query_data_id="90001",
                x_request_id="request-abc", x_signature=signed(),
                secret=SECRET, now_ms=NOW_MS, tenant_id=T,
                expected_seller_id="2002")
    args.update(kw)
    return preview_signed_sandbox_webhook(**args)


def test_sandbox_notification_has_no_financial_effect():
    result = preview()
    assert result.notification_id == "123"
    assert result.signature_valid is True
    assert result.requires_durable_dedupe is True
    assert result.provider_get_authenticated is False
    assert result.paid is False
    assert result.bank_reconciled is False
    assert result.ledger_written is False
    assert result.real_payments_enabled is False


@pytest.mark.parametrize("raw", [
    envelope(user_id=3003),
    envelope(user_id=2002, live_mode=True),
    envelope(action="refund.issued"),
    envelope(type="mp-connect", action="payment.updated"),
    envelope(type="payment", action="application.authorized"),
    envelope(data={"id": "90002"}),
    envelope(id=True),
    envelope(live_mode="false"),
    b'{"id":1,"id":2,"user_id":2002,"live_mode":false,"type":"payment","action":"payment.updated","data":{"id":"90001"}}',
    b'null', b'', b'{invalid', b'\xff', b'{}',
])
def test_webhook_invalid_payloads_fail_closed(raw):
    with pytest.raises(ValueError):
        preview(raw_json=raw)


@pytest.mark.parametrize("override", [
    {"signed_query_data_id": "90002"},
    {"x_request_id": "other"},
    {"x_signature": "ts=1800000000000,v1=" + "0"*64},
    {"secret": b"wrong-secret-ci-only-xxxxxxx"},
    {"now_ms": NOW_MS + 400000},
    {"expected_seller_id": "3003"},
    {"tenant_id": "not-uuid"},
])
def test_webhook_signature_identity_timing_fail_closed(override):
    with pytest.raises(ValueError):
        preview(**override)


def test_mp_connect_event_still_requires_verified_get_and_replay_protection():
    raw = envelope(type="mp-connect", action="application.authorized")
    preview_result = preview(raw_json=raw)
    assert preview_result.event_type == "mp-connect"
    assert preview_result.requires_durable_dedupe
    assert not preview_result.provider_get_authenticated


def test_health_does_not_expose_secret_or_register_webhook():
    with TestClient(app) as client:
        response = client.get("/api/health/features/m2400")
        assert response.status_code == 200
        body = response.json()
        assert body["contract"] == CONTRACT
        assert body["workstream"] == "AI_STUDIO"
        assert body["oauth_exchange_active"] is False
        assert body["webhook_receiver_registered"] is False
        assert body["bank_reconciled"] is False
        assert body["real_payments_enabled"] is False
        assert body["ledger_written"] is False
        assert not any("/webhook" in route.path for route in app.routes
                       if route.path.startswith("/api/v1/"))
