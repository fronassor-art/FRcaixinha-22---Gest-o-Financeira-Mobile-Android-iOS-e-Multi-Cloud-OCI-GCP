import hashlib
import hmac
from decimal import Decimal

from app.mercado_pago_safety import ExpectedPayment, matches_approved_payment, matches_full_refund, verify_webhook_signature


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



def test_refund_requires_full_amount_and_same_platform_collector():
    expected = ExpectedPayment('123', '456', 'saas:license-1', 8990, False)
    refund = dict(
        id=123, collector_id=456, external_reference='saas:license-1',
        transaction_amount=Decimal('89.90'), transaction_amount_refunded=Decimal('89.90'),
        currency_id='BRL', status='refunded', live_mode=False
    )
    assert matches_full_refund(expected, refund)
    assert not matches_approved_payment(expected, refund)
    for invalid in (
        {'transaction_amount_refunded':'10.00'},
        {'transaction_amount_refunded':None},
        {'transaction_amount_refunded':89.90},
        {'transaction_amount_refunded':True},
        {'status':'approved'},
        {'collector_id':789},
        {'external_reference':'saas:other'},
        {'live_mode':True},
    ):
        assert not matches_full_refund(expected, {**refund, **invalid})


def test_m41600_exact_cent_comparison_independent_of_decimal_context():
    from decimal import localcontext
    expected = ExpectedPayment("123", "456", "saas:license", 10050, False)
    payment = dict(id=123, collector_id=456, external_reference="saas:license",
                   currency_id="BRL", live_mode=False, status="approved")
    with localcontext() as ctx:
        ctx.prec = 3
        assert matches_approved_payment(expected, {**payment,"transaction_amount":"100.50"})
        for amount in ("100.50000000000000000000000000001", "100.49999999999999999999999999999",
                       "1e100000000", "1e-100000000", Decimal("sNaN"), True, 100.50):
            assert not matches_approved_payment(expected,{**payment,"transaction_amount":amount})
        refund = {**payment,"status":"refunded","transaction_amount":"100.50"}
        assert matches_full_refund(expected,{**refund,"transaction_amount_refunded":"100.50"})
        assert not matches_full_refund(expected,{**refund,"transaction_amount_refunded":"100.50000000000000000000001"})


def test_m41600_approved_with_refund_or_malformed_identity_denied():
    expected = ExpectedPayment("123","456","saas:license",10050,False)
    payment = dict(id=123,collector_id=456,external_reference="saas:license",
                   currency_id="BRL",live_mode=False,status="approved",transaction_amount="100.50")
    for refund in ("0","0.00",0,Decimal("0.00")):
        assert matches_approved_payment(expected,{**payment,"transaction_amount_refunded":refund})
    for refund in ("0.01","100.50",None,False,0.0,Decimal("NaN")):
        assert not matches_approved_payment(expected,{**payment,"transaction_amount_refunded":refund})
    for changes in ({"id":123.0},{"collector_id":456.0},{"id":True},{"live_mode":0}):
        assert not matches_approved_payment(expected,{**payment,**changes})
    assert not matches_approved_payment(ExpectedPayment("123","456","saas:license",10050,0),{**payment,"live_mode":0})
