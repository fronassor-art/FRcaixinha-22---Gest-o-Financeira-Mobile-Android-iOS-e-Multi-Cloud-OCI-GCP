"""M2201-M2300: pré-leitura de extrato MP e validação pura de assinatura.

Sem HTTP, OAuth, banco, segredos persistidos, writes ou alteração financeira.
O CSV manual NÃO é comprovante bancário autenticado nem liquidação confirmada.
"""
from __future__ import annotations

import csv
import hashlib
import hmac
import io
import re
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation

CONTRACT = "AI_STUDIO_M2300_OFFLINE_SETTLEMENT_AND_WEBHOOK_GUARD_V1"
MAX_CSV_BYTES = 2_000_000
MAX_ROWS = 5_000
MAX_CELL_CHARS = 4096
MAX_CENTS = 10**15 - 1
_REQUIRED = frozenset({
    "SOURCE_ID", "USER_ID", "EXTERNAL_REFERENCE", "TRANSACTION_TYPE",
    "TRANSACTION_AMOUNT", "FEE_AMOUNT", "SETTLEMENT_NET_AMOUNT",
    "TRANSACTION_CURRENCY", "SETTLEMENT_CURRENCY", "SETTLEMENT_DATE",
})
_NUMERIC = re.compile(r"[0-9]{1,40}\Z")
_REFERENCE = re.compile(r"[A-Za-z0-9._:/-]{1,120}\Z")
_MONEY = re.compile(r"-?[0-9]{1,13}(?:\.[0-9]{1,2})?\Z")
_WEBHOOK_ID = re.compile(r"[A-Za-z0-9_-]{1,100}\Z")
_REQUEST_ID = re.compile(r"[A-Za-z0-9._:-]{1,120}\Z")
_HEX = re.compile(r"[0-9a-fA-F]{64}\Z")
_TS = re.compile(r"[0-9]{13}\Z")


@dataclass(frozen=True)
class OfflineSettlementRow:
    payment_id: str
    seller_id: str
    external_reference: str
    transaction_type: str
    gross_cents: int
    fee_cents: int
    net_cents: int
    settled_at: datetime
    review_code: str


@dataclass(frozen=True)
class OfflineSettlementPreview:
    seller_id: str
    sha256: str
    rows: tuple[OfflineSettlementRow, ...]
    review_required_count: int
    arithmetic_match_count: int
    contract: str = CONTRACT
    source: str = field(default="USER_PROVIDED_CSV_UNVERIFIED", init=False)
    authenticated_provider_get: bool = field(default=False, init=False)
    bank_reconciled: bool = field(default=False, init=False)
    payment_confirmed: bool = field(default=False, init=False)
    ledger_written: bool = field(default=False, init=False)
    financial_closing_authorized: bool = field(default=False, init=False)
    payout_authorized: bool = field(default=False, init=False)


def _money_cents(raw: str) -> int:
    """Converte decimal literal, rejeitando floats, expoentes e centésimo parcial."""
    if not isinstance(raw, str) or not _MONEY.fullmatch(raw):
        raise ValueError("Valor monetário não canônico no CSV")
    try:
        cents = Decimal(raw) * 100
        result = int(cents)
    except (InvalidOperation, OverflowError, ValueError) as exc:
        raise ValueError("Valor monetário inválido") from exc
    if cents != result or abs(result) > MAX_CENTS:
        raise ValueError("Centavos fora do limite")
    return result


def preview_manual_settlement_csv(data: bytes, *, expected_seller_id: str) -> OfflineSettlementPreview:
    """Prévia local conservadora; não cruza credencial autenticada nem baixa saldo."""
    if (type(data) is not bytes or not 0 < len(data) <= MAX_CSV_BYTES
            or not isinstance(expected_seller_id, str)
            or not _NUMERIC.fullmatch(expected_seller_id)):
        raise ValueError("Arquivo ou escopo do recebedor inválido")
    try:
        plain = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("CSV deve estar em UTF-8") from exc
    if "\x00" in plain:
        raise ValueError("CSV contém caractere proibido")
    reader = csv.DictReader(io.StringIO(plain, newline=""), delimiter=";", strict=True)
    headers = reader.fieldnames
    if (not headers or len(headers) != len(set(headers))
            or not _REQUIRED.issubset(headers)
            or any(not h or len(h) > 100 for h in headers)):
        raise ValueError("Cabeçalho ausente, duplicado ou incompatível")

    rows: list[OfflineSettlementRow] = []
    seen_ids: set[str] = set()
    review = matched = 0
    try:
        for raw in reader:
            if len(rows) >= MAX_ROWS:
                raise ValueError("Limite de linhas excedido")
            if (None in raw or any(type(v) is not str or len(v) > MAX_CELL_CHARS
                                   for v in raw.values())):
                raise ValueError("Linha CSV malformada ou acima do limite")
            row = {k: v.strip() for k, v in raw.items()}
            if any(raw[k] != row[k] for k in _REQUIRED):
                raise ValueError("Campo obrigatório com espaços não-canônicos")
            payment_id = row["SOURCE_ID"]
            seller_id = row["USER_ID"]
            reference = row["EXTERNAL_REFERENCE"]
            if (not _NUMERIC.fullmatch(payment_id)
                    or not _NUMERIC.fullmatch(seller_id)
                    or seller_id != expected_seller_id):
                raise ValueError("Identidade de pagamento ou recebedor divergente")
            if payment_id in seen_ids:
                raise ValueError("SOURCE_ID repetido: exigir revisão fora do importador")
            seen_ids.add(payment_id)
            if reference and not _REFERENCE.fullmatch(reference):
                raise ValueError("Referência externa com caracteres não permitidos")
            if row["TRANSACTION_CURRENCY"] != "BRL" or row["SETTLEMENT_CURRENCY"] != "BRL":
                raise ValueError("Moeda incompatível com a caixinha")
            kind = row["TRANSACTION_TYPE"]
            if not re.fullmatch(r"[A-Z_]{1,50}", kind):
                raise ValueError("Tipo de movimento inválido")
            gross = _money_cents(row["TRANSACTION_AMOUNT"])
            fee = _money_cents(row["FEE_AMOUNT"])
            net = _money_cents(row["SETTLEMENT_NET_AMOUNT"])
            try:
                settled_at = datetime.fromisoformat(row["SETTLEMENT_DATE"].replace("Z", "+00:00"))
            except ValueError as exc:
                raise ValueError("Data de liquidação inválida") from exc
            if settled_at.utcoffset() is None:
                raise ValueError("Liquidação sem fuso horário")
            reason = "ARITHMETIC_MATCH_UNVERIFIED"
            if kind != "SETTLEMENT":
                reason = "NON_SETTLEMENT_EVENT_REVIEW"
            elif not reference:
                reason = "MISSING_EXTERNAL_REFERENCE_REVIEW"
            elif gross <= 0 or fee > 0 or net < 0:
                reason = "SIGN_OR_AMOUNT_REVIEW"
            elif gross + fee != net:
                reason = "NET_AMOUNT_MISMATCH_REVIEW"
            if reason == "ARITHMETIC_MATCH_UNVERIFIED":
                matched += 1
            else:
                review += 1
            rows.append(OfflineSettlementRow(
                payment_id, seller_id, reference, kind,
                gross, fee, net, settled_at, reason,
            ))
    except csv.Error as exc:
        raise ValueError("CSV estruturado inválido") from exc
    if not rows:
        raise ValueError("Relatório sem lançamentos")
    return OfflineSettlementPreview(
        seller_id=expected_seller_id,
        sha256=hashlib.sha256(data).hexdigest(),
        rows=tuple(rows),
        review_required_count=review,
        arithmetic_match_count=matched,
    )


def verify_webhook_hmac_offline(
    *, data_id: str, request_id: str, x_signature: str, secret: bytes,
    now_ms: int, max_age_ms: int = 300_000,
) -> bool:
    """HMAC SHA-256 MP, sem receber webhooks nem escrever em inbox.

    A assinatura válida não equivale a GET do pagamento, autorização do vendedor
    ou liquidação. Requer idempotência persistente ANTES de qualquer efeito.
    """
    if (not isinstance(data_id, str) or not _WEBHOOK_ID.fullmatch(data_id)
            or not isinstance(request_id, str) or not _REQUEST_ID.fullmatch(request_id)
            or type(secret) is not bytes or not 16 <= len(secret) <= 1024
            or not isinstance(x_signature, str) or len(x_signature) > 256
            or type(now_ms) is not int or now_ms <= 0
            or type(max_age_ms) is not int or not 1000 <= max_age_ms <= 300_000):
        return False
    parts: dict[str, str] = {}
    for part in x_signature.split(","):
        pair = part.strip().split("=", 1)
        if len(pair) != 2 or pair[0] not in ("ts", "v1") or pair[0] in parts:
            return False
        parts[pair[0]] = pair[1]
    ts, digest = parts.get("ts", ""), parts.get("v1", "")
    if not _TS.fullmatch(ts) or not _HEX.fullmatch(digest):
        return False
    if abs(now_ms - int(ts)) > max_age_ms:
        return False
    manifest = f"id:{data_id};request-id:{request_id};ts:{ts};".encode("utf-8")
    expected = hmac.new(secret, manifest, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, digest.lower())
