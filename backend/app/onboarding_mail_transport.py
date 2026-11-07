"""M25500 — SMTP submission adapter for invited user and password recovery.

Delivery is a two-phase operation: a successful SMTP transaction proves only
*acceptance by the outbound server*, not inbox receipt or ownership.
Never invoke from a public HTTP request before database-backed, single-use,
post-commit outbox with retries/idempotency and independent security approval.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from email.message import EmailMessage
from email.utils import parseaddr
import ipaddress
import re
import smtplib
import ssl
from typing import Callable, Mapping
from urllib.parse import urlsplit

from .config import safe_public_https_origin


class MailConfigurationBlocked(Exception):
    pass


class MailSubmissionFailed(Exception):
    pass


@dataclass(frozen=True, repr=False)
class SmtpSubmissionConfig:
    host: str
    port: int
    user: str = field(repr=False)
    password: str = field(repr=False)
    sender: str
    app_origin: str

    def __repr__(self):
        return "SmtpSubmissionConfig(redacted=True)"


@dataclass(frozen=True)
class OutboundAcceptance:
    smtp_accepted: bool
    recipient_verified: bool = False
    provider_delivery_confirmed: bool = False


def _mailbox(raw: str) -> str:
    if type(raw) is not str or len(raw) > 254 or any(ch.isspace() for ch in raw):
        raise MailConfigurationBlocked("EMAIL_FORMAT_INVALID")
    display, parsed = parseaddr(raw)
    if (display or raw != parsed or raw.count("@") != 1
            or not re.fullmatch(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+", raw)):
        raise MailConfigurationBlocked("EMAIL_FORMAT_INVALID")
    local, domain = raw.rsplit("@", 1)
    if (not local or not domain or "." not in domain
            or any(part == "" or part.startswith("-") or part.endswith("-")
                   for part in domain.split("."))):
        raise MailConfigurationBlocked("EMAIL_FORMAT_INVALID")
    return raw


def _smtp_host(raw: str) -> str:
    if (type(raw) is not str or not raw or len(raw) > 253
            or raw != raw.strip() or not re.fullmatch(r"[A-Za-z0-9.-]+", raw)
            or "." not in raw or raw.endswith((".test", ".invalid", ".local", ".internal"))):
        raise MailConfigurationBlocked("SMTP_HOST_INVALID")
    try:
        ipaddress.ip_address(raw)
    except ValueError:
        pass
    else:
        raise MailConfigurationBlocked("SMTP_HOST_INVALID")
    if any(not part or part.startswith("-") or part.endswith("-") for part in raw.split(".")):
        raise MailConfigurationBlocked("SMTP_HOST_INVALID")
    return raw.lower()


def verify_smtp_configuration(env: Mapping[str, str]) -> SmtpSubmissionConfig:
    """Syntax only. Does not prove SMTP authentication, TLS or real delivery."""
    app = safe_public_https_origin(env.get("APP_URL", ""))
    host = _smtp_host(env.get("SMTP_HOST", ""))
    sender = _mailbox(env.get("FR_FINANCE_EMAIL_FROM", ""))
    user, password = env.get("SMTP_USER", ""), env.get("SMTP_PASSWORD", "")
    raw_port = env.get("SMTP_PORT", "587")
    if (app is None or raw_port != "587" or not user or not password
            or len(password) < 16 or any(ch.isspace() for ch in user)
            or len(user) > 254):
        raise MailConfigurationBlocked("SMTP_TLS_CONFIG_UNVERIFIED")
    return SmtpSubmissionConfig(
        host=host, port=587, user=user, password=password,
        sender=sender, app_origin=app,
    )


def _invite_email(*, sender: str, recipient: str, link: str, reset: bool) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = _mailbox(recipient)
    msg["Subject"] = (
        "FR Finance — recuperação de acesso" if reset
        else "FR Finance — convite de acesso"
    )
    msg["Auto-Submitted"] = "auto-generated"
    msg["X-Auto-Response-Suppress"] = "All"
    msg.set_content(
        "Uma operação de acesso à plataforma FR Finance foi solicitada.\n"
        "Se você não reconhece esta solicitação, ignore a mensagem.\n"
        "Link de uso único, sujeito a expiração:\n"
        + link + "\n"
        "Nunca compartilhe este link. A confirmação de e-mail e o aceite "
        "contratual são etapas independentes.\n"
    )
    return msg


def _build_link(config: SmtpSubmissionConfig, *, token: str, reset: bool) -> str:
    # Fragmento não é enviado ao servidor HTTP; aplicação futura deve ler o
    # token do fragmento e enviá-lo a endpoint autenticador sem logs.
    if type(token) is not str or not re.fullmatch(r"[A-Za-z0-9_-]{32,256}", token):
        raise MailConfigurationBlocked("OPERATION_TOKEN_INVALID")
    page = "recuperacao" if reset else "convite"
    return f"{config.app_origin}/#{page}?token={token}"


def submit_access_message(
    *, config: SmtpSubmissionConfig, recipient: str, token: str,
    reset: bool, smtp_factory: Callable = smtplib.SMTP,
    tls_context_factory: Callable = ssl.create_default_context,
) -> OutboundAcceptance:
    """Submit one message over STARTTLS; NEVER claim delivery or identity proof.

    Only a post-commit trusted worker with durable idempotent outbox may call
    this. No SMTP exception or token is returned/logged to HTTP callers.
    """
    mailbox = _mailbox(recipient)
    if not isinstance(config, SmtpSubmissionConfig) or config.port != 587:
        raise MailConfigurationBlocked("SMTP_TLS_CONFIG_UNVERIFIED")
    link = _build_link(config, token=token, reset=reset)
    msg = _invite_email(sender=config.sender, recipient=mailbox, link=link, reset=reset)
    try:
        with smtp_factory(config.host, 587, timeout=10) as client:
            client.ehlo()
            client.starttls(context=tls_context_factory())
            client.ehlo()
            client.login(config.user, config.password)
            refused = client.send_message(msg)
            if refused:
                raise MailSubmissionFailed("SMTP_RECIPIENT_NOT_ACCEPTED")
    except MailSubmissionFailed:
        raise
    except (smtplib.SMTPException, OSError, TimeoutError) as exc:
        raise MailSubmissionFailed("SMTP_SUBMISSION_NOT_CONFIRMED") from None
    # Accepted for processing only. No bounce/delivery/ownership evidence yet.
    return OutboundAcceptance(smtp_accepted=True)
