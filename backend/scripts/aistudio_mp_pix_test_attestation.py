#!/usr/bin/env python3
"""M21800: append-only local TEST Pix GET evidence; never posts or writes ledger."""
from __future__ import annotations
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import stat
import sys

from aistudio_mp_pix_sandbox_lab import (
    BASE, STATE, LabBlocked, read_case, run_get, decrypt_test_token,
    ensure_project, ensure_private_dir,
)

DEST = BASE / "mp-pix-sandbox-verified-get.json"
FIELDS = frozenset((
    "version", "environment", "scenario", "amount_brl", "case_fingerprint",
    "verified_at_utc", "provider_order_status", "provider_payment_status",
    "authenticated_test_get", "bank_reconciled", "ledger_written",
    "financial_effect_applied", "real_money_enabled", "seller_oauth_bound",
))


def attest(case: dict, report: dict, now: datetime) -> dict:
    if (case.get("phase") != "CHECKED" or not case.get("order_id")
            or not case.get("payment_id")
            or report.get("order_id") != case["order_id"]
            or report.get("payment_id") != case["payment_id"]
            or report.get("order_status") != "processed"
            or report.get("payment_status") != "processed"
            or any(report.get(key) is not False for key in (
                "bank_reconciled", "ledger_written", "financial_effect_applied",
                "real_payment_authorized"))
            or type(now) is not datetime or now.utcoffset() is None):
        raise LabBlocked("M21800_TEST_GET_NOT_PROVEN")
    digest = sha256(("\n".join((
        case["reference"], case["order_id"], case["payment_id"],
        case["idempotency_key"], case["amount"], "APRO", "TEST",
    ))).encode("utf-8")).hexdigest()
    return {
        "version": 1, "environment": "TEST", "scenario": "APRO",
        "amount_brl": "50.00", "case_fingerprint": digest,
        "verified_at_utc": now.astimezone(timezone.utc).isoformat(),
        "provider_order_status": "processed",
        "provider_payment_status": "processed",
        "authenticated_test_get": True, "bank_reconciled": False,
        "ledger_written": False, "financial_effect_applied": False,
        "real_money_enabled": False, "seller_oauth_bound": False,
    }


def validate(data: object) -> None:
    if (type(data) is not dict or set(data) != FIELDS
            or type(data["version"]) is not int or data["version"] != 1
            or data["environment"] != "TEST" or data["scenario"] != "APRO"
            or data["amount_brl"] != "50.00"
            or type(data["case_fingerprint"]) is not str
            or not re.fullmatch(r"[0-9a-f]{64}", data["case_fingerprint"])
            or data["provider_order_status"] != "processed"
            or data["provider_payment_status"] != "processed"
            or data["authenticated_test_get"] is not True
            or any(data[k] is not False for k in (
                "bank_reconciled", "ledger_written", "financial_effect_applied",
                "real_money_enabled", "seller_oauth_bound"))):
        raise LabBlocked("M21800_PROOF_INVALID")
    try:
        moment = datetime.fromisoformat(data["verified_at_utc"])
        if moment.utcoffset() is None or moment.utcoffset().total_seconds() != 0:
            raise ValueError()
    except (ValueError, TypeError, AttributeError):
        raise LabBlocked("M21800_PROOF_DATE_INVALID") from None


def _no_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate")
        result[key] = value
    return result


def save(data: dict, file: Path = DEST) -> None:
    validate(data)
    ensure_private_dir()
    if file.is_symlink() or file.exists():
        raise LabBlocked("M21800_ALREADY_RECORDED")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        fd = os.open(file, flags, 0o600)
    except FileExistsError:
        raise LabBlocked("M21800_ALREADY_RECORDED") from None
    with os.fdopen(fd, "wb") as stream:
        stream.write(json.dumps(data, sort_keys=True, separators=(",", ":")).encode())
        stream.flush()
        os.fsync(stream.fileno())


def read(file: Path = DEST) -> dict:
    if file.is_symlink() or not file.is_file():
        raise LabBlocked("M21800_PROOF_MISSING")
    info = file.stat()
    if (info.st_uid != os.getuid() or info.st_nlink != 1
            or stat.S_IMODE(info.st_mode) != 0o600
            or not 0 < info.st_size <= 4096):
        raise LabBlocked("M21800_PROOF_PERMISSIONS")
    try:
        data = json.loads(file.read_bytes(), object_pairs_hook=_no_duplicates)
    except (ValueError, TypeError, OSError):
        raise LabBlocked("M21800_PROOF_INVALID_JSON") from None
    validate(data)
    return data


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in ("record", "audit"):
        print("Uso: aistudio_mp_pix_test_attestation.py record|audit")
        return 2
    try:
        ensure_project()
        if sys.argv[1] == "record":
            if DEST.exists() or DEST.is_symlink():
                raise LabBlocked("M21800_ALREADY_RECORDED")
            case = read_case(STATE)
            if case["phase"] != "CHECKED":
                raise LabBlocked("M21800_CASE_NOT_CHECKED")
            # The previously created order is ONLY READ; never re-POST.
            report = run_get(decrypt_test_token(), case)
            save(attest(case, report, datetime.now(timezone.utc)))
        else:
            read()
    except LabBlocked as exc:
        print("M21800_BLOCKED=" + str(exc), file=sys.stderr)
        return 2
    print("M21800_TEST_MP_GET=PROCESSED")
    print("M21800_LOCAL_EVIDENCE=PRIVATE_NOT_BANK_SETTLEMENT")
    print("M21800_BANK_RECONCILED=FALSE")
    print("M21800_LEDGER_WRITTEN=FALSE")
    print("M21800_REAL_PIX=OFF")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
