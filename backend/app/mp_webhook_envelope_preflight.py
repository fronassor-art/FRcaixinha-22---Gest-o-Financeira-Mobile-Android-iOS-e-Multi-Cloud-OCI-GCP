"""M2400: pré-validação de envelope de webhook Mercado Pago offline.

Não registra rota e não recebe rede. HMAC não substitui GET autenticado.
Sem inbox durável, a notificação não pode dar baixa em qualquer obrigação.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from uuid import UUID

from .mp_operational_preflight import verify_webhook_hmac_offline

MAX_ENVELOPE_BYTES = 16_384
_PAYMENT_ID = re.compile(r"[A-Za-z0-9_-]{1,100}\Z")
_REQUEST = re.compile(r"[A-Za-z0-9._:-]{1,120}\Z")
_SELLER = re.compile(r"[0-9]{1,40}\Z")
_ALLOWED_ACTIONS = frozenset((
    "payment.created", "payment.updated",
    "application.authorized", "application.deauthorized",
))


class RepeatedJsonKeyError(ValueError):
    pass


def _no_repeated_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise RepeatedJsonKeyError("JSON com campos repetidos")
        result[key] = value
    return result


@dataclass(frozen=True)
class WebhookPreview:
    tenant_id: UUID
    seller_id: str
    notification_id: str
    resource_id: str
    event_type: str
    action: str
    fingerprint_sha256: str
    signature_valid: bool
    sandbox_only: bool = True
    requires_durable_dedupe: bool = True
    provider_get_authenticated: bool = False
    bank_reconciled: bool = False
    paid: bool = False
    ledger_written: bool = False
    real_payments_enabled: bool = False


def preview_signed_sandbox_webhook(
    *, raw_json: bytes, signed_query_data_id: str, x_request_id: str,
    x_signature: str, secret: bytes, now_ms: int,
    tenant_id: UUID, expected_seller_id: str,
) -> WebhookPreview:
    if (type(raw_json) is not bytes or not 0 < len(raw_json) <= MAX_ENVELOPE_BYTES
            or type(tenant_id) is not UUID or type(expected_seller_id) is not str
            or not _SELLER.fullmatch(expected_seller_id)
            or type(signed_query_data_id) is not str
            or not _PAYMENT_ID.fullmatch(signed_query_data_id)
            or type(x_request_id) is not str or not _REQUEST.fullmatch(x_request_id)):
        raise ValueError("Envelope/canal inválido")
    try:
        data = json.loads(raw_json.decode("utf-8"),
                          object_pairs_hook=_no_repeated_keys,
                          parse_constant=lambda c: (_ for _ in ()).throw(
                              ValueError("Constante JSON inválida")))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Envelope JSON inválido") from exc
    if type(data) is not dict or type(data.get("data")) is not dict:
        raise ValueError("Notificação sem estrutura")
    resource_id = data["data"].get("id")
    if type(resource_id) is int and resource_id > 0:
        resource_id = str(resource_id)
    seller_id = data.get("user_id")
    if type(seller_id) is int and seller_id > 0:
        seller_id = str(seller_id)
    notification_id = data.get("id")
    if type(notification_id) is int and notification_id > 0:
        notification_id = str(notification_id)
    action = data.get("action")
    event_type = data.get("type")
    if (type(resource_id) is not str or not _PAYMENT_ID.fullmatch(resource_id)
            or resource_id != signed_query_data_id
            or type(seller_id) is not str or not _SELLER.fullmatch(seller_id)
            or seller_id != expected_seller_id
            or type(notification_id) is not str or not _PAYMENT_ID.fullmatch(notification_id)
            or data.get("live_mode") is not False
            or type(action) is not str or action not in _ALLOWED_ACTIONS
            or type(event_type) is not str or event_type not in ("payment", "mp-connect")
            or (event_type == "payment" and not action.startswith("payment."))
            or (event_type == "mp-connect" and not action.startswith("application."))):
        raise ValueError("Escopo, modo, identidade ou evento divergente")
    valid = verify_webhook_hmac_offline(
        data_id=signed_query_data_id, request_id=x_request_id,
        x_signature=x_signature, secret=secret, now_ms=now_ms,
    )
    if not valid:
        raise ValueError("Assinatura inválida ou expirada")
    fp = hashlib.sha256(raw_json).hexdigest()
    return WebhookPreview(
        tenant_id, seller_id, notification_id, resource_id,
        event_type, action, fp, True,
    )
