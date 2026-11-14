"""M3500 — HTTP real moldado, testado só via MockTransport sem dinheiro."""
import json
from uuid import UUID
import httpx
import pytest

from app.pix_automation_contract import (
    ObligationKind, PaymentObligation, RegisteredPixDestination,
    LoanDisbursement,build_pix_command,build_disbursement_order,
)
from app.mp_pix_execution import (
    CONTRACT, ProviderCredentials, PixRecipient,
    ProviderRequestBlocked, ProviderOutcomeUnknown,
    create_collection_pix,read_collection_from_provider,
    build_payout_pix_request,submit_payout_pix,
)

T=UUID("00000000-0000-4000-8000-0000000000a1")
C=UUID("00000000-0000-4000-8000-0000000000a2")
M=UUID("00000000-0000-4000-8000-0000000000a3")
O=UUID("00000000-0000-4000-8000-0000000000a4")
L=UUID("00000000-0000-4000-8000-0000000000a5")
D=UUID("00000000-0000-4000-8000-0000000000a6")


def cmd():
    from datetime import date
    return build_pix_command(PaymentObligation(
        tenant_id=T,cycle_id=C,member_id=M,obligation_id=O,
        kind=ObligationKind.CONTRIBUTION,
        expected_cents=15000,already_paid_cents=0,
        due_date=date(2027,1,10),terms_version="accepted-2027-v1",
        provider_account_id="2002",environment="HOMOLOGACAO",
    ))


def cred(**changes):
    data=dict(account_id="2002",access_token="TEST_SANDBOX_ACCESS_TOKEN_123",
        environment="HOMOLOGACAO",account_binding_verified=True,
        capability_in=True,capability_out=True,
        provider_profile_verified=True,
        server_approved_for_real_network=False)
    data.update(changes)
    return ProviderCredentials(**data)


def qr_response(req):
    assert str(req.url)=="https://api.mercadopago.com/v1/payments"
    assert req.headers["x-idempotency-key"]==cmd().idempotency_key
    assert req.headers["authorization"].startswith("Bearer ")
    body=json.loads(req.content)
    assert body["transaction_amount"]==150
    assert body["payment_method_id"]=="pix"
    assert body["external_reference"]==cmd().external_reference
    return httpx.Response(201,json={
        "id":900001,"status":"pending","transaction_amount":"150.00",
        "collector_id":2002,"external_reference":cmd().external_reference,
        "currency_id":"BRL","live_mode":False,
        "point_of_interaction":{"transaction_data":{
            "qr_code":"00020126MOCK-CI-QR-NOT-PAYABLE",
            "qr_code_base64":"ZmFrZV9pbWFnZQ==",
        }},
    })


@pytest.mark.asyncio
async def test_create_pix_produces_real_shape_and_no_fake_settlement():
    c=await create_collection_pix(
        command=cmd(),credentials=cred(),payer_email="membro@example.invalid",
        transport=httpx.MockTransport(qr_response),
    )
    assert c.payment_id=="900001"
    assert c.amount_cents==15000
    assert c.qr_code.startswith("000201")
    assert c.capital_recognized is False
    assert c.bank_reconciled is False
    assert c.ledger_written is False
    assert "TEST_SANDBOX_ACCESS" not in repr(cred())


@pytest.mark.asyncio
@pytest.mark.parametrize("change",[
    {"collector_id":3003},{"live_mode":True},{"currency_id":"USD"},
    {"transaction_amount":"149.99"},
    {"external_reference":"wrong"},{"status":"approved"},
    {"point_of_interaction":{}},
])
async def test_invalid_provider_pix_creation_rejected(change):
    def respond(req):
        data=json.loads(qr_response(req).content)
        data.update(change)
        return httpx.Response(201,json=data)
    with pytest.raises(ProviderRequestBlocked):
        await create_collection_pix(
            command=cmd(),credentials=cred(),payer_email="membro@example.invalid",
            transport=httpx.MockTransport(respond),
        )


@pytest.mark.asyncio
async def test_provider_real_network_disabled_and_account_mismatch():
    with pytest.raises(ProviderRequestBlocked):
        await create_collection_pix(
            command=cmd(),credentials=cred(),payer_email="membro@example.invalid",
        )
    with pytest.raises(ProviderRequestBlocked):
        await create_collection_pix(
            command=cmd(),credentials=cred(account_id="3003"),
            payer_email="membro@example.invalid",
            transport=httpx.MockTransport(qr_response),
        )


@pytest.mark.asyncio
async def test_timeout_is_ambiguous_never_new_idempotency_key():
    def fail(req):
        raise httpx.ReadTimeout("mock")
    with pytest.raises(ProviderOutcomeUnknown):
        await create_collection_pix(
            command=cmd(),credentials=cred(),payer_email="membro@example.invalid",
            transport=httpx.MockTransport(fail),
        )


@pytest.mark.asyncio
async def test_authenticated_get_approved_is_not_bank_reconciliation():
    def get(req):
        assert req.method=="GET"
        return httpx.Response(200,json={
            "id":900001,"status":"approved","transaction_amount":"150.00",
            "collector_id":2002,"external_reference":cmd().external_reference,
            "currency_id":"BRL","live_mode":False,
        })
    result=await read_collection_from_provider(
        provider_payment_id="900001",operation=cmd(),credentials=cred(),
        transport=httpx.MockTransport(get),
    )
    assert result.verified_approved
    assert not result.bank_reconciled
    assert not result.ledger_written


@pytest.mark.asyncio
async def test_get_wrong_collector_or_ref_denied():
    def bad(req):
        return httpx.Response(200,json={
            "id":900001,"status":"approved","transaction_amount":"150.00",
            "collector_id":3003,"external_reference":"wrong",
            "currency_id":"BRL","live_mode":False,
        })
    with pytest.raises(ProviderRequestBlocked):
        await read_collection_from_provider(
            provider_payment_id="900001",operation=cmd(),credentials=cred(),
            transport=httpx.MockTransport(bad),
        )


def payout():
    destination=RegisteredPixDestination(
        tenant_id=T,member_id=M,destination_id=D,masked_key="***1234",
        fingerprint="a"*64,verified_owner=True,consent_active=True,
    )
    loan=LoanDisbursement(
        tenant_id=T,cycle_id=C,loan_id=L,member_id=M,
        principal_cents=50000,destination=destination,
        approved=True,reservation_confirmed=True,
        adequate_reconciled_cash=True,consent_valid=True,
        environment="HOMOLOGACAO",financial_role="TENANT_ADMIN",
        provider_out_capability=True,
    )
    recipient=PixRecipient(
        destination_id=str(D),key_type="PIX_CODE",
        pix_key="123e4567-e89b-12d3-a456-426614174000",
        identification_type="CPF",identification_number="12345678901",
        key_ownership_verified=True,
    )
    return build_disbursement_order(loan),recipient


def test_payout_request_has_exact_contract_and_no_money_sent():
    order,recipient=payout()
    req=build_payout_pix_request(
        order=order,recipient=recipient,credentials=cred(),
        provider_profile="BR_TRANSACTION_INTENTS_PROCESS_V1",
    )
    data=json.loads(req.content)
    assert req.method=="POST"
    assert req.url.path=="/v1/transaction-intents/process"
    assert req.headers["x-test-token"]=="true"
    assert req.headers["x-idempotency-key"]==order.idempotency_key
    assert data["external_reference"]==order.business_operation_id
    assert data["transaction"]["total_amount"]==500
    assert data["transaction"]["to"]["accounts"][0]["chave"]["type"]=="PIX_CODE"
    assert order.money_transferred is False
    assert recipient.pix_key not in repr(recipient)


@pytest.mark.asyncio
async def test_provider_payout_approved_never_claims_member_received_money():
    order,recipient=payout()
    def server(req):
        data=json.loads(req.content)
        assert data["external_reference"]==order.business_operation_id
        return httpx.Response(202,json={
            "id":"PAYOUT001","status":"approved",
            "external_reference":order.business_operation_id,
        })
    result=await submit_payout_pix(
        order=order,recipient=recipient,credentials=cred(),
        provider_profile="BR_TRANSACTION_INTENTS_PROCESS_V1",
        transport=httpx.MockTransport(server),
    )
    assert result.provider_status=="approved"
    assert result.financial_state.value=="PENDENTE_CONCILIACAO"
    assert result.money_transferred_confirmed is False
    assert result.bank_reconciled is False


@pytest.mark.asyncio
async def test_payout_production_without_verified_capability_is_denied():
    order,recipient=payout()
    with pytest.raises(ProviderRequestBlocked):
        await submit_payout_pix(
            order=order,recipient=recipient,
            credentials=cred(capability_out=False),
            provider_profile="BR_TRANSACTION_INTENTS_PROCESS_V1",
            transport=httpx.MockTransport(lambda req:httpx.Response(202,json={})),
        )
    with pytest.raises(ProviderRequestBlocked):
        await submit_payout_pix(
            order=order,recipient=recipient,credentials=cred(),
            provider_profile="BR_TRANSACTION_INTENTS_PROCESS_V1",
        )


@pytest.mark.parametrize("change",[
    {"key_ownership_verified":False},
    {"identification_number":"123"},
    {"pix_key":"bad\r\nsecret"},
])
def test_bad_destination_rejected_before_any_network(change):
    from dataclasses import replace
    order,recipient=payout()
    with pytest.raises(ProviderRequestBlocked):
        build_payout_pix_request(
            order=order,recipient=replace(recipient,**change),
            credentials=cred(),provider_profile="BR_TRANSACTION_INTENTS_PROCESS_V1",
        )


def test_raw_payout_credentials_not_exposed():
    assert "TEST_SANDBOX_ACCESS" not in repr(cred())
    assert "12345678901" not in repr(payout()[1])
