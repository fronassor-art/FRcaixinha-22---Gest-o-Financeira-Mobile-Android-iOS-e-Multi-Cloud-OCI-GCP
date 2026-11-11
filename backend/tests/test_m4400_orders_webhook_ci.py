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
