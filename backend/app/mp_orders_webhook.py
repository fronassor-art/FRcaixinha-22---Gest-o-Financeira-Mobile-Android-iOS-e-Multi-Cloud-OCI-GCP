"""M4400: signed Mercado Pago Orders webhook ingress factory (OCI staging only).

No router mounted on the public FastAPI. HMAC + durable inbox are **not**
proof of bank settlement; Order GET + independent settlement + journal
are separately required. The Orders resource identifier is ORD..., not
a legacy numeric payment ID.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Awaitable, Callable
from uuid import UUID
import json
import re

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from .mp_operational_preflight import verify_webhook_hmac_offline
from .mp_webhook_staging_runtime import SellerContext, MAX_BODY

CONTRACT="AI_STUDIO_M4400_SIGNED_ORDERS_WEBHOOK_INBOX_V1"
_ORDER=re.compile(r"ORD[A-Z0-9]{12,77}\Z")
_SELLER=re.compile(r"[0-9]{1,40}\Z")
_REQ=re.compile(r"[A-Za-z0-9._:-]{1,120}\Z")
_ACTION=frozenset(("order.created","order.processed","order.canceled",
                   "order.failed"))
_STATUS=frozenset(("action_required","processed","failed","canceled"))


@dataclass(frozen=True)
class SignedOrderEvent:
    tenant_id: UUID
    provider_account_id: str
    event_id: str
    request_id: str
    order_id: str
    action: str
    observed_status: str
    payload_sha256: str
    live_mode: bool
    source: str="SIGNED_ORDER_WEBHOOK_UNSETTLED"
    bank_reconciled: bool=False
    ledger_written: bool=False
    payment_marked_paid: bool=False


def _unique(pairs):
    result={}
    for key,value in pairs:
        if key in result:
            raise ValueError("Repeated JSON key")
        result[key]=value
    return result


def _bad_constant(_):
    raise ValueError("Invalid JSON number")


def _load(raw:bytes)->dict:
    if type(raw) is not bytes or not 0<len(raw)<=MAX_BODY:
        raise ValueError("Invalid Order webhook size")
    try:
        obj=json.loads(raw,object_pairs_hook=_unique,
                       parse_constant=_bad_constant)
    except (TypeError,ValueError,UnicodeError):
        raise ValueError("Invalid Order webhook JSON") from None
    if type(obj) is not dict or type(obj.get("data")) is not dict:
        raise ValueError("Invalid Order webhook shape")
    return obj


def _event_id(raw:bytes,obj:dict)->str:
    ident=obj.get("id")
    if type(ident) is int and ident>0:
        return "N_"+str(ident)
    if type(ident) is str and re.fullmatch(r"[A-Za-z0-9_-]{1,80}",ident):
        return "N_"+ident
    return "N_"+sha256(raw).hexdigest()[:40]


def verify_order_notification(
    *, raw:bytes,data_id:str,query_type:str,
    request_id:str,signature:str,webhook_secret:bytes,
    now_ms:int,account:SellerContext,allow_live_ingest:bool=False,
)->SignedOrderEvent:
    obj=_load(raw)
    resource=obj["data"].get("id")
    user=obj.get("user_id")
    account_id=str(user) if type(user) in (int,str) else ""
    action=obj.get("action")
    status=obj["data"].get("status")
    live=obj.get("live_mode")
    if (type(account) is not SellerContext or account.active is not True
            or type(account.tenant_id) is not UUID
            or not _SELLER.fullmatch(account.seller_id)
            or account_id != account.seller_id
            or type(data_id) is not str or not _ORDER.fullmatch(data_id)
            or resource != data_id or query_type!="order"
            or obj.get("type")!="order"
            or obj.get("api_version")!="v1"
            or action not in _ACTION or status not in _STATUS
            or type(request_id) is not str or not _REQ.fullmatch(request_id)
            or type(live) is not bool
            or (live is True and allow_live_ingest is not True)):
        raise ValueError("Order webhook violates account or scope")
    # The official validator normalizes alphanumeric resource IDs on some
    # versions. Accept only HMAC calculated over this exact resource ID
    # (possibly ASCII-lowercased) after query/body equality.
    signed=verify_webhook_hmac_offline(
        data_id=data_id,request_id=request_id,
        x_signature=signature,secret=webhook_secret,now_ms=now_ms,
    )
    if not signed:
        signed=verify_webhook_hmac_offline(
            data_id=data_id.lower(),request_id=request_id,
            x_signature=signature,secret=webhook_secret,now_ms=now_ms,
        )
    if not signed:
        raise ValueError("Order webhook signature invalid")
    return SignedOrderEvent(
        tenant_id=account.tenant_id,
        provider_account_id=account.seller_id,
        event_id=_event_id(raw,obj),request_id=request_id,
        order_id=data_id,action=action,
        observed_status=status,payload_sha256=sha256(raw).hexdigest(),
        live_mode=live,
    )


def create_orders_staging_router(
    *,resolve_account:Callable[[str],Awaitable[SellerContext|None]],
    load_signing_secret:Callable[[SellerContext],Awaitable[bytes]],
    persist_event:Callable[[SignedOrderEvent],Awaitable[str]],
    now_ms:Callable[[],int],
    allow_live_ingest:bool=False,
)->APIRouter:
    """Not mounted in main.py; deploy only behind trusted TLS and OCI Vault."""
    router=APIRouter(tags=["MP Orders signed webhook staging"])

    @router.post("/integrations/mercadopago/orders",include_in_schema=False)
    async def ingress(request:Request):
        if (request.url.scheme!="https" or
                len(request.headers.getlist("content-type"))!=1 or
                request.headers.get("content-type","").split(";")[0].lower()
                    !="application/json"):
            raise HTTPException(415,"HTTPS JSON required")
        if (len(request.headers.getlist("x-signature"))!=1 or
                len(request.headers.getlist("x-request-id"))!=1):
            raise HTTPException(400,"Ambiguous signed headers")
        qp=request.query_params
        if (len(qp.getlist("data.id"))!=1 or
                len(qp.getlist("type"))!=1 or qp.get("type")!="order"):
            raise HTTPException(400,"Invalid Orders query")
        received=bytearray()
        async for part in request.stream():
            if len(received)+len(part)>MAX_BODY:
                raise HTTPException(413,"Orders webhook too large")
            received.extend(part)
        raw=bytes(received)
        try:
            obj=_load(raw)
            user=obj.get("user_id")
            seller_id=str(user) if type(user) in (int,str) else ""
            if not _SELLER.fullmatch(seller_id):
                raise ValueError()
            seller=await resolve_account(seller_id)
            if type(seller) is not SellerContext:
                raise ValueError()
            secret=await load_signing_secret(seller)
            event=verify_order_notification(
                raw=raw,data_id=qp["data.id"],query_type="order",
                request_id=request.headers["x-request-id"],
                signature=request.headers["x-signature"],
                webhook_secret=secret,now_ms=now_ms(),
                account=seller,allow_live_ingest=allow_live_ingest,
            )
        except ValueError:
            raise HTTPException(401,"Orders webhook not authenticated") from None
        except Exception:
            raise HTTPException(503,"Orders webhook verifier unavailable") from None
        try:
            result=await persist_event(event)
            if result not in ("INSERTED","REPLAY"):
                raise ValueError()
        except Exception:
            raise HTTPException(503,"Orders durable inbox unavailable") from None
        return JSONResponse(status_code=200,content={
            "receipt":result,"bank_reconciled":False,
            "ledger_written":False,"financial_effect_applied":False,
        })

    return router
