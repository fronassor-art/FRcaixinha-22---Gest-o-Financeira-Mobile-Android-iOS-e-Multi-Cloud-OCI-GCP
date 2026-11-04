"""M2900: real HTTPS Mercado Pago webhook ingress, inactive by default.

Server wiring is a separate authorized deployment step. This factory can
receive real signed notifications when connected to OCI Vault and a staging
inbox. It never marks paid, credits accounts or changes the financial ledger.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Awaitable, Callable
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from .mp_operational_preflight import verify_webhook_hmac_offline

MAX_BODY = 16384
_SELLER = re.compile(r"[0-9]{1,40}\Z")
_ID = re.compile(r"[A-Za-z0-9_-]{1,100}\Z")
_REQ = re.compile(r"[A-Za-z0-9._:-]{1,120}\Z")
_ALLOWED = {
    "payment": {"payment.created","payment.updated"},
    "mp-connect": {"application.authorized","application.deauthorized"},
}
CONTRACT = "AI_STUDIO_M2900_SIGNED_WEBHOOK_STAGING_INBOX_V1"


@dataclass(frozen=True)
class SellerContext:
    """seller_id = technical MP account ID; not a fourth SaaS user role."""
    tenant_id: UUID
    seller_id: str
    webhook_secret_ocid: str
    active: bool = True

    @property
    def provider_account_id(self) -> str:
        return self.seller_id


@dataclass(frozen=True)
class SignedWebhookRecord:
    tenant_id: UUID
    seller_id: str
    notification_id: str
    request_id: str
    resource_id: str
    event_type: str
    action: str
    payload_sha256: str
    live_mode: bool
    source: str = "SIGNED_WEBHOOK_UNSETTLED"
    bank_reconciled: bool = False
    ledger_written: bool = False
    payment_marked_paid: bool = False


def _unique(pairs):
    result={}
    for key,value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key]=value
    return result


def _reject_constant(_):
    raise ValueError("Noncanonical JSON")


def _numeric_id(value):
    if type(value) is int and value > 0:
        return str(value)
    if type(value) is str:
        return value
    return ""


def _parse_untrusted(raw: bytes) -> dict:
    if type(raw) is not bytes or not 0 < len(raw) <= MAX_BODY:
        raise ValueError("Invalid envelope size")
    try:
        body = json.loads(raw,object_pairs_hook=_unique,
                          parse_constant=_reject_constant)
    except (UnicodeError,ValueError,TypeError):
        raise ValueError("Invalid envelope") from None
    if type(body) is not dict or type(body.get("data")) is not dict:
        raise ValueError("Invalid structure")
    return body


def verify_webhook_for_seller(
    *, raw: bytes, data_id: str, query_type: str, request_id: str,
    signature: str, webhook_secret: bytes, now_ms: int,
    seller: SellerContext, allow_live_ingest: bool = False,
) -> SignedWebhookRecord:
    body = _parse_untrusted(raw)
    payload_seller = _numeric_id(body.get("user_id"))
    payload_id = _numeric_id(body.get("id"))
    resource_id = _numeric_id(body["data"].get("id"))
    kind = body.get("type")
    action = body.get("action")
    live = body.get("live_mode")
    if (type(seller) is not SellerContext or seller.active is not True
            or type(seller.tenant_id) is not UUID
            or type(seller.seller_id) is not str
            or not _SELLER.fullmatch(seller.seller_id)
            or payload_seller != seller.seller_id
            or type(data_id) is not str or not _ID.fullmatch(data_id)
            or not _ID.fullmatch(resource_id) or data_id != resource_id
            or type(query_type) is not str or kind != query_type
            or kind not in _ALLOWED or action not in _ALLOWED[kind]
            or type(payload_id) is not str or not _ID.fullmatch(payload_id)
            or type(request_id) is not str or not _REQ.fullmatch(request_id)
            or type(live) is not bool
            or (live and allow_live_ingest is not True)):
        raise ValueError("Webhook scope invalid")
    if not verify_webhook_hmac_offline(
        data_id=data_id, request_id=request_id,
        x_signature=signature, secret=webhook_secret, now_ms=now_ms,
    ):
        raise ValueError("Webhook signature invalid")
    return SignedWebhookRecord(
        tenant_id=seller.tenant_id, seller_id=seller.seller_id,
        notification_id=payload_id, request_id=request_id,
        resource_id=resource_id, event_type=kind, action=action,
        payload_sha256=hashlib.sha256(raw).hexdigest(),
        live_mode=live,
    )


def create_webhook_staging_router(
    *,
    resolve_seller: Callable[[str], Awaitable[SellerContext | None]],
    load_signing_secret: Callable[[SellerContext], Awaitable[bytes]],
    persist_verified: Callable[[SignedWebhookRecord], Awaitable[str]],
    now_ms: Callable[[], int],
    allow_live_ingest: bool = False,
) -> APIRouter:
    """Only mount on HTTPS after staging DB, seller mapping and OCI IAM exist.

    Do NOT mount in main.py until deployment / authorization gates pass.
    This is an actual FastAPI POST route factory, not a fake HTTP endpoint.
    """
    router = APIRouter(tags=["Mercado Pago signed webhook staging"])

    @router.post("/integrations/mercadopago/webhook",include_in_schema=False)
    async def inbound(request: Request):
        if (request.url.scheme != "https"
                or len(request.headers.getlist("content-type")) != 1
                or request.headers.get("content-type","").split(";")[0].lower()
                    != "application/json"):
            raise HTTPException(415, "Unsupported channel")
        size = request.headers.get("content-length")
        if size is not None:
            try:
                if not 0 < int(size) <= MAX_BODY:
                    raise ValueError()
            except ValueError:
                raise HTTPException(413,"Envelope too large") from None
        # Content-Length is not mandatory (chunked transfer). Never buffer
        # an unbounded request body before applying the hard size limit.
        received=bytearray()
        async for part in request.stream():
            if len(received)+len(part)>MAX_BODY:
                raise HTTPException(413,"Envelope too large")
            received.extend(part)
        raw=bytes(received)
        query=request.query_params
        if len(query.getlist("data.id")) != 1 or len(query.getlist("type")) != 1:
            raise HTTPException(400,"Query invalid")
        data_id=query["data.id"]
        kind=query["type"]
        # Reject ambiguous signed header copies before resolving the
        # beneficiary account or reading secrets from Vault.
        if (len(request.headers.getlist("x-request-id")) != 1
                or len(request.headers.getlist("x-signature")) != 1):
            raise HTTPException(400,"Signed headers ambiguous")
        req_id=request.headers.get("x-request-id","")
        sig=request.headers.get("x-signature","")
        try:
            decoded=_parse_untrusted(raw)
            user_id=_numeric_id(decoded.get("user_id"))
            if not _SELLER.fullmatch(user_id):
                raise ValueError()
            seller=await resolve_seller(user_id)
            if type(seller) is not SellerContext or not seller.active:
                raise ValueError()
            secret=await load_signing_secret(seller)
            record=verify_webhook_for_seller(
                raw=raw,data_id=data_id,query_type=kind,request_id=req_id,
                signature=sig,webhook_secret=secret,now_ms=now_ms(),
                seller=seller,allow_live_ingest=allow_live_ingest,
            )
        except ValueError:
            raise HTTPException(401,"Webhook not authenticated") from None
        except Exception:
            raise HTTPException(503,"Webhook service unavailable") from None
        try:
            status=await persist_verified(record)
            if status not in ("INSERTED","REPLAY"):
                raise ValueError()
        except Exception:
            raise HTTPException(503,"Durable inbox unavailable") from None
        return JSONResponse(
            status_code=202 if status=="INSERTED" else 200,
            content={
                "receipt":status,
                "financial_effect_applied":False,
                "bank_reconciled":False,
                "ledger_written":False,
            },
        )
    return router
