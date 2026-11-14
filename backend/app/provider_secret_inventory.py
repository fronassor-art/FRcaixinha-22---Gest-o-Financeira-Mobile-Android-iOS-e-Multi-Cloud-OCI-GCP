"""M28300 — approved-purpose OCI secret inventory, NEVER any secret values.

Lists IAM separation and credential owners before operator uploads their
secrets directly to OCI Vault or a similarly approved private runtime.
Does not fetch secrets, read local environment variables or access services.
No entry proves OCI tenancy, commercial MP approval or email ownership.
"""
from __future__ import annotations

from dataclasses import dataclass

@dataclass(frozen=True)
class SecretRequirement:
    alias: str
    service: str
    owner: str
    storage: str
    isolation: str
    requirement: str


REQUIREMENTS = (
    SecretRequirement("SMTP_PASSWORD","EMAIL","SERVICE_MAIL_WORKER","OCI_VAULT",
                      "MAIL_ONLY","SMTP app password/API key for verified sender; STARTTLS required"),
    SecretRequirement("EMAIL_WEBHOOK_SIGNATURE_KEY","EMAIL","SERVICE_MAIL_RECEIPTS","OCI_VAULT",
                      "EMAIL_RECEIPT_ONLY","Authenticates email provider delivery/bounce callbacks when supported"),
    SecretRequirement("MP_CLIENT_SECRET","MP_CONNECT","SERVICE_OAUTH_EXCHANGE","OCI_VAULT",
                      "PLATFORM_OAUTH_ONLY","Application client secret, never delivered to APK"),
    SecretRequirement("MP_WEBHOOK_SECRET","PIX_INBOUND","SERVICE_MP_WEBHOOK","OCI_VAULT",
                      "MP_WEBHOOK_ONLY","HMAC x-signature secret, separate from OAuth secret"),
    SecretRequirement("MP_SELLER_REFRESH_TOKEN","MP_CONNECT","SERVICE_TENANT_OAUTH","OCI_VAULT_PER_TENANT",
                      "TENANT_BOUND","Unique seller consent grant and token version per administrator"),
    SecretRequirement("FR_FINANCE_AUTH_SECRET","USER_ACTIVATION","SERVICE_AUTH_SESSION","OCI_VAULT",
                      "AUTH_SESSION_ONLY","Session/key signing; independent of email and Pix credentials"),
    SecretRequirement("FR_FINANCE_RATE_LIMIT_KEY","USER_ACTIVATION","SERVICE_RATE_LIMIT","OCI_VAULT",
                      "RATE_LIMIT_ONLY","HMAC rate-limit key independent of session secret"),
    SecretRequirement("ENVELOPE_AES_KEY","EMAIL","SERVICE_MAIL_ENVELOPE","OCI_VAULT_PER_TENANT",
                      "TENANT_BOUND","32-byte AES-256-GCM envelope key, version pinned and rotated"),
    SecretRequirement("RECIPIENT_INDEX_HMAC_KEY","EMAIL","SERVICE_RECIPIENT_INDEX","OCI_VAULT_PER_TENANT",
                      "TENANT_BOUND","32-byte index key, never reuse AES-GCM encryption key"),
    SecretRequirement("PG_APP_PASSWORD","OCI_POSTGRES","SERVICE_APP_API","OCI_VAULT",
                      "DB_APP_ONLY","RLS application role secret, no DB superuser"),
    SecretRequirement("PG_AUTH_PASSWORD","OCI_POSTGRES","SERVICE_AUTH_API","OCI_VAULT",
                      "DB_AUTH_ONLY","Separate auth role with limited privileges"),
    SecretRequirement("PG_VERIFIER_PASSWORD","OCI_POSTGRES","SERVICE_PASSWORD_VERIFIER","OCI_VAULT",
                      "DB_VERIFIER_ONLY","Separate password verification role, no session issuance privilege"),
)
AUTHORIZATION_GATES = (
    "OCI_INSTANCE_PRINCIPAL_AND_IAM",
    "TLS_PUBLIC_ENDPOINT",
    "SENDER_DOMAIN_VERIFIED",
    "SMTP_DELIVERY_CALLBACK_ATTESTED",
    "MASTER_MFA_AND_DUAL_APPROVAL",
    "TENANT_RLS_IN_STAGING",
    "RECIPIENT_EMAIL_OWNERSHIP",
    "INVITEE_CONTRACT_CONSENT",
    "MP_APPLICATION_APPROVED",
    "MP_SELLER_OAUTH_CONSENT",
    "MP_ORDERS_PIX_RECONCILIATION",
    "MP_MONEY_OUT_COMMERCIALLY_ENABLED",
)


def secret_names_and_access_plan() -> dict:
    if len({x.alias for x in REQUIREMENTS}) != len(REQUIREMENTS):
        raise RuntimeError("M28300_DUPLICATE_SECRET_ALIAS")
    return {
        "project":"FR_FINANCE_AI_STUDIO",
        "mode":"READ_ONLY_NO_CREDS_OR_DEPLOYMENT",
        "secret_values":None,
        "secrets_collected":False,
        "secrets_exist_in_vault_verified":False,
        "credentials_present_in_chat":False,
        "status":"PROVISION_IN_APPROVED_VAULT_AND_ATTEST",
        "secret_requirements":[{
            "alias":item.alias,
            "service":item.service,
            "owner_role":item.owner,
            "storage":item.storage,
            "isolation":item.isolation,
            "description":item.requirement,
            "state":"NOT_ATTESTED",
        } for item in REQUIREMENTS],
        "approval_gates":[{"gate":gate,"approved":False,"evidence_recorded":False}
                          for gate in AUTHORIZATION_GATES],
        "send_email":False,
        "activate_user":False,
        "pix_collection":False,
        "pix_payout":False,
    }
