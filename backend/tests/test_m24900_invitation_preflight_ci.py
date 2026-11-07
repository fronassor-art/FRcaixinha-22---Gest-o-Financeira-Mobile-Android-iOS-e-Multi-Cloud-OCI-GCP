"""M24900 — fail-closed invitation preflight, no database/HTTP/provider access."""
from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.dependencies import AuthenticatedSession
from app.models import InvitationCreateRequest
from app.routers.invitations import create_invitation, preview_invitation_readiness
from app.config import settings


def session(role, tenant=None, is_master=False):
    return AuthenticatedSession(
        str(uuid4()), role, str(tenant) if tenant else None,
        "ci-only-actor@example.invalid", "Actor CI", is_master,
    )


def invitation(role, tenant=None, doc=None):
    return InvitationCreateRequest(
        target_email="synthetic-recipient@example.invalid",
        target_role=role,
        tenant_id=str(tenant) if tenant else None,
        required_document_id=doc,
    )


def test_admin_preflight_is_never_activation_or_delivery():
    tenant = uuid4()
    doc = uuid4()
    request = invitation("TENANT_MEMBER", tenant, doc)
    report = preview_invitation_readiness(
        request, session("TENANT_ADMIN", tenant),
    )
    assert report["status"] == "BLOCKED"
    assert report["mode"] == "READ_ONLY_NO_DELIVERY"
    assert report["required_document_reference_present"] is True
    for key in (
        "document_published_verified", "recipient_verified",
        "provider_delivery_verified", "activation_authorized",
        "invitation_created", "email_sent", "user_created",
        "membership_changed", "writes_performed",
    ):
        assert report[key] is False
    assert "PUBLISHED_MEMBERSHIP_CONTRACT_NOT_VERIFIED" in report["blocking_gates"]
    assert "EMAIL_DELIVERY_PROVIDER_NOT_VERIFIED" in report["blocking_gates"]
    assert "TRANSACTIONAL_AUDIT_AND_SINGLE_USE_NOT_VERIFIED" in report["blocking_gates"]
    assert request.target_email not in str(report)
    assert str(doc) not in str(report)
    assert str(tenant) not in str(report)


def test_missing_document_stays_blocked_and_never_invents_publication():
    tenant = uuid4()
    report = preview_invitation_readiness(
        invitation("TENANT_MEMBER", tenant),
        session("TENANT_ADMIN", tenant),
    )
    assert report["required_document_reference_present"] is False
    assert "REQUIRED_DOCUMENT_ID_MISSING" in report["blocking_gates"]
    assert report["document_published_verified"] is False


def test_admin_cannot_preflight_master_or_other_tenant():
    current = uuid4()
    admin = session("TENANT_ADMIN", current)
    for request in (
        invitation("TENANT_ADMIN", current, uuid4()),
        invitation("TENANT_MEMBER", uuid4(), uuid4()),
        InvitationCreateRequest(
            target_email="synthetic-recipient@example.invalid",
            target_role="TENANT_MEMBER", tenant_id="invalid-tenant-id",
        ),
    ):
        with pytest.raises(HTTPException) as exc:
            preview_invitation_readiness(request, admin)
        assert exc.value.status_code == 403
    with pytest.raises(HTTPException) as exc:
        preview_invitation_readiness(
            invitation("TENANT_MEMBER", current),
            session("TENANT_MEMBER", current),
        )
    assert exc.value.status_code == 403


def test_master_scoped_admin_intent_is_still_blocked():
    tenant = uuid4()
    master = session("MASTER", is_master=True)
    report = preview_invitation_readiness(
        invitation("TENANT_ADMIN", tenant, uuid4()), master,
    )
    assert report["status"] == "BLOCKED"
    assert "MASTER_MFA_NOT_ATTESTED" in report["blocking_gates"]
    assert "INDEPENDENT_APPROVAL_NOT_ATTESTED" in report["blocking_gates"]
    missing_target = preview_invitation_readiness(
        invitation("TENANT_ADMIN", doc=uuid4()), master,
    )
    assert "TARGET_TENANT_ID_REQUIRED" in missing_target["blocking_gates"]
    with pytest.raises(HTTPException) as exc:
        preview_invitation_readiness(
            invitation("TENANT_MEMBER", tenant, uuid4()), master,
        )
    assert exc.value.status_code == 403
    with pytest.raises(HTTPException):
        preview_invitation_readiness(
            invitation("TENANT_ADMIN", tenant, uuid4()),
            session("MASTER", is_master=False),
        )


def test_versioned_document_alias_is_uuid_checked():
    doc = uuid4()
    request = InvitationCreateRequest.model_validate({
        "target_email": "synthetic-recipient@example.invalid",
        "target_role": "TENANT_MEMBER",
        "requiredDocumentId": str(doc),
    })
    assert request.required_document_id == doc
    with pytest.raises(ValidationError):
        InvitationCreateRequest.model_validate({
            "target_email": "synthetic-recipient@example.invalid",
            "target_role": "TENANT_MEMBER",
            "requiredDocumentId": "not-a-uuid",
        })


def test_real_invite_endpoint_still_503_without_writes(monkeypatch):
    monkeypatch.setattr(settings, "DATABASE_URL", "postgresql://localhost/ci-placeholder")
    with pytest.raises(HTTPException) as exc:
        create_invitation(
            invitation("TENANT_MEMBER", uuid4(), uuid4()),
            session("TENANT_ADMIN", uuid4()),
        )
    assert exc.value.status_code == 403
    tenant = uuid4()
    with pytest.raises(HTTPException) as exc:
        create_invitation(
            invitation("TENANT_MEMBER", tenant, uuid4()),
            session("TENANT_ADMIN", tenant),
        )
    assert exc.value.status_code == 503
    assert "Nenhum convite foi criado ou enviado" in str(exc.value.detail)


def test_no_public_ci_executor_or_database_write_imports():
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    router = (root / "backend/app/routers/invitations.py").read_text()
    preflight = (root / "backend/app/invitation_preflight.py").read_text()
    assert "prepare_invitation_ci" not in router
    assert "register_new_invited_identity_ci" not in router
    assert "account_lifecycle" not in router
    assert "asyncpg.connect(" not in preflight
    assert "psycopg.connect(" not in preflight
    assert "INSERT INTO " not in preflight
    assert "Convites ainda não implementados" in router
