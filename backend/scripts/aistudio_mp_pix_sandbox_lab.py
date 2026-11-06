#!/usr/bin/env python3
"""M21500: isolated, opt-in Mercado Pago Orders Pix TEST lab.

No tenant credentials, OAuth onboarding, ledger, webhook ingestion, payout,
financial settlement or production credentials. Never print token, QR, response
body, payer information or request headers. One test order per local case.
"""
from __future__ import annotations

import json
import os
import re
import stat
import subprocess
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path
from uuid import uuid4

import httpx

from aistudio_mp_credentials_local import (
    BASE, DEST, audit as credential_audit, ensure_private_dir, ensure_project,
    valid_app_id, valid_test_token,
)

API = "https://api.mercadopago.com"
STATE = BASE / "mp-pix-sandbox-lab-state.json"
TEST_AMOUNT = "50.00"
TEST_PAYER = "test_payer@example.com"
TEST_SCENARIO = "APRO"
CONFIRM = "CONFIRMO_PIX_TESTE_50"
MAX_RESPONSE = 65536
ORDER_ID = re.compile(r"ORD[A-Z0-9]{12,77}\Z")
PAYMENT_ID = re.compile(r"PAY[A-Z0-9]{12,77}\Z")
REFERENCE = re.compile(r"frtest-[0-9a-f]{32}\Z")


class LabBlocked(Exception):
    """Redacted failure; do not concatenate untrusted exception details."""


def _pairs(items):
    out = {}
    for key, value in items:
        if key in out:
            raise LabBlocked("JSON_DUPLICATE_KEYS")
        out[key] = value
    return out


def _constant(_value):
    raise LabBlocked("JSON_INVALID_CONSTANT")


def _json(raw: bytes) -> dict:
    if type(raw) is not bytes or not 0 < len(raw) <= MAX_RESPONSE:
        raise LabBlocked("JSON_SIZE")
    try:
        value = json.loads(raw.decode("utf-8"), parse_float=Decimal,
                           parse_constant=_constant, object_pairs_hook=_pairs)
    except (UnicodeError, ValueError, TypeError, InvalidOperation) as exc:
        raise LabBlocked("JSON_INVALID") from None
    if type(value) is not dict:
        raise LabBlocked("JSON_NOT_OBJECT")
    return value


def validate_test_envelope(raw: bytes) -> str:
    data = _json(raw)
    required = {"environment", "provider", "app_client_id",
                "access_token", "real_payments_enabled"}
    if (set(data) != required or data["environment"] != "TEST"
            or data["provider"] != "MERCADO_PAGO"
            or data["real_payments_enabled"] is not False
            or not valid_app_id(data["app_client_id"])
            or not valid_test_token(data["access_token"])):
        raise LabBlocked("TEST_CREDENTIAL_ENVELOPE_INVALID")
    # The APP_USR prefix alone cannot prove the token is from the TEST panel.
    return data["access_token"]


def decrypt_test_token() -> str:
    credential_audit()  # verifies 0600 and refuses symlinks; never prints token
    if not DEST.exists():
        raise LabBlocked("TEST_TOKEN_NOT_CONFIGURED")
    try:
        result = subprocess.run(
            ["age", "--decrypt", str(DEST)], stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, timeout=90, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise LabBlocked("AGE_DECRYPT_UNAVAILABLE") from None
    if result.returncode != 0:
        raise LabBlocked("AGE_DECRYPT_FAILED")
    return validate_test_envelope(result.stdout)


def new_case() -> dict:
    return {
        "version": 1, "environment": "TEST", "amount": TEST_AMOUNT,
        "reference": "frtest-" + uuid4().hex,
        "idempotency_key": str(uuid4()),
        "phase": "REQUEST_RESERVED", "order_id": None, "payment_id": None,
    }


def _check_case(case: dict) -> None:
    if (type(case) is not dict or set(case) != {
            "version", "environment", "amount", "reference",
            "idempotency_key", "phase", "order_id", "payment_id"}
            or type(case["version"]) is not int or case["version"] != 1
            or case["environment"] != "TEST"
            or case["amount"] != TEST_AMOUNT
            or not isinstance(case["reference"], str)
            or not REFERENCE.fullmatch(case["reference"])
            or type(case["idempotency_key"]) is not str
            or not re.fullmatch(r"[0-9a-f-]{36}", case["idempotency_key"])
            or case["phase"] not in ("REQUEST_RESERVED", "CREATED", "CHECKED")
            or (case["order_id"] is not None and
                (type(case["order_id"]) is not str or
                 not ORDER_ID.fullmatch(case["order_id"])))
            or (case["payment_id"] is not None and
                (type(case["payment_id"]) is not str or
                 not PAYMENT_ID.fullmatch(case["payment_id"])))):
        raise LabBlocked("TEST_CASE_INVALID")


def read_case(path: Path = STATE) -> dict:
    if path.is_symlink() or not path.is_file():
        raise LabBlocked("TEST_CASE_MISSING_OR_UNSAFE")
    info = path.stat()
    if (info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600
            or not 0 < info.st_size <= 4096):
        raise LabBlocked("TEST_CASE_PERMISSIONS")
    case = _json(path.read_bytes())
    _check_case(case)
    return case


def save_case(case: dict, path: Path = STATE, *, initial: bool = False) -> None:
    _check_case(case)
    ensure_private_dir()
    if path.is_symlink() or (initial and path.exists()):
        raise LabBlocked("TEST_CASE_ALREADY_EXISTS")
    if not initial:
        read_case(path)
    blob = json.dumps(case, separators=(",", ":"), sort_keys=True).encode()
    temp = path.with_name(path.name + "." + uuid4().hex + ".tmp")
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(temp, flags, 0o600)
    try:
        with os.fdopen(fd, "wb") as out:
            out.write(blob)
            out.flush()
            os.fsync(out.fileno())
        if initial and path.exists():
            raise LabBlocked("TEST_CASE_ALREADY_EXISTS")
        os.replace(temp, path)
        os.chmod(path, 0o600)
    finally:
        try:
            temp.unlink(missing_ok=True)
        except OSError:
            pass


def _amount(value: object) -> bool:
    return type(value) is str and value == TEST_AMOUNT


def validate_order(payload: dict, case: dict, *, first: bool) -> dict:
    _check_case(case)
    tx = payload.get("transactions")
    payments = tx.get("payments") if type(tx) is dict else None
    if (type(payload.get("id")) is not str
            or not ORDER_ID.fullmatch(payload["id"])
            or payload.get("external_reference") != case["reference"]
            or payload.get("type") != "online"
            or not _amount(payload.get("total_amount"))
            or payload.get("live_mode", False) is not False
            or payload.get("country_code", "BRA") != "BRA"
            or type(payments) is not list or len(payments) != 1
            or type(payments[0]) is not dict):
        raise LabBlocked("ORDER_TEST_IDENTITY_MISMATCH")
    payment = payments[0]
    method = payment.get("payment_method")
    if (type(payment.get("id")) is not str
            or not PAYMENT_ID.fullmatch(payment["id"])
            or not _amount(payment.get("amount"))
            or type(method) is not dict
            or method.get("id") != "pix"
            or method.get("type") != "bank_transfer"):
        raise LabBlocked("ORDER_TEST_PAYMENT_MISMATCH")
    statuses = {
        ("action_required", "waiting_transfer"),
        ("processed", "accredited"),
        ("canceled", "expired"),
        ("failed", "expired"),
    }
    order_status = (payload.get("status"), payload.get("status_detail"))
    payment_status = (payment.get("status"), payment.get("status_detail"))
    if order_status not in statuses or payment_status not in statuses:
        raise LabBlocked("ORDER_TEST_STATUS_UNRECOGNIZED")
    if first and (order_status != ("action_required", "waiting_transfer")
                  or payment_status != ("action_required", "waiting_transfer")):
        raise LabBlocked("ORDER_TEST_CREATION_STATUS_UNEXPECTED")
    if not first and (payload["id"] != case["order_id"] or
                      payment["id"] != case["payment_id"]):
        raise LabBlocked("ORDER_TEST_GET_MISMATCH")
    return {
        "order_id": payload["id"], "payment_id": payment["id"],
        "order_status": order_status[0], "payment_status": payment_status[0],
        "bank_reconciled": False, "ledger_written": False,
        "financial_effect_applied": False, "real_payment_authorized": False,
    }


def build_test_request(token: str, case: dict) -> httpx.Request:
    _check_case(case)
    if not valid_test_token(token):
        raise LabBlocked("TEST_TOKEN_FORMAT_INVALID")
    body = {
        "type": "online", "external_reference": case["reference"],
        "total_amount": TEST_AMOUNT,
        "payer": {"email": TEST_PAYER, "first_name": TEST_SCENARIO},
        "transactions": {"payments": [{
            "amount": TEST_AMOUNT,
            "payment_method": {"id": "pix", "type": "bank_transfer"},
        }]},
    }
    return httpx.Request("POST", API + "/v1/orders", headers={
        "Authorization": "Bearer " + token,
        "X-Idempotency-Key": case["idempotency_key"],
        "Content-Type": "application/json", "Accept": "application/json",
    }, content=json.dumps(body, separators=(",", ":")).encode())


def request_provider(req: httpx.Request, transport=None) -> dict:
    if (req.url.scheme != "https" or req.url.host != "api.mercadopago.com"
            or (req.method == "POST" and req.url.path != "/v1/orders")
            or (req.method == "GET" and
                not re.fullmatch(r"/v1/orders/ORD[A-Z0-9]{12,77}", req.url.path))
            or req.method not in ("POST", "GET")):
        raise LabBlocked("NETWORK_DESTINATION_BLOCKED")
    try:
        with httpx.Client(transport=transport, trust_env=False,
                          follow_redirects=False,
                          timeout=httpx.Timeout(10.0)) as client:
            response = client.send(req)
    except (httpx.HTTPError, OSError):
        raise LabBlocked("NETWORK_UNAVAILABLE_NO_AUTOMATIC_RETRY") from None
    expected = 201 if req.method == "POST" else 200
    if response.status_code != expected:
        raise LabBlocked("PROVIDER_HTTP_" + str(response.status_code))
    return _json(response.content)


def run_create(token: str, case: dict, *, transport=None) -> dict:
    if case["phase"] != "REQUEST_RESERVED":
        raise LabBlocked("CREATE_RETRY_NOT_ALLOWED")
    response = request_provider(build_test_request(token, case), transport)
    return validate_order(response, case, first=True)


def run_get(token: str, case: dict, *, transport=None) -> dict:
    _check_case(case)
    if not valid_test_token(token) or not case["order_id"]:
        raise LabBlocked("TEST_GET_NOT_READY")
    req = httpx.Request("GET", API + "/v1/orders/" + case["order_id"],
                        headers={"Authorization": "Bearer " + token,
                                 "Accept": "application/json"})
    return validate_order(request_provider(req, transport), case, first=False)


def _safe_summary(report: dict) -> None:
    print("M21500_PROVIDER_ORDER_STATUS=" + report["order_status"])
    print("M21500_PROVIDER_PAYMENT_STATUS=" + report["payment_status"])
    print("M21500_BANK_RECONCILED=FALSE")
    print("M21500_LEDGER_WRITTEN=FALSE")
    print("M21500_FINANCIAL_EFFECT=FALSE")
    print("M21500_REAL_PIX=DISABLED")


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in ("prepare", "run-test", "status"):
        print("Uso: aistudio_mp_pix_sandbox_lab.py prepare|run-test|status")
        return 2
    try:
        ensure_project()  # exact clean approved Git SHA + financial real OFF
        mode = sys.argv[1]
        credential_audit()
        if mode == "prepare":
            if STATE.exists() or STATE.is_symlink():
                case = read_case()
                print("M21500_CASE_PHASE=" + case["phase"])
            else:
                print("M21500_CASE_PHASE=NEW")
            print("M21500_TEST_SCENARIO=APRO")
            print("M21500_TEST_AMOUNT_BRL=50.00")
            print("M21500_NETWORK=OFF")
            return 0
        if mode == "run-test":
            if STATE.exists() or STATE.is_symlink():
                raise LabBlocked("CASE_ALREADY_RESERVED_NO_DUPLICATE_POST")
            if not sys.stdin.isatty():
                raise LabBlocked("INTERACTIVE_TERMINAL_REQUIRED")
            print("TESTE ISOLADO Orders Pix APRO, R$50,00. Confirme no painel a credencial de TESTE.")
            print("Criará UMA order de teste; não efetua baixa de contribuição ou repasse.")
            if input("Digite " + CONFIRM + " para confirmar: ").strip() != CONFIRM:
                raise LabBlocked("USER_DID_NOT_CONFIRM")
            token = decrypt_test_token()
            case = new_case()
            save_case(case, initial=True)  # durable before POST; no duplicate on ambiguity
            report = run_create(token, case)
            case.update(order_id=report["order_id"],
                        payment_id=report["payment_id"], phase="CREATED")
            save_case(case)
            _safe_summary(report)
            print("M21500_CASE_PHASE=CREATED")
            return 0
        case = read_case()
        if not case["order_id"]:
            raise LabBlocked("ORDER_UNKNOWN_CHECK_PROVIDER_DASHBOARD_NO_REPOST")
        token = decrypt_test_token()
        report = run_get(token, case)
        case["phase"] = "CHECKED"
        save_case(case)
        _safe_summary(report)
        print("M21500_CASE_PHASE=CHECKED")
        return 0
    except LabBlocked as exc:
        print("M21500_BLOQUEADO=" + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
