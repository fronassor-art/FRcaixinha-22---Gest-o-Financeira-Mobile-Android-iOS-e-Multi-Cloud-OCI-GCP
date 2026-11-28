"""Validações sem efeitos para futura integração Mercado Pago.

Este módulo NÃO envia cobranças, recebe webhooks, consulta o provedor,
armazena tokens, concilia automaticamente ou altera o razão contábil.
"""
from dataclasses import dataclass
from decimal import Decimal, DecimalException
import hashlib
import hmac
import re
from typing import Any, Mapping


def verify_webhook_signature(*, secret: str, signature: str, request_id: str, resource_id: str) -> bool:
    """Valida HMAC-SHA256 do cabeçalho; não confirma pagamento nem evita replay."""
    if not all(isinstance(x, str) and x for x in (secret, signature, request_id, resource_id)):
        return False
    if any(ch in request_id or ch in resource_id for ch in (';', '\n', '\r')):
        return False
    fields = {}
    for part in signature.split(','):
        if '=' not in part:
            return False
        key, value = (x.strip() for x in part.split('=', 1))
        if key in fields or not key or not value:
            return False
        fields[key] = value
    timestamp, provided = fields.get('ts', ''), fields.get('v1', '')
    if not timestamp.isascii() or not timestamp.isdigit() or not re.fullmatch(r'[0-9a-fA-F]{64}', provided):
        return False
    normalized_id = resource_id.lower() if resource_id.isascii() and resource_id.isalnum() else resource_id
    manifest = f'id:{normalized_id};request-id:{request_id};ts:{timestamp};'
    expected = hmac.new(secret.encode('utf-8'), manifest.encode('utf-8'), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, provided.lower())


@dataclass(frozen=True)
class ExpectedPayment:
    provider_payment_id: str
    collector_id: str
    external_reference: str
    amount_cents: int
    live_mode: bool


def _exact_cents(amount: object, cents: int) -> bool:
    """Exact equality without multiplication in the ambient Decimal context."""
    if type(cents) is not int or not 0 <= cents <= 999_999_999_999:
        return False
    if type(amount) not in (str, int, Decimal):
        return False
    if type(amount) is str and (len(amount) > 128 or not re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", amount)):
        return False
    try:
        value = Decimal(amount)
        expected = Decimal(f"{cents // 100}.{cents % 100:02d}")
        return value.is_finite() and value == expected
    except (DecimalException, ValueError, OverflowError):
        return False


def _matches_payment_identity(expected: ExpectedPayment, payment: Mapping[str, Any]) -> bool:
    if type(expected) is not ExpectedPayment or type(expected.live_mode) is not bool:
        return False
    if type(expected.amount_cents) is not int or not 0 < expected.amount_cents <= 999_999_999_999:
        return False
    for identifier in (expected.provider_payment_id, expected.collector_id):
        if type(identifier) is not str or not re.fullmatch(r"[0-9]{1,40}", identifier) or not identifier.strip("0"):
            return False
    if type(expected.external_reference) is not str or not 0 < len(expected.external_reference) <= 120:
        return False
    if not isinstance(payment, Mapping) or payment.get("currency_id") != "BRL" or payment.get("live_mode") is not expected.live_mode:
        return False
    for field, identifier in (("id", expected.provider_payment_id), ("collector_id", expected.collector_id)):
        value = payment.get(field)
        if type(value) not in (str, int) or (type(value) is int and not 0 < value < 10**40) or str(value) != identifier:
            return False
    return (payment.get("external_reference") == expected.external_reference
            and _exact_cents(payment.get("transaction_amount"), expected.amount_cents))


def matches_approved_payment(expected: ExpectedPayment, payment: Mapping[str, Any]) -> bool:
    """Confere resposta autoritativa recebida do provedor; não liquida obrigação.

    O chamador deve obter a resposta por canal autenticado usando a conta correta;
    payload de webhook ou dados enviados pelo cliente não são prova de pagamento.
    """
    return (isinstance(payment, Mapping) and payment.get("status") == "approved"
            and _matches_payment_identity(expected, payment)
            and ("transaction_amount_refunded" not in payment
                 or _exact_cents(payment["transaction_amount_refunded"], 0)))



def matches_full_refund(expected: ExpectedPayment, payment: Mapping[str, Any]) -> bool:
    """Aceita só reembolso TOTAL confirmado pela Payments API autenticada.

    A resposta deve manter identificadores, conta recebedora, referência,
    moeda, ambiente e valor originais. Um status 'refunded' sem o montante
    reembolsado NÃO autoriza retirar acesso SaaS. Reembolsos parciais exigem
    política explícita e seguem bloqueados.
    """
    return (isinstance(payment, Mapping) and payment.get("status") == "refunded"
            and _matches_payment_identity(expected, payment)
            and _exact_cents(payment.get("transaction_amount_refunded"), expected.amount_cents))
