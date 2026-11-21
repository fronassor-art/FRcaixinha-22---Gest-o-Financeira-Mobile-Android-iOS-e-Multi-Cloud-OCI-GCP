"""FR Finance M38993: M048 one-use token flow, original PostgreSQL only.

Synthetic tests; never connect to the Android PostgreSQL or deliver email.
"""
from __future__ import annotations
import asyncio
import hashlib
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.config import settings
from app.access_delivery_binding import AccessDeliveryBinding, AccessDeliveryReceipt
from app.access_delivery_pg18 import (
    Pg18AccessDelivery, AccessQueueConfig, AccessQueueBlocked,
    _verified_access_token,
)
from app.onboarding_mail_transport import SmtpSubmissionConfig

ROOT = Path(__file__).resolve().parents[2]
M048 = ROOT / "backend/local_migrations/048_frfinance_access_token_redemption.sql"
VALID = "A" * 56


@pytest.fixture(autouse=True)
def isolate_state():
    if hasattr(app.state, "access_delivery_runtime"):
        delattr(app.state, "access_delivery_runtime")
    yield
    if hasattr(app.state, "access_delivery_runtime"):
        delattr(app.state, "access_delivery_runtime")


def binding(verify=None, reset=None):
    async def noop(**kwargs):
        return AccessDeliveryReceipt(uuid4(), True, True)
    return AccessDeliveryBinding(
        invite=noop, reset=noop,
        verify_invitation_email=verify,
        complete_password_reset=reset,
        original_db_verified=True, segregated_worker_verified=True,
        durable_outbox_verified=True, scoped_audit_verified=True,
        smtp_credential_protected=True, external_delivery_authorized=True,
    )


@pytest.mark.parametrize("path,body", [
    ("/api/v1/auth/reset-password",
     {"token": VALID, "new_password": "correct horse battery staple"}),
    ("/api/v1/invitations/verify-email", {"token": VALID}),
])
def test_disabled_until_m048_approved(monkeypatch, path, body):
    monkeypatch.setattr(settings, "DATABASE_URL", "postgresql://dummy-ci-only")
    with TestClient(app) as client:
        r = client.post(path, json=body)
    assert r.status_code == 503
    assert VALID not in r.text


@pytest.mark.parametrize("result", [False, None])
def test_invalid_or_consumed_reset_token_never_changes_password(monkeypatch, result):
    monkeypatch.setattr(settings, "DATABASE_URL", "postgresql://dummy-ci-only")
    async def fake_reset(**kw):
        return result
    app.state.access_delivery_runtime = binding(reset=fake_reset)
    with TestClient(app) as client:
        response = client.post("/api/v1/auth/reset-password",
                               json={"token":VALID,"new_password":"Long-Password!123"})
    assert response.status_code == 400
    assert VALID not in response.text


def test_valid_synthetic_reset_does_not_leak_secrets(monkeypatch):
    monkeypatch.setattr(settings, "DATABASE_URL", "postgresql://dummy-ci-only")
    calls = []
    async def fake_reset(**kw):
        calls.append(kw)
        return True
    app.state.access_delivery_runtime = binding(reset=fake_reset)
    with TestClient(app) as client:
        r = client.post("/api/v1/auth/reset-password",json={
            "token":VALID,"new_password":"Long-Password!123"})
    assert r.status_code == 200
    assert r.json() == {
        "status":"PASSWORD_UPDATED",
        "sessions_revoked":True,
        "next_step":"LOGIN_AGAIN",
        "real_user_activation":False,
    }
    assert calls == [{"token":VALID,"new_password":"Long-Password!123"}]
    assert VALID not in r.text
    assert "Long-Password" not in r.text


def test_valid_synthetic_invite_does_not_activate_user(monkeypatch):
    monkeypatch.setattr(settings, "DATABASE_URL", "postgresql://dummy-ci-only")
    calls = []
    async def verify(**kw):
        calls.append(kw)
        return True
    app.state.access_delivery_runtime = binding(verify=verify)
    with TestClient(app) as client:
        r = client.post("/api/v1/invitations/verify-email",json={"token":VALID})
    assert r.status_code == 200
    assert r.json() == {
        "status":"EMAIL_OWNERSHIP_VERIFIED",
        "invitation_accepted":False,
        "membership_created":False,
        "account_activated":False,
        "next_step":"CONTRACT_ACCEPTANCE_AND_IDENTITY",
    }
    assert calls == [{"token":VALID}]
    assert VALID not in r.text


@pytest.mark.parametrize("token", ["short","a","a\n"*30,"/../", " " * 56])
def test_invalid_token_without_db(token):
    with pytest.raises(AccessQueueBlocked):
        _verified_access_token(token)


def test_token_digest_without_exposing_token():
    digest = _verified_access_token(VALID)
    assert digest == hashlib.sha256(VALID.encode("ascii")).hexdigest()
    assert VALID not in digest


class FakeDB:
    def __init__(self, accepted=True):
        self.accepted=accepted
        self.actions=[]
        self.closed=False
    @asynccontextmanager
    async def transaction(self):
        self.actions.append("BEGIN")
        try:
            yield
            self.actions.append("COMMIT")
        except BaseException:
            self.actions.append("ROLLBACK")
            raise
    async def fetchval(self, statement, *params):
        self.actions.append((statement,params))
        return self.accepted
    async def close(self):
        self.closed=True


def config():
    return AccessQueueConfig(
        dsn="postgresql://frc_ai_auth:ci@127.0.0.1:5433/frcaixinha_aistudio_dev",
        encryption_key=b"A"*32,
        hmac_key=b"ci-hmac-password-digest-key-long-enough",
        smtp=SmtpSubmissionConfig(
            host="smtp-relay.brevo.com",port=587,user="ci",password="ci",
            sender="notificacoes@frfinance.com.br",app_origin="https://frfinance.com.br",
        ),
    )


@pytest.mark.asyncio
async def test_existing_pg_only_one_tx_for_invite_verification(monkeypatch):
    import app.access_delivery_pg18 as m
    db=FakeDB(True)
    async def dbconnect(conf): return db
    monkeypatch.setattr(m,"_connect",dbconnect)
    result=await Pg18AccessDelivery(config()).verify_invitation_email(token=VALID)
    assert result is True
    assert db.actions[0]=="BEGIN" and db.actions[-1]=="COMMIT"
    assert "frfinance_verify_invite_email" in db.actions[1][0]
    assert db.actions[1][1]==(_verified_access_token(VALID),)
    assert db.closed


@pytest.mark.asyncio
async def test_existing_pg_only_one_tx_for_password_change(monkeypatch):
    import app.access_delivery_pg18 as m
    import app.security as sec
    db=FakeDB(True)
    async def dbconnect(conf): return db
    monkeypatch.setattr(m,"_connect",dbconnect)
    monkeypatch.setattr(sec,"hash_password_secure",
        lambda v: "$argon2id$" + "x"*90)
    result=await Pg18AccessDelivery(config()).complete_password_reset(
        token=VALID,new_password="correct horse battery staple")
    assert result is True
    assert db.actions[0]=="BEGIN" and db.actions[-1]=="COMMIT"
    assert "frfinance_redeem_reset_token" in db.actions[1][0]
    assert db.actions[1][1][0]==_verified_access_token(VALID)
    assert db.actions[1][1][1].startswith("$argon2id$")
    assert "correct horse" not in str(db.actions)
    assert db.closed


@pytest.mark.asyncio
async def test_argon2_not_available_never_accesses_db(monkeypatch):
    import app.access_delivery_pg18 as m
    import app.security as sec
    async def impossible(_): pytest.fail("database should not be contacted")
    monkeypatch.setattr(m,"_connect",impossible)
    monkeypatch.setattr(sec,"hash_password_secure",
        lambda _: "$2b$" + "x"*80)
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as e:
        await Pg18AccessDelivery(config()).complete_password_reset(
            token=VALID,new_password="safe password 123")
    assert e.value.status_code==503


def test_m048_sql_guards_and_atomic_revoke_on_original_db():
    sql=M048.read_text()
    for req in [
        "current_database()<>'frcaixinha_aistudio_dev'",
        "session_user<>'frc_ai_owner'",
        "inet_server_port()<>5433",
        "'frfinance.migration_048_approved'",
        "frcaixinha_aistudio_pg18",
        "pg_advisory_xact_lock",
        "FOR UPDATE OF t",
        "UPDATE public.credentials",
        "password_changed_at=checked_at",
        "UPDATE public.sessions",
        "SET revoked_at=checked_at",
        "UPDATE public.password_reset_tokens",
        "consumed_at=checked_at",
        "delivery_status='DELIVERED'",
        "to_regprocedure('public.frfinance_ack_access_mail(uuid,boolean)')",
        "REVOKE ALL ON FUNCTION public.frfinance_redeem_reset_token",
        "GRANT EXECUTE ON FUNCTION public.frfinance_redeem_reset_token",
    ]:
        assert req in sql, req
    for not_allowed in [
        "CREATE DATABASE", "CREATE TABLE ", "CREATE ROLE ",
        "ALTER ROLE", "DROP TABLE ", "initdb", "frcaixinha_2_2_pg18",
        "pg_resetwal", "SET ROLE",
    ]:
        assert not_allowed not in sql
