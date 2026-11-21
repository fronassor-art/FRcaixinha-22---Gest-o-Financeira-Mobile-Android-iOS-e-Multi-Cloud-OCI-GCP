"""M2900: signed FastAPI webhook router factory; staging route never mounted."""
import hashlib
import hmac
import json
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.main import app as production_app
from app.mp_webhook_staging_runtime import (
    SellerContext, SignedWebhookRecord, CONTRACT,
    create_webhook_staging_router, verify_webhook_for_seller,
)

T=UUID("00000000-0000-4000-8000-0000000000a1")
SECRET=b"CI_MOCK_MP_WEBHOOK_SIGNATURE_KEY_123456"
NOW=1800000000000
SELLER=SellerContext(T,"2002","ocid1.secret.oc1.sa-saopaulo-1.abcdefghijklmnop")


def event(**kw):
    d={
        "id":100001,"user_id":2002,"live_mode":False,
        "type":"payment","action":"payment.updated",
        "data":{"id":"900001"},
    }
    d.update(kw)
    return json.dumps(d,separators=(",",":")).encode()


def signature(data_id="900001",request="ci-request-1",timestamp=NOW):
    msg=f"id:{data_id};request-id:{request};ts:{timestamp};".encode()
    return f"ts={timestamp},v1={hmac.new(SECRET,msg,hashlib.sha256).hexdigest()}"


def validate(**change):
    args=dict(
        raw=event(),data_id="900001",query_type="payment",
        request_id="ci-request-1",signature=signature(),
        webhook_secret=SECRET,now_ms=NOW,seller=SELLER,
    )
    args.update(change)
    return verify_webhook_for_seller(**args)


def test_signed_event_is_not_payment_or_ledger():
    result=validate()
    assert result.tenant_id==T
    assert result.notification_id=="100001"
    assert result.resource_id=="900001"
    assert result.source=="SIGNED_WEBHOOK_UNSETTLED"
    assert not result.bank_reconciled
    assert not result.ledger_written
    assert not result.payment_marked_paid


@pytest.mark.parametrize("change",[
    {"raw":event(user_id=3003)},
    {"raw":event(data={"id":"900002"})},
    {"raw":event(type="mp-connect",action="payment.updated")},
    {"raw":event(live_mode=True)},
    {"raw":event(live_mode="false")},
    {"raw":event(action="transfer.completed")},
    {"data_id":"900002"},
    {"query_type":"mp-connect"},
    {"request_id":"replayed"},
    {"signature":"ts=1800000000000,v1="+"0"*64},
    {"now_ms":NOW+400000},
    {"webhook_secret":b"wrong-secret-123456789"},
    {"raw":b'{"id":1,"id":2,"user_id":2002,"data":{"id":"900001"}}'},
    {"raw":b""},
    {"raw":b"x"*16385},
    {"seller":SellerContext(T,"3003","oci_dummy")},
    {"seller":SellerContext(T,"2002","oci_dummy",False)},
])
def test_spoofing_mismatch_replay_or_invalid_payload_rejected(change):
    with pytest.raises(ValueError):
        validate(**change)


def test_live_event_can_be_recorded_without_financial_effect_if_explicitly_enabled():
    result=validate(raw=event(live_mode=True),allow_live_ingest=True)
    assert result.live_mode is True
    assert not result.bank_reconciled and not result.ledger_written


def make_client(store_result="INSERTED"):
    calls=[]
    async def resolve(seller_id):
        calls.append(("resolve",seller_id))
        return SELLER
    async def secret(_seller):
        calls.append(("secret",None))
        return SECRET
    async def persist(rec):
        assert type(rec) is SignedWebhookRecord
        calls.append(("persist",rec.notification_id))
        return store_result
    api=FastAPI()
    api.include_router(create_webhook_staging_router(
        resolve_seller=resolve,load_signing_secret=secret,
        persist_verified=persist,now_ms=lambda:NOW,
    ))
    return TestClient(api,base_url="https://stage.example.invalid"),calls


def send(client,**kw):
    args=dict(
        url="/integrations/mercadopago/webhook?type=payment&data.id=900001",
        data=event(),
        headers={
            "content-type":"application/json",
            "x-request-id":"ci-request-1",
            "x-signature":signature(),
        },
    )
    args.update(kw)
    return client.post(args["url"],content=args["data"],headers=args["headers"])


def test_https_endpoint_records_durable_inbox_only():
    client,calls=make_client()
    with client:
        response=send(client)
    assert response.status_code==202
    assert response.json()=={
        "receipt":"INSERTED",
        "financial_effect_applied":False,
        "bank_reconciled":False,
        "ledger_written":False,
    }
    assert calls==[("resolve","2002"),("secret",None),("persist","100001")]


def test_same_signed_event_replay_is_acknowledged():
    client,calls=make_client("REPLAY")
    with client:
        response=send(client)
    assert response.status_code==200
    assert response.json()["receipt"]=="REPLAY"


@pytest.mark.parametrize("change,expected",[
    ({"url":"/integrations/mercadopago/webhook?type=payment"},400),
    ({"url":"/integrations/mercadopago/webhook?type=payment&data.id=900001&data.id=900001"},400),
    ({"data":b"x"*16385},413),
    ({"headers":{"content-type":"text/plain"}},415),
    ({"headers":{"content-type":"application/json","x-request-id":"ci-request-1",
                "x-signature":"wrong"}},401),
])
def test_endpoint_fails_closed(change,expected):
    client,calls=make_client()
    with client:
        response=send(client,**change)
    assert response.status_code==expected
    assert ("persist","100001") not in calls


def test_runtime_main_does_not_mount_staging_route():
    assert not any(r.path=="/integrations/mercadopago/webhook"
                   for r in production_app.routes)
    with TestClient(production_app) as client:
        d=client.get("/api/health/features/m2900").json()
    assert d["contract"]==CONTRACT
    assert d["workstream"]=="AI_STUDIO"
    assert d["webhook_staging_router_factory"] is True
    assert d["staging_migration_applied"] is False
    assert d["real_webhooks_active"] is False
    assert d["bank_reconciled"] is False
    assert d["ledger_written"] is False


def test_staging_sql_has_strict_database_guard():
    from pathlib import Path
    sql=(Path(__file__).resolve().parents[1]/
         "staging_migrations/034_mp_signed_webhook_staging_only.sql").read_text()
    assert "frcaixinha_staging" in sql
    assert "frcaixinha.mp_staging_authorized" in sql
    assert "mp_signed_webhook_inbox_staging" in sql
    assert "SECURITY DEFINER" in sql
    assert "ledger_written=false" in sql
    assert "bank_reconciled=false" in sql
    assert "FROM PUBLIC" in sql
