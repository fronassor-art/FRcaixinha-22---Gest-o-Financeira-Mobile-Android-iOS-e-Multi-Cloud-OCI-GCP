"""FR Finance M38999: the VERIFIED original auth/outbox DB is sufficient.

No second DB, no financial DATABASE_URL, no SMTP or activation. Synthetic
bindings only; original M047/M048 deployment remains OFF by default.
"""
from __future__ import annotations

from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from app.config import settings
from app.main import app
from app.access_delivery_binding import AccessDeliveryBinding, AccessDeliveryReceipt
from app.dependencies import AuthenticatedSession, get_current_session


TENANT = "00000000-0000-4000-8000-0000000000c1"
DOCUMENT = "00000000-0000-4000-8000-0000000000c2"
TOKEN = "A" * 56


async def _invite(**kwargs):
    return AccessDeliveryReceipt(uuid4(), persisted=True,
                                 durable_outbox_queued=True)


async def _reset(**kwargs):
    return AccessDeliveryReceipt(uuid4(), persisted=True,
                                 durable_outbox_queued=True)


async def _verify(**kwargs):
    return True


def _binding(**changes):
    values = dict(
        invite=_invite, reset=_reset,
        verify_invitation_email=_verify, complete_password_reset=_verify,
        original_db_verified=True, segregated_worker_verified=True,
        durable_outbox_verified=True, scoped_audit_verified=True,
        smtp_credential_protected=True, external_delivery_authorized=True,
    )
    values.update(changes)
    return AccessDeliveryBinding(**values)


@pytest.fixture(autouse=True)
def isolate(monkeypatch):
    monkeypatch.setattr(settings, "DATABASE_URL", "")
    monkeypatch.setenv("FR_FINANCE_ACCESS_MAIL_ENABLE", "OFF")
    monkeypatch.setenv("FR_FINANCE_ACCESS_MAIL_WORKER", "OFF")
    app.dependency_overrides.clear()
    if hasattr(app.state, "access_delivery_runtime"):
        delattr(app.state, "access_delivery_runtime")
    yield
    app.dependency_overrides.clear()
    if hasattr(app.state, "access_delivery_runtime"):
        delattr(app.state, "access_delivery_runtime")


def test_all_four_access_routes_remain_503_without_reviewed_original_runtime():
    with TestClient(app) as client:
        responses = [
            client.post("/api/v1/auth/forgot-password",
                        json={"email": "test@example.invalid"}),
            client.post("/api/v1/auth/reset-password",
                        json={"token": TOKEN, "new_password": "safe-password-1234"}),
            client.post("/api/v1/invitations/verify-email",
                        json={"token": TOKEN}),
        ]
        assert all(r.status_code == 503 for r in responses)


def test_original_verified_runtime_accepts_enqueuing_without_financial_db():
    calls = []
    async def reset(**kw):
        calls.append(kw)
        return await _reset(**kw)
    app.state.access_delivery_runtime = _binding(reset=reset)
    with TestClient(app) as c:
        r = c.post("/api/v1/auth/forgot-password",
                   json={"email": "ci-m38999@example.com"})
    assert r.status_code == 202
    assert r.json()["user_exists"] is None
    assert r.json()["email_sent"] is False
    assert calls and calls[0]["email"] == "ci-m38999@example.com"
    assert calls[0]["source_ip"] == "testclient"
    assert settings.DATABASE_URL == ""


def test_original_verified_runtime_completes_one_use_password_no_financial_db():
    calls = []
    async def redeem(**kw):
        calls.append(kw)
        return True
    app.state.access_delivery_runtime = _binding(complete_password_reset=redeem)
    with TestClient(app) as c:
        r = c.post("/api/v1/auth/reset-password",
                   json={"token": TOKEN, "new_password": "safe-password-1234"})
    assert r.status_code == 200
    assert r.json()["sessions_revoked"] is True
    assert r.json()["real_user_activation"] is False
    assert calls == [{"token": TOKEN, "new_password": "safe-password-1234"}]
    assert TOKEN not in r.text


def test_original_verified_runtime_verifies_invitation_without_financial_db():
    app.state.access_delivery_runtime = _binding()
    with TestClient(app) as c:
        r = c.post("/api/v1/invitations/verify-email", json={"token": TOKEN})
    assert r.status_code == 200
    assert r.json()["account_activated"] is False
    assert r.json()["membership_created"] is False
    assert TOKEN not in r.text


def test_original_verified_runtime_accepts_scoped_invite_without_financial_db():
    calls = []
    async def invite(**kw):
        calls.append(kw)
        return await _invite(**kw)
    app.state.access_delivery_runtime = _binding(invite=invite)
    app.dependency_overrides[get_current_session] = lambda: AuthenticatedSession(
        str(uuid4()), "TENANT_ADMIN", TENANT,
        "ci-admin@example.invalid", "Admin", False,
    )
    with TestClient(app) as c:
        r = c.post("/api/v1/invitations", json={
            "target_email": "invitee@example.invalid",
            "target_role": "TENANT_MEMBER",
            "tenant_id": TENANT, "required_document_id": DOCUMENT,
        })
    assert r.status_code == 202
    assert r.json()["email_sent"] is False
    assert r.json()["user_created"] is False
    assert len(calls) == 1


@pytest.mark.parametrize("flag", [
    "original_db_verified", "segregated_worker_verified",
    "durable_outbox_verified", "scoped_audit_verified",
    "smtp_credential_protected", "external_delivery_authorized",
])
def test_missing_original_attestation_never_enqueues_without_financial_db(flag):
    calls = []
    async def never(**kw):
        calls.append(kw)
        return await _reset(**kw)
    app.state.access_delivery_runtime = _binding(
        reset=never, **{flag: False},
    )
    with TestClient(app) as c:
        r = c.post("/api/v1/auth/forgot-password",
                   json={"email": "ci-denied@example.invalid"})
    assert r.status_code == 503
    assert calls == []


def test_original_auth_routes_do_not_require_financial_connection_setting():
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    auth = (root / "backend/app/routers/auth.py").read_text()
    invite = (root / "backend/app/routers/invitations.py").read_text()
    assert "runtime = require_access_delivery(request)" in auth
    assert "runtime = require_access_delivery(request)" in invite
    assert "submit_access_message(" not in auth + invite
    assert "CREATE DATABASE" not in auth + invite
