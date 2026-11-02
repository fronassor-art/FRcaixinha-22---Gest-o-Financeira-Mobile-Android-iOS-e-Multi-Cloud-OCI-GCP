"""Adaptadores REAIS de entrega de convite e cobrança SaaS, DESLIGADOS por padrão.

Nenhum endpoint público usa estes adaptadores nesta etapa. Tokens permanecem
no servidor; a API do pagamento pertence à PLATAFORMA, nunca à caixinha.
A confirmação depende de consulta autenticada à API Mercado Pago.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from email.message import EmailMessage
import os
import re
import smtplib
import ssl
from typing import Any, Mapping
from urllib.parse import urlencode, urlsplit

import httpx

from .mercado_pago_adapter import (
    PixCollectionRequest, PixCollectionResponse, build_create_pix_request,
    build_get_payment_request, parse_collection_response,
)
from .mercado_pago_safety import ExpectedPayment, matches_approved_payment, verify_webhook_signature


class ProviderUnavailable(RuntimeError):
    """Configuração, autorização ou confirmação externa insuficiente."""


@dataclass(frozen=True)
class InviteMailConfig:
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_password: str
    sender: str
    public_app_url: str
    use_starttls: bool = True

    def verify(self) -> None:
        url=urlsplit(self.public_app_url)
        if (url.scheme != "https" or not url.hostname or url.username or url.password
                or url.fragment or url.query or self.smtp_port not in range(1,65536)
                or not all((self.smtp_host,self.smtp_user,self.smtp_password,self.sender))
                or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+",self.sender)):
            raise ProviderUnavailable("Provedor SMTP ou URL HTTPS não está configurado com segurança.")


@dataclass(frozen=True)
class PlatformMpConfig:
    access_token: str
    collector_id: str
    webhook_secret: str
    live_mode: bool

    def verify(self) -> None:
        if (not self.access_token or '\r' in self.access_token or '\n' in self.access_token
                or not re.fullmatch(r"[0-9]{1,40}",self.collector_id)
                or len(self.webhook_secret) < 20):
            raise ProviderUnavailable("Credenciais SaaS de plataforma incompletas.")


def _required_real_gate(*, kind: str) -> None:
    """Exige duas aprovações independentes da configuração técnica."""
    prefix={"INVITES":"AI_STUDIO_REAL_INVITES","SAAS":"AI_STUDIO_REAL_SAAS"}[kind]
    if (os.getenv(prefix) != "APPROVED"
            or os.getenv("AI_STUDIO_LEGAL_CLEARANCE") != "APPROVED"
            or os.getenv("AI_STUDIO_OPERATIONAL_REVIEW") != "APPROVED"):
        raise ProviderUnavailable("Integração real bloqueada até autorização jurídica e operacional.")


def invitation_delivery_ready(config: InviteMailConfig) -> bool:
    try:
        _required_real_gate(kind="INVITES")
        config.verify()
        return True
    except ProviderUnavailable:
        return False


def platform_saas_ready(config: PlatformMpConfig) -> bool:
    try:
        _required_real_gate(kind="SAAS")
        config.verify()
        return True
    except ProviderUnavailable:
        return False


def send_invitation_email(*, config: InviteMailConfig, recipient: str,
                          token: str, invitation_id: str,
                          smtp_factory=None) -> None:
    """Entrega SMTP genuína somente após habilitação expressa.

    Chamador deve gravar hash do convite em uma transação ANTES de enviar.
    Se entrega falhar, revogar o token; nunca marcar entregue por suposição.
    """
    _required_real_gate(kind="INVITES")
    config.verify()
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+",recipient) or not re.fullmatch(r"[A-Za-z0-9_-]{32,128}",token):
        raise ProviderUnavailable("Destinatário ou token de convite inválido.")
    if not re.fullmatch(r"[0-9a-fA-F-]{36}",invitation_id):
        raise ProviderUnavailable("Identificador do convite inválido.")
    url=config.public_app_url.rstrip("/")+"/accept-invitation?"+urlencode(
        {"token":token,"invitation":invitation_id}
    )
    msg=EmailMessage()
    msg["From"]=config.sender
    msg["To"]=recipient
    msg["Subject"]="Convite de acesso ao aplicativo"
    msg.set_content(
        "Você recebeu um convite individual. Se não solicitou, ignore.\n"
        "Acesse o link HTTPS para validar o convite e ler o contrato antes do aceite:\n"
        f"{url}\n"
        "O link expira, pode ser revogado e só poderá ser usado uma vez.\n"
    )
    factory=smtp_factory or smtplib.SMTP
    try:
        with factory(config.smtp_host,config.smtp_port,timeout=10) as client:
            if config.use_starttls:
                client.starttls(context=ssl.create_default_context())
            client.login(config.smtp_user,config.smtp_password)
            refused=client.send_message(msg)
            if refused:
                raise ProviderUnavailable("O servidor SMTP recusou o destinatário.")
    except (smtplib.SMTPException,OSError,TimeoutError) as exc:
        raise ProviderUnavailable("Falha ao entregar convite por SMTP.") from exc


async def create_platform_pix(*, config: PlatformMpConfig, intent: PixCollectionRequest,
                              client: httpx.AsyncClient) -> PixCollectionResponse:
    """Emite cobrança SaaS na conta da plataforma. Nunca altera patrimônio de tenant."""
    _required_real_gate(kind="SAAS")
    config.verify()
    request=build_create_pix_request(access_token=config.access_token,payment=intent)
    try:
        response=await client.send(request,follow_redirects=False)
        return parse_collection_response(response,expected=intent,
                                         collector_id=config.collector_id,
                                         live_mode=config.live_mode)
    except (httpx.HTTPError,ValueError) as exc:
        raise ProviderUnavailable("Cobrança não confirmada pelo provedor.") from exc


async def fetch_authoritative_saas_payment(*, config: PlatformMpConfig,
                                           payment_id: str, client: httpx.AsyncClient
                                           ) -> Mapping[str,Any]:
    """GET confiável. Um webhook ou o frontend NUNCA podem criar status APPROVED."""
    _required_real_gate(kind="SAAS")
    config.verify()
    request=build_get_payment_request(access_token=config.access_token,
                                      provider_payment_id=payment_id)
    try:
        response=await client.send(request,follow_redirects=False)
        if response.status_code != 200 or len(response.content)>65536:
            raise ProviderUnavailable("Consulta ao pagamento indisponível.")
        result=response.json()
        if not isinstance(result,dict) or str(result.get("id"))!=payment_id:
            raise ProviderUnavailable("Pagamento não pertence à consulta.")
        return result
    except (httpx.HTTPError,ValueError) as exc:
        raise ProviderUnavailable("Consulta ao Mercado Pago não validada.") from exc


def verify_saas_webhook(*, config: PlatformMpConfig, signature: str,
                        request_id: str, payment_id: str,
                        now: datetime | None = None) -> bool:
    """Assinatura HMAC e timestamp recente; ainda requer GET e idempotência no DB."""
    try:
        _required_real_gate(kind="SAAS")
        config.verify()
        ts=next((part.strip().split("=",1)[1] for part in signature.split(",")
                 if part.strip().startswith("ts=")),None)
        if ts is None or not ts.isascii() or not ts.isdecimal() or not re.fullmatch(r"[0-9]{1,40}",payment_id):
            return False
        clock=now or datetime.now(timezone.utc)
        if abs(clock.timestamp()-int(ts))>300:
            return False
        return verify_webhook_signature(secret=config.webhook_secret,signature=signature,
                                        request_id=request_id,resource_id=payment_id)
    except (ValueError,ProviderUnavailable):
        return False


def confirm_authoritative_approved_payment(*, expected: ExpectedPayment,
                                           provider_response: Mapping[str,Any]) -> bool:
    """A aprovação de licença depende de todos os campos coincidentes."""
    return matches_approved_payment(expected,provider_response)


def read_configuration_status() -> dict[str,str]:
    """Somente diagnóstico não sensível; não expõe URL, senha, token ou segredo."""
    # Não retornar valores de env; somente estados.
    def approved(prefix: str) -> str:
        try:
            _required_real_gate(kind=prefix)
        except ProviderUnavailable:
            return "BLOCKED_BY_GOVERNANCE"
        return "GOVERNANCE_GATE_OPEN_CONFIG_UNVERIFIED"
    return {"invitation_delivery":approved("INVITES"),
            "saas_platform_payment":approved("SAAS"),
            "environment":"NO_OPERATIONS_PERFORMED"}
