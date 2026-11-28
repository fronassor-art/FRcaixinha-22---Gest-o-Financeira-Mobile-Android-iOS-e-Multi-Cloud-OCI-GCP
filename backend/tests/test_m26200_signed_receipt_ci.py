"""M26200 — unsigned/duplicate/late/forged CI mail receipts never become proof."""
from dataclasses import FrozenInstanceError
import json
from uuid import uuid4

import pytest

from app.synthetic_mail_receipt import (
    ReceiptVerificationBlocked, VerifiedSyntheticReceipt,
    receipt_signature, verify_synthetic_mail_receipt,
)

SECRET = b"ci-only-hmac-test-secret-32bytes-long-never-production"
NOW = 1_799_000_000


def fixture(*, kind="CI_SMTP_ACCEPTED", when=NOW, event=None, invitation=None):
    obj = {
        "event_id": str(event or uuid4()),
        "invitation_event_id": str(invitation or uuid4()),
        "kind": kind,
        "occurred_at": when,
    }
    body = json.dumps(obj, separators=(",", ":"), ensure_ascii=False).encode()
    return body, receipt_signature(SECRET, NOW, body), str(NOW)


def verify(body, sig, stamp, *, key=SECRET, now=NOW):
    return verify_synthetic_mail_receipt(
        body=body, signature=sig, timestamp=stamp, secret=key, now=now,
    )


@pytest.mark.parametrize("kind", ["CI_SMTP_ACCEPTED", "CI_BOUNCE"])
def test_exact_hmac_receipt_is_authenticated_only_in_ci(kind):
    body, sig, stamp = fixture(kind=kind)
    result = verify(body, sig, stamp)
    assert isinstance(result, VerifiedSyntheticReceipt)
    assert result.kind == kind
    assert result.signature_authenticated_in_ci is True
    assert result.provider_delivery_confirmed is False
    assert result.recipient_verified is False
    assert result.consent_recorded is False
    assert result.user_activated is False
    assert len(result.body_sha256) == 64
    for secret in (SECRET.decode(), sig, body.decode()):
        assert secret not in repr(result)
    with pytest.raises(FrozenInstanceError):
        result.recipient_verified = True


@pytest.mark.parametrize("mutate", [
    lambda body, sig, stamp: (body + b" ", sig, stamp),
    lambda body, sig, stamp: (body.replace(b"CI_SMTP_ACCEPTED", b"CI_BOUNCE"), sig, stamp),
    lambda body, sig, stamp: (body, sig[:-1] + ("0" if sig[-1] != "0" else "1"), stamp),
    lambda body, sig, stamp: (body, sig.upper(), stamp),
    lambda body, sig, stamp: (body, sig, stamp + "\n"),
    lambda body, sig, stamp: (body, sig, str(int(stamp) + 1)),
])
def test_tampering_signature_headers_or_body_is_blocked(mutate):
    body, sig, stamp = fixture()
    with pytest.raises(ReceiptVerificationBlocked):
        verify(*mutate(body, sig, stamp))


@pytest.mark.parametrize("time_offset", [-301, 301, -600, 600])
def test_clock_replay_window_rejects_old_and_future_events(time_offset):
    body, sig, stamp = fixture()
    with pytest.raises(ReceiptVerificationBlocked):
        verify(body, sig, stamp, now=NOW+time_offset)


@pytest.mark.parametrize("bad", [
    b'{"event_id":"duplicate","event_id":"duplicate","invitation_event_id":"X","kind":"CI_BOUNCE","occurred_at":1799000000}',
    b'{"event_id":"X","invitation_event_id":"Y","kind":"DELIVERED","occurred_at":1799000000}',
    b'{"event_id":"X","invitation_event_id":"Y","kind":[],"occurred_at":1799000000}',
    b'{"event_id":"X","invitation_event_id":"Y","kind":"CI_BOUNCE","occurred_at":1.799e9}',
    b'{"event_id":"X","invitation_event_id":"Y","kind":"CI_BOUNCE","occurred_at":1799000000,"email":"secret@example.com"}',
    b'[]', b'null', b'\xff', b'{',
])
def test_signed_but_invalid_shape_is_blocked(bad):
    signature = receipt_signature(SECRET, NOW, bad)
    with pytest.raises(ReceiptVerificationBlocked):
        verify(bad, signature, str(NOW))


@pytest.mark.parametrize("invalid", [None, True, "", "xyz", [], {}, 123])
def test_invalid_kind_never_escapes_with_unhandled_typeerror(invalid):
    obj = {
        "event_id": str(uuid4()), "invitation_event_id": str(uuid4()),
        "kind": invalid, "occurred_at": NOW,
    }
    body = json.dumps(obj).encode()
    with pytest.raises(ReceiptVerificationBlocked):
        verify(body, receipt_signature(SECRET, NOW, body), str(NOW))


@pytest.mark.parametrize("invalid", ["CI_MAIL_DELIVERED", "SMTP_ACCEPTED", "CI_SMTP_ACCEPTED "])
def test_no_real_provider_delivery_claim_allowed(invalid):
    body, sig, stamp = fixture(kind=invalid)
    with pytest.raises(ReceiptVerificationBlocked):
        verify(body, sig, stamp)


def test_signed_receipt_must_bind_uuid_and_current_timestamp():
    body, _, stamp = fixture(when=NOW-301)
    with pytest.raises(ReceiptVerificationBlocked):
        verify(body, receipt_signature(SECRET, NOW, body), stamp)
    body = json.dumps({
        "event_id": str(uuid4()).upper(),
        "invitation_event_id": str(uuid4()),
        "kind": "CI_SMTP_ACCEPTED", "occurred_at": NOW,
    }).encode()
    with pytest.raises(ReceiptVerificationBlocked):
        verify(body, receipt_signature(SECRET, NOW, body), stamp)


def test_signed_but_empty_or_huge_body_fails_closed():
    for raw in (b"", b"A"*2049):
        with pytest.raises(ReceiptVerificationBlocked):
            verify(raw, "0"*64, str(NOW))


def test_unsigned_or_short_secret_rejected_even_with_synthetic_data():
    body, sig, stamp = fixture()
    for weak in (b"x", b"x"*31, "", None):
        with pytest.raises(ReceiptVerificationBlocked):
            verify(body, sig, stamp, key=weak)


def test_invalid_receipt_error_never_contains_secrets_or_sensitive_body():
    body, _, stamp = fixture()
    with pytest.raises(ReceiptVerificationBlocked) as err:
        verify(body, "a"*64, stamp)
    for value in (SECRET.decode(), body.decode(), str(uuid4())):
        assert value not in str(err.value)


def test_no_public_endpoint_or_network_used_by_ci_verifier():
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    service = (root/"backend/app/synthetic_mail_receipt.py").read_text()
    routes = (root/"backend/app/routers/invitations.py").read_text()
    auth = (root/"backend/app/routers/auth.py").read_text()
    assert "hmac.compare_digest" in service
    assert "object_pairs_hook=_unique_pairs" in service
    assert "SMTP(" not in service and "requests." not in service
    assert "verify_synthetic_mail_receipt" not in routes
    assert "verify_synthetic_mail_receipt" not in auth
    assert "SELECT " not in service and "UPDATE " not in service
