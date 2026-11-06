"""M3000: isolated OCI ASGI staging server; mock OCI Vault and postgres."""
import base64
import hashlib
import hmac
import json
from contextlib import asynccontextmanager
from types import SimpleNamespace
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.main import app as termux_app
from app.oci_mp_staging_server import (
    CONTRACT, StagingServerBlocked, StagingServerConfig,
    create_staging_app, validate_staging_database_dsn,
)

DSN="postgresql://frcaixinha_mp_webhook_ingest:strong-ci-mock-password-123@" \
    "db-internal.example.invalid/frcaixinha_staging?sslmode=verify-full"
SECRET_ID="ocid1.secret.oc1.sa-saopaulo-1.dbsecretabcdefghijklmnop"
WEBHOOK_ID="ocid1.secret.oc1.sa-saopaulo-1.hmacsecretabcdefghijklm"
HMAC_SECRET="ci-webhook-secret-very-long-sandbox"
NOW=1800000000000
TENANT=UUID("00000000-0000-4000-8000-0000000000a1")


def config(**updates):
    values=dict(
        enabled=True,environment="homologation",region="sa-saopaulo-1",
        db_dsn_secret_ocid=SECRET_ID,server_mode="RECEIVE_ONLY",
        accept_live_notifications=False,
    )
    values.update(updates)
    return StagingServerConfig(**values)


class FakeOCI:
    def __init__(self):
        self.lookups=[]
    def get_secret_bundle(self,secret_ocid,stage):
        self.lookups.append((secret_ocid,stage))
        if secret_ocid == SECRET_ID:
            value=DSN
        elif secret_ocid == WEBHOOK_ID:
            value=HMAC_SECRET
        else:
            raise RuntimeError("invalid mock OCID")
        raw=base64.b64encode(value.encode()).decode()
        return SimpleNamespace(data=SimpleNamespace(
            secret_bundle_content=SimpleNamespace(content=raw,content_type="BASE64")
        ))


class FakeConn:
    def __init__(self):
        self.saved=[]
        self.rows=[]
    async def fetchval(self,sql,*args):
        if "current_database()" in sql:
            return True
        if "mp_staging_append_signed_webhook" in sql:
            self.saved.append(args)
            return "INSERTED"
        raise AssertionError("unrecognized query")
    async def fetchrow(self,sql,*args):
        if "mp_staging_resolve_seller" in sql and args == ("2002",):
            return {
                "tenant_id":TENANT,"seller_id":"2002",
                "webhook_secret_ocid":WEBHOOK_ID,
            }
        return None
    @asynccontextmanager
    async def transaction(self):
        yield self


class FakePool:
    def __init__(self):
        self.connection=FakeConn()
        self.closed=False
    @asynccontextmanager
    async def acquire(self):
        yield self.connection
    async def close(self):
        self.closed=True


def signed():
    envelope={
        "id":100001,"user_id":2002,"live_mode":False,
        "type":"payment","action":"payment.updated",
        "data":{"id":"900001"},
    }
    raw=json.dumps(envelope,separators=(",",":")).encode()
    msg=f"id:900001;request-id:ci-request-1;ts:{NOW};".encode()
    digest=hmac.new(HMAC_SECRET.encode(),msg,hashlib.sha256).hexdigest()
    return raw,f"ts={NOW},v1={digest}"


def test_disabled_server_does_not_register_webhook_or_call_oci():
    server=create_staging_app(StagingServerConfig())
    with TestClient(server) as c:
        d=c.get("/api/health/oci-staging").json()
        assert d["webhook_receiver_ready"] is False
        assert c.post("/integrations/mercadopago/webhook").status_code==404
    assert d["bank_reconciled"] is False


@pytest.mark.parametrize("changed",[
    {"enabled":False},{"environment":"production"},
    {"environment":"development"},{"server_mode":"LIVE_MONEY"},
    {"region":"invalid region"},{"db_dsn_secret_ocid":"bad"},
])
def test_staging_config_rejects_unsafe_runtime(changed):
    with pytest.raises(StagingServerBlocked):
        config(**changed).require_safe_receive_only()


@pytest.mark.parametrize("url",[
    "postgresql://root:password@db-internal.example.invalid/frcaixinha_staging?sslmode=verify-full",
    "postgresql://frcaixinha_mp_webhook_ingest:password@localhost/frcaixinha_staging?sslmode=verify-full",
    "postgresql://frcaixinha_mp_webhook_ingest:password@db-internal.example.invalid/other?sslmode=verify-full",
    "postgresql://frcaixinha_mp_webhook_ingest:password@db-internal.example.invalid/frcaixinha_staging?sslmode=disable",
    "postgresql://frcaixinha_mp_webhook_ingest:password@db-internal.example.invalid/frcaixinha_staging",
    "not-a-url",
])
def test_database_dsn_must_use_tls_and_dedicated_role(url):
    with pytest.raises(StagingServerBlocked):
        validate_staging_database_dsn(url)


def test_environment_contains_only_references_not_plaintext():
    vals=dict(
        FRC_MP_OCI_STAGING_ENABLED="1",ENVIRONMENT="homologation",
        OCI_REGION="sa-saopaulo-1",FRC_MP_STAGING_DB_SECRET_OCID=SECRET_ID,
        FRC_MP_STAGING_SERVER_MODE="RECEIVE_ONLY",
    )
    c=StagingServerConfig.from_environment(vals)
    assert c.db_dsn_secret_ocid==SECRET_ID
    assert "strong-ci-mock-password-123" not in repr(c)
    assert "redacted" in repr(c)


def test_server_can_boot_with_oci_vault_and_pg_mock_and_accept_signed_webhook():
    oci=FakeOCI()
    pool=FakePool()
    factories=[]
    def sdk(region):
        assert region=="sa-saopaulo-1"
        return oci
    async def pg(*,dsn,min_size,max_size,timeout):
        assert dsn==DSN
        assert (min_size,max_size,timeout)==(1,4,5)
        factories.append("pg")
        return pool
    stage=create_staging_app(config(),sdk_client_factory=sdk,
                             pool_factory=pg,clock_ms=lambda:NOW)
    with TestClient(stage,base_url="https://oci-stage.example.invalid") as client:
        health=client.get("/api/health/oci-staging").json()
        assert health["webhook_receiver_ready"] is True
        raw,signature=signed()
        response=client.post(
            "/integrations/mercadopago/webhook?type=payment&data.id=900001",
            content=raw,
            headers={"content-type":"application/json",
                     "x-request-id":"ci-request-1","x-signature":signature},
        )
        assert response.status_code==202,response.text
        assert response.json()["ledger_written"] is False
        assert len(pool.connection.saved)==1
    assert pool.closed is True
    assert factories==["pg"]
    assert oci.lookups==[(SECRET_ID,"CURRENT"),(WEBHOOK_ID,"CURRENT")]


def test_main_app_still_has_no_payment_webhook_or_oci_staging_connection():
    assert not any(r.path=="/integrations/mercadopago/webhook" for r in termux_app.routes)
    with TestClient(termux_app) as client:
        d=client.get("/api/health/features/m3000").json()
    assert d["contract"]==CONTRACT
    assert d["workstream"]=="AI_STUDIO"
    for key in (
        "oci_staging_deployed","webhook_receiver_registered_in_main",
        "mp_provider_connected","bank_reconciled",
        "ledger_written","real_payments_enabled",
    ):
        assert d[key] is False


@pytest.mark.parametrize("override",[
    {"accept_live_notifications":True},
    {"environment":"production","accept_live_notifications":True},
    {"server_mode":"LIVE_MONEY"},
])
def test_m22200_staging_rejects_live_even_if_requested(override):
    with pytest.raises(StagingServerBlocked):
        config(**override).require_safe_receive_only()


def test_m22200_disabled_staging_does_not_register_real_webhook():
    import os
    from app.oci_mp_staging_server import StagingServerConfig,create_staging_app
    with TestClient(create_staging_app(StagingServerConfig())) as client:
        assert client.post("/integrations/mercadopago/webhook",json={
            "live_mode":True,"type":"payment",
        }).status_code==404
        state=client.get("/api/health/oci-staging").json()
        assert state["real_payments_enabled"] is False
        assert state["bank_reconciled"] is False
