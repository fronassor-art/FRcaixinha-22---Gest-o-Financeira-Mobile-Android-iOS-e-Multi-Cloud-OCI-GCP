"""Validações sem efeitos para futura integração Mercado Pago.

Este módulo NÃO envia cobranças, recebe webhooks, consulta o provedor,
armazena tokens, concilia automaticamente ou altera o razão contábil.
"""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
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


def matches_approved_payment(expected: ExpectedPayment, payment: Mapping[str, Any]) -> bool:
    """Confere resposta autoritativa recebida do provedor; não liquida obrigação.

    O chamador deve obter a resposta por canal autenticado usando a conta correta;
    payload de webhook ou dados enviados pelo cliente não são prova de pagamento.
    """
    if not isinstance(expected.amount_cents, int) or isinstance(expected.amount_cents, bool) or expected.amount_cents <= 0:
        return False
    if not all((expected.provider_payment_id, expected.collector_id, expected.external_reference)):
        return False
    if not isinstance(payment, Mapping) or payment.get('status') != 'approved' or payment.get('currency_id') != 'BRL':
        return False
    if payment.get('live_mode') is not expected.live_mode:
        return False
    if (str(payment.get('id', '')) != expected.provider_payment_id or
            str(payment.get('collector_id', '')) != expected.collector_id or
            payment.get('external_reference') != expected.external_reference):
        return False
    amount = payment.get('transaction_amount')
    if isinstance(amount, bool) or not isinstance(amount, (str, int, Decimal)):
        return False
    try:
        value = Decimal(amount)
        return value.is_finite() and value > 0 and value * 100 == Decimal(expected.amount_cents)
    except (InvalidOperation, ValueError):
        return False



def matches_full_refund(expected: ExpectedPayment, payment: Mapping[str, Any]) -> bool:
    """Aceita só reembolso TOTAL confirmado pela Payments API autenticada.

    A resposta deve manter identificadores, conta recebedora, referência,
    moeda, ambiente e valor originais. Um status 'refunded' sem o montante
    reembolsado NÃO autoriza retirar acesso SaaS. Reembolsos parciais exigem
    política explícita e seguem bloqueados.
    """
    if not isinstance(payment, Mapping) or payment.get('status') != 'refunded':
        return False
    refunded = payment.get('transaction_amount_refunded')
    if isinstance(refunded, bool) or not isinstance(refunded, (str, int, Decimal)):
        return False
    try:
        amount = Decimal(refunded)
        if (not amount.is_finite() or amount <= 0
                or amount * 100 != Decimal(expected.amount_cents)):
            return False
    except (InvalidOperation, ValueError, TypeError):
        return False
    # Somente reutiliza o verificador dos campos imutáveis da operação.
    # O campo status é verificado acima como refunded, não aprovado.
    original = dict(payment)
    original['status'] = 'approved'
    return matches_approved_payment(expected, original)
