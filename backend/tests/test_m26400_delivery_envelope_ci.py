"""M26400: authentic AES-GCM confidential delivery envelopes; no network or DB."""
from dataclasses import replace
import base64
from uuid import uuid4

import pytest

from app.delivery_envelope import (
    DeliveryScope, DeliverySecret, SealedDelivery,
    EnvelopeBlocked, open_delivery, seal_delivery,
)

NOW = 1794000000
TOKEN = "A" * 48
KEY_ID = "ci-vault-test-key-2026"


class FakeKeyProvider:
    """Ephemeral fixture, not a runtime secret store."""
    def __init__(self, key=b"K" * 32):
        self.key = key
        self.calls = []
    def load_key(self, key_id):
        self.calls.append(key_id)
        assert key_id == KEY_ID
        return self.key


def fixture():
    scope = DeliveryScope(
        tenant_id=uuid4(), event_id=uuid4(), document_id=uuid4(),
        target_role="TENANT_MEMBER", purpose="INVITATION",
        issued_at=NOW, expires_at=NOW + 3600,
    )
    secret = DeliverySecret(recipient="synthetic@example.com", token=TOKEN)
    return scope, secret


def test_round_trip_random_nonces_and_no_plaintext_in_envelope():
    scope, secret = fixture()
    source = FakeKeyProvider()
    one = seal_delivery(scope=scope, secret=secret, key_id=KEY_ID, provider=source, now=NOW)
    two = seal_delivery(scope=scope, secret=secret, key_id=KEY_ID, provider=source, now=NOW)
    assert one.nonce_b64 != two.nonce_b64
    assert one.ciphertext_b64 != two.ciphertext_b64
    assert open_delivery(envelope=one, scope=scope, provider=source, now=NOW+2) == secret
    assert open_delivery(envelope=two, scope=scope, provider=source, now=NOW+2) == secret
    assert one.version == 1
    assert KEY_ID not in repr(one)
    assert secret.recipient not in repr(one)
    assert secret.recipient not in repr(secret)
    assert TOKEN not in repr(one)
    assert TOKEN not in one.ciphertext_b64
    assert secret.recipient not in one.ciphertext_b64
    assert source.calls == [KEY_ID]*4


@pytest.mark.parametrize("field,value", [
    ("tenant_id", uuid4()),
    ("event_id", uuid4()),
    ("document_id", uuid4()),
    ("target_role", "TENANT_ADMIN"),
    ("purpose", "PASSWORD_RESET"),
    ("issued_at", NOW - 10),
    ("expires_at", NOW + 4000),
])
def test_associated_data_fails_closed_if_context_changes(field,value):
    scope, secret = fixture()
    enc = seal_delivery(scope=scope, secret=secret, key_id=KEY_ID, provider=FakeKeyProvider(), now=NOW)
    with pytest.raises(EnvelopeBlocked):
        open_delivery(envelope=enc, scope=replace(scope, **{field:value}),
                      provider=FakeKeyProvider(), now=NOW+1)


@pytest.mark.parametrize("field,value", [
    ("nonce_b64", "invalid////"),
    ("nonce_b64", base64.urlsafe_b64encode(b"A"*11).decode()),
    ("ciphertext_b64", "a"*10000),
    ("ciphertext_b64", "bad////"),
    ("version", 2),
    ("key_id", "wrong-key-2026"),
])
def test_rejects_mutated_nonce_ciphertext_key_and_version(field,value):
    scope, secret = fixture()
    env = seal_delivery(scope=scope, secret=secret, key_id=KEY_ID, provider=FakeKeyProvider(), now=NOW)
    with pytest.raises(EnvelopeBlocked):
        open_delivery(envelope=replace(env, **{field:value}), scope=scope,
                      provider=FakeKeyProvider(), now=NOW+1)


def test_ciphertext_tag_tamper_rejected():
    scope, secret = fixture()
    envelope = seal_delivery(scope=scope, secret=secret, key_id=KEY_ID, provider=FakeKeyProvider(), now=NOW)
    raw = bytearray(base64.urlsafe_b64decode(envelope.ciphertext_b64))
    raw[-1] ^= 1
    mutated = replace(envelope,ciphertext_b64=base64.urlsafe_b64encode(raw).decode())
    with pytest.raises(EnvelopeBlocked):
        open_delivery(envelope=mutated,scope=scope,provider=FakeKeyProvider(),now=NOW+1)


def test_wrong_32_byte_key_rejected_and_short_key_never_allowed():
    scope, secret = fixture()
    env = seal_delivery(scope=scope, secret=secret, key_id=KEY_ID, provider=FakeKeyProvider(), now=NOW)
    with pytest.raises(EnvelopeBlocked):
        open_delivery(envelope=env,scope=scope,provider=FakeKeyProvider(b"Z"*32),now=NOW+1)
    with pytest.raises(EnvelopeBlocked):
        seal_delivery(scope=scope,secret=secret,key_id=KEY_ID,provider=FakeKeyProvider(b"x"*16),now=NOW)


@pytest.mark.parametrize("token", ["short", "", "contains spaces", "A"*257, "x\nBcc:evil"])
def test_weak_tokens_are_refused(token):
    scope, secret = fixture()
    with pytest.raises(EnvelopeBlocked):
        seal_delivery(scope=scope,secret=replace(secret,token=token),
                      key_id=KEY_ID,provider=FakeKeyProvider(),now=NOW)


@pytest.mark.parametrize("recipient", ["bad", "bad\nBcc:admin@evil.com", "", "bad person@example.com"])
def test_recipient_injection_is_refused(recipient):
    scope, secret = fixture()
    with pytest.raises(EnvelopeBlocked):
        seal_delivery(scope=scope,secret=replace(secret,recipient=recipient),
                      key_id=KEY_ID,provider=FakeKeyProvider(),now=NOW)


def test_expired_or_preissued_envelope_cannot_be_opened():
    scope, secret = fixture()
    env = seal_delivery(scope=scope,secret=secret,key_id=KEY_ID,provider=FakeKeyProvider(),now=NOW)
    for now in (NOW-1, scope.expires_at, scope.expires_at+1):
        with pytest.raises(EnvelopeBlocked):
            open_delivery(envelope=env,scope=scope,provider=FakeKeyProvider(),now=now)


def test_seal_requires_fresh_time_and_bounded_lifetime():
    scope, secret = fixture()
    for altered in (
        replace(scope,expires_at=NOW+86401),
        replace(scope,expires_at=NOW),
        replace(scope,document_id=None),
        replace(scope,target_role="MASTER"),
    ):
        with pytest.raises(EnvelopeBlocked):
            seal_delivery(scope=altered,secret=secret,key_id=KEY_ID,
                          provider=FakeKeyProvider(),now=NOW)
    with pytest.raises(EnvelopeBlocked):
        seal_delivery(scope=scope,secret=secret,key_id=KEY_ID,
                      provider=FakeKeyProvider(),now=NOW+60)


def test_kms_failure_never_logs_or_falls_back_to_default_key():
    class BrokenVault:
        def load_key(self,key_id):
            raise RuntimeError("internal-vault-password-must-not-leak")
    scope, secret = fixture()
    with pytest.raises(EnvelopeBlocked) as err:
        seal_delivery(scope=scope,secret=secret,key_id=KEY_ID,provider=BrokenVault(),now=NOW)
    assert "internal-vault" not in str(err.value)
    assert TOKEN not in str(err.value)
    assert "synthetic@example.com" not in str(err.value)


def test_no_route_imports_crypto_envelope_or_exposes_secrets():
    from pathlib import Path
    root=Path(__file__).resolve().parents[2]
    service=(root/"backend/app/delivery_envelope.py").read_text()
    assert "AESGCM(key).encrypt" in service
    assert "AESGCM(key).decrypt" in service
    assert "os.urandom(12)" in service
    assert "load_key(key_id)" in service
    assert "FR_FINANCE_MAIL_ENVELOPE_V1" in service
    assert "os.getenv(" not in service
    assert "INSERT INTO" not in service
    for path in ("invitations.py", "auth.py", "master.py"):
        assert "seal_delivery" not in (root/"backend/app/routers"/path).read_text()
