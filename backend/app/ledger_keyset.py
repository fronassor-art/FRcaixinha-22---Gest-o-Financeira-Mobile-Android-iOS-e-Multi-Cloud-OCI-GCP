"""Cursor read-only da conta contábil: posição não é autenticação ou snapshot."""
import base64
import binascii
import json
import re
import uuid
from datetime import datetime
from decimal import Decimal
from fastapi import HTTPException
from .models import LedgerAccountJournalEntryResponse

INVALID_CURSOR = "Cursor contábil inválido."


def encode_cursor(tenant, account, row):
    value = {
        "v": 1, "tenant": str(tenant), "account": str(account),
        "date": row["transaction_date"].isoformat(),
        "transaction": str(uuid.UUID(str(row["transaction_id"]))),
        "entry": str(uuid.UUID(str(row["id"]))),
    }
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def decode_cursor(token, tenant, account):
    if not isinstance(token, str) or not 1 <= len(token) <= 400 or not re.fullmatch(
        r"[A-Za-z0-9_-]+", token
    ):
        raise HTTPException(status_code=422, detail=INVALID_CURSOR)
    try:
        value = json.loads(base64.urlsafe_b64decode(
            token + "=" * (-len(token) % 4)
        ).decode("utf-8"))
        if not isinstance(value, dict) or set(value) != {
            "v", "tenant", "account", "date", "transaction", "entry"
        } or type(value["v"]) is not int or value["v"] != 1 or (
            value["tenant"] != str(tenant) or value["account"] != str(account)
        ):
            raise ValueError("scope")
        posted = datetime.fromisoformat(value["date"])
        if posted.tzinfo is None or posted.utcoffset() is None:
            raise ValueError("timezone")
        transaction, entry = uuid.UUID(value["transaction"]), uuid.UUID(value["entry"])
        canonical = {
            "transaction_date": posted, "transaction_id": transaction, "id": entry,
        }
        if (value["date"] != posted.isoformat()
                or value["transaction"] != str(transaction)
                or value["entry"] != str(entry)
                or token != encode_cursor(tenant, account, canonical)):
            raise ValueError("noncanonical")
    except (TypeError, ValueError, KeyError, OverflowError, binascii.Error,
            UnicodeDecodeError):
        raise HTTPException(status_code=422, detail=INVALID_CURSOR)
    return posted, transaction, entry


def validate_rows(rows, page_size):
    if len(rows) > page_size + 1:
        raise HTTPException(status_code=503, detail="Excesso de linhas contábeis.")
    result, last = [], None
    for row in rows:
        try:
            entry = uuid.UUID(str(row["id"]))
            transaction = uuid.UUID(str(row["transaction_id"]))
            posted = row["transaction_date"]
            cents, kind = row["amount_cents"], row["entry_type"]
            description, reference = row["description"], row["reference_id"]
            if not isinstance(posted, datetime) or posted.tzinfo is None or (
                posted.utcoffset() is None
            ):
                raise ValueError("date")
            key = posted, transaction, entry
            if (last is not None and key >= last
                    or type(cents) is not int or not (1 <= cents <= 100000000000)
                    or kind not in ("DR", "CR")
                    or not isinstance(description, str) or not description.strip()
                    or len(description) > 500 or any(ord(ch) < 32 for ch in description)
                    or not isinstance(reference, str) or not reference.strip()
                    or len(reference) > 200 or any(ord(ch) < 32 for ch in reference)):
                raise ValueError("invalid row or order")
            last = key
            result.append(LedgerAccountJournalEntryResponse(
                id=str(entry), transaction_id=str(transaction),
                transaction_date=posted, description=description,
                reference_id=reference, entry_type=kind, amount_cents=cents,
                amount_brl=(Decimal(cents) / Decimal(100)).quantize(Decimal("0.01")),
            ))
        except (KeyError, TypeError, ValueError, OverflowError):
            raise HTTPException(
                status_code=503, detail="Página contábil inválida; consulta bloqueada.",
            )
    return result
