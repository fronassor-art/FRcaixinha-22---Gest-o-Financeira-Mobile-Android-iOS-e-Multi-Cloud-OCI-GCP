"""FR Caixinha AI Studio — Orders API Pix MLB, M4100.

Checkout Transparente (Brasil) new integrations use /v1/orders. This
adapter does NOT provision merchants, post ledger, reconcile bank, or mark
obligations paid. The issuer has only the tenant's verified OAuth token.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import json
import re

import httpx

from .pix_automation_contract import PixPaymentCommand, decimal_brl
from .mp_pix_execution import (
    ProviderCredentials, ProviderRequestBlocked, _read_json, _send,
)

CONTRACT = "AI_STUDIO_M4100_MLB_ORDERS_PIX_V1"
BASE = "https://api.mercadopago.com"
_ORDER = re.compile(r"ORD[A-Z0-9]{12,77}\Z")
_PAYMENT = re.compile(r"PAY[A-Z0-9]{12,77}\Z")
_EMAIL = re.compile(r"[^\s@]+@[^\s@]+\.[^\s@]+\Z")
_MAX_QR = 4096
_MAX_IMAGE = 700000


@dataclass(frozen=True)
class OrdersPixCheckout:
    operation_id: str
    order_id: str
    payment_id: str
    amount_cents: int
    status: str
    status_detail: str
    qr_code: str
    qr_code_base64: str | None
    ticket_url: str | None
    checkout_type: str = "orders_pix"
    capital_recognized: bool = False
    bank_reconciled: bool = False
    ledger_written: bool = False


@dataclass(frozen=True)
class OrdersReadReport:
    order_id: str
    payment_id: str
    status: str
    status_detail: str
    payment_status: str
    payment_detail: str
    provider_response_structure_verified: bool
    ready_for_independent_settlement_lookup: bool
    bank_reconciled: bool = False
    ledger_written: bool = False
    financial_effect_applied: bool = False


def _expected(command: PixPaymentCommand, credentials: ProviderCredentials):
    if type(command) is not PixPaymentCommand or type(credentials) is not ProviderCredentials:
        raise ProviderRequestBlocked("Cobrança Orders sem contrato")
    credentials.require(purpose="IN", network=False)
    if credentials.account_id != command.obligation.provider_account_id:
        raise ProviderRequestBlocked("Conta de recebedor incompatível")


def build_create_order_pix_request(
    *, command: PixPaymentCommand, credentials: ProviderCredentials,
    payer_email: str,
) -> httpx.Request:
    _expected(command, credentials)
    if type(payer_email) is not str or len(payer_email) > 254 or not _EMAIL.fullmatch(payer_email):
        raise ProviderRequestBlocked("Identidade de pagador inválida")
    amount = decimal_brl(command.amount_cents)
    doc = {
        "type": "online",
        "total_amount": amount,
        "external_reference": command.external_reference,
        "processing_mode": "automatic",
        "transactions": {
            "payments": [{
                "amount": amount,
                "payment_method": {"id":"pix","type":"bank_transfer"},
            }],
        },
        "payer": {"email": payer_email},
    }
    return httpx.Request(
        "POST", BASE + "/v1/orders",
        headers={
            "Authorization": "Bearer " + credentials.access_token,
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-Idempotency-Key": command.idempotency_key,
        },
        content=json.dumps(doc,ensure_ascii=True,separators=(",",":")).encode(),
    )


def _amount(raw, expected_cents: int) -> bool:
    if type(raw) is not str or not re.fullmatch(r"[0-9]{1,10}\.[0-9]{2}", raw):
        return False
    return Decimal(raw)*100 == expected_cents


def _extract(
    *, data: dict, command: PixPaymentCommand, credentials: ProviderCredentials,
    creation: bool,
) -> tuple[str,str,str,str,str,str,dict]:
    if (type(data.get("id")) is not str or not _ORDER.fullmatch(data["id"])
            or data.get("external_reference") != command.external_reference
            or data.get("type") != "online"
            or data.get("processing_mode") != "automatic"
            or not _amount(data.get("total_amount"),command.amount_cents)
            or data.get("country_code", "BRA") != "BRA"
            or data.get("marketplace", "NONE") != "NONE"):
        raise ProviderRequestBlocked("Order incompatível com obrigação")
    # Some MP Orders payloads do not include seller ID or live_mode. The
    # binding must then be proven by the OAuth credential resolving the GET.
    for seller_field in ("user_id","collector_id","seller_id"):
        if seller_field in data and str(data[seller_field]) != credentials.account_id:
            raise ProviderRequestBlocked("Conta conectada divergente")
    if "live_mode" in data and data["live_mode"] is not (
            credentials.environment == "PRODUCAO"):
        raise ProviderRequestBlocked("Ambiente de Order divergente")
    tx = data.get("transactions")
    if type(tx) is not dict or type(tx.get("payments")) is not list or len(tx["payments"])!=1:
        raise ProviderRequestBlocked("Pix deve ter uma única transação")
    payment = tx["payments"][0]
    if type(payment) is not dict or type(payment.get("id")) is not str or not _PAYMENT.fullmatch(payment["id"]):
        raise ProviderRequestBlocked("ID da transação Pix incompatível")
    if not _amount(payment.get("amount"),command.amount_cents):
        raise ProviderRequestBlocked("Valor da parcela Pix divergente")
    method=payment.get("payment_method")
    if type(method) is not dict or method.get("id")!="pix" or method.get("type")!="bank_transfer":
        raise ProviderRequestBlocked("Método não é Pix")
    status=data.get("status")
    detail=data.get("status_detail")
    pay_status=payment.get("status")
    pay_detail=payment.get("status_detail")
    valid={
        ("action_required","waiting_transfer"),
        ("processed","accredited"),
        ("canceled","expired"),
        ("failed","expired"),
    }
    if (type(status) is not str or type(detail) is not str
            or (status,detail) not in valid
            or (pay_status,pay_detail) not in valid):
        raise ProviderRequestBlocked("Status Orders não reconhecido")
    if creation and ((status,detail)!=("action_required","waiting_transfer")
                     or (pay_status,pay_detail)!=("action_required","waiting_transfer")):
        raise ProviderRequestBlocked("Order não está aguardando Pix")
    return data["id"],payment["id"],status,detail,pay_status,pay_detail,method


def parse_created_order_pix(
    *, data: dict, command: PixPaymentCommand, credentials: ProviderCredentials,
) -> OrdersPixCheckout:
    order_id,payment_id,status,detail,_,_,method=_extract(
        data=data,command=command,credentials=credentials,creation=True)
    qr=method.get("qr_code")
    image=method.get("qr_code_base64")
    url=method.get("ticket_url")
    if (type(qr) is not str or not 0<len(qr)<=_MAX_QR
            or image is not None and
              (type(image) is not str or not 0<len(image)<=_MAX_IMAGE
               or not re.fullmatch(r"[A-Za-z0-9+/]+={0,2}",image))
            or url is not None and
              (type(url) is not str or len(url)>4096
               or not url.startswith(("https://www.mercadopago.com.br/","https://mercadopago.com.br/")))):
        raise ProviderRequestBlocked("QR retornado inválido")
    return OrdersPixCheckout(
        operation_id=command.operation_id,order_id=order_id,
        payment_id=payment_id,amount_cents=command.amount_cents,
        status=status,status_detail=detail,qr_code=qr,
        qr_code_base64=image,ticket_url=url,
    )


def parse_read_order_pix(
    *, data: dict, order_id: str,
    command: PixPaymentCommand, credentials: ProviderCredentials,
) -> OrdersReadReport:
    ident,payment_id,status,detail,ps,pd,_=_extract(
        data=data,command=command,credentials=credentials,creation=False)
    if ident != order_id:
        raise ProviderRequestBlocked("Order consultada divergente")
    is_processed=(status,detail)==("processed","accredited") and (
        ps,pd)==("processed","accredited")
    # Processing/GET from OAuth is NOT a bank settlement statement.
    return OrdersReadReport(
        order_id=ident,payment_id=payment_id,status=status,
        status_detail=detail,payment_status=ps,payment_detail=pd,
        provider_response_structure_verified=True,
        ready_for_independent_settlement_lookup=is_processed,
    )


async def create_order_pix(
    *, command: PixPaymentCommand,credentials: ProviderCredentials,
    payer_email: str,transport: httpx.AsyncBaseTransport|None=None,
) -> OrdersPixCheckout:
    _expected(command,credentials)
    credentials.require(purpose="IN",network=transport is None)
    req=build_create_order_pix_request(
        command=command,credentials=credentials,payer_email=payer_email)
    response=await _send(
        req,transport=transport,
        approved_network=credentials.server_approved_for_real_network,
    )
    return parse_created_order_pix(
        data=_read_json(response),command=command,credentials=credentials)


async def read_order_pix(
    *, order_id: str,command: PixPaymentCommand,
    credentials: ProviderCredentials,transport: httpx.AsyncBaseTransport|None=None,
) -> OrdersReadReport:
    _expected(command,credentials)
    if type(order_id) is not str or not _ORDER.fullmatch(order_id):
        raise ProviderRequestBlocked("ID Order inválido")
    credentials.require(purpose="IN",network=transport is None)
    request=httpx.Request(
        "GET",BASE+"/v1/orders/"+order_id,
        headers={
            "Authorization":"Bearer "+credentials.access_token,
            "Accept":"application/json",
        },
    )
    response=await _send(
        request,transport=transport,
        approved_network=credentials.server_approved_for_real_network,
    )
    return parse_read_order_pix(
        data=_read_json(response),order_id=order_id,
        command=command,credentials=credentials,
    )
