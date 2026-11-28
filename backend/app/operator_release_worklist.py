"""M27900/M28000 — actionable external deployment checklist; no enablement.

This is an operator planning document generated from syntactically valid,
nonsecret provider data. It cannot attest vendor permissions, delivery,
contractual consent, database security, MFA or account ownership.
"""
from __future__ import annotations

from typing import Mapping

from .provider_intake_schema import GATE_FIELDS, intake_audit, validate_manifest


PROVIDER_TASKS = {
    "OCI_HOSTING":(
        ("OPERATOR", "Criar tenancy/instância OCI de staging e configurar SSH restrito, VCN, firewall, DNS, HTTPS."),
        ("DEVELOPER", "Implantar API em staging, checar SHA runtime, RLS, backups, restauração e certificado TLS."),
        ("OPERATOR", "Aprovar orçamento/tier e comprovar recursos e limites da OCI."),
    ),
    "OCI_VAULT_IAM":(
        ("OPERATOR", "Criar Vault e segredos separadamente por finalidade; informar apenas OCIDs e versões não secretas."),
        ("DEVELOPER", "Configurar Dynamic Group, IAM mínimo e rotação; testar uso por Instance Principal."),
    ),
    "MAIL_PROVIDER":(
        ("OPERATOR", "Registrar domínio/remetente e configurar SPF, DKIM e DMARC com provedor de e-mail."),
        ("OPERATOR", "Salvar senha/API key de SMTP no OCI Vault, nunca no GitHub, aplicativo ou chat."),
        ("DEVELOPER", "Validar STARTTLS, autenticidade de callbacks e outbox transacional com quarentena."),
        ("DEVELOPER", "Testar entrega real somente para caixa de e-mail de teste autorizada."),
    ),
    "USER_ACTIVATION":(
        ("OPERATOR", "Fornecer texto contratual final aprovado e identidade do responsável legal."),
        ("DEVELOPER", "Provar posse do e-mail em banco de staging real, sem token em logs."),
        ("DEVELOPER", "Testar MFA Master, dupla aprovação, aceite do próprio convidado e sessão de uso único."),
        ("DEVELOPER", "Testar recuperação de senha, revogação de sessões e trilha de auditoria."),
    ),
    "MP_CONNECT":(
        ("OPERATOR", "Criar aplicação Mercado Pago, configurar redirect URI HTTPS e obter Client ID público."),
        ("OPERATOR", "Guardar Client Secret em OCI Vault; não enviar token pelo chat/GitHub."),
        ("DEVELOPER", "Testar OAuth authorization_code com PKCE, state, refresh token e vínculos separados por caixinha."),
        ("OPERATOR", "Solicitar autorização explícita do administrador de cada conta Mercado Pago."),
    ),
    "PIX_INBOUND":(
        ("OPERATOR", "Configurar webhooks de Orders no Mercado Pago e guardar chave de assinatura no Vault."),
        ("DEVELOPER", "Testar Pix da Orders API com credenciais de teste, idempotência e validação x-signature."),
        ("DEVELOPER", "Conferir pagamento no provedor e no Livro-Razão antes de qualquer baixa contábil."),
    ),
    "PIX_OUTBOUND":(
        ("OPERATOR", "Solicitar por escrito ao Mercado Pago confirmação comercial da API de Payouts/transferências Pix para a aplicação."),
        ("OPERATOR", "Confirmar documentação, limites, endpoints e modelo de autorização efetivamente habilitados."),
        ("DEVELOPER", "Testar autorização de cada pagamento, limites, destinatários, antifraude e conciliação antes de mover dinheiro."),
    ),
}
SENSITIVE_ITEMS = (
    "SMTP_PASSWORD", "MP_CLIENT_SECRET", "MP_WEBHOOK_SIGNATURE_SECRET",
    "MP_OAUTH_REFRESH_TOKEN", "MP_SELLER_ACCESS_TOKEN",
    "AUTH_SECRET", "OCI_SECRET_CONTENT", "POSTGRESQL_PASSWORD",
)
OFF_FLAGS = {
    "smtp_network_send": False,
    "invite_delivery_enabled": False,
    "member_activation_enabled": False,
    "admin_activation_enabled": False,
    "password_recovery_live": False,
    "mp_oauth_live": False,
    "pix_orders_live": False,
    "pix_payouts_live": False,
    "money_movement_enabled": False,
}


def release_worklist(manifest: Mapping) -> dict:
    validated = validate_manifest(manifest)
    audit = intake_audit(validated)
    tasks = []
    for gate in audit["gates"]:
        name = gate["gate"]
        tasks.append({
            "id": name,
            "status": gate["status"],
            "public_fields_missing": list(gate["missing_public_fields"]),
            "provider_test_approved": False,
            "live_provider_authorized": False,
            "actions": [
                {"responsible": owner, "action": description, "state":"PENDING_EXTERNAL_EVIDENCE"}
                for owner, description in PROVIDER_TASKS[name]
            ],
        })
    return {
        "project": "FR_FINANCE_AI_STUDIO",
        "mode": "OPERATOR_WORKLIST_NO_ACTIVATION",
        "public_fields_complete": not audit["public_fields_absent"],
        "overall_status": "EXTERNAL_ATTESTATION_AND_SECURITY_APPROVAL_REQUIRED",
        "required_secret_names_only": list(SENSITIVE_ITEMS),
        "secrets_collected": False,
        "enables_any_action": False,
        "live_state": dict(OFF_FLAGS),
        "stages": tasks,
    }
