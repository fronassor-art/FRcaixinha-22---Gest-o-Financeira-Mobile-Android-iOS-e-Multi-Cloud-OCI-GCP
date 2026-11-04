"""AI Studio M2800: REAL Mercado Pago OAuth token HTTP client, NOT wired.

This adapter can communicate with the official HTTPS endpoint if explicitly
enabled on a configured server. It never creates a payment or writes a token.
No publicly registered route invokes this module.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit

import httpx

from .mp_oauth_connect_preflight import OAuthDraft

URL = "https://api.mercadopago.com/oauth/token"
_MAX_RESPONSE = 32768
_DIGITS = re.compile(r"[0-9]{1,40}\Z")
_CODE = re.compile(r"[A-Za-z0-9_.-]{1,512}\Z")
_PKCE = re.compile(r"[A-Za-z0-9_~-]{43,128}\Z")


class OAuthConnectionBlocked(RuntimeError):
    """Sanitized error (no API key, request body, code or token)."""


@dataclass(frozen=True, repr=False)
class OAuthTokens:
    seller_id: str
    scope: str
    expires_in: int
    access_token: str = field(repr=False)
    refresh_token: str = field(repr=False)
    live_mode: bool = False

    def __repr__(self) -> str:
        return "OAuthTokens(redacted=True, sandbox_only=True)"

    def __str__(self) -> str:
        return self.__repr__()


def _unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, val in pairs:
        if key in result:
            raise ValueError("Repeated JSON key")
        result[key] = val
    return result


def _no_constant(_value: str):
    raise ValueError("Noncanonical JSON constant")


def _sensitive(value: Any) -> bool:
    return type(value) is str and 16 <= len(value) <= 4096 and not any(c.isspace() for c in value)


def _parse_token_response(response: httpx.Response, *, seller_id: str) -> OAuthTokens:
    if (response.status_code != 200 or len(response.content) > _MAX_RESPONSE
            or not response.content):
        raise OAuthConnectionBlocked("OAuth token endpoint unavailable")
    try:
        data = json.loads(
            response.content, object_pairs_hook=_unique,
            parse_constant=_no_constant,
        )
        if type(data) is not dict:
            raise ValueError("No JSON object")
        user = data.get("user_id")
        if type(user) is int and user > 0:
            user = str(user)
        if (type(user) is not str or not _DIGITS.fullmatch(user)
                or user != seller_id or data.get("live_mode") is not False
                or data.get("token_type") != "bearer"
                or type(data.get("expires_in")) is not int
                or not 0 < data["expires_in"] <= 15_552_000
                or not _sensitive(data.get("access_token"))
                or not _sensitive(data.get("refresh_token"))
                or type(data.get("scope")) is not str
                or not 0 < len(data["scope"]) <= 512):
            raise ValueError("Identity/mode/scope mismatch")
        return OAuthTokens(
            seller_id=user, scope=data["scope"],
            expires_in=data["expires_in"],
            access_token=data["access_token"],
            refresh_token=data["refresh_token"],
        )
    except (ValueError, TypeError, UnicodeError):
        raise OAuthConnectionBlocked("OAuth token response not authorized") from None


def _validate_oauth_inputs(
    *, client_id: str, client_secret: str, expected_seller_id: str,
    code: str | None = None, code_verifier: str | None = None,
    redirect_uri: str | None = None, refresh_token: str | None = None,
):
    if (type(client_id) is not str or not _DIGITS.fullmatch(client_id)
            or not _sensitive(client_secret)
            or type(expected_seller_id) is not str
            or not _DIGITS.fullmatch(expected_seller_id)):
        raise OAuthConnectionBlocked("OAuth server identity invalid")
    if code is not None:
        if (type(code) is not str or not _CODE.fullmatch(code)
                or type(code_verifier) is not str or not _PKCE.fullmatch(code_verifier)
                or type(redirect_uri) is not str or not 0 < len(redirect_uri) <= 512):
            raise OAuthConnectionBlocked("OAuth authorization code invalid")
        uri = urlsplit(redirect_uri)
        if (uri.scheme != "https" or not uri.netloc or uri.username
                or uri.password or uri.query or uri.fragment):
            raise OAuthConnectionBlocked("OAuth redirect invalid")
    if refresh_token is not None and not _sensitive(refresh_token):
        raise OAuthConnectionBlocked("OAuth refresh token invalid")


async def _send_token_post(
    *, body: dict[str, str], seller_id: str,
    transport: httpx.AsyncBaseTransport | None = None,
    real_https_authorized: bool = False,
) -> OAuthTokens:
    # Network is disabled unless the server explicitly opts in at deployment.
    if transport is None and real_https_authorized is not True:
        raise OAuthConnectionBlocked("Real HTTPS transport not authorized")
    if transport is not None and not isinstance(transport, httpx.AsyncBaseTransport):
        raise OAuthConnectionBlocked("OAuth HTTP transport invalid")
    try:
        async with httpx.AsyncClient(
            transport=transport, trust_env=False,
            follow_redirects=False, timeout=httpx.Timeout(5.0),
        ) as http:
            response = await http.post(
                URL, json=body,
                headers={"Accept":"application/json",
                         "Content-Type":"application/json"},
            )
    except httpx.HTTPError:
        raise OAuthConnectionBlocked("OAuth transport unavailable") from None
    return _parse_token_response(response, seller_id=seller_id)


async def exchange_sandbox_authorization_code(
    *, draft: OAuthDraft, returned_state: str,
    code: str, client_secret: str, expected_seller_id: str,
    consumed_by_durable_store: bool,
    transport: httpx.AsyncBaseTransport | None = None,
    real_https_authorized: bool = False,
) -> OAuthTokens:
    """Only after durable state is consumed for tenant/actor by the server.

    This bool is NOT proof of consumption; callers must use a trusted
    database repository and must not expose this method to arbitrary clients.
    """
    if (type(draft) is not OAuthDraft or draft.live_mode is not False
            or type(returned_state) is not str
            or returned_state != draft.state
            or consumed_by_durable_store is not True):
        raise OAuthConnectionBlocked("OAuth callback has not been consumed")
    _validate_oauth_inputs(
        client_id=draft.client_id, client_secret=client_secret,
        expected_seller_id=expected_seller_id,
        code=code, code_verifier=draft.code_verifier,
        redirect_uri=draft.redirect_uri,
    )
    return await _send_token_post(
        body={
            "client_id": draft.client_id,
            "client_secret": client_secret,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": draft.redirect_uri,
            "code_verifier": draft.code_verifier,
            "test_token": "true",
        },
        seller_id=expected_seller_id, transport=transport,
        real_https_authorized=real_https_authorized,
    )


async def refresh_sandbox_seller_token(
    *, client_id: str, client_secret: str, expected_seller_id: str,
    refresh_token: str,
    seller_binding_confirmed: bool,
    transport: httpx.AsyncBaseTransport | None = None,
    real_https_authorized: bool = False,
) -> OAuthTokens:
    if seller_binding_confirmed is not True:
        raise OAuthConnectionBlocked("Seller consent/revocation not verified")
    _validate_oauth_inputs(
        client_id=client_id, client_secret=client_secret,
        expected_seller_id=expected_seller_id,
        refresh_token=refresh_token,
    )
    return await _send_token_post(
        body={
            "client_id": client_id, "client_secret": client_secret,
            "grant_type": "refresh_token", "refresh_token": refresh_token,
            "test_token": "true",
        },
        seller_id=expected_seller_id, transport=transport,
        real_https_authorized=real_https_authorized,
    )
