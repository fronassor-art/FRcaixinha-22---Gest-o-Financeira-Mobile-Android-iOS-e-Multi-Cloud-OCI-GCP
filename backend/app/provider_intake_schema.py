"""M27700 — FR Finance AI Studio nonsecret provider-intake contract.

Only PUBLIC identifiers/hostnames may be stored. Never collect tokens,
passwords, client secrets, email webhook secrets, DSNs or key material here.
Complete field syntax is NOT proof of provider control or production approval.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Mapping
from urllib.parse import urlsplit

from .config import safe_public_https_origin
from .onboarding_mail_transport import _mailbox, _smtp_host, MailConfigurationBlocked
from .mp_oauth_connect_preflight import _validate_redirect

PROJECT = "FR_FINANCE_AI_STUDIO"
VERSION = 1


class IntakeBlocked(ValueError):
    pass


@dataclass(frozen=True)
class PublicField:
    key: str
    category: str
    description: str
    example: str


FIELDS = (
    PublicField("APP_URL","infra","Origem HTTPS pública prevista do aplicativo","https://app.seudominio.com.br"),
    PublicField("OCI_REGION","oci","Região escolhida na tenancy OCI","sa-saopaulo-1"),
    PublicField("OCI_COMPARTMENT_OCID","oci","OCID público do compartimento da implantação","ocid1.compartment.oc1..identificador"),
    PublicField("OCI_INSTANCE_OCID","oci","OCID da instância autorizada para executar o serviço","ocid1.instance.oc1..identificador"),
    PublicField("OCI_VAULT_OCID","oci","OCID do Vault que guardará os segredos","ocid1.vault.oc1.regiao.identificador"),
    PublicField("OCI_DATABASE_HOST","oci","Hostname previsto do PostgreSQL OCI com TLS","db.seudominio.com.br"),
    PublicField("SMTP_HOST","email","Servidor de envio SMTP com STARTTLS","smtp.provedor.com.br"),
    PublicField("SMTP_PORT","email","Porta SMTP com STARTTLS (587)","587"),
    PublicField("SMTP_USER","email","Identificador público da conta de envio, sem senha","envios@seudominio.com.br"),
    PublicField("FR_FINANCE_EMAIL_FROM","email","Remetente verificado no domínio","contato@seudominio.com.br"),
    PublicField("MP_APPLICATION_ID","mercado_pago","Client ID público da aplicação Mercado Pago","1234567890123456"),
    PublicField("MP_OAUTH_REDIRECT_URI","mercado_pago","Callback HTTPS exato registrado no OAuth Connect","https://api.seudominio.com.br/api/v1/mp/oauth/callback"),
    PublicField("MP_WEBHOOK_URL","mercado_pago","Endpoint HTTPS que receberá notificações assinadas","https://api.seudominio.com.br/api/v1/mp/webhooks"),
)
FIELD_BY_KEY = {field.key: field for field in FIELDS}
GATE_FIELDS = {
    "OCI_HOSTING": ("APP_URL","OCI_REGION","OCI_COMPARTMENT_OCID",
                    "OCI_INSTANCE_OCID","OCI_DATABASE_HOST"),
    "OCI_VAULT_IAM": ("OCI_REGION","OCI_COMPARTMENT_OCID","OCI_VAULT_OCID"),
    "MAIL_PROVIDER": ("APP_URL","SMTP_HOST","SMTP_PORT",
                      "SMTP_USER","FR_FINANCE_EMAIL_FROM"),
    "USER_ACTIVATION": ("APP_URL","FR_FINANCE_EMAIL_FROM","OCI_DATABASE_HOST"),
    "MP_CONNECT": ("MP_APPLICATION_ID","MP_OAUTH_REDIRECT_URI"),
    "PIX_INBOUND": ("MP_APPLICATION_ID","MP_WEBHOOK_URL","MP_OAUTH_REDIRECT_URI"),
    "PIX_OUTBOUND": ("MP_APPLICATION_ID","MP_OAUTH_REDIRECT_URI"),
}
EXTERNAL_REQUIREMENTS = {
    "OCI_HOSTING":"VM com IP, DNS, HTTPS/TLS, firewall, backup restaurado e RLS homologados.",
    "OCI_VAULT_IAM":"Vault criado, segredo versionado, dynamic group e política IAM mínima testados.",
    "MAIL_PROVIDER":"Domínio controlado, SPF/DKIM/DMARC, remetente homologado, credencial no Vault, STARTTLS e recibos reais auditados.",
    "USER_ACTIVATION":"MFA Master, dupla aprovação, e-mail realmente verificado, contrato aceito pelo convidado e transação RLS de uso único.",
    "MP_CONNECT":"Aplicação aprovada, OAuth authorization_code+PKCE e consentimento de cada administrador, refresh e segregação por tenant.",
    "PIX_INBOUND":"Orders Pix do vendedor, webhook x-signature validado, idempotência e conciliação com Livro-Razão.",
    "PIX_OUTBOUND":"Habilitação comercial Money Out/PSP_TRANSFER confirmada pelo Mercado Pago e testes de limites.",
}


def _deny() -> IntakeBlocked:
    return IntakeBlocked("M27700_PUBLIC_INTAKE_INVALID")


def _dns_host(host: str) -> bool:
    if type(host) is not str or not 4 <= len(host) <= 253 or host != host.strip():
        return False
    if host.lower() != host or not re.fullmatch(r"[a-z0-9.-]+", host):
        return False
    labels = host.split(".")
    return (len(labels) >= 2 and len(labels[-1]) >= 2
            and all(re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", x)
                    for x in labels)
            and not host.endswith((".local",".internal",".test",".invalid",".example",".localhost"))
            and not re.fullmatch(r"\d+\.\d+\.\d+\.\d+",host))


def _public_endpoint(value: str) -> bool:
    if type(value) is not str or len(value) > 512:
        return False
    try:
        parsed = urlsplit(value)
        return (
            parsed.scheme == "https" and parsed.hostname is not None
            and safe_public_https_origin(f"https://{parsed.hostname}") is not None
            and parsed.port in (None,443) and parsed.username is None
            and parsed.password is None and not parsed.query and not parsed.fragment
            and parsed.path.startswith("/") and len(parsed.path) > 1
            and not parsed.path.startswith("//") and not any(c.isspace() for c in value)
        )
    except ValueError:
        return False


def validate_field(key: str, value: str) -> str:
    """Return syntactically approved PUBLIC input, never a credential."""
    if type(key) is not str or key not in FIELD_BY_KEY:
        raise _deny()
    if type(value) is not str or not value or len(value) > 512 or value != value.strip():
        raise _deny()
    if any(c in value for c in ("\n","\r","\x00")):
        raise _deny()
    try:
        valid = {
            "APP_URL": lambda: safe_public_https_origin(value) == value.rstrip("/"),
            "OCI_REGION": lambda: bool(re.fullmatch(r"[a-z]{2}-[a-z0-9-]{3,48}-[0-9]",value)),
            "OCI_COMPARTMENT_OCID": lambda: bool(re.fullmatch(r"ocid1\.compartment\.oc1\.[a-z0-9._-]{10,256}",value)),
            "OCI_INSTANCE_OCID": lambda: bool(re.fullmatch(r"ocid1\.instance\.oc1\.[a-z0-9._-]{10,256}",value)),
            "OCI_VAULT_OCID": lambda: bool(re.fullmatch(r"ocid1\.vault\.oc1\.[a-z0-9._-]{10,256}",value)),
            "OCI_DATABASE_HOST": lambda: _dns_host(value),
            "SMTP_HOST": lambda: _smtp_host(value)==value,
            "SMTP_PORT": lambda: value=="587",
            "SMTP_USER": lambda: _mailbox(value)==value,
            "FR_FINANCE_EMAIL_FROM": lambda: _mailbox(value)==value,
            "MP_APPLICATION_ID": lambda: bool(re.fullmatch(r"[0-9]{1,40}",value)),
            "MP_OAUTH_REDIRECT_URI": lambda: _validate_redirect(value)==value,
            "MP_WEBHOOK_URL": lambda: _public_endpoint(value),
        }[key]()
    except (MailConfigurationBlocked, ValueError, TypeError, KeyError):
        valid = False
    if not valid:
        raise _deny()
    return value


def new_manifest() -> dict:
    return {"schema_version": VERSION, "project": PROJECT, "public_inputs": {}}


def validate_manifest(manifest: object) -> dict:
    if (type(manifest) is not dict or set(manifest) !=
            {"schema_version","project","public_inputs"}
            or type(manifest["schema_version"]) is not int
            or manifest["schema_version"] != VERSION
            or manifest["project"] != PROJECT
            or type(manifest["public_inputs"]) is not dict):
        raise _deny()
    fields = manifest["public_inputs"]
    if len(fields) > len(FIELDS):
        raise _deny()
    for key,value in fields.items():
        validate_field(key,value)
    return {"schema_version":VERSION,"project":PROJECT,"public_inputs":dict(fields)}


def intake_audit(manifest: Mapping) -> dict:
    """Always fail closed: field syntax does not activate external providers."""
    safe = validate_manifest(manifest)
    fields = safe["public_inputs"]
    checks = []
    for name, required in GATE_FIELDS.items():
        missing = [key for key in required if key not in fields]
        checks.append({
            "gate":name,
            "status":"PUBLIC_FIELDS_MISSING" if missing else "PROVIDER_ATTESTATION_REQUIRED",
            "public_fields_complete":not missing,
            "missing_public_fields":missing,
            "provider_evidence_required":EXTERNAL_REQUIREMENTS[name],
            "operationally_verified":False,
            "enabled":False,
        })
    return {
        "project":PROJECT,"mode":"READ_ONLY_NEVER_ACTIVATES",
        "public_fields_present":sorted(fields),
        "public_fields_absent":sorted(set(FIELD_BY_KEY)-set(fields)),
        "status":"BLOCKED_EXTERNAL_EVIDENCE",
        "email_real_active":False,
        "user_activation_active":False,
        "pix_inbound_active":False,
        "pix_outbound_active":False,
        "provider_credentials_stored":False,
        "writes_performed":False,
        "gates":checks,
    }
