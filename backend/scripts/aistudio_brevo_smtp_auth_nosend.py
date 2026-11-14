#!/usr/bin/env python3
"""FR Finance M38570-M38649: opt-in Brevo SMTP STARTTLS AUTH, NO EMAIL SEND.

Only a local, interactive operator may explicitly request one authentication
attempt. This is NOT a delivery test, sender/domain approval, or release gate.
No CLI/env/config credentials; no SMTP message envelope is ever constructed.
"""
from __future__ import annotations

import argparse
import getpass
import re
import smtplib
import ssl
import sys

HOST = "smtp-relay.brevo.com"
PORT = 587
TIMEOUT_SECONDS = 12
AUTHORIZATION = "AUTHORIZE_BREVO_SMTP_STARTTLS_AUTH_NO_SEND"
_LOGIN = re.compile(r"[A-Za-z0-9._%+-]{1,128}@[A-Za-z0-9.-]{1,190}\.[A-Za-z]{2,30}\Z", re.ASCII)


class SmtpPreflightBlocked(ValueError):
    """Stable diagnostic only. Never attach SMTP replies or credential values."""


def _credential_format(login: object, secret: object) -> None:
    if (type(login) is not str or len(login) > 254
            or not _LOGIN.fullmatch(login)
            or login.lower() == HOST):
        raise SmtpPreflightBlocked("M38649_SMTP_LOGIN_FORMAT_BLOCKED")
    if (type(secret) is not str or not 8 <= len(secret) <= 512
            or not all(33 <= ord(ch) <= 126 for ch in secret)):
        raise SmtpPreflightBlocked("M38649_SMTP_KEY_FORMAT_BLOCKED")


def _prompt_credentials() -> tuple[str, str]:
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        raise SmtpPreflightBlocked("M38649_INTERACTIVE_TTY_REQUIRED")
    try:
        # Both fields are hidden. Never paste credentials into the chat.
        login = getpass.getpass("Login SMTP Brevo (oculto): ")
        secret = getpass.getpass("Chave SMTP Brevo (oculta): ")
    except Exception:
        raise SmtpPreflightBlocked("M38649_CREDENTIAL_PROMPT_FAILED") from None
    _credential_format(login, secret)
    return login, secret


def _smtp_auth_no_send(login: str, secret: str) -> None:
    """Use only: TCP banner, EHLO, STARTTLS, EHLO, AUTH; close socket.

    Deliberately never calls MAIL FROM, RCPT TO, DATA, SEND, or SMTP QUIT
    (closing the socket is sufficient here). Network access only after an
    explicit interactive authorization and credential validation.
    """
    _credential_format(login, secret)
    context = ssl.create_default_context()
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    if not context.check_hostname or context.verify_mode != ssl.CERT_REQUIRED:
        raise SmtpPreflightBlocked("M38649_TLS_POLICY_BLOCKED")
    smtp = smtplib.SMTP(timeout=TIMEOUT_SECONDS)
    try:
        code, _ = smtp.connect(HOST, PORT)
        if type(code) is not int or code != 220:
            raise SmtpPreflightBlocked("M38649_SMTP_BANNER_BLOCKED")
        code, _ = smtp.ehlo()
        if type(code) is not int or code != 250:
            raise SmtpPreflightBlocked("M38649_SMTP_EHLO_BLOCKED")
        if not smtp.has_extn("starttls"):
            raise SmtpPreflightBlocked("M38649_STARTTLS_REQUIRED")
        code, _ = smtp.starttls(context=context)
        if type(code) is not int or code != 220:
            raise SmtpPreflightBlocked("M38649_STARTTLS_NEGOTIATION_BLOCKED")
        code, _ = smtp.ehlo()
        if type(code) is not int or code != 250 or not smtp.has_extn("auth"):
            raise SmtpPreflightBlocked("M38649_TLS_AUTH_CAPABILITY_BLOCKED")
        code, _ = smtp.login(login, secret)
        if type(code) is not int or code != 235:
            raise SmtpPreflightBlocked("M38649_SMTP_AUTH_NOT_CONFIRMED")
    except SmtpPreflightBlocked:
        raise
    except smtplib.SMTPAuthenticationError:
        raise SmtpPreflightBlocked("M38649_SMTP_CREDENTIALS_REJECTED") from None
    except smtplib.SMTPNotSupportedError:
        raise SmtpPreflightBlocked("M38649_SMTP_EXTENSION_UNSUPPORTED") from None
    except (OSError, TimeoutError, smtplib.SMTPException, ssl.SSLError):
        raise SmtpPreflightBlocked("M38649_SMTP_TLS_OR_NETWORK_FAILURE") from None
    except Exception:
        raise SmtpPreflightBlocked("M38649_SMTP_UNCLASSIFIED_FAILURE") from None
    finally:
        smtp.close()


def _closed_status() -> None:
    print("M38649_MAIL_SEND=NONE")
    print("M38649_EMAIL_REAL=OFF")
    print("M38649_PIX_REAL=OFF")
    print("M38649_PAYMENTS_REAL=OFF")
    print("M38649_REAL_USER_ACTIVATION=OFF")
    print("M38649_DATABASE_MUTATIONS=NONE")
    print("M38649_PROVIDER_CONFIG_MUTATIONS=NONE")
    print("M38649_PRODUCTION=BLOCKED")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Brevo SMTP TLS+AUTH no-send preflight")
    parser.add_argument("action", nargs="?", choices=("offline", "live"), default="offline")
    parser.add_argument("authorization", nargs="?")
    args = parser.parse_args(argv)

    print("=== FR FINANCE M38570-M38649 SMTP AUTH NO SEND ===")
    if args.action == "offline":
        if args.authorization is not None:
            print("M38649_PREFLIGHT=BLOCKED_UNEXPECTED_AUTHORIZATION")
            _closed_status()
            return 2
        print("M38649_MODE=OFFLINE_NO_NETWORK_NO_CREDENTIALS")
        print("M38649_SMTP_AUTH=NOT_TESTED")
        _closed_status()
        return 0

    if args.authorization != AUTHORIZATION:
        print("M38649_PREFLIGHT=BLOCKED_EXPLICIT_AUTHORIZATION_REQUIRED")
        _closed_status()
        return 2

    try:
        login, secret = _prompt_credentials()
        try:
            _smtp_auth_no_send(login, secret)
        finally:
            # Python cannot guarantee secure zeroization of immutable strings.
            # Do not persist to disk, logger, shell history or exceptions.
            del login, secret
    except SmtpPreflightBlocked as exc:
        print("M38649_PREFLIGHT=BLOCKED")
        print("M38649_CAUSE=" + str(exc))
        print("M38649_SMTP_AUTH=NOT_CONFIRMED")
        _closed_status()
        return 2
    except Exception:
        print("M38649_PREFLIGHT=BLOCKED_UNCLASSIFIED")
        print("M38649_SMTP_AUTH=NOT_CONFIRMED")
        _closed_status()
        return 2

    print("M38649_MODE=LIVE_OPT_IN_AUTH_ONLY")
    print("M38649_SMTP_TLS_AND_LOGIN=PROVIDER_REPORTED_SUCCESS")
    print("M38649_SMTP_AUTH=CONFIRMED_FOR_THIS_SESSION_ONLY")
    print("M38649_DOMAIN_STATUS=NOT_ATTESTED_BY_SMTP")
    print("M38649_SENDER_VERIFICATION=NOT_ATTESTED")
    print("M38649_CONTROLLED_DELIVERY=NOT_TESTED")
    print("M38649_DKIM_ALIGNMENT=NOT_TESTED")
    print("M38649_REAL_RECIPIENT_CONSENT=NOT_ATTESTED")
    _closed_status()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
