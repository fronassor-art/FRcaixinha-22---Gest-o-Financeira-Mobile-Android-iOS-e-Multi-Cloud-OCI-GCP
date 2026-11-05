"""M17000: adversarial signed CI events, never real authorizations."""
from datetime import datetime, timedelta, timezone
import hmac
from hashlib import sha256
import json
from uuid import UUID

import pytest
from app.notification_origin_attestation import (
    CONTRACT, DOMAIN, verify_synthetic_origin,
)
from app.pix_automation_contract import FinancialOperationBlocked

NOW = datetime(2026, 11, 5, 12, 0, 0, tzinfo=timezone.utc)
SECRET = b"CI-ONLY-notification-HMAC-check-very-long-2026-11"
T = "ffffffff-0000-4000-8000-000000000011"
U = "ffffffff-0000-4000-8000-000000000001"
E = "eeeeeeee-0000-4000-8000-000000000001"


def sample():
    return {
        "event_id": E, "event_kind": "CONTRIBUTION_DUE_INFO",
        "tenant_id": T, "recipient_id": U, "role": "TENANT_MEMBER",
        "cycle_year": 2027, "occurred_at": "2026-11-05T12:00:00Z",
        "source_digest": "a"*64,
    }


def sign(data, secret=SECRET):
    blob = json.dumps(data, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")
    return hmac.new(secret, DOMAIN + blob, sha256).hexdigest()


_ABSENT = object()


def check(data=None, signature=_ABSENT, secret=SECRET, now=NOW):
    candidate = sample() if data is None else data
    signature = sign(candidate, SECRET) if signature is _ABSENT else signature
    return verify_synthetic_origin(candidate, signature, secret, now=now)


def test_valid_signature_is_only_synthetic_evidence():
    p = check()
    assert CONTRACT == "AI_STUDIO_M17000_NOTIFICATION_ORIGIN_SIGNED_SYNTHETIC_V1"
    assert p.event_id == UUID(E)
    assert p.recipient_id == UUID(U)
    assert p.verified_synthetic_hmac
    for flag in ("authenticated_production_event",
                 "notification_delivery_authorized",
                 "financial_effect_applied", "bank_reconciled"):
        assert getattr(p, flag) is False


@pytest.mark.parametrize("change", [
    {"tenant_id": "ffffffff-0000-4000-8000-000000000012"},
    {"recipient_id": "ffffffff-0000-4000-8000-000000000002"},
    {"role": "MASTER"}, {"event_kind": "SECURITY_SESSION_ALERT"},
    {"cycle_year": 2028}, {"source_digest": "b"*64},
    {"occurred_at": "2026-11-05T12:00:01Z"},
])
def test_tamper_all_bound_dimensions_rejected(change):
    raw = sample()
    signature = sign(raw)
    raw.update(change)
    with pytest.raises(FinancialOperationBlocked):
        verify_synthetic_origin(raw, signature, SECRET, now=NOW)


@pytest.mark.parametrize("bad", [
    {"event_id": "00000000-0000-0000-0000-000000000000"},
    {"recipient_id": "00000000-0000-0000-0000-000000000000"},
    {"role": "MASTER"}, {"event_kind": "UNSUPPORTED"},
    {"cycle_year": 2020.5}, {"cycle_year": True},
    {"occurred_at": "2026-11-05T12:00:00-03:00"},
    {"occurred_at": "2026-11-05T12:00:00.000Z"},
    {"event_id": E.upper()}, {"source_digest": "invalid"},
    {"tenant_id": None}, {"extra": "never"},
])
def test_invalid_signed_payload_still_rejected(bad):
    raw = sample()
    raw.update(bad)
    with pytest.raises(FinancialOperationBlocked):
        check(raw)


@pytest.mark.parametrize("delta", [
    timedelta(seconds=301), timedelta(seconds=-31),
    timedelta(hours=1), timedelta(days=1),
])
def test_clock_window_fails_closed(delta):
    with pytest.raises(FinancialOperationBlocked):
        check(now=NOW+delta)


def test_boundaries_300_seconds_and_future_30_seconds():
    assert check(now=NOW+timedelta(seconds=300)).verified_synthetic_hmac
    assert check(now=NOW-timedelta(seconds=30)).verified_synthetic_hmac


@pytest.mark.parametrize("bad", [
    b"short", b"", "not-bytes", None, bytearray(b"x"*32),
])
def test_secret_must_be_real_bytes_with_32_minimum(bad):
    with pytest.raises(FinancialOperationBlocked):
        check(secret=bad)


@pytest.mark.parametrize("bad", [
    "", "A"*64, "xyz", "0"*63, None, 42,
])
def test_signature_format_is_canonical(bad):
    with pytest.raises(FinancialOperationBlocked):
        check(signature=bad)


def test_cross_context_hmac_domain_separation():
    raw = sample()
    body = json.dumps(raw, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True).encode("ascii")
    foreign_sig = hmac.new(SECRET, b"OTHER-SERVICE\n"+body, sha256).hexdigest()
    with pytest.raises(FinancialOperationBlocked):
        check(signature=foreign_sig)


def test_no_http_route_can_issue_synthetic_signatures():
    from app.main import app
    assert not any("sign" in route.path.lower()
                   and "notification" in route.path.lower()
                   for route in app.routes)
