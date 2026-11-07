"""Não há API pública de aceite, reset ou entrega sem verificação de e-mail."""
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.account_lifecycle import LifecycleDenied, prepare_invitation_ci, prepare_password_reset_ci
from app.dependencies import AuthenticatedSession
from app.routers.auth import forgot_password
from app.routers.invitations import create_invitation
from app.models import ForgotPasswordRequest, InvitationCreateRequest
from app.config import settings


class NoDatabase:
    def execute(self, *_args, **_kwargs):
        raise AssertionError("Nenhum banco deve ser acessado fora do CI isolado")


def test_lifecycle_helpers_refuse_execution_outside_disposable_ci(monkeypatch):
    monkeypatch.delenv("FRCAIXINHA_CI_ISOLATED", raising=False)
    db = NoDatabase()
    with pytest.raises(LifecycleDenied):
        prepare_password_reset_ci(db, uuid4())
    with pytest.raises(LifecycleDenied):
        prepare_invitation_ci(db, tenant_id=uuid4(), inviter_id=uuid4(),
                              recipient_email="ci@example.com",
                              target_role="TENANT_MEMBER",
                              required_document_id=uuid4())


def test_password_recovery_public_endpoint_stays_blocked():
    with pytest.raises(HTTPException) as exc:
        forgot_password(ForgotPasswordRequest(email="ci@example.com"))
    assert exc.value.status_code == 503
    assert "ainda não implementada" in str(exc.value.detail)


def test_invitation_public_endpoint_does_not_invent_delivery(monkeypatch):
    monkeypatch.setattr(settings, "DATABASE_URL", "postgresql://localhost/frcaixinha_ci")
    master = AuthenticatedSession(str(uuid4()), "MASTER", None,
                                  "master@example.com", "Master sintetico", True)
    with pytest.raises(HTTPException) as exc:
        create_invitation(
            InvitationCreateRequest(target_email="recipient@example.com",
                                    target_role="TENANT_ADMIN"),
            master,
        )
    assert exc.value.status_code == 503
    assert "Nenhum convite foi criado ou enviado" in str(exc.value.detail)
