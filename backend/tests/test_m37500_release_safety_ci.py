"""M37500: adversarial pure gates: zero external operations, zero real approvals."""
from dataclasses import replace
import pytest

from app.m37500_release_safety import (
    GateDecision, MemberAdmission, MailOutbox, PaymentReconciliation,
    StagingInfrastructure, review_member, review_mail, review_payment,
    review_infrastructure, review_annual_distribution, all_real_actions_off,
)

T = "10000000-0000-4000-8000-000000000001"
U = "10000000-0000-4000-8000-000000000002"
A = "10000000-0000-4000-8000-000000000003"
B = "10000000-0000-4000-8000-000000000004"
OTHER = "10000000-0000-4000-8000-000000000005"
HASH = "a" * 64
KEY = "m37500_sandbox_idempotency_key_0001"


def member(**changes):
    x = dict(
        tenant_id=T, invitation_tenant_id=T,
        subject_id=U, invitation_subject_id=U, admin_id=A,
        independent_approver_id=B, request_key=KEY, previous_request_key=None,
        published_contract_sha=HASH, accepted_contract_sha=HASH,
        email_ownership_consumed=True, subject_identity_verified=True,
        consent_affirmative=True, admin_approved=True,
        independent_approved=True, master_mfa_verified=True,
        contribution_cents=15000, overdue_days=0,
    )
    x.update(changes)
    return MemberAdmission(**x)


def mail(**changes):
    x = dict(
        tenant_id=T, request_key=KEY, recipient_digest=HASH,
        encrypted_envelope_digest="b" * 64, challenged_at_epoch=1000,
        expires_at_epoch=1300, now_epoch=1100, attempts=0,
        provider_state="DELIVERED", ownership_proven=True,
        duplicate_claim_observed=False,
    )
    x.update(changes)
    return MailOutbox(**x)


def payment(**changes):
    x = dict(
        tenant_id=T, provider_tenant_id=T, ledger_tenant_id=T,
        request_key=KEY, provider_payment_id="12345678",
        order_amount_cents=15000, provider_amount_cents=15000,
        ledger_amount_cents=15000, currency="BRL",
        provider_state="APPROVED", webhook_signature_verified=True,
        direct_provider_readback_verified=True, provider_test_mode=True,
        ledger_reference_unique=True, reversal_or_dispute_observed=False,
        previously_seen_request=False,
    )
    x.update(changes)
    return PaymentReconciliation(**x)


def infra(**changes):
    x = dict(
        region="sa-saopaulo-1", staging_vm_running=1,
        staging_vm_provisioning=0, active_vaults=1, project_dynamic_groups=1,
        internet_route_configured=True, public_https_443_ingress=True,
        public_ssh_22_ingress=False, public_database_ingress=False,
        tls_endpoint_verified=True, backup_restore_verified=True,
        iam_instance_principal_verified=True,
    )
    x.update(changes)
    return StagingInfrastructure(**x)


@pytest.mark.parametrize("review,sample", [
    (review_member, member),
    (review_mail, mail),
    (review_payment, payment),
    (review_infrastructure, infra),
])
def test_valid_synthetic_preflight_cannot_authorize_real_operation(review, sample):
    x = review(sample())
    assert x.sandbox_candidate and not x.failures
    assert x.code.endswith("SANDBOX_CANDIDATE_ONLY")
    assert not x.real_activation_authorized
    assert not x.provider_payment_authorized
    assert not x.pix_real_authorized
    assert all_real_actions_off(x)


@pytest.mark.parametrize("field,value", [
    ("tenant_id", OTHER),
    ("invitation_tenant_id", OTHER),
    ("subject_id", OTHER),
    ("invitation_subject_id", OTHER),
    ("subject_id", A),
    ("admin_id", B),
    ("admin_id", U),
    ("independent_approver_id", U),
    ("request_key", "short"),
    ("previous_request_key", KEY),
    ("published_contract_sha", "invalid"),
    ("accepted_contract_sha", "b" * 64),
    ("email_ownership_consumed", False),
    ("email_ownership_consumed", "TRUE"),
    ("subject_identity_verified", False),
    ("consent_affirmative", False),
    ("admin_approved", False),
    ("independent_approved", False),
    ("master_mfa_verified", False),
    ("contribution_cents", 14999),
    ("contribution_cents", True),
    ("contribution_cents", -1),
    ("contribution_cents", 10**12),
    ("overdue_days", 90),
    ("overdue_days", 100),
    ("overdue_days", -1),
    ("overdue_days", True),
])
def test_member_rejects_missing_or_forged_evidence(field, value):
    x = review_member(member(**{field: value}))
    assert x.failures and not x.sandbox_candidate
    assert all_real_actions_off(x)


@pytest.mark.parametrize("field,value", [
    ("tenant_id", OTHER.upper()),
    ("request_key", "fake"),
    ("recipient_digest", "plaintext@example.com"),
    ("encrypted_envelope_digest", "x"),
    ("challenged_at_epoch", "1000"),
    ("expires_at_epoch", 1000),
    ("expires_at_epoch", 2000),
    ("now_epoch", 1300),
    ("now_epoch", 900),
    ("attempts", 3),
    ("attempts", -1),
    ("attempts", True),
    ("provider_state", "ACCEPTED"),
    ("provider_state", "PENDING"),
    ("provider_state", "BOUNCED"),
    ("provider_state", "UNKNOWN"),
    ("ownership_proven", False),
    ("duplicate_claim_observed", True),
])
def test_mail_fail_closed_before_sandbox_candidate(field, value):
    x = review_mail(mail(**{field: value}))
    assert x.failures and not x.sandbox_candidate
    assert all_real_actions_off(x)


@pytest.mark.parametrize("field,value", [
    ("provider_tenant_id", OTHER),
    ("ledger_tenant_id", OTHER),
    ("request_key", "bad"),
    ("provider_payment_id", "pay_123"),
    ("order_amount_cents", 14999),
    ("provider_amount_cents", 14999),
    ("ledger_amount_cents", 14999),
    ("order_amount_cents", 0),
    ("order_amount_cents", True),
    ("currency", "USD"),
    ("provider_state", "PENDING"),
    ("provider_state", "REVERSED"),
    ("webhook_signature_verified", False),
    ("webhook_signature_verified", "true"),
    ("direct_provider_readback_verified", False),
    ("provider_test_mode", False),
    ("ledger_reference_unique", False),
    ("reversal_or_dispute_observed", True),
    ("previously_seen_request", True),
])
def test_three_source_payment_rejects_mismatch_or_replay(field, value):
    x = review_payment(payment(**{field: value}))
    assert x.failures and not x.sandbox_candidate
    assert all_real_actions_off(x)


@pytest.mark.parametrize("field,value", [
    ("region", "us-ashburn-1"),
    ("staging_vm_running", 0),
    ("staging_vm_running", True),
    ("staging_vm_provisioning", -1),
    ("active_vaults", 0),
    ("project_dynamic_groups", 0),
    ("internet_route_configured", False),
    ("public_https_443_ingress", False),
    ("public_ssh_22_ingress", True),
    ("public_database_ingress", True),
    ("tls_endpoint_verified", False),
    ("backup_restore_verified", False),
    ("iam_instance_principal_verified", False),
])
def test_oci_preflight_rejects_missing_infrastructure(field, value):
    x = review_infrastructure(infra(**{field: value}))
    assert x.failures and not x.sandbox_candidate


def test_real_user_observed_oci_readback_is_blocked_without_vm_https_iam_vault():
    x = review_infrastructure(infra(
        staging_vm_running=0, active_vaults=0, project_dynamic_groups=0,
        public_https_443_ingress=False, tls_endpoint_verified=False,
        backup_restore_verified=False, iam_instance_principal_verified=False,
    ))
    assert "NO_RUNNING_STAGING_VM" in x.failures
    assert "HTTPS_443_INGRESS_MISSING" in x.failures
    assert "VAULT_OR_IAM_GROUP_NOT_READY" in x.failures
    assert not x.real_activation_authorized


@pytest.mark.parametrize("total,admin,members,overdue,approved", [
    (10000, 1500, 8500, False, True),
    (10001, 1500, 8501, False, True),
    (0, 0, 0, False, True),
    (10000, 1600, 8400, False, False),
    (10000, 1500, 8500, True, False),
    (10000, 1500, 8500, None, False),
    (10000, 1500, 8400, False, False),
    (True, 0, 0, False, False),
    (-1, 0, 0, False, False),
])
def test_annual_distribution_is_integer_cent_exact_and_never_paid(
    total, admin, members, overdue, approved
):
    x = review_annual_distribution(
        total_profit_cents=total, admin_cents=admin,
        members_cents=members, overdue_member_included=overdue,
    )
    assert x.sandbox_candidate is approved
    assert all_real_actions_off(x)


@pytest.mark.parametrize("review", [
    review_member, review_mail, review_payment, review_infrastructure,
])
def test_wrong_evidence_type_denied(review):
    x = review("not a typed proof")
    assert x.failures == ("WRONG_EVIDENCE_TYPE",)
    assert all_real_actions_off(x)


def test_gate_decision_cannot_be_forged_into_real_activation():
    with pytest.raises(ValueError):
        GateDecision("FAKE", (), True, real_activation_authorized=True)
    with pytest.raises(ValueError):
        GateDecision("FAKE", (), True, provider_payment_authorized=True)
    with pytest.raises(ValueError):
        GateDecision("FAKE", (), True, pix_real_authorized=True)
    with pytest.raises(ValueError):
        GateDecision("FAKE", (), False)
    with pytest.raises(ValueError):
        GateDecision("FAKE", ("FAIL",), True)
    assert not all_real_actions_off()
    assert not all_real_actions_off("junk")
