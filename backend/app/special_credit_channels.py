"""FR Finance — four provider-bound message envelopes (NO TRANSPORT).

Real communications are OFF by design. No function here issues HTTP/SMTP,
acquires tokens, or marks an outbox entry as sent. Integrators must later add
an independently approved dispatch worker and proof of provider delivery.
"""
from __future__ import annotations

from dataclasses import dataclass
from email.utils import parseaddr
import re
from typing import Any

from .special_credit_contract import SpecialCreditDenied, public_push_preview


@dataclass(frozen=True)
class PreparedEnvelope:
    channel: str
    url: str
    body: dict[str, Any]
    requires_secret: str
    real_send_enabled: bool = False


def _safe_target(value: str, pattern: str, message: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(pattern, value):
        raise SpecialCreditDenied(message)
    return value


def push_fcm_envelope(*, project_id: str, device_token: str) -> PreparedEnvelope:
    project = _safe_target(project_id, r"[A-Za-z0-9._~:-]{3,150}",
                           "Projeto Firebase inválido.")
    token = _safe_target(device_token, r"[A-Za-z0-9:_\-.]{20,4096}",
                         "Token de dispositivo inválido.")
    return PreparedEnvelope(
        channel="PUSH",
        url=f"https://fcm.googleapis.com/v1/projects/{project}/messages:send",
        body={"message":{"token":token,"notification":public_push_preview(),
                         "data":{"destination":"minhas-oportunidades"}}},
        requires_secret="FCM_OAUTH2_SCOPED_BEARER",
    )


def brevo_email_envelope(*, verified_sender: str, recipient: str,
                         unsubscribe_url: str) -> PreparedEnvelope:
    sender = _safe_target(verified_sender, r"[^\s@]{1,64}@[^\s@]{1,200}",
                          "Remetente não validado.")
    to = _safe_target(recipient, r"[^\s@]{1,64}@[^\s@]{1,200}",
                      "Destinatário inválido.")
    if parseaddr(sender)[1] != sender or parseaddr(to)[1] != to:
        raise SpecialCreditDenied("Endereço de e-mail inválido.")
    if not unsubscribe_url.startswith("https://") or len(unsubscribe_url)>500:
        raise SpecialCreditDenied("Cancelamento de marketing exige HTTPS.")
    return PreparedEnvelope(
        channel="EMAIL",
        url="https://api.brevo.com/v3/smtp/email",
        body={"sender":{"name":"FR Finance","email":sender},
              "to":[{"email":to}],"subject":"FR Finance • Nova oportunidade",
              "textContent":"Você tem uma oportunidade para consulta no FR Finance. "
                            "Nenhum crédito foi aprovado ou liberado. "
                            "Gerenciar mensagens: "+unsubscribe_url},
        requires_secret="BREVO_API_KEY",
    )


def whatsapp_template_envelope(*, phone_number_id: str, e164_digits: str,
                               approved_template: str, graph_api_version: str = "v23.0") -> PreparedEnvelope:
    number_id = _safe_target(phone_number_id,r"[0-9]{6,24}",
                             "Identificador do remetente WhatsApp inválido.")
    recipient = _safe_target(e164_digits,r"[1-9][0-9]{9,14}",
                             "Telefone de destino inválido.")
    template = _safe_target(approved_template,r"[a-z][a-z0-9_]{3,100}",
                            "Template aprovado inválido.")
    version = _safe_target(graph_api_version,r"v[0-9]{1,2}\.0",
                           "Versão Graph API inválida.")
    return PreparedEnvelope(
        channel="WHATSAPP",
        url=f"https://graph.facebook.com/{version}/{number_id}/messages",
        body={"messaging_product":"whatsapp","to":recipient,"type":"template",
              "template":{"name":template,"language":{"code":"pt_BR"}}},
        requires_secret="WHATSAPP_CLOUD_API_BEARER",
    )


def brevo_sms_marketing_envelope(*, sender: str, e164_digits: str,
                                content: str) -> PreparedEnvelope:
    source = _safe_target(sender,r"[A-Za-z0-9]{1,11}",
                          "Identificador SMS inválido.")
    recipient = _safe_target(e164_digits,r"[1-9][0-9]{9,14}",
                             "Número SMS inválido.")
    # Campaigns must be explicitly sent as marketing, not transaction messages.
    if not isinstance(content,str) or not 10 <= len(content) <= 140:
        raise SpecialCreditDenied("Corpo SMS fora dos limites.")
    if "aprovado" in content.lower() or "liberado" in content.lower():
        raise SpecialCreditDenied("SMS não pode sugerir crédito já liberado.")
    return PreparedEnvelope(
        channel="SMS",
        url="https://api.brevo.com/v3/transactionalSMS/send",
        body={"sender":source,"recipient":recipient,"type":"marketing",
              "content":content},
        requires_secret="BREVO_SMS_API_KEY",
    )


def provider_dispatch(*_args: Any, **_kwargs: Any) -> None:
    """No external communication without a separate, reviewed deployment."""
    raise SpecialCreditDenied(
        "Envio externo não autorizado: faltam homologação, canal e consentimento.")
