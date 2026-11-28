"""M3300: streaming limit, duplicate signed headers and account role naming."""
import hashlib
import hmac
import json
from uuid import UUID

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from app.main import app as termux_app
from app.mp_webhook_staging_runtime import (
    MAX_BODY, SignedWebhookRecord, SellerContext, create_webhook_staging_router,
)

TENANT=UUID("00000000-0000-4000-8000-0000000000a1")
SECRET=b"CI_2026_WEBHOOK_HMAC_M3300_SECRET_123456"
TS=1800000000000


def fixture():
    body={
        "id":100001,"user_id":2002,"live_mode":False,
        "type":"payment","action":"payment.updated",
        "data":{"id":"900001"},
    }
    content=json.dumps(body,separators=(",",":")).encode()
    message=f"id:900001;request-id:ci-request-1;ts:{TS};".encode()
    digest=hmac.new(SECRET,message,hashlib.sha256).hexdigest()
    return content,f"ts={TS},v1={digest}"


def make_app():
    calls=[]
    async def lookup(identifier):
        calls.append("resolve")
        return SellerContext(TENANT,"2002","ocid1.secret.oc1.mocksecretreference")
    async def secret(record):
        calls.append("vault")
        return SECRET
    async def save(record):
        assert type(record) is SignedWebhookRecord
        calls.append("persist")
        return "INSERTED"
    api=FastAPI()
    api.include_router(create_webhook_staging_router(
        resolve_seller=lookup,load_signing_secret=secret,
        persist_verified=save,now_ms=lambda:TS,
    ))
    return api,calls


def headers(signature):
    return {
        "content-type":"application/json",
        "x-request-id":"ci-request-1",
        "x-signature":signature,
    }


def url():
    return "/integrations/mercadopago/webhook?type=payment&data.id=900001"


def test_signed_valid_small_body_still_persisted_without_payment():
    api,calls=make_app()
    body,sig=fixture()
    with TestClient(api,base_url="https://ci-staging.example.invalid") as client:
        r=client.post(url(),content=body,headers=headers(sig))
    assert r.status_code==202
    assert calls==["resolve","vault","persist"]
    assert r.json()["financial_effect_applied"] is False


def test_chunked_stream_over_limit_is_refused_before_secret_or_db():
    api,calls=make_app()
    body,sig=fixture()
    def streaming_body():
        yield b"x"*10000
        yield b"x"*10000
    with TestClient(api,base_url="https://ci-staging.example.invalid") as client:
        r=client.post(url(),content=streaming_body(),headers=headers(sig))
    assert r.status_code==413
    assert "vault" not in calls
    assert "persist" not in calls


@pytest.mark.parametrize("name",["x-signature","x-request-id"])
def test_duplicate_signed_headers_rejected_before_resolving_account(name):
    api,calls=make_app()
    body,sig=fixture()
    raw=list(headers(sig).items())
    raw.append((name,dict(headers(sig))[name]))
    with TestClient(api,base_url="https://ci-staging.example.invalid") as client:
        r=client.post(url(),content=body,headers=raw)
    assert r.status_code==400
    assert calls==[]


def test_forged_forwarded_https_does_not_bypass_actual_asgi_scheme():
    api,calls=make_app()
    body,sig=fixture()
    hs=headers(sig)
    hs["x-forwarded-proto"]="https"
    with TestClient(api,base_url="http://ci-staging.example.invalid") as client:
        r=client.post(url(),content=body,headers=hs)
    assert r.status_code==415
    assert calls==[]


def test_provider_account_id_alias_is_not_new_role():
    record=SellerContext(TENANT,"2002","ocid1.secret.oc1.mocksecretreference")
    assert record.provider_account_id=="2002"
    assert record.seller_id=="2002"
    assert record.active is True


def test_termux_main_still_does_not_register_real_webhook():
    assert not any(
        r.path=="/integrations/mercadopago/webhook"
        for r in termux_app.routes
    )
    with TestClient(termux_app) as client:
        d=client.get("/api/health/features/m3300").json()
    assert d["workstream"]=="AI_STUDIO"
    assert d["contract"]=="AI_STUDIO_M3300_MP_WEBHOOK_INGRESS_HARDENING_V1"
    assert d["staging_router_not_mounted_locally"] is True
    assert d["real_webhooks_active"] is False
    assert d["real_payments_enabled"] is False
