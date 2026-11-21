"""M25500 — SMTP only with TLS, no real networking, delivery never implied."""
import pytest

from app.onboarding_mail_transport import (
    MailConfigurationBlocked, MailSubmissionFailed, OutboundAcceptance,
    verify_smtp_configuration, submit_access_message,
)


def env():
    return {
        "ENVIRONMENT": "staging",
        "APP_URL": "https://financas.exemplo.com.br",
        "SMTP_HOST": "smtp.exemplo.com.br",
        "SMTP_PORT": "587",
        "SMTP_USER": "ci-only-user@example.com",
        "SMTP_PASSWORD": "temporary-ci-placeholder-secret",
        "FR_FINANCE_EMAIL_FROM": "notificacoes@exemplo.com.br",
    }


TOKEN = "A" * 48


class FakeSMTP:
    records = []
    def __init__(self, host, port, timeout):
        assert host == "smtp.exemplo.com.br"
        assert port == 587
        assert timeout == 10
        self.calls = []
        self.mail = None
        FakeSMTP.records.append(self)
    def __enter__(self):
        return self
    def __exit__(self, typ, value, traceback):
        return False
    def ehlo(self):
        self.calls.append("EHLO")
    def starttls(self, *, context):
        assert context == "FAKE_CERTIFICATE_VERIFIER"
        self.calls.append("STARTTLS")
    def login(self, user, password):
        assert user == "ci-only-user@example.com"
        assert password == "temporary-ci-placeholder-secret"
        self.calls.append("LOGIN")
    def send_message(self, mail):
        self.mail = mail
        self.calls.append("SEND")
        return {}


def test_submit_invite_requires_verified_syntax_and_tls():
    conf = verify_smtp_configuration(env())
    assert conf.port == 587
    assert "temporary-ci-placeholder-secret" not in repr(conf)
    FakeSMTP.records.clear()
    receipt = submit_access_message(
        config=conf, recipient="membro@example.com", token=TOKEN,
        reset=False, smtp_factory=FakeSMTP,
        tls_context_factory=lambda: "FAKE_CERTIFICATE_VERIFIER",
    )
    assert receipt == OutboundAcceptance(smtp_accepted=True)
    assert receipt.provider_delivery_confirmed is False
    assert receipt.recipient_verified is False
    instance = FakeSMTP.records[-1]
    assert instance.calls == ["EHLO", "STARTTLS", "EHLO", "LOGIN", "SEND"]
    assert instance.mail["To"] == "membro@example.com"
    assert "convite de acesso" in str(instance.mail["Subject"])
    assert "#convite?token=" in instance.mail.get_content()
    assert TOKEN in instance.mail.get_content()
    assert "temporary-ci-placeholder-secret" not in instance.mail.get_content()


def test_submit_reset_uses_a_different_link_but_not_a_delivery_proof():
    conf = verify_smtp_configuration(env())
    submit_access_message(
        config=conf, recipient="pessoa@example.com", token=TOKEN,
        reset=True, smtp_factory=FakeSMTP,
        tls_context_factory=lambda: "FAKE_CERTIFICATE_VERIFIER",
    )
    assert "#recuperacao?token=" in FakeSMTP.records[-1].mail.get_content()
    assert "recuperação de acesso" in FakeSMTP.records[-1].mail["Subject"]


@pytest.mark.parametrize("key,value", [
    ("APP_URL", "http://insecure.example.com"),
    ("APP_URL", "https://localhost"),
    ("SMTP_HOST", "127.0.0.1"),
    ("SMTP_HOST", "smtp.internal"),
    ("SMTP_HOST", "localhost"),
    ("SMTP_PORT", "25"),
    ("SMTP_PORT", "465"),
    ("SMTP_USER", ""),
    ("SMTP_PASSWORD", "short"),
    ("FR_FINANCE_EMAIL_FROM", "bad recipient\r\nX: forged"),
    ("FR_FINANCE_EMAIL_FROM", "unknown"),
])
def test_bad_smtp_configuration_is_blocked(key, value):
    raw = env()
    raw[key] = value
    with pytest.raises(MailConfigurationBlocked):
        verify_smtp_configuration(raw)


@pytest.mark.parametrize("token", ["", "short", "x"*300, "bad token", "x\nBcc: test"])
def test_no_weak_or_injectable_tokens(token):
    conf = verify_smtp_configuration(env())
    FakeSMTP.records.clear()
    with pytest.raises(MailConfigurationBlocked):
        submit_access_message(
            config=conf, recipient="user@example.com", token=token,
            reset=False, smtp_factory=FakeSMTP,
            tls_context_factory=lambda: "FAKE_CERTIFICATE_VERIFIER",
        )
    assert not FakeSMTP.records


def test_recipient_rejects_header_injection_without_opening_network():
    conf = verify_smtp_configuration(env())
    FakeSMTP.records.clear()
    with pytest.raises(MailConfigurationBlocked):
        submit_access_message(
            config=conf, recipient="pessoa@example.com\nBcc: other@example.com",
            token=TOKEN, reset=False, smtp_factory=FakeSMTP,
        )
    assert not FakeSMTP.records


def test_submission_error_is_generic_and_never_claims_delivery():
    conf = verify_smtp_configuration(env())
    class ConnectionFails:
        def __init__(self, *args, **kwargs):
            raise TimeoutError("secret host information")
    with pytest.raises(MailSubmissionFailed) as exc:
        submit_access_message(
            config=conf, recipient="recipient@example.com",
            token=TOKEN, reset=False, smtp_factory=ConnectionFails,
        )
    assert "secret host information" not in str(exc.value)
    assert TOKEN not in str(exc.value)


def test_provider_rejection_is_not_accepted():
    conf = verify_smtp_configuration(env())
    class RecipientRefused(FakeSMTP):
        def send_message(self, mail):
            return {mail["To"]: (550, "refused")}
    with pytest.raises(MailSubmissionFailed):
        submit_access_message(
            config=conf, recipient="recipient@example.com",
            token=TOKEN, reset=False, smtp_factory=RecipientRefused,
            tls_context_factory=lambda: "FAKE_CERTIFICATE_VERIFIER",
        )


def test_no_public_route_invokes_mail_transport_directly():
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    invites = (root / "backend/app/routers/invitations.py").read_text()
    auth = (root / "backend/app/routers/auth.py").read_text()
    assert "submit_access_message" not in invites
    assert "submit_access_message" not in auth
    assert "Recuperação de senha por e-mail ainda não implementada" in auth
    assert "Convites ainda não implementados" in invites
