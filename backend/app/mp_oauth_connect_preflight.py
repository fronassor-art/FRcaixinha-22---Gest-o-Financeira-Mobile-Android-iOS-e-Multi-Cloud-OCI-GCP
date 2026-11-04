"""M2301-M2400: borda OAuth Connect SEM rede, token ou persistência.

Este módulo SOMENTE prepara prova de vinculação. Não inicia OAuth para
terceiros, não troca code por token, não grava token e não habilita dinheiro.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import re
import secrets
from dataclasses import dataclass
from urllib.parse import urlsplit, urlencode
from uuid import UUID

CONTRACT = "AI_STUDIO_M2400_CONNECT_AND_WEBHOOK_PRECHECK_V1"
_AUTH_URL = "https://auth.mercadopago.com/authorization"
_STATE_RE = re.compile(r"[A-Za-z0-9_-]{32,128}\Z")
_CODE_RE = re.compile(r"[A-Za-z0-9_.-]{1,512}\Z")
_APP_RE = re.compile(r"[0-9]{1,40}\Z")
_COLLECTOR_RE = re.compile(r"[0-9]{1,40}\Z")
TEN_MINUTES = 600


def _validate_redirect(uri: str) -> str:
    if type(uri) is not str or len(uri) > 512:
        raise ValueError("Redirect_uri inválida")
    parsed = urlsplit(uri)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username
            or parsed.password or parsed.fragment or parsed.query
            or parsed.port is not None or parsed.hostname in (
                "localhost", "127.0.0.1", "::1")
            or any(c.isspace() for c in uri)):
        raise ValueError("Redirect URI HTTPS estática obrigatória")
    return uri


@dataclass(frozen=True, repr=False)
class OAuthDraft:
    tenant_id: UUID
    initiated_by: UUID
    client_id: str
    redirect_uri: str
    state: str
    code_verifier: str
    created_at_epoch: int
    live_mode: bool = False

    def __repr__(self) -> str:
        return "OAuthDraft(redacted=True, sandbox_only=True)"

    @property
    def pkce_challenge(self) -> str:
        digest = hashlib.sha256(self.code_verifier.encode("ascii")).digest()
        return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")

    @property
    def authorization_url(self) -> str:
        params = urlencode({
            "client_id": self.client_id, "response_type": "code",
            "platform_id": "mp", "state": self.state,
            "redirect_uri": self.redirect_uri,
            "code_challenge": self.pkce_challenge,
            "code_challenge_method": "S256",
        })
        return _AUTH_URL + "?" + params


def prepare_oauth_draft(
    *, tenant_id: UUID, initiated_by: UUID, client_id: str,
    registered_redirect_uri: str, now_epoch: int,
) -> OAuthDraft:
    if (type(tenant_id) is not UUID or type(initiated_by) is not UUID
            or type(client_id) is not str or not _APP_RE.fullmatch(client_id)
            or type(now_epoch) is not int or now_epoch <= 0):
        raise ValueError("Contexto OAuth inválido")
    uri = _validate_redirect(registered_redirect_uri)
    state = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(64)
    if not 43 <= len(verifier) <= 128 or not _STATE_RE.fullmatch(state):
        raise ValueError("Geração de estado PKCE inválida")
    return OAuthDraft(
        tenant_id, initiated_by, client_id, uri, state, verifier, now_epoch,
    )


def precheck_oauth_callback(
    *, draft: OAuthDraft, tenant_id: UUID, initiated_by: UUID,
    provided_state: str, code: str, redirect_uri: str,
    now_epoch: int, already_consumed: bool,
) -> bool:
    """Somente valida contexto; consumo ÚNICO deve ser atômico no banco."""
    if (type(draft) is not OAuthDraft or draft.live_mode is not False
            or type(tenant_id) is not UUID or type(initiated_by) is not UUID
            or draft.tenant_id != tenant_id or draft.initiated_by != initiated_by
            or type(provided_state) is not str
            or type(code) is not str or not _CODE_RE.fullmatch(code)
            or type(redirect_uri) is not str
            or not hmac.compare_digest(draft.redirect_uri, redirect_uri)
            or type(now_epoch) is not int or type(already_consumed) is not bool
            or already_consumed or now_epoch < draft.created_at_epoch
            or now_epoch - draft.created_at_epoch > TEN_MINUTES):
        return False
    return hmac.compare_digest(draft.state, provided_state)


@dataclass(frozen=True)
class SellerBindingPreview:
    tenant_id: UUID
    seller_id: str
    sandbox_metadata_consistent: bool
    needs_persistent_vault_and_oauth_exchange: bool = True
    payment_authorized: bool = False
    provider_connected: bool = False
    ledger_written: bool = False
    bank_reconciled: bool = False


def review_seller_token_metadata(
    *, tenant_id: UUID, expected_seller_id: str, token_metadata: object,
) -> SellerBindingPreview:
    """Não retorna nem registra tokens; valida APENAS metadados externos."""
    if (type(tenant_id) is not UUID or type(expected_seller_id) is not str
            or not _COLLECTOR_RE.fullmatch(expected_seller_id)
            or type(token_metadata) is not dict):
        raise ValueError("Tenant/seller/metadados inválidos")
    actual_id = token_metadata.get("user_id")
    if type(actual_id) is int and actual_id > 0:
        actual_id = str(actual_id)
    valid = (
        type(actual_id) is str and _COLLECTOR_RE.fullmatch(actual_id) is not None
        and hmac.compare_digest(actual_id, expected_seller_id)
        and token_metadata.get("live_mode") is False
        and token_metadata.get("token_type") == "bearer"
        and type(token_metadata.get("expires_in")) is int
        and 0 < token_metadata["expires_in"] <= 15_552_000
    )
    return SellerBindingPreview(tenant_id, expected_seller_id, bool(valid))
