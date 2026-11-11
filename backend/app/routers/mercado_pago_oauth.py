"""FR Finance: Mercado Pago OAuth callback on the EXISTING FastAPI.

State/PKCE verification, one-time consumption, seller identity and encrypted
token persistence belong to the existing server-side OAuth coordinator/store.
Do not call provider or store tokens from the public HTTP handler.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Awaitable, Callable

from fastapi import APIRouter, HTTPException, Request

_STATE = re.compile(r"[A-Za-z0-9_-]{32,128}\Z")
_CODE = re.compile(r"[A-Za-z0-9_.-]{1,512}\Z")

router = APIRouter(prefix="/mercadopago/oauth", tags=["Mercado Pago Connect"])


@dataclass(frozen=True, slots=True)
class OAuthCallbackReceipt:
    state_consumed_once: bool = False
    tenant_bound: bool = False
    seller_verified: bool = False
    refresh_token_sealed: bool = False
    live_payments_enabled: bool = False


@dataclass(frozen=True, slots=True)
class OAuthCallbackBinding:
    complete: Callable[..., Awaitable[OAuthCallbackReceipt]]
    original_database_verified: bool = False
    durable_pkce_state_verified: bool = False
    vault_store_verified: bool = False
    seller_registry_verified: bool = False
    callback_https_registered: bool = False
    sandbox_only: bool = True


def _runtime(request: Request) -> OAuthCallbackBinding:
    binding = getattr(request.app.state, "mp_oauth_callback_runtime", None)
    if (type(binding) is not OAuthCallbackBinding
            or binding.original_database_verified is not True
            or binding.durable_pkce_state_verified is not True
            or binding.vault_store_verified is not True
            or binding.seller_registry_verified is not True
            or binding.callback_https_registered is not True
            or binding.sandbox_only is not True):
        raise HTTPException(503, "OAuth Mercado Pago ainda não integrado ao serviço operacional.")
    return binding


@router.get("/callback", include_in_schema=False)
async def connect_callback(request: Request):
    """Never echo authorization code/state/token or use HTTP redirects.

    Operational binding must resolve tenant + initiating actor from the stored,
    single-use state. A successful simulation does not authorize Pix real.
    """
    if request.url.scheme != "https":
        raise HTTPException(403, "Callback requer HTTPS público.")
    params = request.query_params
    if (len(params.getlist("state")) != 1 or
            len(params.getlist("code")) != 1 or
            len(list(params.multi_items())) != 2):
        raise HTTPException(400, "Parâmetros OAuth inválidos.")
    state, code = params.get("state"), params.get("code")
    if (type(state) is not str or not _STATE.fullmatch(state)
            or type(code) is not str or not _CODE.fullmatch(code)):
        raise HTTPException(400, "Parâmetros OAuth inválidos.")
    binding = _runtime(request)
    try:
        receipt = await binding.complete(state=state, authorization_code=code)
    except Exception:
        raise HTTPException(503, "Vinculação OAuth não confirmada.") from None
    if (type(receipt) is not OAuthCallbackReceipt
            or receipt.state_consumed_once is not True
            or receipt.tenant_bound is not True
            or receipt.seller_verified is not True
            or receipt.refresh_token_sealed is not True
            or receipt.live_payments_enabled is not False):
        raise HTTPException(503, "Vinculação OAuth não confirmada.")
    return {
        "status": "SANDBOX_CONNECT_CONFIRMED",
        "real_payments_enabled": False,
        "pix_inbound_enabled": False,
        "pix_outbound_enabled": False,
    }
