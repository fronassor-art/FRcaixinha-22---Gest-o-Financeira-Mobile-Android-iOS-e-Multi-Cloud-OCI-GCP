"""FR Finance M38570-M38649: strict no-send SMTP authenticated preflight tests.

Only fake SMTP sockets. No network, real credentials, DB, mail or Pix.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
import smtplib
import ssl
import types

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "backend/scripts/aistudio_brevo_smtp_auth_nosend.py"
LOGIN = "12345@smtp-brevo.com"
SECRET = "SYNTHETIC_KEY_FOR_OFFLINE_TESTS_ONLY_12345"


def _load():
    spec = importlib.util.spec_from_file_location("m38649_smtp_preflight", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class FakeSmtp:
    def __init__(self, *, timeout, fail=None, overrides=None):
        self.timeout = timeout
        self.fail = fail
        self.overrides = overrides or {}
        self.calls = []
        self.closed = False
        self.tls_active = False

    def connect(self, host, port):
        self.calls.append(("connect", host, port))
        if self.fail == "connect":
            raise OSError("SENSITIVE_PRIVATE_NETWORK_ADDRESS")
        return self.overrides.get("banner", 220), b"SENSITIVE_BANNER"

    def ehlo(self):
        self.calls.append(("ehlo",))
        n = sum(c[0] == "ehlo" for c in self.calls)
        return self.overrides.get("ehlo_" + str(n), 250), b"SENSITIVE_EHLO"

    def has_extn(self, name):
        self.calls.append(("has_extn", name))
        return self.overrides.get(name, True)

    def starttls(self, *, context):
        self.calls.append(("starttls",))
        assert context.check_hostname is True
        assert context.verify_mode == ssl.CERT_REQUIRED
        assert context.minimum_version >= ssl.TLSVersion.TLSv1_2
        if self.fail == "tls":
            raise ssl.SSLError("SENSITIVE_TLS_FAILURE")
        self.tls_active = True
        return self.overrides.get("starttls_code", 220), b"SENSITIVE_TLS_REPLY"

    def login(self, username, key):
        self.calls.append(("login", username, key))
        assert self.tls_active is True, "AUTH must never precede TLS"
        if self.fail == "auth":
            raise smtplib.SMTPAuthenticationError(535, b"SENSITIVE_PROVIDER_AUTH_ERROR")
        return self.overrides.get("auth_code", 235), b"SENSITIVE_AUTH_REPLY"

    def close(self):
        self.calls.append(("close",))
        self.closed = True


def _install_fake(monkeypatch, mod, *, fail=None, overrides=None):
    clients = []
    def factory(*args, **kwargs):
        assert args == ()
        client = FakeSmtp(timeout=kwargs["timeout"], fail=fail,
                          overrides=overrides)
        clients.append(client)
        return client
    monkeypatch.setattr(mod.smtplib, "SMTP", factory)
    return clients


def test_offline_no_prompt_no_network(monkeypatch, capsys):
    mod = _load()
    monkeypatch.setattr(mod, "_prompt_credentials",
                        lambda: pytest.fail("prompted unexpectedly"))
    monkeypatch.setattr(mod, "_smtp_auth_no_send",
                        lambda *_: pytest.fail("connected unexpectedly"))
    assert mod.main(["offline"]) == 0
    out = capsys.readouterr().out
    assert "M38649_MODE=OFFLINE_NO_NETWORK_NO_CREDENTIALS" in out
    assert "M38649_SMTP_AUTH=NOT_TESTED" in out
    assert "M38649_PRODUCTION=BLOCKED" in out


@pytest.mark.parametrize("argv", [
    ["live"], ["live", "AUTHORIZE_SEND_REAL_EMAIL"],
    ["offline", "AUTHORIZE_BREVO_SMTP_STARTTLS_AUTH_NO_SEND"],
])
def test_no_explicit_authorization_must_not_prompt(monkeypatch, argv):
    mod = _load()
    monkeypatch.setattr(mod, "_prompt_credentials",
                        lambda: pytest.fail("prompted unexpectedly"))
    assert mod.main(argv) == 2


def test_excess_arguments_rejected_before_network(monkeypatch):
    mod = _load()
    monkeypatch.setattr(mod, "_prompt_credentials",
                        lambda: pytest.fail("prompted unexpectedly"))
    with pytest.raises(SystemExit):
        mod.main(["live", mod.AUTHORIZATION, "EXTRA"])


def test_non_interactive_tty_rejected_before_password_prompt(monkeypatch):
    mod = _load()
    monkeypatch.setattr(mod.sys, "stdin", types.SimpleNamespace(isatty=lambda: False))
    monkeypatch.setattr(mod.getpass, "getpass", lambda *_: pytest.fail("prompt"))
    with pytest.raises(mod.SmtpPreflightBlocked, match="TTY_REQUIRED"):
        mod._prompt_credentials()


@pytest.mark.parametrize("login,secret,code", [
    ("", SECRET, "LOGIN_FORMAT"),
    ("smtp-relay.brevo.com", SECRET, "LOGIN_FORMAT"),
    ("a@example.com\nBcc:attacker@example.org", SECRET, "LOGIN_FORMAT"),
    ("frfinance.com.br", SECRET, "LOGIN_FORMAT"),
    (LOGIN, "", "KEY_FORMAT"),
    (LOGIN, "pass\r\nMAIL FROM", "KEY_FORMAT"),
    (LOGIN, "A" * 513, "KEY_FORMAT"),
    (LOGIN, "🔑" * 10, "KEY_FORMAT"),
    (LOGIN, None, "KEY_FORMAT"),
])
def test_invalid_credentials_blocked_before_network(login, secret, code, monkeypatch):
    mod = _load()
    clients = _install_fake(monkeypatch, mod)
    with pytest.raises(mod.SmtpPreflightBlocked, match=code):
        mod._smtp_auth_no_send(login, secret)
    assert clients == []


def test_complete_hello_starttls_hello_auth_only_sequence(monkeypatch):
    mod = _load()
    clients = _install_fake(monkeypatch, mod)
    mod._smtp_auth_no_send(LOGIN, SECRET)
    assert len(clients) == 1
    calls = clients[0].calls
    assert clients[0].timeout == mod.TIMEOUT_SECONDS
    assert calls == [
        ("connect", "smtp-relay.brevo.com", 587),
        ("ehlo",),
        ("has_extn", "starttls"),
        ("starttls",),
        ("ehlo",),
        ("has_extn", "auth"),
        ("login", LOGIN, SECRET),
        ("close",),
    ]
    assert clients[0].closed is True


@pytest.mark.parametrize("overrides,blocked,expected_calls", [
    ({"banner": 421}, "SMTP_BANNER", ["connect", "close"]),
    ({"ehlo_1": 500}, "SMTP_EHLO", ["connect", "ehlo", "close"]),
    ({"starttls": False}, "STARTTLS_REQUIRED", ["connect", "ehlo", "has_extn", "close"]),
    ({"starttls_code": 454}, "STARTTLS_NEGOTIATION",
     ["connect", "ehlo", "has_extn", "starttls", "close"]),
    ({"ehlo_2": 500}, "TLS_AUTH_CAPABILITY", None),
    ({"auth": False}, "TLS_AUTH_CAPABILITY", None),
    ({"auth_code": 250}, "SMTP_AUTH_NOT_CONFIRMED", None),
])
def test_negative_smtp_cases_fail_closed(
    monkeypatch, overrides, blocked, expected_calls
):
    mod = _load()
    clients = _install_fake(monkeypatch, mod, overrides=overrides)
    with pytest.raises(mod.SmtpPreflightBlocked, match=blocked):
        mod._smtp_auth_no_send(LOGIN, SECRET)
    assert len(clients) == 1 and clients[0].closed
    if expected_calls:
        assert [c[0] for c in clients[0].calls] == expected_calls


@pytest.mark.parametrize("failure,code", [
    ("connect", "SMTP_TLS_OR_NETWORK_FAILURE"),
    ("tls", "SMTP_TLS_OR_NETWORK_FAILURE"),
    ("auth", "SMTP_CREDENTIALS_REJECTED"),
])
def test_network_tls_and_auth_errors_sanitized(monkeypatch, failure, code):
    mod = _load()
    clients = _install_fake(monkeypatch, mod, fail=failure)
    with pytest.raises(mod.SmtpPreflightBlocked) as err:
        mod._smtp_auth_no_send(LOGIN, SECRET)
    assert str(err.value) == "M38649_" + code
    assert "SENSITIVE" not in str(err.value)
    assert clients[0].closed


def test_live_opt_in_never_sends_or_enables_user_activation(monkeypatch, capsys):
    mod = _load()
    monkeypatch.setattr(mod, "_prompt_credentials", lambda: (LOGIN, SECRET))
    clients = _install_fake(monkeypatch, mod)
    assert mod.main(["live", mod.AUTHORIZATION]) == 0
    out = capsys.readouterr().out
    assert "M38649_SMTP_AUTH=CONFIRMED_FOR_THIS_SESSION_ONLY" in out
    assert "M38649_DOMAIN_STATUS=NOT_ATTESTED_BY_SMTP" in out
    assert "M38649_MAIL_SEND=NONE" in out
    assert "M38649_EMAIL_REAL=OFF" in out
    assert "M38649_REAL_USER_ACTIVATION=OFF" in out
    assert "M38649_PIX_REAL=OFF" in out
    assert "M38649_PRODUCTION=BLOCKED" in out
    assert LOGIN not in out and SECRET not in out
    assert "SENSITIVE" not in out
    assert clients[0].closed


def test_failed_live_opt_in_has_no_secret_in_output(monkeypatch, capsys):
    mod = _load()
    monkeypatch.setattr(mod, "_prompt_credentials", lambda: (LOGIN, SECRET))
    _install_fake(monkeypatch, mod, fail="auth")
    assert mod.main(["live", mod.AUTHORIZATION]) == 2
    out = capsys.readouterr().out
    assert "M38649_CAUSE=M38649_SMTP_CREDENTIALS_REJECTED" in out
    assert "M38649_SMTP_AUTH=NOT_CONFIRMED" in out
    assert "M38649_PRODUCTION=BLOCKED" in out
    assert SECRET not in out and LOGIN not in out
    assert "SENSITIVE" not in out


def test_static_no_mail_envelope_no_db_no_cloud_no_env_key():
    source = SCRIPT.read_text()
    for forbidden in (
        "sendmail(", "send_message(", ".mail(", ".rcpt(", ".data(",
        "SMTP_SSL(", "set_debuglevel(", "os.getenv(", "os.environ",
        "psycopg.connect(", "INSERT INTO", "subprocess.run(",
        "oci.core.ComputeClient(", "requests.post(",
    ):
        assert forbidden not in source
    assert "AUTHORIZATION = " in source
    assert "getpass.getpass" in source
    assert "smtp.starttls(context=context)" in source
    assert "smtp.login(login, secret)" in source
    assert "smtp.close()" in source
