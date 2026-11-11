"""M38960: operational API wiring for invitations/recovery, no extra DB/API/SMTP.

Real Termux and production do not inject an access worker yet. These tests use
explicit, synthetic in-memory worker receipts and never modify a real user.
"""
from __future__ import annotations

import ast
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.access_delivery_binding import (
    AccessDeliveryBinding, AccessDeliveryReceipt,
    invitation_accepted_response, password_recovery_accepted_response,
    verified_enqueue,
)
from app.config import settings
from app.dependencies import AuthenticatedSession, get_current_session
from app.main import app


ROOT = Path(__file__).resolve().parents[2]
T = "00000000-0000-4000-8000-0000000000b1"
DOC = "00000000-0000-4000-8000-0000000000b2"


def admin(*, role="TENANT_ADMIN", tenant=T, master=False):
    return AuthenticatedSession(
        user_id=str(uuid4()), role=role, tenant_id=tenant,
        email="ci-admin@example.invalid", name="CI admin", is_master=master,
    )


def valid_binding(*, invite=None, reset=None, **overrides):
    async def fake_invite(**kw):
        return AccessDeliveryReceipt(
            event_id=uuid4(), persisted=True, durable_outbox_queued=True)
    async def fake_reset(**kw):
        return AccessDeliveryReceipt(
            event_id=uuid4(), persisted=True, durable_outbox_queued=True)
    flags = dict(
        original_db_verified=True,
        segregated_worker_verified=True,
        durable_outbox_verified=True,
        scoped_audit_verified=True,
        smtp_credential_protected=True,
        external_delivery_authorized=True,
    )
    flags.update(overrides)
    return AccessDeliveryBinding(
        invite=invite or fake_invite, reset=reset or fake_reset, **flags)


@pytest.fixture(autouse=True)
def cleanup_runtime():
    try:
        if hasattr(app.state, "access_delivery_runtime"):
            delattr(app.state, "access_delivery_runtime")
        app.dependency_overrides.clear()
        yield
    finally:
        if hasattr(app.state, "access_delivery_runtime"):
            delattr(app.state, "access_delivery_runtime")
        app.dependency_overrides.clear()


def test_no_worker_forget_password_is_503_not_fake_accepted(monkeypatch):
    monkeypatch.setattr(settings, "DATABASE_URL", "postgresql://ci-only-placeholder")
    with TestClient(app) as c:
        r = c.post("/api/v1/auth/forgot-password",
                   json={"email": "unknown-m38960@example.com"})
    assert r.status_code == 503
    assert "não implementada" in r.json()["detail"]
    assert r.headers["cache-control"] == "no-store"


def test_no_worker_invitation_is_503_after_scoped_authorization(monkeypatch):
    monkeypatch.setattr(settings, "DATABASE_URL", "postgresql://ci-only-placeholder")
    app.dependency_overrides[get_current_session] = lambda: admin()
    with TestClient(app) as c:
        r = c.post("/api/v1/invitations", json=dict(
            target_email="ci-recipient@example.com",
            target_role="TENANT_MEMBER",
            tenant_id=T,
            required_document_id=DOC,
        ))
    assert r.status_code == 503
    assert "não implementada" in r.json()["detail"]


def test_no_worker_and_no_auth_cannot_issue_invites():
    with TestClient(app) as c:
        r = c.post("/api/v1/invitations", json={
            "target_email": "ci-recipient@example.com",
            "target_role": "TENANT_MEMBER",
            "tenant_id": T,
            "required_document_id": DOC,
        })
    assert r.status_code in (401, 403, 503)


@pytest.mark.parametrize("missing_flag", [
    "original_db_verified",
    "segregated_worker_verified",
    "durable_outbox_verified",
    "scoped_audit_verified",
    "smtp_credential_protected",
    "external_delivery_authorized",
])
def test_each_missing_worker_attestation_blocks_any_operation(monkeypatch, missing_flag):
    monkeypatch.setattr(settings, "DATABASE_URL", "postgresql://ci-only-placeholder")
    calls = []
    async def fake_reset(**kwargs):
        calls.append(kwargs)
        return AccessDeliveryReceipt(uuid4(), True, True)
    app.state.access_delivery_runtime = valid_binding(
        reset=fake_reset, **{missing_flag: False})
    with TestClient(app) as c:
        r = c.post("/api/v1/auth/forgot-password",
                   json={"email": "ci-missing-flag@example.com"})
    assert r.status_code == 503
    assert calls == []


def test_refuse_non_binding_object_that_claims_everything(monkeypatch):
    monkeypatch.setattr(settings, "DATABASE_URL", "postgresql://ci-only-placeholder")
    app.state.access_delivery_runtime = object()
    with TestClient(app) as c:
        r = c.post("/api/v1/auth/forgot-password",
                   json={"email": "ci-forged-bind@example.com"})
    assert r.status_code == 503


@pytest.mark.parametrize("overrides", [
    {"persisted": False},
    {"durable_outbox_queued": False},
    {"email_sent": True},
    {"recipient_verified": True},
    {"user_activated": True},
    {"event_id": UUID(int=0)},
])
def test_synthetic_receipt_cannot_imply_real_delivery_or_activation(overrides):
    values = dict(
        event_id=uuid4(), persisted=True, durable_outbox_queued=True,
        email_sent=False, recipient_verified=False, user_activated=False,
    )
    values.update(overrides)
    with pytest.raises(HTTPException) as exc:
        verified_enqueue(AccessDeliveryReceipt(**values))
    assert exc.value.status_code == 503


def test_invitation_response_only_claims_queued_state():
    accepted = invitation_accepted_response(
        AccessDeliveryReceipt(uuid4(), True, True))
    assert accepted["status"] == "QUEUED_FOR_DELIVERY"
    assert accepted["email_sent"] is False
    assert accepted["recipient_verified"] is False
    assert accepted["activation_authorized"] is False
    assert accepted["user_created"] is False


def test_recovery_response_does_not_leak_user_lookup_or_token():
    accepted = password_recovery_accepted_response(
        AccessDeliveryReceipt(uuid4(), True, True))
    assert accepted["status"] == "REQUEST_ACCEPTED_IF_ELIGIBLE"
    assert accepted["user_exists"] is None
    assert accepted["email_sent"] is False
    assert "event_id" not in accepted


def test_provisioned_faux_worker_routes_only_intent_not_smtp(monkeypatch):
    monkeypatch.setattr(settings, "DATABASE_URL", "postgresql://ci-only-placeholder")
    calls = []
    async def issue(**kwargs):
        calls.append(("INVITATION", kwargs))
        return AccessDeliveryReceipt(uuid4(), True, True)
    async def reset(**kwargs):
        calls.append(("RESET", kwargs))
        return AccessDeliveryReceipt(uuid4(), True, True)
    app.state.access_delivery_runtime = valid_binding(invite=issue, reset=reset)
    app.dependency_overrides[get_current_session] = lambda: admin()
    with TestClient(app) as c:
        response = c.post("/api/v1/invitations", json={
            "target_email": "ci-recipient@example.com",
            "target_role": "TENANT_MEMBER",
            "tenant_id": T,
            "required_document_id": DOC,
        })
        password = c.post("/api/v1/auth/forgot-password",
                          json={"email": "CI-reset-m38960@example.com"})
    assert response.status_code == 202
    assert response.json()["status"] == "QUEUED_FOR_DELIVERY"
    assert password.status_code == 202
    assert password.json()["user_exists"] is None
    assert calls[0][0] == "INVITATION"
    assert calls[0][1]["payload"].tenant_id == T
    assert calls[1] == ("RESET", {"email": "ci-reset-m38960@example.com"})


def test_master_not_allowed_without_mfa_even_if_worker_injected(monkeypatch):
    monkeypatch.setattr(settings, "DATABASE_URL", "postgresql://ci-only-placeholder")
    calls = []
    async def issue(**kwargs):
        calls.append(kwargs)
        return AccessDeliveryReceipt(uuid4(), True, True)
    app.state.access_delivery_runtime = valid_binding(invite=issue)
    app.dependency_overrides[get_current_session] = lambda: admin(
        role="MASTER", tenant=None, master=True)
    with TestClient(app) as c:
        resp = c.post("/api/v1/invitations", json={
            "target_email": "admin@example.com",
            "target_role": "TENANT_ADMIN",
            "tenant_id": T,
            "required_document_id": DOC,
        })
    assert resp.status_code == 503
    assert calls == []


@pytest.mark.parametrize("role", ["TENANT_MEMBER", "MASTER"])
def test_non_admin_cannot_send_member_invite(monkeypatch, role):
    monkeypatch.setattr(settings, "DATABASE_URL", "postgresql://ci-only-placeholder")
    app.state.access_delivery_runtime = valid_binding()
    app.dependency_overrides[get_current_session] = lambda: admin(
        role=role, master=role == "MASTER")
    with TestClient(app) as c:
        resp = c.post("/api/v1/invitations", json={
            "target_email": "member@example.com",
            "target_role": "TENANT_MEMBER",
            "tenant_id": T,
            "required_document_id": DOC,
        })
    assert resp.status_code == 403


@pytest.mark.parametrize("tenant,doc", [
    (None, DOC), (T, None),
])
def test_missing_tenant_or_published_document_reference_blocks(monkeypatch, tenant, doc):
    monkeypatch.setattr(settings, "DATABASE_URL", "postgresql://ci-only-placeholder")
    app.state.access_delivery_runtime = valid_binding()
    app.dependency_overrides[get_current_session] = lambda: admin()
    with TestClient(app) as c:
        resp = c.post("/api/v1/invitations", json={
            "target_email": "member@example.com", "target_role": "TENANT_MEMBER",
            "tenant_id": tenant, "required_document_id": doc,
        })
    assert resp.status_code in (403, 422)


def test_existing_main_routes_are_not_duplicated():
    from app.main import app
    paths = [(route.path, "POST") for route in app.routes
             if "POST" in getattr(route, "methods", set())]
    assert paths.count(("/api/v1/invitations", "POST")) == 1
    assert paths.count(("/api/v1/auth/forgot-password", "POST")) == 1


def test_no_new_database_or_public_smtp_inline():
    for path in [
        "backend/app/access_delivery_binding.py",
        "backend/app/routers/invitations.py",
        "backend/app/routers/auth.py",
    ]:
        src = (ROOT / path).read_text(encoding="utf-8")
        ast.parse(src)
    routes = (
        (ROOT / "backend/app/routers/auth.py").read_text()
        + (ROOT / "backend/app/routers/invitations.py").read_text())
    for forbidden in (
        "submit_access_message(", "CREATE DATABASE", "initdb",
        "pg_ctl start", "pg_resetwal", "os.system(", "subprocess.run(",
    ):
        assert forbidden not in routes
    assert "app.state" not in routes  # all state access isolated in reviewed binding
