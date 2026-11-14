"""M4300: Money Out never enabled by flags, unsigned production denied."""
from dataclasses import replace
from uuid import UUID
import pytest
from app.mp_money_out_policy import MoneyOutGate,evaluate_money_out_gate
from app.mp_pix_execution import (
    ProviderCredentials,PixRecipient,ProviderRequestBlocked,
    build_payout_pix_request,
)
from app.pix_automation_contract import DisbursementOrder

T=UUID("00000000-0000-4000-8000-0000000000a1")
M=UUID("00000000-0000-4000-8000-0000000000a2")
L=UUID("00000000-0000-4000-8000-0000000000a3")
D=UUID("00000000-0000-4000-8000-0000000000a4")


def gate(**overrides):
    params=dict(tenant_id=T,provider_account_id="2002",
        environment="HOMOLOGACAO",admin_account_connected=True,
        application_authorized=True,commercial_money_out_approved=True,
        loan_disbursement_use_case_approved=True,
        legal_and_compliance_approved=True,account_balance_verified=True,
        recipient_pix_key_verified=True,destination_ownership_verified=True,
        signed_body_validated=True,signature_key_in_server_vault=True,
        webhook_and_get_verified=True,atomic_reservation_ready=True,
        audit_artifact_id="MP_COMPLIANCE_PROOF_2027")
    params.update(overrides)
    return MoneyOutGate(**params)


def test_all_green_is_only_review_never_send():
    report=evaluate_money_out_gate(gate())
    assert report.eligible_for_manual_review
    assert report.sandbox_dryrun_allowed
    assert not report.production_execution_authorized
    assert not report.money_transferred
    assert not report.ledger_written


@pytest.mark.parametrize("field",(
    "admin_account_connected","application_authorized",
    "commercial_money_out_approved","loan_disbursement_use_case_approved",
    "legal_and_compliance_approved","account_balance_verified",
    "recipient_pix_key_verified","destination_ownership_verified",
    "signed_body_validated","signature_key_in_server_vault",
    "webhook_and_get_verified","atomic_reservation_ready",
))
def test_one_missing_precondition_disables_dryrun(field):
    report=evaluate_money_out_gate(gate(**{field:False}))
    assert report.pending
    assert not report.eligible_for_manual_review
    assert not report.sandbox_dryrun_allowed


def test_commercial_not_an_app_user_role():
    report=evaluate_money_out_gate(gate(audit_artifact_id=None))
    assert "INDEPENDENT_PROVIDER_ATTESTATION" in report.pending
    report=evaluate_money_out_gate(gate(environment="PRODUCAO"))
    assert "PRODUCTION_POLICY_DISABLED_UNTIL_EXTERNAL_SIGNOFF" in report.pending
    assert not report.production_execution_authorized


def payout_request(env="HOMOLOGACAO"):
    order=DisbursementOrder(
        tenant_id=T,loan_id=L,member_id=M,destination_id=D,
        amount_cents=50000,
        business_operation_id="L_"+"a"*40,
        idempotency_key="payout_"+"a"*40,
    )
    recipient=PixRecipient(
        destination_id=str(D),key_type="PIX_CODE",
        pix_key="123e4567-e89b-12d3-a456-426614174000",
        identification_type="CPF",identification_number="12345678901",
        key_ownership_verified=True,
    )
    creds=ProviderCredentials(
        account_id="2002",access_token="TEST_SANDBOX_OAUTH_TOKEN_123456",
        environment=env,account_binding_verified=True,
        capability_out=True,provider_profile_verified=True,
        server_approved_for_real_network=True,
    )
    return order,recipient,creds


def test_existing_payout_port_blocks_unsigned_production_even_if_flags_true():
    order,recipient,credentials=payout_request("PRODUCAO")
    with pytest.raises(ProviderRequestBlocked):
        build_payout_pix_request(
            order=order,recipient=recipient,credentials=credentials,
            provider_profile="BR_TRANSACTION_INTENTS_PROCESS_V1",
        )


def test_staging_payout_request_explicitly_disables_signature_enforcement():
    order,recipient,credentials=payout_request()
    req=build_payout_pix_request(
        order=order,recipient=recipient,credentials=credentials,
        provider_profile="BR_TRANSACTION_INTENTS_PROCESS_V1",
    )
    assert req.headers["x-enforce-signature"]=="false"
    assert "x-signature" not in req.headers
    assert req.headers["x-idempotency-key"]==order.idempotency_key
