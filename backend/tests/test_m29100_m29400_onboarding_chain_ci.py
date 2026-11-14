"""M29100–M29400: Master -> Admin -> Member correlation and fail-closed CI.

No database or external service. A passing positive case proves only that the
cross-step constraints are mutually consistent in a synthetic fixture.
"""
from dataclasses import replace
from pathlib import Path
from uuid import uuid4
import inspect
import pytest
from fastapi import HTTPException

from app.onboarding_chain_policy import JourneyCase, assess_journey, readiness_contract
from app.dependencies import AuthenticatedSession
from app.models import InvitationCreateRequest, ForgotPasswordRequest
from app.routers.invitations import create_invitation
from app.routers.auth import forgot_password
from app.config import settings

ROOT = Path(__file__).resolve().parents[2]


def sample(flow="ADMIN"):
    tenant, actor, recipient, reviewer, invitation, doc = [uuid4() for _ in range(6)]
    admin = flow == "ADMIN"
    return JourneyCase(
        flow=flow, now=500, tenant_id=tenant, actor_id=actor,
        actor_role="MASTER" if admin else "TENANT_ADMIN",
        actor_tenant_id=None if admin else tenant,
        actor_is_master=admin, recipient_id=recipient,
        reviewer_id=reviewer, reviewer_tenant_id=tenant,
        reviewer_approved=True, master_mfa_claimed=admin,
        expected_revision=8, observed_revision=8,
        invitation_id=invitation, invitation_tenant_id=tenant,
        invitation_recipient_id=recipient,
        invitation_target_role="TENANT_ADMIN" if admin else "TENANT_MEMBER",
        invitation_document_id=doc, invitation_expires_at=1000,
        invitation_consumptions=1, invitation_revoked=False,
        challenge_invitation_id=invitation, challenge_recipient_id=recipient,
        challenge_expires_at=800, challenge_consumptions=1,
        email_verified_claimed=True, delivery_status="DELIVERED",
        published_document_id=doc, published_sha256="a"*64,
        accepted_sha256="a"*64, consent_actor_id=recipient,
        consent_explicit=True, session_user_id=recipient,
        session_tenant_id=tenant,
        session_role="TENANT_ADMIN" if admin else "TENANT_MEMBER",
        session_active_claimed=True,
    )


@pytest.mark.parametrize("flow", ["ADMIN", "MEMBER"])
def test_hypothetical_clean_journey_still_does_not_activate(flow):
    report = assess_journey(sample(flow))
    assert report["policy_consistent_hypothetically"] is True
    assert report["violations"] == []
    assert report["production_authorized"] is False
    assert report["assertions_from_trusted_db"] is False
    assert report["real_invitation_enabled"] is False
    assert report["real_account_activation_enabled"] is False
    assert report["writes_performed"] is False


@pytest.mark.parametrize("changes,code", [
    ({"actor_role": "TENANT_MEMBER"}, "MASTER_CONTEXT_INVALID"),
    ({"actor_is_master": False}, "MASTER_CONTEXT_INVALID"),
    ({"actor_tenant_id": uuid4()}, "MASTER_CONTEXT_INVALID"),
    ({"master_mfa_claimed": False}, "MASTER_MFA_NOT_CLAIMED"),
    ({"reviewer_approved": False}, "INDEPENDENT_REVIEW_NOT_MATCHED"),
    ({"reviewer_tenant_id": uuid4()}, "INDEPENDENT_REVIEW_NOT_MATCHED"),
    ({"expected_revision": 9}, "REVIEW_REVISION_CONFLICT"),
    ({"invitation_tenant_id": uuid4()}, "INVITATION_SCOPE_MISMATCH"),
    ({"invitation_recipient_id": uuid4()}, "INVITATION_SCOPE_MISMATCH"),
    ({"invitation_target_role": "TENANT_MEMBER"}, "INVITATION_SCOPE_MISMATCH"),
    ({"invitation_revoked": True}, "INVITATION_REVOKED_OR_EXPIRED"),
    ({"invitation_expires_at": 500}, "INVITATION_REVOKED_OR_EXPIRED"),
    ({"invitation_consumptions": 0}, "INVITATION_SINGLE_USE_NOT_MATCHED"),
    ({"invitation_consumptions": 2}, "INVITATION_SINGLE_USE_NOT_MATCHED"),
    ({"challenge_invitation_id": uuid4()}, "EMAIL_CHALLENGE_BINDING_MISMATCH"),
    ({"challenge_recipient_id": uuid4()}, "EMAIL_CHALLENGE_BINDING_MISMATCH"),
    ({"challenge_expires_at": 500}, "EMAIL_CHALLENGE_EXPIRED_OR_OUT_OF_SCOPE"),
    ({"challenge_expires_at": 1001}, "EMAIL_CHALLENGE_EXPIRED_OR_OUT_OF_SCOPE"),
    ({"challenge_consumptions": 2}, "EMAIL_OWNERSHIP_SINGLE_USE_NOT_MATCHED"),
    ({"email_verified_claimed": False}, "EMAIL_OWNERSHIP_SINGLE_USE_NOT_MATCHED"),
    ({"delivery_status": "SMTP_ACCEPTED"}, "DELIVERY_PROOF_NOT_MATCHED"),
    ({"published_document_id": uuid4()}, "PUBLISHED_CONTRACT_BINDING_MISMATCH"),
    ({"accepted_sha256": "b"*64}, "VERSIONED_CONTRACT_DIGEST_MISMATCH"),
    ({"accepted_sha256": "A"*64}, "VERSIONED_CONTRACT_DIGEST_MISMATCH"),
    ({"consent_actor_id": uuid4()}, "RECIPIENT_CONSENT_NOT_MATCHED"),
    ({"consent_explicit": False}, "RECIPIENT_CONSENT_NOT_MATCHED"),
    ({"session_user_id": uuid4()}, "INDIVIDUAL_SESSION_SCOPE_MISMATCH"),
    ({"session_tenant_id": uuid4()}, "INDIVIDUAL_SESSION_SCOPE_MISMATCH"),
    ({"session_role": "MASTER"}, "INDIVIDUAL_SESSION_SCOPE_MISMATCH"),
    ({"session_active_claimed": False}, "INDIVIDUAL_SESSION_SCOPE_MISMATCH"),
    ({"reset_token_consumptions": 1}, "UNREQUESTED_PASSWORD_RESET_EVIDENCE"),
])
def test_admin_adversarial_scenario_always_denied(changes, code):
    report = assess_journey(replace(sample("ADMIN"), **changes))
    assert code in report["violations"]
    assert not report["policy_consistent_hypothetically"]
    assert not report["production_authorized"]


@pytest.mark.parametrize("changes,code", [
    ({"actor_role": "MASTER"}, "TENANT_ADMIN_CONTEXT_INVALID"),
    ({"actor_tenant_id": uuid4()}, "TENANT_ADMIN_CONTEXT_INVALID"),
    ({"invitation_target_role": "TENANT_ADMIN"}, "INVITATION_SCOPE_MISMATCH"),
    ({"session_role": "TENANT_ADMIN"}, "INDIVIDUAL_SESSION_SCOPE_MISMATCH"),
])
def test_member_adversarial_scenario_always_denied(changes, code):
    report = assess_journey(replace(sample("MEMBER"), **changes))
    assert code in report["violations"]
    assert report["real_account_activation_enabled"] is False


def test_self_invite_and_self_approval_rejected():
    a = sample()
    report = assess_journey(replace(
        a, recipient_id=a.actor_id, reviewer_id=a.actor_id
    ))
    assert "SELF_INVITATION_DENIED" in report["violations"]
    assert "INDEPENDENT_REVIEW_NOT_MATCHED" in report["violations"]
    assert not report["production_authorized"]


def test_recipient_cannot_self_approve():
    a = sample()
    report = assess_journey(replace(a, reviewer_id=a.recipient_id))
    assert "INDEPENDENT_REVIEW_NOT_MATCHED" in report["violations"]


def test_reset_requires_single_use_and_prior_sessions_revoked():
    a = sample()
    ok = assess_journey(replace(
        a, password_reset_performed=True,
        reset_token_consumptions=1,
        previous_sessions_revoked=True
    ))
    assert ok["policy_consistent_hypothetically"] is True
    for consumed, revoked in ((0, True), (1, False), (2, True)):
        bad = assess_journey(replace(
            a, password_reset_performed=True,
            reset_token_consumptions=consumed,
            previous_sessions_revoked=revoked
        ))
        assert "PASSWORD_RESET_SESSION_FAMILY_NOT_REVOKED" in bad["violations"]


@pytest.mark.parametrize("changes", [
    {"invitation_consumptions": True},
    {"now": "500"},
    {"reviewer_approved": 1},
    {"tenant_id": "fake"},
    {"invitation_id": uuid4().hex},
    {"actor_tenant_id": "cross-tenant"},
    {"session_tenant_id": "cross-tenant"},
    {"expected_revision": False},
    {"password_reset_performed": 1},
])
def test_malformed_synthetic_claims_are_rejected(changes):
    with pytest.raises(ValueError, match="M29100_MALFORMED_EVIDENCE"):
        assess_journey(replace(sample(), **changes))


def test_invalid_flow_and_zero_uuid_are_not_accepted():
    a = sample()
    invalid = assess_journey(replace(a, flow="MASTER"))
    assert "INVALID_FLOW" in invalid["violations"]
    with pytest.raises(ValueError):
        assess_journey(object())


def test_preexisting_public_invite_and_recovery_remain_blocked(monkeypatch):
    monkeypatch.setattr(settings, "DATABASE_URL", "postgresql://localhost/ci-placeholder")
    tenant=uuid4()
    admin=AuthenticatedSession(str(uuid4()), "TENANT_ADMIN", str(tenant),
                              "synthetic@invalid.example", "CI only", False)
    payload=InvitationCreateRequest(target_email="ci@example.com",
                                    target_role="TENANT_MEMBER",
                                    tenant_id=str(tenant),
                                    required_document_id=uuid4())
    with pytest.raises(HTTPException) as error:
        create_invitation(payload, admin)
    assert error.value.status_code == 503
    assert "Nenhum convite" in str(error.value.detail)

    with pytest.raises(HTTPException) as recovery:
        forgot_password(ForgotPasswordRequest(email="ci@example.com"))
    assert recovery.value.status_code == 503


def test_ci_executors_not_registered_as_public_http_routes():
    router=(ROOT/"backend/app/routers/invitations.py").read_text()
    auth=(ROOT/"backend/app/routers/auth.py").read_text()
    policy=inspect.getsource(assess_journey)
    assert "register_new_invited_identity_ci" not in router
    assert "prepare_invitation_ci" not in router
    assert "reset_password_ci" not in auth
    for forbidden in ("asyncpg.connect", "psycopg.connect", "requests.post",
                      "oci.core", "INSERT INTO", "UPDATE public.", "DELETE FROM"):
        assert forbidden not in policy


def test_readiness_contract_does_not_confuse_ci_with_staging():
    contract = readiness_contract()
    assert contract["project"] == "FR_FINANCE_AI_STUDIO"
    assert len(contract["controls"]) == 4
    assert not any([
        contract["provider_evidence"], contract["database_evidence"],
        contract["master_mfa_operationally_verified"], contract["public_routes_activated"],
        contract["migrations_applied"], contract["real_users_enabled"],
        contract["real_pix_enabled"], contract["production_authorized"],
    ])
