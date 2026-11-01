import hashlib
import hmac
from decimal import Decimal

from app.mercado_pago_safety import ExpectedPayment, matches_approved_payment, verify_webhook_signature


def test_webhook_signature_rejects_tampering_and_duplicates():
    secret, request_id, resource_id, ts = 'segredo-sintetico', 'solicitacao-1', 'ABC123', '1700000000'
    digest = hmac.new(secret.encode(), f'id:abc123;request-id:{request_id};ts:{ts};'.encode(), hashlib.sha256).hexdigest()
    args = dict(secret=secret, signature=f'ts={ts},v1={digest}', request_id=request_id, resource_id=resource_id)
    assert verify_webhook_signature(**args)
    assert not verify_webhook_signature(**{**args, 'resource_id': 'outro'})
    assert not verify_webhook_signature(**{**args, 'signature': f'ts={ts},v1={digest},v1={digest}'})
    assert not verify_webhook_signature(**{**args, 'secret': ''})
    assert not verify_webhook_signature(**{**args, 'request_id': 'outro;id:injetado'})


def test_reconciliation_requires_matching_approved_provider_record():
    expected = ExpectedPayment('123', '456', 'tenant-a:contrib-1', 10050, False)
    valid = dict(id=123, collector_id=456, external_reference='tenant-a:contrib-1', transaction_amount=Decimal('100.50'), currency_id='BRL', status='approved', live_mode=False)
    assert matches_approved_payment(expected, valid)
    for change in ({'status': 'pending'}, {'transaction_amount': '100.51'}, {'collector_id': 999},
                   {'external_reference': 'tenant-b:contrib-1'}, {'live_mode': True},
                   {'currency_id': 'USD'}, {'transaction_amount': 100.50}):
        assert not matches_approved_payment(expected, {**valid, **change})
