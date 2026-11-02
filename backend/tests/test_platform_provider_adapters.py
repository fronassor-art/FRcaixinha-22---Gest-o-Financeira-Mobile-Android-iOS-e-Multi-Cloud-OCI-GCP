"""Provedores reais: testes só com SMTP fake e HTTPX MockTransport; nunca rede."""
import asyncio
from datetime import datetime,timezone
import hashlib
import hmac
import json

import httpx
import pytest

from app.platform_provider_adapters import (
 InviteMailConfig,PlatformMpConfig,ProviderUnavailable,
 invitation_delivery_ready,platform_saas_ready,send_invitation_email,
 create_platform_pix,fetch_authoritative_saas_payment,verify_saas_webhook,
 confirm_authoritative_approved_payment,read_configuration_status
)
from app.mercado_pago_adapter import PixCollectionRequest
from app.mercado_pago_safety import ExpectedPayment


@pytest.fixture
def gates(monkeypatch):
    for name in ("AI_STUDIO_REAL_INVITES","AI_STUDIO_REAL_SAAS",
                 "AI_STUDIO_LEGAL_CLEARANCE","AI_STUDIO_OPERATIONAL_REVIEW"):
        monkeypatch.setenv(name,"APPROVED")


def test_provider_gates_off_by_default(monkeypatch):
    for name in ("AI_STUDIO_REAL_INVITES","AI_STUDIO_REAL_SAAS",
                 "AI_STUDIO_LEGAL_CLEARANCE","AI_STUDIO_OPERATIONAL_REVIEW"):
        monkeypatch.delenv(name,raising=False)
    mail=InviteMailConfig("smtp.example.org",587,"ci","secret",
                          "invites@example.org","https://app.example.org")
    mp=PlatformMpConfig("fake-test-token","12345","s"*25,False)
    assert not invitation_delivery_ready(mail)
    assert not platform_saas_ready(mp)
    with pytest.raises(ProviderUnavailable):
        send_invitation_email(config=mail,recipient="member@example.org",
                              token="a"*43,invitation_id="123e4567-e89b-12d3-a456-426614174000",
                              smtp_factory=lambda *a,**k:None)
    assert read_configuration_status()["saas_platform_payment"]=="BLOCKED_BY_GOVERNANCE"


def test_invite_delivery_uses_smtp_auth_and_https_link_without_fake_success(gates):
    class FakeSmtp:
        last=None
        def __init__(self,host,port,timeout):
            assert host=="smtp.example.org" and port==587 and timeout==10
            self.messages=[]
            FakeSmtp.last=self
        def __enter__(self):return self
        def __exit__(self,*args):return False
        def starttls(self,context):assert context
        def login(self,user,password):assert (user,password)==("ci","secret")
        def send_message(self,message):
            self.messages.append(message)
            return {}
    mail=InviteMailConfig("smtp.example.org",587,"ci","secret",
                          "invites@example.org","https://app.example.org")
    send_invitation_email(
        config=mail,recipient="member@example.org",
        token="A"*43,invitation_id="123e4567-e89b-12d3-a456-426614174000",
        smtp_factory=FakeSmtp,
    )
    message=FakeSmtp.last.messages[0]
    body=message.get_content()
    assert "https://app.example.org/accept-invitation" in body
    assert "token="+"A"*43 in body
    assert "secret" not in body
    assert message["To"]=="member@example.org"
    with pytest.raises(ProviderUnavailable):
        send_invitation_email(config=InviteMailConfig("smtp.example.org",587,"ci","secret",
                     "invites@example.org","http://app.example.org"),
                     recipient="member@example.org",token="A"*43,
                     invitation_id="123e4567-e89b-12d3-a456-426614174000",
                     smtp_factory=FakeSmtp)


@pytest.mark.asyncio
async def test_checkout_and_authoritative_get_use_platform_account_only(gates):
    history=[]
    def provider(req):
        history.append(req)
        assert req.headers["Authorization"]=="Bearer TEST-CI-PLATFORM"
        if req.method=="POST":
            assert req.url.path=="/v1/payments"
            assert req.headers["X-Idempotency-Key"]=="ci-idem-007"
            assert json.loads(req.content)["external_reference"]=="saas:ci007"
            return httpx.Response(201,json={
                "id": "456789","status":"pending","transaction_amount":"89.90",
                "collector_id":"12345","external_reference":"saas:ci007",
                "currency_id":"BRL","live_mode":False,
                "point_of_interaction":{"transaction_data":{"qr_code":"pix-synthetic"}},
            })
        assert req.url.path=="/v1/payments/456789"
        return httpx.Response(200,json={
            "id":"456789","status":"approved","transaction_amount":"89.90",
            "collector_id":"12345","external_reference":"saas:ci007",
            "currency_id":"BRL","live_mode":False,
        })
    config=PlatformMpConfig("TEST-CI-PLATFORM","12345","S"*25,False)
    async with httpx.AsyncClient(transport=httpx.MockTransport(provider)) as client:
        created=await create_platform_pix(
            config=config,
            intent=PixCollectionRequest("saas:ci007",8990,"payer@example.com",
                                        "Licença SaaS teste","ci-idem-007"),
            client=client,
        )
        assert created.provider_payment_id=="456789"
        assert created.status=="pending"
        paid=await fetch_authoritative_saas_payment(
            config=config,payment_id="456789",client=client,
        )
        assert confirm_authoritative_approved_payment(
            expected=ExpectedPayment("456789","12345","saas:ci007",8990,False),
            provider_response=paid,
        )
    assert [r.method for r in history]==["POST","GET"]
    assert not confirm_authoritative_approved_payment(
        expected=ExpectedPayment("456789","12345","saas:ci007",8991,False),
        provider_response=paid,
    )


def test_verified_webhook_needs_fresh_ts_and_correct_hmac(gates):
    config=PlatformMpConfig("TEST-CI-PLATFORM","12345","top-secret-key-long-enough",False)
    now=datetime(2026,11,1,22,0,tzinfo=timezone.utc)
    ts=str(int(now.timestamp()))
    manifest=f"id:456789;request-id:req-ci-01;ts:{ts};"
    signature="ts="+ts+",v1="+hmac.new(config.webhook_secret.encode(),
                         manifest.encode(),hashlib.sha256).hexdigest()
    assert verify_saas_webhook(config=config,signature=signature,
                               request_id="req-ci-01",payment_id="456789",now=now)
    assert not verify_saas_webhook(config=config,signature=signature,
                                   request_id="req-ci-02",payment_id="456789",now=now)
    assert not verify_saas_webhook(config=config,signature=signature,
                                   request_id="req-ci-01",payment_id="456789",
                                   now=datetime(2026,11,2,22,0,tzinfo=timezone.utc))
