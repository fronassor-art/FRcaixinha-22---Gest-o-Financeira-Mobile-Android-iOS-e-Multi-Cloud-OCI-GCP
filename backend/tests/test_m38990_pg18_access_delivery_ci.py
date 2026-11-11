"""M38990: operational one-DB access queue; synthetic tests never contact DB/SMTP."""
from __future__ import annotations

import asyncio
import base64
from contextlib import asynccontextmanager
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.access_delivery_pg18 import (
    AccessQueueBlocked, Pg18AccessDelivery, _digest, _email, _sealed, _unseal,
    install_existing_access_delivery, require_reviewed_config,
    verify_existing_schema,
)
from app.dependencies import AuthenticatedSession
from app.main import app

ROOT = Path(__file__).resolve().parents[2]
SQL = ROOT / "backend/local_migrations/047_frfinance_access_delivery_outbox.sql"


def env():
    return {
        "ENVIRONMENT": "homologation",
        "FRCAIXINHA_TERMUX_LOCAL_API": "1",
        "FR_FINANCE_ACCESS_MAIL_ENABLE": "REVIEWED_SINGLE_DB",
        "FR_FINANCE_OUTBOX_047_VERIFIED": "YES",
        "FR_FINANCE_SMTP_OPERATOR_APPROVED": "YES",
        "AUTH_DATABASE_URL": (
            "postgresql://frc_ai_auth:synthetic-not-a-real-password@"
            "127.0.0.1:5433/frcaixinha_aistudio_dev"
        ),
        "FR_FINANCE_ACCESS_ENCRYPTION_KEY_B64": base64.b64encode(
            b"x"*32).decode(),
        "FR_FINANCE_ACCESS_HMAC_KEY": "separate-HMAC-pepper-for-synthetic-CI-only-XYZ",
        "APP_URL": "https://frfinance.com.br",
        "SMTP_HOST": "smtp-relay.brevo.com",
        "SMTP_PORT": "587",
        "SMTP_USER": "ci-only-user@example.invalid",
        "SMTP_PASSWORD": "synthetic-ci-only-long-password",
        "FR_FINANCE_EMAIL_FROM": "notificacoes@frfinance.com.br",
    }


@pytest.mark.parametrize("variable", [
    "FR_FINANCE_ACCESS_MAIL_ENABLE", "FR_FINANCE_OUTBOX_047_VERIFIED",
    "FR_FINANCE_SMTP_OPERATOR_APPROVED", "AUTH_DATABASE_URL",
    "FR_FINANCE_ACCESS_ENCRYPTION_KEY_B64", "FR_FINANCE_ACCESS_HMAC_KEY",
    "APP_URL", "SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD",
    "FR_FINANCE_EMAIL_FROM",
])
def test_all_operational_prerequisites_are_required(variable):
    val = env()
    val.pop(variable, None)
    with pytest.raises(AccessQueueBlocked):
        require_reviewed_config(val)


@pytest.mark.parametrize("wrong", [
    "postgresql://frc_ai_owner:synthetic-long@127.0.0.1:5433/frcaixinha_aistudio_dev",
    "postgresql://frc_ai_auth:synthetic-long@127.0.0.1:5432/frcaixinha_aistudio_dev",
    "postgresql://frc_ai_auth:synthetic-long@127.0.0.1:5433/frcaixinha_2_2_dev",
    "postgresql://frc_ai_auth:synthetic-long@localhost:5433/frcaixinha_aistudio_dev",
    "postgresql://frc_ai_auth:synthetic-long@127.0.0.1:5433/frcaixinha_aistudio_dev?options=unsafe",
])
def test_wrong_owner_port_hostname_db_or_url_options_fail_closed(wrong):
    val = env()
    val["AUTH_DATABASE_URL"] = wrong
    with pytest.raises(AccessQueueBlocked):
        require_reviewed_config(val)


def test_envelope_authenticates_event_type_and_data():
    conf = require_reviewed_config(env())
    event = uuid4()
    token = "A"*56
    data = _sealed(conf, event=event, kind="INVITE_MEMBER",
                   recipient="member@example.com", token=token)
    assert len(data) > 44
    assert token.encode() not in data
    assert b"member@example.com" not in data
    assert _unseal(conf, event=event, kind="INVITE_MEMBER", ciphertext=data) == (
        "member@example.com", token)
    with pytest.raises(AccessQueueBlocked):
        _unseal(conf, event=uuid4(), kind="INVITE_MEMBER", ciphertext=data)
    with pytest.raises(AccessQueueBlocked):
        _unseal(conf, event=event, kind="RESET", ciphertext=data)
    with pytest.raises(AccessQueueBlocked):
        _unseal(conf, event=event, kind="INVITE_MEMBER",
                ciphertext=data[:-1]+bytes([data[-1]^1]))
    assert "synthetic" not in repr(conf)


def test_digests_do_not_store_plaintext_emails():
    config = require_reviewed_config(env())
    a = _digest(config, "email", "member@example.com")
    b = _digest(config, "email", "other@example.com")
    assert len(a) == len(b) == 64
    assert a != b
    assert "@example.com" not in a


@pytest.mark.parametrize("bad", [
    "a", "missing-at", "member @example.com", "member@example",
    "a@bad..example", "member\n@example.com",
])
def test_reject_bad_recipient_before_db(bad):
    with pytest.raises(AccessQueueBlocked):
        _email(bad)


class FakeDB:
    def __init__(self, *, accepted=True, record=None):
        self.accepted = accepted
        self.record = record
        self.closed = False
        self.calls = []

    @asynccontextmanager
    async def transaction(self):
        self.calls.append("BEGIN")
        try:
            yield
            self.calls.append("COMMIT")
        except BaseException:
            self.calls.append("ROLLBACK")
            raise

    async def fetchval(self, sql, *args):
        self.calls.append((sql, args))
        if "enqueue" in sql:
            return self.accepted
        if "ack" in sql:
            return self.accepted
        return False

    async def fetchrow(self, sql, *args):
        self.calls.append((sql, args))
        return self.record

    async def close(self):
        self.closed = True


def session():
    tenant = uuid4()
    sid = uuid4()
    return AuthenticatedSession(
        str(uuid4()), "TENANT_ADMIN", str(tenant),
        "admin@example.invalid", "Admin Test", False,
        verified_session_id=str(sid),
        verification_source="POSTGRES_TOKEN_HASH_REFRESH",
    )


@pytest.mark.asyncio
async def test_real_port_queues_member_invite_in_one_pg_transaction(monkeypatch):
    import app.access_delivery_pg18 as m
    db = FakeDB()
    monkeypatch.setattr(m, "_connect", lambda conf: asyncio.sleep(0, result=db))
    conf = require_reviewed_config(env())
    sess = session()
    payload = SimpleNamespace(
        target_role="TENANT_MEMBER", tenant_id=sess.tenant_id,
        target_email="member@example.com", required_document_id=uuid4(),
    )
    result = await Pg18AccessDelivery(conf).invite(session=sess, payload=payload)
    assert result.persisted is True and result.durable_outbox_queued is True
    assert result.email_sent is False
    assert db.calls[0] == "BEGIN"
    assert db.calls[-1] == "COMMIT"
    assert db.closed
    sql, args = db.calls[1]
    assert "frfinance_enqueue_member_invite" in sql
    assert args[2] == UUID(sess.tenant_id)
    assert args[4] == "member@example.com"
    assert len(args[5]) == 64 and args[5].isalnum()
    assert b"member@example.com" not in args[8]


@pytest.mark.asyncio
async def test_outbox_rejection_rolls_back_and_does_not_claim_mail(monkeypatch):
    import app.access_delivery_pg18 as m
    db = FakeDB(accepted=False)
    monkeypatch.setattr(m, "_connect", lambda conf: asyncio.sleep(0, result=db))
    conf = require_reviewed_config(env())
    sess = session()
    payload = SimpleNamespace(
        target_role="TENANT_MEMBER", tenant_id=sess.tenant_id,
        target_email="member@example.com", required_document_id=uuid4(),
    )
    with pytest.raises(HTTPException) as exc:
        await Pg18AccessDelivery(conf).invite(session=sess, payload=payload)
    assert exc.value.status_code == 503
    assert db.closed and db.calls[-1] == "ROLLBACK"


@pytest.mark.asyncio
async def test_legacy_unverified_session_never_touches_database(monkeypatch):
    import app.access_delivery_pg18 as m
    monkeypatch.setattr(m, "_connect", lambda c: pytest.fail("never DB"))
    sess = session()
    sess.verification_source = "LEGACY_NO_SESSION_BINDING"
    payload = SimpleNamespace(
        tenant_id=sess.tenant_id, target_email="m@example.com",
        required_document_id=uuid4(),
    )
    with pytest.raises(HTTPException) as exc:
        await Pg18AccessDelivery(require_reviewed_config(env())).invite(
            session=sess, payload=payload)
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_reset_queue_has_no_email_address_in_response(monkeypatch):
    import app.access_delivery_pg18 as m
    db = FakeDB()
    monkeypatch.setattr(m, "_connect", lambda c: asyncio.sleep(0, result=db))
    conf = require_reviewed_config(env())
    receipt = await Pg18AccessDelivery(conf).reset(
        email="member@example.com", source_ip="127.0.0.1")
    assert receipt.persisted and receipt.durable_outbox_queued
    sql, args = db.calls[1]
    assert "frfinance_enqueue_password_reset" in sql
    assert args[1] == "member@example.com"
    assert args[3] == _digest(conf, "email", "member@example.com")
    assert args[4] == _digest(conf, "origin", "127.0.0.1")
    assert db.closed


@pytest.mark.asyncio
async def test_smtp_dispatch_never_sends_without_queued_record(monkeypatch):
    import app.access_delivery_pg18 as m
    db = FakeDB(record=None)
    monkeypatch.setattr(m, "_connect", lambda c: asyncio.sleep(0, result=db))
    monkeypatch.setattr(m, "submit_access_message", lambda **k: pytest.fail("SMTP"))
    result = await Pg18AccessDelivery(require_reviewed_config(env())).dispatch_one()
    assert result == "IDLE"


@pytest.mark.asyncio
async def test_smtp_acceptance_is_not_delivery_or_activation(monkeypatch):
    import app.access_delivery_pg18 as m
    conf = require_reviewed_config(env())
    event, token = uuid4(), "A"*56
    record = dict(
        event_id=event, kind="RESET",
        sealed_message=_sealed(conf,event=event,kind="RESET",
                               recipient="member@example.com",token=token),
        expires_at=__import__("datetime").datetime.now(
            __import__("datetime").timezone.utc)
            + __import__("datetime").timedelta(minutes=1),
    )
    work = FakeDB(record=record)
    ack = FakeDB(accepted=True)
    sequence = iter((work,ack))
    monkeypatch.setattr(m, "_connect", lambda c: asyncio.sleep(
        0, result=next(sequence)))
    def fake_smtp(**kwargs):
        assert kwargs["recipient"] == "member@example.com"
        assert kwargs["token"] == token
        assert kwargs["reset"] is True
        return SimpleNamespace(smtp_accepted=True)
    monkeypatch.setattr(m, "submit_access_message", fake_smtp)
    assert await Pg18AccessDelivery(conf).dispatch_one() == "SMTP_ACCEPTED_NOT_DELIVERED"
    assert ack.calls[0][1][1] is True


def test_api_queue_never_auto_starts_a_second_server_or_db():
    main = (ROOT / "backend/app/main.py").read_text()
    source = (ROOT / "backend/app/access_delivery_pg18.py").read_text()
    assert "install_existing_access_delivery(app, os.environ)" in main
    assert 'FR_FINANCE_ACCESS_MAIL_ENABLE' in main
    assert 'FR_FINANCE_ACCESS_MAIL_WORKER' in main
    for forbidden in (
        "CREATE DATABASE", "createdb", "initdb", "pg_ctl start",
        "FastAPI(", "uvicorn.run(", "os.system(", "CREATE ROLE",
    ):
        assert forbidden not in source
    assert "frcaixinha_2_2_dev" not in source


def test_sql_is_only_one_original_postgresql_database_and_approved_migration():
    sql = SQL.read_text()
    assert "current_database()<>'frcaixinha_aistudio_dev'" in sql
    assert "inet_server_port()<>5433" in sql
    assert "session_user<>'frc_ai_owner'" in sql
    assert "'frfinance.migration_047_approved'" in sql
    assert "frcaixinha_aistudio_pg18" in sql
    assert "frfinance_enqueue_member_invite" in sql
    assert "frfinance_enqueue_password_reset" in sql
    assert "frfinance_claim_access_mail" in sql
    assert "frfinance_ack_access_mail" in sql
    assert "FOR UPDATE SKIP LOCKED" in sql
    assert "ENABLE ROW LEVEL SECURITY" in sql
    assert "FORCE ROW LEVEL SECURITY" in sql
    assert "CREATE DATABASE" not in sql
    assert "CREATE ROLE" not in sql
    assert "frcaixinha_2_2_pg18" not in sql
    assert "ALTER ROLE" not in sql


def test_service_off_by_default_in_existing_testclient(monkeypatch):
    monkeypatch.delenv("FR_FINANCE_ACCESS_MAIL_ENABLE", raising=False)
    with TestClient(app) as client:
        assert client.get("/api/health").status_code == 200
        assert not hasattr(app.state, "access_delivery_runtime")
