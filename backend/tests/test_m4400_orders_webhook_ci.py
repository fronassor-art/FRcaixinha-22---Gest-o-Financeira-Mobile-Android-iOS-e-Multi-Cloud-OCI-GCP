"""M4400 Orders webhook HMAC, tenant isolation, duplicate events, route."""
from datetime import datetime,timezone
import hashlib
import hmac
import json
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.main import app as main_app
from app.mp_orders_webhook import (
    CONTRACT,SignedOrderEvent,verify_order_notification,
    create_orders_staging_router,
)
from app.mp_webhook_staging_runtime import SellerContext

ORD="ORD01HRYFWNYRE1MR1E60MW3X0T2P"
T=UUID("00000000-0000-4000-8000-0000000000a1")
SECRET=b"sandbox_key_for_orders_webhook_123456"
NOW=1_800_000_000_000
REQ="00000000-0000-4000-8000-0000000000a3"


def event_body(**kw):
    data={
        "type":"order","api_version":"v1","action":"order.processed",
        "user_id":"2002","live_mode":False,
        "data":{"id":ORD,"status":"processed"},
    }
    data.update(kw)
    return data


def signature(data_id=ORD,request_id=REQ,ts=NOW):
    manifest=f"id:{data_id};request-id:{request_id};ts:{ts};"
    digest=hmac.new(SECRET,manifest.encode(),hashlib.sha256).hexdigest()
    return f"ts={ts},v1={digest}"


def verify(raw=None,**kwargs):
    values=dict(raw=json.dumps(event_body()).encode(),
        data_id=ORD,query_type="order",request_id=REQ,
        signature=signature(),webhook_secret=SECRET,now_ms=NOW,
        account=SellerContext(T,"2002","ocid1.secret.oc1.test12345678"),
    )
    if raw is not None:values["raw"]=raw
    values.update(kwargs)
    return verify_order_notification(**values)


def test_order_hmac_authenticates_but_never_reconciles_bank():
    record=verify()
    assert record.order_id==ORD
    assert record.provider_account_id=="2002"
    assert record.event_id.startswith("N_")
    assert record.action=="order.processed"
    assert record.observed_status=="processed"
    assert not record.bank_reconciled
    assert not record.payment_marked_paid
    assert not record.ledger_written
    assert CONTRACT=="AI_STUDIO_M4400_SIGNED_ORDERS_WEBHOOK_INBOX_V1"


@pytest.mark.parametrize("changes",[
    {"data_id":"ORD01ANOTHERORDER000000000000"},
    {"query_type":"payment"},
    {"request_id":"mismatch"},
    {"signature":"ts=1800000000000,v1="+"0"*64},
    {"webhook_secret":b"wrong-key-not-the-merchant-secret"},
    {"now_ms":NOW+600_000},
    {"account":SellerContext(T,"9999","ocid1.secret.oc1.test12345678")},
    {"allow_live_ingest":False},
])
def test_invalid_signature_or_account_denied(changes):
    if changes=={"allow_live_ingest":False}:
        values=dict(changes)
        values["raw"]=json.dumps(event_body(live_mode=True)).encode()
    else:values=changes
    with pytest.raises(ValueError):
        verify(**values)


def test_body_order_id_mismatch_or_repeated_keys_denied():
    for raw in (
        json.dumps(event_body(data={"id":"ORD01ANOTHERORDER000000000000","status":"processed"})).encode(),
        b'{"type":"order","type":"order","data":{"id":"'+ORD.encode()+b'"}}',
    ):
        with pytest.raises(ValueError):
            verify(raw=raw)


def test_ascii_lowercase_signed_manifest_accepted_but_only_matching_order():
    record=verify(signature=signature(data_id=ORD.lower()))
    assert record.order_id==ORD


def test_order_route_mounted_on_original_fastapi_but_inert_without_binding():
    paths = [r.path for r in main_app.routes]
    assert paths.count("/integrations/mercadopago/orders") == 1
    # The real HTTP route uses the existing HMAC validator, but has no
    # approved seller/Vault/inbox worker on the developer's Termux.
    if hasattr(main_app.state, "mp_orders_ingress_runtime"):
        delattr(main_app.state, "mp_orders_ingress_runtime")
    with TestClient(main_app, base_url="https://testserver") as client:
        response = client.post(
            "/integrations/mercadopago/orders",
            params={"data.id":ORD, "type":"order"},
            headers={"x-signature":signature(), "x-request-id":REQ,
                     "content-type":"application/json"},
            json=event_body(),
        )
    assert response.status_code == 503
    assert "Orders webhook verifier unavailable" in response.json()["detail"]


def test_signed_router_persists_once_and_replays_without_money():
    saved={}
    async def resolve(seller_id):
        return SellerContext(T,seller_id,"ocid1.secret.oc1.test12345678")
    async def secret(_account):
        return SECRET
    async def persist(event):
        previous=saved.get(event.event_id)
        if previous:
            assert previous==event
            return "REPLAY"
        saved[event.event_id]=event
        return "INSERTED"

    app=FastAPI()
    app.include_router(create_orders_staging_router(
        resolve_account=resolve,load_signing_secret=secret,
        persist_event=persist,now_ms=lambda:NOW,
    ))
    with TestClient(app,base_url="https://testserver") as client:
        req={"params":{"data.id":ORD,"type":"order"},
             "headers":{"x-signature":signature(),
                        "x-request-id":REQ,
                        "content-type":"application/json"},
             "json":event_body()}
        a=client.post("/integrations/mercadopago/orders",**req)
        b=client.post("/integrations/mercadopago/orders",**req)
        assert a.status_code==200 and b.status_code==200
        assert a.json()["receipt"]=="INSERTED"
        assert b.json()["receipt"]=="REPLAY"
        assert not b.json()["bank_reconciled"]
        assert not b.json()["ledger_written"]
        assert len(saved)==1
        forged=client.post("/integrations/mercadopago/orders",
            params={"data.id":ORD,"type":"order"},
            headers={"x-signature":"ts=1800000000000,v1="+"0"*64,
                     "x-request-id":REQ,"content-type":"application/json"},
            json=event_body())
        assert forged.status_code==401
        over=client.post("/integrations/mercadopago/orders",
            params={"data.id":ORD,"type":"order"},
            headers={"x-signature":signature(),"x-request-id":REQ,
                     "content-type":"application/json"},
            content=b"x"*17000)
        assert over.status_code==413


# M40955 — malformed envelope and wrong account never reach financial effects.
@pytest.mark.parametrize("raw", [
    json.dumps(event_body(action=[])).encode(),
    json.dumps(event_body(data={"id":ORD,"status":{}})).encode(),
    json.dumps(event_body()).encode("utf-16"),
    b'{"data":'+b'['*1500+b'0'+b']'*1500+b'}',
])
def test_m40955_orders_malformed_envelope(raw):
    with pytest.raises(ValueError):
        verify(raw=raw)

@pytest.mark.parametrize("seller", [
    SellerContext(T,"9999","test-secret"),
    SellerContext(T,"2002","test-secret",False),
    SellerContext(T,"2002","test-secret",1),
])
def test_m40955_orders_account_mismatch_before_secret(seller):
    calls=[]
    async def resolve(seller_id):
        calls.append("resolve")
        return seller
    async def forbidden(*_):
        calls.append("unexpected")
        raise AssertionError("Secret or inbox access forbidden")
    api=FastAPI()
    api.include_router(create_orders_staging_router(
        resolve_account=resolve,load_signing_secret=forbidden,
        persist_event=forbidden,now_ms=lambda:NOW))
    with TestClient(api,base_url="https://testserver") as client:
        result=client.post("/integrations/mercadopago/orders",
            params={"data.id":ORD,"type":"order"},
            headers={"x-signature":signature(),"x-request-id":REQ},
            json=event_body())
    assert result.status_code==401
    assert calls==["resolve"]


# M40956 — integrated, in-process synthetic ingress and release NO-GO.
# Existing CI executes this suite. No new service, database, provider or route
# in the deployed app. Callbacks are deliberately memory-only.
@pytest.mark.parametrize("kind", ["payment", "mp-connect", "order"])
@pytest.mark.parametrize("failure", [
    "none", "unknown_account", "wrong_account", "registry_unavailable",
    "secret_unavailable", "invalid_signature", "inbox_unavailable",
    "unexpected_receipt", "live_disabled",
])
def test_m40956_integrated_ingress_fail_closed(kind, failure):
    from app.mp_webhook_staging_runtime import create_webhook_staging_router

    other = UUID("00000000-0000-4000-8000-0000000000b2")
    accounts = {
        "2002": SellerContext(T, "2002", "synthetic-a"),
        "3003": SellerContext(other, "3003", "synthetic-b"),
    }
    keys = {"2002": SECRET, "3003": b"synthetic_distinct_tenant_key_123456"}
    calls, records = [], []

    async def resolve(seller_id):
        calls.append(("resolve", seller_id))
        if failure == "registry_unavailable":
            raise RuntimeError("synthetic failure")
        if failure == "unknown_account":
            return None
        if failure == "wrong_account":
            return accounts["2002"]
        return accounts[seller_id]

    async def secret(account):
        calls.append(("secret", account.seller_id))
        if failure == "secret_unavailable":
            raise RuntimeError("synthetic failure")
        return keys[account.seller_id]

    async def persist(record):
        calls.append(("inbox", record.tenant_id))
        if failure == "inbox_unavailable":
            raise RuntimeError("synthetic failure")
        if failure == "unexpected_receipt":
            return "PAID"
        records.append(record)
        return "INSERTED"

    api = FastAPI()
    api.include_router(create_webhook_staging_router(
        resolve_seller=resolve, load_signing_secret=secret,
        persist_verified=persist, now_ms=lambda: NOW))
    api.include_router(create_orders_staging_router(
        resolve_account=resolve, load_signing_secret=secret,
        persist_event=persist, now_ms=lambda: NOW))

    resource = ORD if kind == "order" else "900001"
    endpoint = "/integrations/mercadopago/" + (
        "orders" if kind == "order" else "webhook")
    body = (event_body(user_id="3003") if kind == "order" else {
        "id": 100001, "user_id": 3003, "live_mode": False, "type": kind,
        "action": ("payment.updated" if kind == "payment"
                   else "application.authorized"),
        "data": {"id": resource},
    })
    body["live_mode"] = failure == "live_disabled"
    signed_key = SECRET if failure == "invalid_signature" else keys["3003"]
    digest = hmac.new(
        signed_key, f"id:{resource};request-id:{REQ};ts:{NOW};".encode(),
        hashlib.sha256).hexdigest()
    with TestClient(api, base_url="https://testserver") as client:
        response = client.post(
            endpoint, params={"type": kind, "data.id": resource},
            headers={"x-request-id": REQ, "x-signature": f"ts={NOW},v1={digest}"},
            json=body)

    if failure == "none":
        assert response.status_code == (200 if kind == "order" else 202)
        assert response.json()["receipt"] == "INSERTED"
        for field in ("financial_effect_applied", "bank_reconciled", "ledger_written"):
            assert response.json()[field] is False
        assert len(records) == 1
        record = records[0]
        assert record.tenant_id == other
        assert record.tenant_id != T
        assert record.bank_reconciled is False
        assert record.payment_marked_paid is False
        assert record.ledger_written is False
        assert calls == [("resolve", "3003"), ("secret", "3003"), ("inbox", other)]
    else:
        expected = 503 if failure in {
            "registry_unavailable", "secret_unavailable", "inbox_unavailable",
            "unexpected_receipt",
        } else 401
        assert response.status_code == expected
        assert records == []
        assert calls[0] == ("resolve", "3003")
        if failure in {"unknown_account", "wrong_account", "registry_unavailable"}:
            assert calls == [("resolve", "3003")]
        elif failure in {"secret_unavailable", "invalid_signature", "live_disabled"}:
            assert calls == [("resolve", "3003"), ("secret", "3003")]
        else:
            assert calls == [("resolve", "3003"), ("secret", "3003"), ("inbox", other)]
        assert "synthetic" not in response.text
        assert "receipt" not in response.json()


def test_m40956_integrated_source_evidence_cannot_release_production():
    from scripts.frfinance_m40939_release_gate import MANIFEST, validate
    from app.launch_readiness import readiness_manifest

    gate = validate(json.loads(MANIFEST.read_text(encoding="utf-8")))
    assert gate["M40939_DECISION"] == "NO_GO"
    assert gate["M40939_PRODUCTION_GATES"] == 20
    assert gate["M40939_PRODUCTION"] == "BLOCKED"
    assert gate["M40939_MIGRATION"] == "NOT_AUTHORIZED"
    for flag in ("PIX_REAL", "PAGAMENTOS_REAIS", "ATIVACAO_REAL"):
        assert gate["M40939_" + flag] == "OFF"

    report = readiness_manifest({})
    assert report["status"] == "BLOCKED"
    assert report["total_gates"] == report["unverified_gates"] == 20
    assert all(r["production_verified"] is False for r in report["requirements"])
    assert report["real_pix_active"] is False
    assert report["financial_closing_authorized"] is False
    assert report["writes_performed"] is False
    assert report["sql_trust"]["status"] == "NO_GO"
    assert report["sql_trust"]["master_write_operations_enabled"] is False
