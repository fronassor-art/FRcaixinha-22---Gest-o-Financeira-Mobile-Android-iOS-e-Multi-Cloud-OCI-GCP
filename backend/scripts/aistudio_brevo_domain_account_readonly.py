#!/usr/bin/env python3
"""FR Finance M38530-M38569: Brevo domain-account GET status, opt-in only.

Uses official GET /v3/senders/domains/frfinance.com.br, never PUT/authenticate
or SMTP send. The API key is entered into an interactive terminal (getpass),
is never printed or persisted by this tool, and is not accepted as an argument.
Do not run in CI, cron or an unattended session.
"""
from __future__ import annotations

import argparse
import getpass
import json
import re
import ssl
import sys
from urllib.error import HTTPError
from urllib.request import (
    HTTPRedirectHandler, HTTPSHandler, ProxyHandler, Request, build_opener,
)

from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent))
from app.brevo_account_domain_attestation import (
    BrevoDomainStatusBlocked, DOMAIN, assess_brevo_account_response,
)

_URL="https://api.brevo.com/v3/senders/domains/frfinance.com.br"
_API_KEY_PATTERN=re.compile(r"[A-Za-z0-9_.-]{20,512}\Z")
_MAX_RESPONSE=32768


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _prompt_api_key() -> str:
    if not sys.stdin.isatty():
        raise BrevoDomainStatusBlocked("M38530_INTERACTIVE_TERMINAL_REQUIRED")
    try:
        api_key=getpass.getpass("Chave de API Brevo (oculta, nao salva): ")
    except Exception:
        raise BrevoDomainStatusBlocked("M38530_KEY_INPUT_UNAVAILABLE") from None
    if (type(api_key) is not str
            or _API_KEY_PATTERN.fullmatch(api_key) is None):
        raise BrevoDomainStatusBlocked("M38530_BREVO_API_KEY_INVALID_FORMAT")
    return api_key


def _unique_json(pairs):
    output={}
    for key,value in pairs:
        if key in output:
            raise BrevoDomainStatusBlocked("M38530_BREVO_JSON_DUPLICATE_KEY")
        output[key]=value
    return output


def _api_get_domain(api_key: str) -> object:
    """Fixed HTTPS host+path, strict response and TLS; no request redirects."""
    if type(api_key) is not str or _API_KEY_PATTERN.fullmatch(api_key) is None:
        raise BrevoDomainStatusBlocked("M38530_BREVO_API_KEY_INVALID_FORMAT")
    request=Request(
        _URL,method="GET",
        headers={"api-key":api_key,"Accept":"application/json"},
    )
    opener=build_opener(
        ProxyHandler({}),
        HTTPSHandler(context=ssl.create_default_context()),
        _NoRedirect(),
    )
    try:
        with opener.open(request,timeout=10) as response:
            if response.getcode()!=200:
                raise BrevoDomainStatusBlocked("M38530_BREVO_GET_NOT_OK")
            mime=response.headers.get("Content-Type","").lower()
            if not mime.startswith("application/json"):
                raise BrevoDomainStatusBlocked("M38530_BREVO_RESPONSE_NOT_JSON")
            raw=response.read(_MAX_RESPONSE+1)
            if len(raw)>_MAX_RESPONSE:
                raise BrevoDomainStatusBlocked("M38530_BREVO_RESPONSE_TOO_LARGE")
    except HTTPError as exc:
        if exc.code in (401,403):
            code="M38530_BREVO_CREDENTIALS_UNAUTHORIZED"
        elif exc.code==404:
            code="M38530_BREVO_DOMAIN_NOT_REGISTERED"
        elif exc.code==429:
            code="M38530_BREVO_RATE_LIMITED"
        else:
            code="M38530_BREVO_PROVIDER_HTTP_FAILURE"
        raise BrevoDomainStatusBlocked(code) from None
    except BrevoDomainStatusBlocked:
        raise
    except Exception:
        raise BrevoDomainStatusBlocked("M38530_BREVO_TLS_OR_NETWORK_FAILURE") from None

    try:
        return json.loads(raw.decode("utf-8"),object_pairs_hook=_unique_json)
    except BrevoDomainStatusBlocked:
        raise
    except Exception:
        raise BrevoDomainStatusBlocked("M38530_BREVO_RESPONSE_INVALID_JSON") from None


def main(argv: list[str] | None = None) -> int:
    parser=argparse.ArgumentParser(
        description="FR Finance account domain status at Brevo: explicit GET only.",
    )
    parser.add_argument("action",nargs="?",choices=("offline","live"),default="offline")
    parser.add_argument("authorization",nargs="?")
    args=parser.parse_args(argv)
    if args.action=="offline":
        if args.authorization is not None:
            print("M38569_BREVO_ACCOUNT=BLOCKED_UNEXPECTED_AUTHORIZATION")
            return 2
        print("=== FR FINANCE M38530-M38569 BREVO ACCOUNT ===")
        print("M38569_MODE=OFFLINE_NO_NETWORK_NO_API_KEY")
        print("M38569_BREVO_VERIFIED=NOT_QUERIED")
        print("M38569_BREVO_AUTHENTICATED=NOT_QUERIED")
        print("M38569_SMTP_SEND=NONE")
        print("M38569_DATABASE_MUTATIONS=NONE")
        print("M38569_PRODUCTION=BLOCKED")
        return 0
    if args.authorization!="AUTHORIZE_BREVO_DOMAIN_STATUS_GET_ONLY":
        print("M38569_BREVO_ACCOUNT=BLOCKED_OPERATOR_AUTHORIZATION_REQUIRED")
        return 2

    try:
        api_key=_prompt_api_key()
        payload=_api_get_domain(api_key)
        report=assess_brevo_account_response(payload)
    except BrevoDomainStatusBlocked as exc:
        print("M38569_BREVO_ACCOUNT=BLOCKED")
        print("M38569_CAUSE="+str(exc))
        print("M38569_SMTP_SEND=NONE")
        print("M38569_EMAIL_REAL=OFF")
        print("M38569_ACTIVATION_REAL=OFF")
        print("M38569_PRODUCTION=BLOCKED")
        return 2
    except Exception:
        print("M38569_BREVO_ACCOUNT=BLOCKED_UNCLASSIFIED")
        print("M38569_EMAIL_REAL=OFF")
        print("M38569_PRODUCTION=BLOCKED")
        return 2
    finally:
        # Never store, echo, persist or log the API key or raw API response.
        if "api_key" in locals():
            del api_key

    print("=== FR FINANCE M38569 BREVO ACCOUNT GET READ ONLY ===")
    print("M38569_BREVO_ACCOUNT=LIVE_READ_ONLY_RESPONSE")
    print("M38569_EXPECTED_DOMAIN="+DOMAIN)
    print("M38569_BREVO_VERIFIED="+str(report.account_domain_verified).upper())
    print("M38569_BREVO_AUTHENTICATED="+str(report.account_domain_authenticated).upper())
    print("M38569_BREVO_CODE_STATUS="+report.brevo_code_status)
    print("M38569_DKIM_STATUS="+report.dkim_status)
    print("M38569_DMARC_STATUS="+report.dmarc_status)
    for item in report.blockers:
        print("M38569_BLOCKER="+item)
    print("M38569_DNS_PUBLIC_SHAPE_PREVIOUS=CONFIRMED_BY_OPERATOR_LOG")
    print("M38569_SMTP_AUTH=NOT_TESTED")
    print("M38569_EMAIL_DELIVERY=NOT_ATTESTED")
    print("M38569_EMAIL_REAL=OFF")
    print("M38569_REAL_USERS=OFF")
    print("M38569_REAL_PIX=OFF")
    print("M38569_DATABASE_MUTATIONS=NONE")
    print("M38569_PROVIDER_MUTATIONS=NONE")
    print("M38569_PRODUCTION=BLOCKED")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
