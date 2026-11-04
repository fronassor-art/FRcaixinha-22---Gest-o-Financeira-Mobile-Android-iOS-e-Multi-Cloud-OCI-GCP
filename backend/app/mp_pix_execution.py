"""AI Studio — adaptadores HTTPS reais Mercado Pago Pix IN e Payouts.

Independent provider gateway; no auto-start, no public routes, no live
credentials, no ledger writes. Real network only with deployment-time
authorization and provider capability attestation, never based on HTTP payload.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from hashlib import sha256
import json
import re
from typing import Any
from urllib.parse import quote

import httpx

from .mercado_pago_adapter import PixCollectionRequest, build_create_pix_request
from .mercado_pago_safety import ExpectedPayment, matches_approved_payment
from .pix_automation_contract import (
    FinancialOperationBlocked, PixPaymentCommand, DisbursementOrder,
    PayoutState, decimal_brl,
)

CONTRACT = "AI_STUDIO_M3500_MP_PIX_PROVIDER_EXECUTION_PORTS_V1"
BASE = "https://api.mercadopago.com"
_MAX_RESPONSE = 65536
_ID = re.compile(r"[0-9]{1,40}\Z")
_REF = re.compile(r"[A-Za-z0-9_-]{8,64}\Z")
_PIX_TYPES = frozenset(("EMAIL","PHONE","CPF","CNPJ","PIX_CODE"))


class ProviderRequestBlocked(RuntimeError):
    """Safe error without token, Pix key, CPF, HTTP body or recipient name."""


class ProviderOutcomeUnknown(ProviderRequestBlocked):
    """Timeout/ambiguous response: check provider; NEVER create fresh transfer."""


@dataclass(frozen=True,repr=False)
class ProviderCredentials:
    """Trusted server-only credentials after account binding and secret store."""
    account_id: str
    access_token: str = field(repr=False)
    environment: str = "HOMOLOGACAO"
    account_binding_verified: bool = False
    capability_in: bool = False
    capability_out: bool = False
    provider_profile_verified: bool = False
    server_approved_for_real_network: bool = False

    def __repr__(self):
        return "ProviderCredentials(redacted=True)"

    def require(self, *, purpose: str, network: bool):
        if (type(self.account_id) is not str or not _ID.fullmatch(self.account_id)
                or type(self.access_token) is not str
                or len(self.access_token) < 16
                or self.account_binding_verified is not True
                or self.environment not in ("HOMOLOGACAO","PRODUCAO")
                or (purpose=="IN" and self.capability_in is not True)
                or (purpose=="OUT" and
                    (self.capability_out is not True or
                     self.provider_profile_verified is not True))
                or (network and self.server_approved_for_real_network is not True)):
            raise ProviderRequestBlocked("Credenciais/capacidade não homologadas")


@dataclass(frozen=True)
class CreatedPix:
    operation_id: str
    payment_id: str
    amount_cents: int
    status: str
    qr_code: str
    qr_code_base64: str | None = None
    ticket_url: str | None = None
    capital_recognized: bool = False
    ledger_written: bool = False
    bank_reconciled: bool = False


@dataclass(frozen=True)
class VerifiedProviderRead:
    payment_id: str
    status: str
    verified_approved: bool
    bank_reconciled: bool = False
    ledger_written: bool = False


@dataclass(frozen=True,repr=False)
class PixRecipient:
    """Resolved only from encrypted, server-approved beneficiary record."""
    destination_id: str
    key_type: str
    pix_key: str = field(repr=False)
    identification_type: str = "CPF"
    identification_number: str = field(default="",repr=False)
    key_ownership_verified: bool = False

    def __repr__(self):
        return "PixRecipient(redacted=True)"

    def validate(self):
        if (not re.fullmatch(r"[0-9a-f-]{36}",self.destination_id)
                or self.key_type not in _PIX_TYPES
                or type(self.pix_key) is not str
                or not 3 <= len(self.pix_key) <= 140
                or any(c in self.pix_key for c in "\r\n")
                or self.identification_type not in ("CPF","CNPJ")
                or type(self.identification_number) is not str
                or not re.fullmatch(r"[0-9]{11}|[0-9]{14}",self.identification_number)
                or self.key_ownership_verified is not True):
            raise ProviderRequestBlocked("Conta Pix destinatária não verificada")


@dataclass(frozen=True)
class SentPayout:
    business_operation_id: str
    provider_payout_id: str
    provider_status: str
    financial_state: PayoutState = PayoutState.PENDING_RECONCILIATION
    bank_reconciled: bool = False
    ledger_written: bool = False
    money_transferred_confirmed: bool = False


def _unique_keys(items):
    out={}
    for k,v in items:
        if k in out:
            raise ValueError("duplicated JSON key")
        out[k]=v
    return out


def _bad_constant(_):
    raise ValueError("nonfinite value")


def _read_json(response: httpx.Response) -> dict:
    if (response.status_code not in (200,201,202)
            or not 0 < len(response.content) <= _MAX_RESPONSE):
        raise ProviderRequestBlocked("Resposta de provedor indisponível")
    try:
        data=json.loads(
            response.content,object_pairs_hook=_unique_keys,
            parse_float=Decimal,parse_constant=_bad_constant,
        )
        if type(data) is not dict:
            raise ValueError("not an object")
        return data
    except (TypeError,ValueError,UnicodeError):
        raise ProviderRequestBlocked("Resposta de provedor inválida") from None


def _client(transport):
    if transport is not None and not isinstance(transport,httpx.AsyncBaseTransport):
        raise ProviderRequestBlocked("Canal HTTP não confiável")
    return httpx.AsyncClient(
        transport=transport,trust_env=False,follow_redirects=False,
        timeout=httpx.Timeout(6.0),
    )


async def _send(
    request: httpx.Request, *, transport: httpx.AsyncBaseTransport | None,
    approved_network: bool,
) -> httpx.Response:
    if (request.url.scheme!="https" or request.url.host!="api.mercadopago.com"
            or transport is None and approved_network is not True):
        raise ProviderRequestBlocked("Canal real não autorizado")
    try:
        async with _client(transport) as client:
            return await client.send(request,follow_redirects=False)
    except httpx.HTTPError:
        raise ProviderOutcomeUnknown(
            "Resultado externo incerto: consultar provedor antes de repetir"
        ) from None


def _verified_qr(value: Any, limit: int) -> str | None:
    if value is None:
        return None
    if type(value) is not str or not 0 < len(value) <= limit:
        raise ProviderRequestBlocked("QR Pix inválido")
    return value


async def create_collection_pix(
    *, command: PixPaymentCommand, credentials: ProviderCredentials,
    payer_email: str, transport: httpx.AsyncBaseTransport | None = None,
) -> CreatedPix:
    """Actual POST /v1/payments; no ledger or status mutation."""
    if type(command) is not PixPaymentCommand or type(credentials) is not ProviderCredentials:
        raise ProviderRequestBlocked("Comando Pix inválido")
    credentials.require(purpose="IN",network=transport is None)
    if credentials.account_id != command.obligation.provider_account_id:
        raise ProviderRequestBlocked("Recebedor incorreto")
    try:
        request=build_create_pix_request(
            access_token=credentials.access_token,
            payment=PixCollectionRequest(
                operation_id=command.external_reference,
                amount_cents=command.amount_cents,
                payer_email=payer_email,
                description="FR Caixinha "+command.obligation.kind.value,
                idempotency_key=command.idempotency_key,
            ),
        )
    except (TypeError,ValueError):
        raise ProviderRequestBlocked("Dados de cobrança inválidos") from None
    response=await _send(
        request,transport=transport,
        approved_network=credentials.server_approved_for_real_network,
    )
    data=_read_json(response)
    try:
        ident=data["id"]
        ident=str(ident) if type(ident) in (int,str) else ""
        collector=data["collector_id"]
        collector=str(collector) if type(collector) in (int,str) else ""
        amount=data["transaction_amount"]
        if (not _ID.fullmatch(ident)
                or collector!=credentials.account_id
                or data["external_reference"]!=command.external_reference
                or data["currency_id"]!="BRL"
                or type(data["live_mode"]) is not bool
                or data["live_mode"] is not (credentials.environment=="PRODUCAO")
                or type(amount) not in (int,str,Decimal)
                or not Decimal(amount).is_finite()
                or Decimal(amount)*100!=command.amount_cents
                or data["status"] not in ("pending","in_process")):
            raise ValueError("payment response mismatch")
        interaction=data.get("point_of_interaction")
        if type(interaction) is not dict:
            raise ValueError("missing Pix data")
        tx=interaction.get("transaction_data")
        if type(tx) is not dict:
            raise ValueError("missing Pix data")
        qr=_verified_qr(tx.get("qr_code"),4096)
        if not qr:
            raise ValueError("missing qr")
        png=_verified_qr(tx.get("qr_code_base64"),700000)
        ticket=_verified_qr(tx.get("ticket_url"),4096)
        if ticket is not None and not ticket.startswith(
                ("https://www.mercadopago.com.br/","https://mercadopago.com.br/")):
            raise ValueError("invalid ticket")
        return CreatedPix(command.operation_id,ident,command.amount_cents,
                          data["status"],qr,png,ticket)
    except (KeyError,TypeError,ValueError,ArithmeticError):
        raise ProviderRequestBlocked(
            "Cobrança não corresponde ao contrato/conta recebedora"
        ) from None


async def read_collection_from_provider(
    *, provider_payment_id: str, operation: PixPaymentCommand,
    credentials: ProviderCredentials,
    transport: httpx.AsyncBaseTransport | None = None,
) -> VerifiedProviderRead:
    """Never claims bank settlement from payment status alone."""
    if (type(operation) is not PixPaymentCommand
            or type(credentials) is not ProviderCredentials
            or type(provider_payment_id) is not str
            or not _ID.fullmatch(provider_payment_id)):
        raise ProviderRequestBlocked("Consulta de pagamento inválida")
    credentials.require(purpose="IN",network=transport is None)
    if credentials.account_id!=operation.obligation.provider_account_id:
        raise ProviderRequestBlocked("Conta incompatível")
    req=httpx.Request(
        "GET",f"{BASE}/v1/payments/{provider_payment_id}",
        headers={"Authorization":f"Bearer {credentials.access_token}",
                 "Accept":"application/json"},
    )
    response=await _send(
        req,transport=transport,
        approved_network=credentials.server_approved_for_real_network,
    )
    data=_read_json(response)
    if str(data.get("id",""))!=provider_payment_id:
        raise ProviderRequestBlocked("ID da consulta divergente")
    if data.get("status") not in (
            "pending","in_process","approved","rejected",
            "cancelled","refunded","charged_back"):
        raise ProviderRequestBlocked("Status de pagamento desconhecido")
    verified=matches_approved_payment(
        ExpectedPayment(
            provider_payment_id=provider_payment_id,
            collector_id=credentials.account_id,
            external_reference=operation.external_reference,
            amount_cents=operation.amount_cents,
            live_mode=credentials.environment=="PRODUCAO",
        ),
        data,
    )
    # A nonapproved status still requires matching bank/tenant context, so do
    # not return a trusted reference from a mismatched provider response.
    if (str(data.get("collector_id",""))!=credentials.account_id
            or data.get("external_reference")!=operation.external_reference
            or data.get("currency_id")!="BRL"
            or data.get("live_mode") is not (credentials.environment=="PRODUCAO")):
        raise ProviderRequestBlocked("Escopo da consulta incompatível")
    return VerifiedProviderRead(provider_payment_id,str(data["status"]),verified)


def build_payout_pix_request(
    *, order: DisbursementOrder, recipient: PixRecipient,
    credentials: ProviderCredentials, provider_profile: str,
) -> httpx.Request:
    """Documented Brazilian Transaction-Intents payout profile.

    Distinct from /v1/payouts batch API. Selection and eligibility must
    be validated in Mercado Pago developer portal before enabling.
    """
    if (type(order) is not DisbursementOrder
            or type(recipient) is not PixRecipient
            or type(credentials) is not ProviderCredentials
            or order.status is not PayoutState.RESERVED
            or not _REF.fullmatch(order.business_operation_id)
            or not _REF.fullmatch(order.idempotency_key)
            or provider_profile != "BR_TRANSACTION_INTENTS_PROCESS_V1"):
        raise ProviderRequestBlocked("Perfil Payouts não homologado")
    credentials.require(purpose="OUT",network=False)
    recipient.validate()
    if recipient.destination_id != str(order.destination_id):
        raise ProviderRequestBlocked("Destino foi alterado após reserva")
    # Exact cents serialized as decimal JSON numeric literal; never float.
    amount=decimal_brl(order.amount_cents)
    doc={
        "external_reference":order.business_operation_id,
        "point_of_interaction":{"type":"PSP_TRANSFER"},
        "transaction":{
            "from":{"accounts":[{"amount":"__EXACT__"}]},
            "to":{"accounts":[{"type":"current","amount":"__EXACT__",
                "chave":{"type":recipient.key_type,"value":recipient.pix_key},
                "owner":{"identification":{
                    "type":recipient.identification_type,
                    "number":recipient.identification_number,
                }}}]},
            "total_amount":"__EXACT__",
        },
    }
    raw=json.dumps(doc,ensure_ascii=True,separators=(",",":")).replace(
        '"__EXACT__"',amount
    ).encode("utf-8")
    return httpx.Request(
        "POST",f"{BASE}/v1/transaction-intents/process",
        headers={
            "Authorization":f"Bearer {credentials.access_token}",
            "Content-Type":"application/json",
            "Accept":"application/json",
            "X-Idempotency-Key":order.idempotency_key,
            "X-test-token":"true" if credentials.environment=="HOMOLOGACAO" else "false",
        },
        content=raw,
    )


async def submit_payout_pix(
    *, order: DisbursementOrder, recipient: PixRecipient,
    credentials: ProviderCredentials, provider_profile: str,
    transport: httpx.AsyncBaseTransport | None = None,
) -> SentPayout:
    """Real Payouts POST only with approved deployment capability.

    Even HTTP 200/202 or 'approved' NEVER means member received funds.
    """
    request=build_payout_pix_request(
        order=order,recipient=recipient,credentials=credentials,
        provider_profile=provider_profile,
    )
    if transport is None:
        credentials.require(purpose="OUT",network=True)
    response=await _send(
        request,transport=transport,
        approved_network=credentials.server_approved_for_real_network,
    )
    data=_read_json(response)
    ident=data.get("id")
    if (type(ident) not in (int,str)
            or not re.fullmatch("[A-Za-z0-9_-]{1,80}",str(ident))
            or data.get("external_reference")!=order.business_operation_id
            or data.get("status") not in ("approved","pending","in_process")):
        raise ProviderRequestBlocked("Payout não corresponde à operação")
    return SentPayout(
        business_operation_id=order.business_operation_id,
        provider_payout_id=str(ident),provider_status=str(data["status"]),
    )
