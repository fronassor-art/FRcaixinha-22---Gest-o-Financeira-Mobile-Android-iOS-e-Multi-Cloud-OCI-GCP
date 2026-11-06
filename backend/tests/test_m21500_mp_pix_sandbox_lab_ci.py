"""M21500: offline regression for the official Mercado Pago Pix test scenario."""
from copy import deepcopy
import json
import os
from pathlib import Path
import stat
import sys

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import aistudio_mp_pix_sandbox_lab as lab


TOKEN = "APP_USR-" + "X" * 45
ORD = "ORD01JP84C939T20S0P1DN382FQ6K"
PAY = "PAY01JP84C939T20S0P1DN6FCMWQC"


def case():
    return lab.new_case()


def response(case, *, approved=False):
    status, detail = ("processed", "accredited") if approved else (
        "action_required", "waiting_transfer")
    return {
        "id": ORD, "type": "online", "country_code": "BRA",
        "external_reference": case["reference"], "total_amount": "50.00",
        "status": status, "status_detail": detail, "live_mode": False,
        "transactions": {"payments": [{
            "id": PAY, "amount": "50.00", "status": status,
            "status_detail": detail,
            "payment_method": {"id": "pix", "type": "bank_transfer",
                               "qr_code": "00020126fake"},
        }]},
    }


def test_official_apro_pix_payload_and_headers():
    c = case()
    req = lab.build_test_request(TOKEN, c)
    body = json.loads(req.content)
    assert req.method == "POST"
    assert str(req.url) == "https://api.mercadopago.com/v1/orders"
    assert req.headers["x-idempotency-key"] == c["idempotency_key"]
    assert body["payer"] == {"email": lab.TEST_PAYER, "first_name": "APRO"}
    assert body["total_amount"] == "50.00"
    assert body["transactions"]["payments"] == [
        {"amount": "50.00", "payment_method": {"id": "pix", "type": "bank_transfer"}}
    ]
    assert TOKEN not in req.content.decode()
    assert "notification_url" not in body
    assert "collector_id" not in body


def test_mock_create_get_no_financial_effects():
    c = case()
    calls = []
    def handler(req):
        calls.append((req.method, req.url.path))
        return httpx.Response(
            201 if req.method == "POST" else 200,
            json=response(c, approved=req.method == "GET"))
    transport = httpx.MockTransport(handler)
    created = lab.run_create(TOKEN, c, transport=transport)
    assert created["order_status"] == "action_required"
    c.update(order_id=created["order_id"], payment_id=created["payment_id"],
             phase="CREATED")
    read = lab.run_get(TOKEN, c, transport=transport)
    assert read["order_status"] == "processed"
    assert calls == [("POST", "/v1/orders"), ("GET", "/v1/orders/" + ORD)]
    assert read["bank_reconciled"] is False
    assert read["ledger_written"] is False
    assert read["financial_effect_applied"] is False
    assert read["real_payment_authorized"] is False


@pytest.mark.parametrize("field,bad", [
    ("id", "BAD_ORDER"), ("external_reference", "another"),
    ("total_amount", "50.01"), ("country_code", "ARG"),
    ("type", "offline"), ("live_mode", True),
    ("status", "processed"), ("status_detail", "accredited"),
])
def test_unexpected_create_rejected(field, bad):
    c = case()
    doc = response(c)
    doc[field] = bad
    with pytest.raises(lab.LabBlocked):
        lab.validate_order(doc, c, first=True)


@pytest.mark.parametrize("field,bad", [
    ("id", "BAD_PAYMENT"), ("amount", "51.00"),
    ("status", "processed"), ("status_detail", "accredited"),
])
def test_payment_mismatch_rejected(field, bad):
    c = case()
    doc = response(c)
    doc["transactions"]["payments"][0][field] = bad
    with pytest.raises(lab.LabBlocked):
        lab.validate_order(doc, c, first=True)


def test_duplicate_payment_and_wrong_method_rejected():
    c = case()
    doc = response(c)
    doc["transactions"]["payments"].append(deepcopy(
        doc["transactions"]["payments"][0]))
    with pytest.raises(lab.LabBlocked):
        lab.validate_order(doc, c, first=True)
    doc = response(c)
    doc["transactions"]["payments"][0]["payment_method"]["id"] = "card"
    with pytest.raises(lab.LabBlocked):
        lab.validate_order(doc, c, first=True)


def test_get_exact_order_and_payment_binding():
    c = case()
    c.update(order_id=ORD, payment_id=PAY, phase="CREATED")
    doc = response(c, approved=True)
    assert lab.validate_order(doc, c, first=False)["order_status"] == "processed"
    doc["transactions"]["payments"][0]["id"] = "PAY01OTHER000000000000000"
    with pytest.raises(lab.LabBlocked):
        lab.validate_order(doc, c, first=False)


@pytest.mark.parametrize("status", [302, 400, 401, 403, 409, 423, 429, 500, 503])
def test_errors_no_retry_and_no_body_echo(status):
    c = case()
    calls = []
    def handler(req):
        calls.append(req)
        return httpx.Response(status, content=b"SECRET_PROVIDED_BY_PROVIDER")
    with pytest.raises(lab.LabBlocked, match="PROVIDER_HTTP_"):
        lab.run_create(TOKEN, c, transport=httpx.MockTransport(handler))
    assert len(calls) == 1


def test_timeout_no_retry_no_new_idempotency_key():
    c = case()
    calls = []
    def handler(req):
        calls.append(req)
        raise httpx.ConnectTimeout("no connection")
    with pytest.raises(lab.LabBlocked, match="NO_AUTOMATIC_RETRY"):
        lab.run_create(TOKEN, c, transport=httpx.MockTransport(handler))
    assert len(calls) == 1
    assert c["phase"] == "REQUEST_RESERVED"


@pytest.mark.parametrize("raw", [
    b"", b"[]", b"null", b'{"x":1,"x":2}', b'{"n":NaN}',
    b"{" + b" " * 70000 + b"}",
])
def test_invalid_or_oversize_json_rejected(raw):
    with pytest.raises(lab.LabBlocked):
        lab._json(raw)


def test_cipher_envelope_rejects_prod_flags_and_unknown_keys():
    good = {"environment": "TEST", "provider": "MERCADO_PAGO",
            "app_client_id": "123456", "access_token": TOKEN,
            "real_payments_enabled": False}
    assert lab.validate_test_envelope(json.dumps(good).encode()) == TOKEN
    for updates in (
        {"environment": "PRODUCAO"}, {"real_payments_enabled": True},
        {"access_token": "PROD_TOKEN"}, {"app_client_id": "abc"},
        {"another_field": "not allowed"},
    ):
        value = {**good, **updates}
        with pytest.raises(lab.LabBlocked):
            lab.validate_test_envelope(json.dumps(value).encode())


def test_state_private_and_no_token(tmp_path, monkeypatch):
    monkeypatch.setattr(lab, "ensure_private_dir", lambda: None)
    path = tmp_path / "state.json"
    c = case()
    lab.save_case(c, path=path, initial=True)
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert TOKEN not in path.read_text()
    assert lab.read_case(path) == c
    with pytest.raises(lab.LabBlocked, match="ALREADY_EXISTS"):
        lab.save_case(case(), path=path, initial=True)
    c.update(phase="CREATED", order_id=ORD, payment_id=PAY)
    lab.save_case(c, path=path)
    assert lab.read_case(path) == c


def test_symlink_state_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(lab, "ensure_private_dir", lambda: None)
    target = tmp_path / "target"
    target.write_text("any data")
    path = tmp_path / "state"
    path.symlink_to(target)
    with pytest.raises(lab.LabBlocked):
        lab.read_case(path)
    with pytest.raises(lab.LabBlocked):
        lab.save_case(case(), path=path, initial=True)


def test_no_repost_existing_case_even_in_mock():
    c = case()
    c["phase"] = "CREATED"
    with pytest.raises(lab.LabBlocked, match="CREATE_RETRY_NOT_ALLOWED"):
        lab.run_create(TOKEN, c, transport=httpx.MockTransport(
            lambda _: pytest.fail("must not call HTTP")))


def test_module_is_not_a_public_payment_api():
    root = Path(__file__).resolve().parents[1]
    s = (root / "scripts/aistudio_mp_pix_sandbox_lab.py").read_text()
    assert "from fastapi" not in s
    assert "INSERT INTO" not in s
    assert "REAL_PIX_COLLECTION_ACTIVE=YES" not in s
    assert "check=True" not in s
    assert "follow_redirects=False" in s
    assert "CONFIRMO_PIX_TESTE_50" in s
