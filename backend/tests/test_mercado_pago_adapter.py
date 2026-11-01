import json
from decimal import Decimal

import pytest
from app.mercado_pago_adapter import PixCollectionRequest, build_create_pix_request, build_get_payment_request


def collection(**changes):
    values = dict(operation_id='tenant1:contribution1', amount_cents=10005, payer_email='pessoa@example.com', description='Contribuição', idempotency_key='operacao_1')
    values.update(changes)
    return PixCollectionRequest(**values)


def test_build_pix_with_exact_amount_and_stable_idempotency_without_network():
    first = build_create_pix_request(access_token='token-sintetico', payment=collection())
    second = build_create_pix_request(access_token='token-sintetico', payment=collection())
    payload = json.loads(first.content, parse_float=Decimal)
    assert first.method == 'POST' and str(first.url) == 'https://api.mercadopago.com/v1/payments'
    assert payload['transaction_amount'] == Decimal('100.05')
    assert payload['payment_method_id'] == 'pix' and payload['external_reference'] == 'tenant1:contribution1'
    assert first.headers['X-Idempotency-Key'] == second.headers['X-Idempotency-Key'] == 'operacao_1'
    assert first.content == second.content


@pytest.mark.parametrize('changes', [dict(amount_cents=0), dict(amount_cents=True), dict(idempotency_key=''), dict(operation_id='outro/tenant'), dict(payer_email='inválido')])
def test_invalid_pix_parameters_rejected(changes):
    with pytest.raises(ValueError):
        build_create_pix_request(access_token='token-sintetico', payment=collection(**changes))


def test_lookup_is_fixed_host_and_rejects_path_injection():
    request = build_get_payment_request(access_token='token-sintetico', provider_payment_id='123')
    assert str(request.url) == 'https://api.mercadopago.com/v1/payments/123'
    with pytest.raises(ValueError):
        build_get_payment_request(access_token='token-sintetico', provider_payment_id='../outro')
