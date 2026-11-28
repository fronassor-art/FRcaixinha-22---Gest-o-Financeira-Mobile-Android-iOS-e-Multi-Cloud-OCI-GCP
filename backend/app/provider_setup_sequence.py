"""M28100 — deterministic ordered next steps for *public* provider inputs.

A field being filled is only a syntax check and never an operational attestation.
Do not print field values; no network, secrets, files or PostgreSQL access.
"""
from __future__ import annotations

from typing import Mapping

from .provider_intake_schema import FIELD_BY_KEY, validate_manifest, intake_audit

# Each phase is a narrow action instead of asking operators to fabricate
# instance/vault/database identifiers before OCI resources actually exist.
PHASES = (
    ("01_ACCOUNTS", (
        ("OCI_REGION", "Confirmar a região principal da conta OCI no Console; ainda não criar VM paga."),
        ("MP_APPLICATION_ID", "Criar ou localizar a aplicação em Mercado Pago Developers e copiar apenas o Application ID público."),
    )),
    ("02_DOMAIN_AND_MAIL", (
        ("APP_URL", "Escolher e registrar domínio próprio; este endereço só será válido após DNS e HTTPS."),
        ("SMTP_HOST", "Escolher um serviço de e-mail e obter o hostname SMTP oficial."),
        ("SMTP_PORT", "Confirmar STARTTLS na porta 587; não testar login nem enviar senha."),
        ("SMTP_USER", "Obter o identificador público da conta SMTP, sem a senha."),
        ("FR_FINANCE_EMAIL_FROM", "Registrar o remetente permitido e validar domínio/SPF/DKIM/DMARC no provedor."),
    )),
    ("03_OCI_STAGING", (
        ("OCI_COMPARTMENT_OCID", "Criar o compartment de staging e copiar seu OCID."),
        ("OCI_INSTANCE_OCID", "Provisionar apenas VM autorizada pelo orçamento e copiar o OCID."),
        ("OCI_DATABASE_HOST", "Definir hostname DNS do PostgreSQL OCI com TLS antes de colocar credenciais."),
        ("OCI_VAULT_OCID", "Criar Vault e copiar somente o OCID; manter segredos e versões fora do cadastro."),
    )),
    ("04_CALLBACKS", (
        ("MP_OAUTH_REDIRECT_URI", "Registrar callback HTTPS exato na aplicação Mercado Pago; nunca inserir code/state em URL pública."),
        ("MP_WEBHOOK_URL", "Registrar destino HTTPS do webhook; chave de assinatura vai para Vault, nunca para Git."),
    )),
)
OPS_PROOFS = (
    ("OCI_PUBLIC_HTTPS", "Comprovar DNS/TLS e acesso público à API de staging."),
    ("OCI_IAM_VAULT", "Comprovar dynamic group, IAM mínimo, Vault e acesso seguro à versão autorizada."),
    ("PG_ROLES_RLS", "Comprovar PostgreSQL OCI separado, migrações homologadas, RLS e backup restaurado."),
    ("SMTP_REAL", "Comprovar domínio/remetente, STARTTLS, entrega em caixa autorizada e reconciliação de falhas."),
    ("USER_SECURITY", "Comprovar posse real do e-mail, MFA Master, dupla aprovação e aceite individual de contrato."),
    ("MP_OAUTH_SELLER", "Comprovar OAuth Connect real com consentimento explícito e tokens separados por administrador."),
    ("MP_PIX_ORDERS", "Comprovar Orders Pix teste, assinatura x-signature, status e conciliação."),
    ("MP_PAYOUTS", "Obter autorização comercial/documental do provedor para Payouts/transferências."),
)


def prioritized_public_steps(manifest: Mapping) -> dict:
    safe = validate_manifest(manifest)
    present = set(safe["public_inputs"])
    stages = []
    next_missing = None
    for label, fields in PHASES:
        missing = [{"field": name, "action": message} for name, message in fields if name not in present]
        if next_missing is None and missing:
            next_missing = missing[0]["field"]
        stages.append({
            "phase": label,
            "status": "PUBLIC_FIELDS_COMPLETE_NOT_VERIFIED" if not missing else "PUBLIC_INPUT_PENDING",
            "missing": missing,
            "validated_public_count": len(fields) - len(missing),
            "total_public_count": len(fields),
            "operationally_verified": False,
        })
    all_fields = {name for _,fields in PHASES for name,_ in fields}
    if all_fields != set(FIELD_BY_KEY):
        raise RuntimeError("M28100_SETUP_FIELD_INVENTORY_MISMATCH")
    return {
        "scope": "AI_STUDIO_PUBLIC_INPUT_SETUP_ORDER",
        "mode": "INSTRUCTIONS_ONLY_NO_NETWORK_OR_ACTIVATION",
        "project": "FR_FINANCE_AI_STUDIO",
        "next_public_field": next_missing,
        "stages": stages,
        "remaining_public_count": len(set(FIELD_BY_KEY) - present),
        "external_proofs": [{"gate": gate, "required_evidence":description, "verified":False}
                            for gate,description in OPS_PROOFS],
        "all_external_gates_blocked": True,
        "credentials_required_in_chat": False,
        "requires_oci_secret_handling": True,
        "real_email_enabled": False,
        "real_users_enabled": False,
        "real_pix_enabled": False,
    }
