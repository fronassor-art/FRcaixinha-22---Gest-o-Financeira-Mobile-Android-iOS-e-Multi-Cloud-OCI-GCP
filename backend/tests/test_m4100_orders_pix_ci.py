"""M4100 Orders API: Brazilian Pix official shape, no artificial settlement."""
from copy import deepcopy
from datetime import date
from uuid import UUID
import json

import httpx
import pytest

from app.mp_orders_api import (
    CONTRACT, OrdersPixCheckout, create_order_pix, read_order_pix,
    build_create_order_pix_request,parse_created_order_pix,
    parse_read_order_pix,
)
from app.mp_pix_execution import ProviderCredentials, ProviderRequestBlocked
from app.pix_automation_contract import (
    PaymentObligation,ObligationKind,build_pix_command,
)

T=UUID("00000000-0000-4000-8000-0000000000a1")
C=UUID("00000000-0000-4000-8000-0000000000a2")
M=UUID("00000000-0000-4000-8000-0000000000a3")
O=UUID("00000000-0000-4000-8000-0000000000a4")
ORD="ORD01HRYFWNYRE1MR1E60MW3X0T2P"
PAY="PAY01HRYFXQ53Q3JPEC48MYWMR0TE"


def command(kind=ObligationKind.CONTRIBUTION,oid=O):
    return build_pix_command(PaymentObligation(
        tenant_id=T,cycle_id=C,member_id=M,obligation_id=oid,
        kind=kind,expected_cents=15000,already_paid_cents=0,
        due_date=date(2027,1,10),terms_version="signed-v2027-1",
        provider_account_id="2002",environment="HOMOLOGACAO",
        loan_id=UUID("00000000-0000-4000-8000-0000000000a5")
                if kind is ObligationKind.LOAN_INSTALLMENT else None,
    ))


def credentials(**updates):
    params=dict(account_id="2002",access_token="APP_USR_FAKE_TEST_TOKEN_12345",
                account_binding_verified=True,capability_in=True,
                environment="HOMOLOGACAO",server_approved_for_real_network=False)
    params.update(updates)
    return ProviderCredentials(**params)


def order_data(*,processed=False):
    s="processed" if processed else "action_required"
    d="accredited" if processed else "waiting_transfer"
    return {
        "id":ORD,"type":"online","processing_mode":"automatic",
        "country_code":"BRA","marketplace":"NONE",
        "external_reference":command().external_reference,
        "total_amount":"150.00","status":s,"status_detail":d,
        "transactions":{"payments":[{
            "id":PAY,"amount":"150.00","status":s,
            "status_detail":d,
            "payment_method":{
                "id":"pix","type":"bank_transfer",
                "qr_code":"00020126FAKE-ORDERS-PIXI",
                "qr_code_base64":"ZmFrZV9wbmc=",
                "ticket_url":"https://www.mercadopago.com.br/sandbox/payments/test/ticket",
            },
        }]},
    }


def test_orders_pix_request_has_exact_mlb_format_and_idempotency():
    req=build_create_order_pix_request(
        command=command(),credentials=credentials(),
        payer_email="member@example.invalid")
    data=json.loads(req.content)
    assert req.url.host=="api.mercadopago.com"
    assert req.url.path=="/v1/orders"
    assert req.method=="POST"
    assert req.headers["x-idempotency-key"]==command().idempotency_key
    assert data["type"]=="online"
    assert data["processing_mode"]=="automatic"
    assert data["external_reference"]==command().external_reference
    assert data["total_amount"]=="150.00"
    payment=data["transactions"]["payments"]
    assert len(payment)==1
    assert payment[0]["amount"]=="150.00"
    assert payment[0]["payment_method"]=={"id":"pix","type":"bank_transfer"}
    assert "expiration_time" not in data
    assert "notification_url" not in data
    assert "seller_id" not in data
    assert "access_token" not in json.dumps(data)


@pytest.mark.asyncio
async def test_real_http_shape_mock_only_no_money():
    def handler(req):
        assert req.url.path=="/v1/orders"
        return httpx.Response(201,json=order_data())
    c=await create_order_pix(
        command=command(),credentials=credentials(),
        payer_email="member@example.invalid",
        transport=httpx.MockTransport(handler))
    assert isinstance(c,OrdersPixCheckout)
    assert c.order_id==ORD
    assert c.payment_id==PAY
    assert c.status=="action_required"
    assert c.status_detail=="waiting_transfer"
    assert c.checkout_type=="orders_pix"
    assert c.qr_code.startswith("000201")
    assert not c.bank_reconciled
    assert not c.capital_recognized
    assert not c.ledger_written


@pytest.mark.asyncio
async def test_authenticated_get_processed_still_not_bank_settlement():
    def handler(req):
        assert req.method=="GET"
        assert req.url.path=="/v1/orders/"+ORD
        return httpx.Response(200,json=order_data(processed=True))
    result=await read_order_pix(
        order_id=ORD,command=command(),credentials=credentials(),
        transport=httpx.MockTransport(handler))
    assert result.ready_for_independent_settlement_lookup is True
    assert result.provider_response_structure_verified is True
    assert result.bank_reconciled is False
    assert result.ledger_written is False
    assert result.financial_effect_applied is False


@pytest.mark.asyncio
async def test_get_waiting_transfer_cannot_trigger_ledger():
    result=await read_order_pix(
        order_id=ORD,command=command(),credentials=credentials(),
        transport=httpx.MockTransport(
            lambda _:httpx.Response(200,json=order_data())))
    assert result.ready_for_independent_settlement_lookup is False


@pytest.mark.parametrize("change",[
    ("id","ORDbad!"),("external_reference","other"),
    ("total_amount","149.99"),("country_code","ARG"),
    ("marketplace","SPLIT"),("status","processed"),
    ("status_detail","accredited"),("processing_mode","manual"),
    ("type","point"),
])
def test_wrong_order_or_status_cannot_render_payable_qr(change):
    data=order_data()
    data[change[0]]=change[1]
    with pytest.raises(ProviderRequestBlocked):
        parse_created_order_pix(
            data=data,command=command(),credentials=credentials())


@pytest.mark.parametrize("field,value",[
    ("id","PAYbad"),("amount","151.00"),
    ("status","processed"),("status_detail","accredited"),
])
def test_wrong_transaction_rejected(field,value):
    data=order_data()
    data["transactions"]["payments"][0][field]=value
    with pytest.raises(ProviderRequestBlocked):
        parse_created_order_pix(
            data=data,command=command(),credentials=credentials())


@pytest.mark.parametrize("field,value",[
    ("id","credit_card"),("type","credit_card"),
    ("qr_code",None),
    ("qr_code",""),
    ("ticket_url","http://redirect.example.invalid/pay"),
    ("qr_code_base64","!!!"),
])
def test_unsafe_pix_method_rejected(field,value):
    data=order_data()
    data["transactions"]["payments"][0]["payment_method"][field]=value
    with pytest.raises(ProviderRequestBlocked):
        parse_created_order_pix(
            data=data,command=command(),credentials=credentials())


@pytest.mark.parametrize("change",[
    ("live_mode",True),("user_id","3333"),("collector_id","9999"),
])
def test_identity_mismatch_rejected(change):
    data=order_data()
    data[change[0]]=change[1]
    with pytest.raises(ProviderRequestBlocked):
        parse_created_order_pix(
            data=data,command=command(),credentials=credentials())


def test_more_than_one_payment_cannot_match_single_obligation():
    data=order_data()
    data["transactions"]["payments"].append(deepcopy(
        data["transactions"]["payments"][0]))
    with pytest.raises(ProviderRequestBlocked):
        parse_created_order_pix(
            data=data,command=command(),credentials=credentials())


@pytest.mark.asyncio
async def test_no_unapproved_real_https_outbound():
    with pytest.raises(ProviderRequestBlocked):
        await create_order_pix(
            command=command(),credentials=credentials(),
            payer_email="member@example.invalid")
    with pytest.raises(ProviderRequestBlocked):
        await read_order_pix(
            order_id=ORD,command=command(),credentials=credentials())


def test_per_month_and_per_loan_ids_differ():
    another=command(oid=UUID("00000000-0000-4000-8000-0000000000a6"))
    loan=command(kind=ObligationKind.LOAN_INSTALLMENT)
    assert len({command().idempotency_key,
                another.idempotency_key,loan.idempotency_key})==3


def test_orders_read_must_match_exact_identity():
    data=order_data(processed=True)
    with pytest.raises(ProviderRequestBlocked):
        parse_read_order_pix(data=data,order_id="ORD01OTHERPAYMENT12345678",
            command=command(),credentials=credentials())
    data=order_data(processed=True)
    data["transactions"]["payments"][0]["amount"]="151.00"
    with pytest.raises(ProviderRequestBlocked):
        parse_read_order_pix(data=data,order_id=ORD,
            command=command(),credentials=credentials())


def test_does_not_claim_bank_connected():
    assert CONTRACT=="AI_STUDIO_M4100_MLB_ORDERS_PIX_V1"


def test_official_pix_test_response_allows_empty_qr_base64():
    # MP official Orders Pix APRO fixture has a QR string but "" for image.
    data=order_data()
    data["transactions"]["payments"][0]["payment_method"]["qr_code_base64"]=""
    checkout=parse_created_order_pix(
        data=data,command=command(),credentials=credentials())
    assert checkout.qr_code_base64 is None
    assert checkout.qr_code.startswith("000201")
    assert checkout.bank_reconciled is False
    assert checkout.ledger_written is False


@pytest.mark.parametrize("value",[None,42,{},[]])
def test_orders_reject_nontext_payment_status_without_type_error(value):
    data=order_data()
    data["transactions"]["payments"][0]["status"]=value
    with pytest.raises(ProviderRequestBlocked):
        parse_created_order_pix(
            data=data,command=command(),credentials=credentials())
