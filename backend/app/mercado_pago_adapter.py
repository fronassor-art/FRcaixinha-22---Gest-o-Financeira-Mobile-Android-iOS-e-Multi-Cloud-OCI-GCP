"""Serialização do Checkout API Pix; chamadas externas ainda não habilitadas.

Este módulo apenas constrói requisições; não envia, não obtém tokens e não
altera ledger. A conexão depende dos controles e da homologação pendentes.
"""
from dataclasses import dataclass
from decimal import Decimal
import json
import re
from urllib.parse import quote

import httpx

_BASE_URL = 'https://api.mercadopago.com'


@dataclass(frozen=True)
class PixCollectionRequest:
    operation_id: str
    amount_cents: int
    payer_email: str
    description: str
    idempotency_key: str


def _headers(token: str) -> dict[str, str]:
    if not isinstance(token, str) or not token.strip() or any(c in token for c in '\r\n'):
        raise ValueError('Credencial ausente ou inválida')
    return {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}


def build_create_pix_request(*, access_token: str, payment: PixCollectionRequest) -> httpx.Request:
    """Prepara POST sem enviá-lo. Chave e referência vêm de operação persistida."""
    if (not isinstance(payment.amount_cents, int) or isinstance(payment.amount_cents, bool)
            or payment.amount_cents <= 0 or payment.amount_cents > 999999999999):
        raise ValueError('Valor inválido')
    if (not re.fullmatch(r'[A-Za-z0-9._:-]{1,100}', payment.operation_id)
            or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', payment.idempotency_key)):
        raise ValueError('Identificador ou chave de idempotência inválido')
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', payment.payer_email) or len(payment.payer_email) > 254:
        raise ValueError('E-mail do pagador inválido')
    if not payment.description or len(payment.description) > 255:
        raise ValueError('Descrição inválida')
    headers = _headers(access_token)
    headers['X-Idempotency-Key'] = payment.idempotency_key
    # Insere o valor decimal diretamente no JSON, sem conversão binária float.
    amount = format(Decimal(payment.amount_cents) / Decimal(100), '.2f')
    body = {
        'description': payment.description, 'payment_method_id': 'pix',
        'payer': {'email': payment.payer_email}, 'external_reference': payment.operation_id,
    }
    content = '{"transaction_amount":' + amount + ',' + json.dumps(body, ensure_ascii=True, separators=(',', ':'))[1:]
    return httpx.Request('POST', f'{_BASE_URL}/v1/payments', headers=headers, content=content.encode('utf-8'))


def build_get_payment_request(*, access_token: str, provider_payment_id: str) -> httpx.Request:
    """Prepara consulta por ID numérico conhecido; não executa a consulta."""
    if not re.fullmatch(r'[0-9]{1,40}', provider_payment_id):
        raise ValueError('Identificador de pagamento inválido')
    return httpx.Request('GET', f'{_BASE_URL}/v1/payments/{quote(provider_payment_id, safe="")}', headers=_headers(access_token))


@dataclass(frozen=True)
class PixCollectionResponse:
    provider_payment_id: str
    status: str
    qr_code: str | None


def parse_collection_response(response: httpx.Response, *, expected: PixCollectionRequest,
                              collector_id: str, live_mode: bool) -> PixCollectionResponse:
    """Valida resposta de cobrança recebida por canal autenticado, sem contabilizar.

    A resposta de webhook nunca deve ser passada como resposta da API do provedor.
    O chamador será responsável por persistir os IDs e conciliar o pagamento.
    """
    if response.status_code not in (200, 201) or len(response.content) > 65536:
        raise ValueError('Resposta do provedor indisponível ou inválida')
    try:
        data = json.loads(response.content, parse_float=Decimal)
        payment_id = str(data['id'])
        amount = data['transaction_amount']
        status = data['status']
        if (not re.fullmatch(r'[0-9]{1,40}', payment_id) or isinstance(amount, bool)
                or not isinstance(amount, (Decimal, int, str))
                or not Decimal(amount).is_finite()
                or Decimal(amount) * 100 != expected.amount_cents
                or not collector_id or str(data['collector_id']) != collector_id
                or data['external_reference'] != expected.operation_id
                or data['currency_id'] != 'BRL' or data['live_mode'] is not live_mode
                or status not in ('pending', 'in_process', 'approved', 'rejected', 'cancelled')):
            raise ValueError('Resposta não corresponde à cobrança esperada')
        interaction = data.get('point_of_interaction') or {}
        if not isinstance(interaction, dict):
            raise ValueError('Interação inválida')
        tx_data = interaction.get('transaction_data') or {}
        if not isinstance(tx_data, dict):
            raise ValueError('Dados Pix inválidos')
        qr = tx_data.get('qr_code')
        if qr is not None and (not isinstance(qr, str) or not qr or len(qr) > 4096):
            raise ValueError('Código Pix inválido')
        return PixCollectionResponse(provider_payment_id=payment_id, status=status, qr_code=qr)
    except (KeyError, TypeError, ValueError, ArithmeticError):
        raise ValueError('Resposta do provedor inválida ou divergente') from None
