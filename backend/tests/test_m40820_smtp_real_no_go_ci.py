"""M40820: default real SMTP transport blocked, mocks preserved, no sending."""
from __future__ import annotations

from pathlib import Path

import pytest
import smtplib

from app.onboarding_mail_transport import (
    MailConfigurationBlocked, OutboundAcceptance,
    SmtpSubmissionConfig, submit_access_message,
)

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "backend/app/onboarding_mail_transport.py"
WORKFLOW = ROOT / ".github/workflows/frfinance-m40820-smtp-egress-no-go-ci.yml"
DOC = ROOT / "docs/FR_FINANCE_M40820_SMTP_REAL_EGRESS_NO_GO.md"
CFG = SmtpSubmissionConfig(
    host="smtp.example.invalid", port=587,
    user="synthetic-offline-user", password="synthetic-offline-password",
    sender="synthetic@example.invalid", app_origin="https://example.invalid",
)
TOKEN = "A" * 48


@pytest.mark.parametrize("reset", [False, True])
def test_default_smtp_socket_blocked_even_with_synthetic_valid_inputs(reset):
    with pytest.raises(MailConfigurationBlocked, match="M40820_REAL_SMTP_TRANSPORT_BLOCKED"):
        submit_access_message(config=CFG, recipient="user@example.invalid",
                              token=TOKEN, reset=reset)


def test_builtin_smtp_ssl_socket_blocked_as_explicit_factory():
    with pytest.raises(MailConfigurationBlocked, match="M40820_REAL_SMTP_TRANSPORT_BLOCKED"):
        submit_access_message(config=CFG, recipient="user@example.invalid",
                              token=TOKEN, reset=False, smtp_factory=smtplib.SMTP_SSL)


def test_no_smtp_socket_before_config_recipient_checks():
    with pytest.raises(MailConfigurationBlocked, match="M40820_REAL_SMTP_TRANSPORT_BLOCKED"):
        submit_access_message(config=CFG, recipient="invalid recipient",
                              token="bad token", reset=False)


class OfflineSmtp:
    sent = []
    def __init__(self, host, port, timeout):
        assert host == CFG.host and port == 587 and timeout == 10
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def ehlo(self):
        pass
    def starttls(self, *, context):
        assert context == "LOCAL_FAKE_CERT"
    def login(self, user, password):
        assert user == CFG.user and password == CFG.password
    def send_message(self, msg):
        self.sent.append(msg)
        return {}


@pytest.mark.parametrize("reset", [False, True])
def test_explicit_offline_mock_preserves_email_contract(reset):
    OfflineSmtp.sent.clear()
    response = submit_access_message(
        config=CFG, recipient="user@example.invalid", token=TOKEN,
        reset=reset, smtp_factory=OfflineSmtp,
        tls_context_factory=lambda: "LOCAL_FAKE_CERT",
    )
    assert response == OutboundAcceptance(smtp_accepted=True)
    assert response.recipient_verified is False
    assert response.provider_delivery_confirmed is False
    assert len(OfflineSmtp.sent) == 1
    msg = OfflineSmtp.sent[0]
    assert TOKEN in msg.get_content()
    assert msg["To"] == "user@example.invalid"


def test_mock_factory_failure_does_not_claim_acceptance():
    class Fails:
        def __init__(self, *a, **kw):
            raise TimeoutError("Synthetic network error with hidden credentials")
    from app.onboarding_mail_transport import MailSubmissionFailed
    with pytest.raises(MailSubmissionFailed) as exc:
        submit_access_message(config=CFG, recipient="user@example.invalid",
                              token=TOKEN, reset=False, smtp_factory=Fails)
    assert "hidden credentials" not in str(exc.value)


def test_no_default_live_transport_source_assertion():
    source = SOURCE.read_text(encoding="utf-8")
    assert 'smtp_factory is smtplib.SMTP or smtp_factory is smtplib.SMTP_SSL' in source
    assert "M40820_REAL_SMTP_TRANSPORT_BLOCKED" in source
    assert "not independently proven network-free" in source.lower()


def test_ci_and_docs_keep_external_mail_and_money_no_go():
    yml = WORKFLOW.read_text(encoding="utf-8")
    doc = DOC.read_text(encoding="utf-8")
    for tag in ("PIX_REAL: 'OFF'", "PAGAMENTOS_REAIS: 'OFF'",
                "ATIVACAO_REAL: 'OFF'", "test_m40820_smtp_real_no_go_ci.py"):
        assert tag in yml
    for tag in ("M40570", "M40730", "NO-GO", "PRODUCTION=BLOCKED"):
        assert tag in doc
