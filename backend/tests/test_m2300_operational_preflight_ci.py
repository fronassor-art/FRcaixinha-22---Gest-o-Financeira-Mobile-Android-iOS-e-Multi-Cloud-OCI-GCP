"""M2300: parsers e HMAC isolados; testes não acionam Mercado Pago nem PostgreSQL."""
from dataclasses import replace
from datetime import timezone
import hashlib
import hmac

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.mp_operational_preflight import (
    CONTRACT, MAX_CSV_BYTES, preview_manual_settlement_csv, verify_webhook_hmac_offline,
)

HEADER = (
    "SOURCE_ID;USER_ID;EXTERNAL_REFERENCE;TRANSACTION_TYPE;"
    "TRANSACTION_AMOUNT;FEE_AMOUNT;SETTLEMENT_NET_AMOUNT;"
    "TRANSACTION_CURRENCY;SETTLEMENT_CURRENCY;SETTLEMENT_DATE"
)
ROW = (
    "900001;2002;tenant:contribution-001;SETTLEMENT;"
    "150.00;-3.60;146.40;BRL;BRL;2027-08-20T12:00:00-03:00"
)
SELLER = "2002"
SECRET = b"fixture-only-webhook-secret-123456"
NOW = 1800000000000


def csv_bytes(*rows, header=HEADER):
    return ("\ufeff" + "\n".join((header, *rows)) + "\n").encode("utf-8")


def test_settlement_csv_is_never_banking_proof():
    payload = csv_bytes(ROW)
    result = preview_manual_settlement_csv(payload, expected_seller_id=SELLER)
    assert result.contract == CONTRACT
    assert result.sha256 == hashlib.sha256(payload).hexdigest()
    assert result.source == "USER_PROVIDED_CSV_UNVERIFIED"
    assert result.rows[0].gross_cents == 15000
    assert result.rows[0].fee_cents == -360
    assert result.rows[0].net_cents == 14640
    assert result.rows[0].settled_at.utcoffset().total_seconds() == -10800
    assert result.rows[0].review_code == "ARITHMETIC_MATCH_UNVERIFIED"
    assert result.review_required_count == 0
    assert result.arithmetic_match_count == 1
    for name in ("authenticated_provider_get", "bank_reconciled", "payment_confirmed",
                 "ledger_written", "financial_closing_authorized", "payout_authorized"):
        assert getattr(result, name) is False


@pytest.mark.parametrize("gross,fee,net", [
    ("150.00", "-3.60", "146.40"),
    ("1", "0", "1"),
    ("0.01", "-0.01", "0"),
    ("9999999999999.99", "-0.01", "9999999999999.98"),
])
def test_amounts_cents_exact(gross, fee, net):
    r = ROW.replace("150.00;-3.60;146.40", f"{gross};{fee};{net}")
    result = preview_manual_settlement_csv(csv_bytes(r), expected_seller_id=SELLER)
    assert result.rows[0].review_code == "ARITHMETIC_MATCH_UNVERIFIED"


@pytest.mark.parametrize("gross,fee,net", [
    ("150.00", "-3.60", "146.41"), ("150.00", "3.60", "153.60"),
    ("0", "0", "0"), ("-150.00", "0", "-150.00"),
    ("150.00", "-200.00", "-50.00"),
])
def test_mismatched_money_requires_review(gross, fee, net):
    r = ROW.replace("150.00;-3.60;146.40", f"{gross};{fee};{net}")
    result = preview_manual_settlement_csv(csv_bytes(r), expected_seller_id=SELLER)
    assert result.review_required_count == 1
    assert result.arithmetic_match_count == 0


@pytest.mark.parametrize("bad", [
    "1.001", "1e3", "nan", "Infinity", "+1", "1,50",
    "1.2.3", " 1 ", "99999999999999", "-99999999999999", "0x10",
])
def test_invalid_money_rejected(bad):
    r = ROW.replace("150.00;-3.60;146.40", f"{bad};-3.60;146.40")
    with pytest.raises(ValueError):
        preview_manual_settlement_csv(csv_bytes(r), expected_seller_id=SELLER)


def test_non_settlement_and_missing_reference_require_review():
    non = ROW.replace("SETTLEMENT;", "REFUND;").replace("900001", "900002")
    missing = ROW.replace("tenant:contribution-001", "").replace("900001", "900003")
    result = preview_manual_settlement_csv(csv_bytes(non, missing), expected_seller_id=SELLER)
    assert [r.review_code for r in result.rows] == [
        "NON_SETTLEMENT_EVENT_REVIEW", "MISSING_EXTERNAL_REFERENCE_REVIEW"]
    assert result.review_required_count == 2


@pytest.mark.parametrize("r", [
    ROW.replace("2002;", "3003;", 1),
    ROW.replace("900001;", "non-numeric;", 1),
    ROW.replace("tenant:contribution-001", "=SUM(A1:A2)"),
    ROW.replace("BRL;BRL", "USD;BRL"),
    ROW.replace("BRL;BRL", "BRL;USD"),
    ROW.replace("2027-08-20T12:00:00-03:00", "2027-08-20T12:00:00"),
    ROW.replace("2027-08-20T12:00:00-03:00", "invalid"),
    ROW.replace("SETTLEMENT;", "SETTLEMENT;extra;"),
])
def test_reject_out_of_scope_or_malformed_rows(r):
    with pytest.raises(ValueError):
        preview_manual_settlement_csv(csv_bytes(r), expected_seller_id=SELLER)


def test_duplicate_source_id_and_header_rejected():
    with pytest.raises(ValueError):
        preview_manual_settlement_csv(csv_bytes(ROW, ROW), expected_seller_id=SELLER)
    bad_header = HEADER + ";USER_ID"
    with pytest.raises(ValueError):
        preview_manual_settlement_csv(csv_bytes(ROW + ";2002", header=bad_header), expected_seller_id=SELLER)


@pytest.mark.parametrize("bad", [b"", b"\xff", b"\x00", b"x" * (MAX_CSV_BYTES + 1), "hello".encode()])
def test_bad_input_rejected(bad):
    with pytest.raises(ValueError):
        preview_manual_settlement_csv(bad, expected_seller_id=SELLER)


def test_row_limit_bounded():
    payload = csv_bytes(*[
        ROW.replace("900001", str(900001+i)) for i in range(5001)
    ])
    with pytest.raises(ValueError, match="Limite"):
        preview_manual_settlement_csv(payload, expected_seller_id=SELLER)


def sign(*, data_id="900001", request_id="request_001", ts=NOW, secret=SECRET):
    text = f"id:{data_id};request-id:{request_id};ts:{ts};".encode()
    mac = hmac.new(secret, text, hashlib.sha256).hexdigest()
    return f"ts={ts},v1={mac}"


def verify(**overrides):
    p = dict(data_id="900001", request_id="request_001",
             x_signature=sign(), secret=SECRET, now_ms=NOW)
    p.update(overrides)
    return verify_webhook_hmac_offline(**p)


def test_hmac_valid_signature_does_not_enable_payment():
    assert verify() is True
    assert verify(x_signature=sign(ts=NOW-299_000)) is True


@pytest.mark.parametrize("overrides", [
    {"data_id": "900002"}, {"request_id": "request_002"},
    {"secret": b"fixture-only-other-secret-abcdef"},
    {"x_signature": "ts=1800000000000,v1=not-a-digest"},
    {"x_signature": "v1=" + "0"*64},
    {"x_signature": "ts=1800000000000,ts=1800000000000,v1=" + "0"*64},
    {"x_signature": "ts=1800000000000,v1=" + "0"*64 + ",extra=1"},
    {"x_signature": "ts=1800000000000,v1=" + "0"*64 + ",v1=" + "0"*64},
    {"x_signature": ""},
    {"data_id": "a;request-id:injected"},
    {"request_id": "r;ts:injected"},
    {"secret": b"short"},
    {"now_ms": NOW + 301_000},
    {"now_ms": NOW - 301_000},
    {"max_age_ms": 99999999},
])
def test_hmac_rejects_tampering_replays_and_wrong_context(overrides):
    assert verify(**overrides) is False


def test_hmac_strict_timestamp_and_clock_boundaries():
    assert verify(x_signature=sign(ts=NOW-300_000)) is True
    assert verify(x_signature=sign(ts=NOW+300_000)) is True
    assert verify(x_signature=sign(ts=NOW+300_001)) is False
    assert verify(x_signature=sign(ts=123)) is False


def test_endpoint_only_reports_guard_readiness_not_provider_connection():
    with TestClient(app) as client:
        res = client.get("/api/health/features/m2300")
    assert res.status_code == 200
    body = res.json()
    assert body["workstream"] == "AI_STUDIO"
    assert body["contract"] == CONTRACT
    assert body["offline_csv_preview_only"] is True
    assert body["webhook_validator_not_registered"] is True
    for flag in ("provider_connected", "bank_reconciled", "ledger_written",
                 "financial_closing_authorized", "real_payments_enabled",
                 "pix_enabled", "webhook_live_active"):
        assert body[flag] is False
