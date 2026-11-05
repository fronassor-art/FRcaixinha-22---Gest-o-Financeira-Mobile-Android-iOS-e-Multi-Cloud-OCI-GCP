"""M4300 Money Out: commercial and signing gates for Brazilian Pix OUT.

FR Caixinha is management software, not a financial institution.
Money Out is an external provider rail. No flag here authorizes payout;
operator/PSP attestation and audited signer are outside this module.
"""
from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID
import re

CONTRACT="AI_STUDIO_M4300_MONEY_OUT_COMMERCIAL_SIGNING_GATE_V1"


@dataclass(frozen=True)
class MoneyOutGate:
    tenant_id: UUID
    provider_account_id: str
    environment: str
    admin_account_connected: bool
    application_authorized: bool
    commercial_money_out_approved: bool
    loan_disbursement_use_case_approved: bool
    legal_and_compliance_approved: bool
    account_balance_verified: bool
    recipient_pix_key_verified: bool
    destination_ownership_verified: bool
    signed_body_validated: bool
    signature_key_in_server_vault: bool
    webhook_and_get_verified: bool
    atomic_reservation_ready: bool
    audit_artifact_id: str | None = None

    def __post_init__(self):
        if (type(self.tenant_id) is not UUID
                or type(self.provider_account_id) is not str
                or not re.fullmatch(r"[0-9]{1,40}",self.provider_account_id)
                or self.environment not in ("HOMOLOGACAO","PRODUCAO")):
            raise ValueError("Money Out sem identidade de caixinha")
        for item in (
            self.admin_account_connected,self.application_authorized,
            self.commercial_money_out_approved,
            self.loan_disbursement_use_case_approved,
            self.legal_and_compliance_approved,
            self.account_balance_verified,self.recipient_pix_key_verified,
            self.destination_ownership_verified,self.signed_body_validated,
            self.signature_key_in_server_vault,self.webhook_and_get_verified,
            self.atomic_reservation_ready,
        ):
            if type(item) is not bool:
                raise ValueError("Prova Money Out deve ser booleana")
        if self.audit_artifact_id is not None and (
            type(self.audit_artifact_id) is not str
            or not re.fullmatch(r"[A-Za-z0-9._:-]{12,128}",self.audit_artifact_id)
        ):
            raise ValueError("Evidência comercial inválida")


@dataclass(frozen=True)
class MoneyOutReadiness:
    contract: str
    pending: tuple[str,...]
    eligible_for_manual_review: bool
    sandbox_dryrun_allowed: bool
    production_execution_authorized: bool = False
    money_transferred: bool = False
    bank_reconciled: bool = False
    ledger_written: bool = False


_REQUIRED={
    "admin_account_connected":"OAUTH_ADMIN_ACCOUNT",
    "application_authorized":"APP_PROVIDER_AUTH",
    "commercial_money_out_approved":"MONEY_OUT_COMMERCIAL_CONTRACT",
    "loan_disbursement_use_case_approved":"LOAN_USE_CASE_PROVIDER_APPROVAL",
    "legal_and_compliance_approved":"CREDIT_LEGAL_COMPLIANCE",
    "account_balance_verified":"PROVIDER_BALANCE_PROOF",
    "recipient_pix_key_verified":"REGISTERED_PIX_KEY",
    "destination_ownership_verified":"RECIPIENT_OWNERSHIP_PROOF",
    "signed_body_validated":"SIGNED_BODY_EXACT_BYTES",
    "signature_key_in_server_vault":"PROTECTED_SIGNATURE_KEY",
    "webhook_and_get_verified":"SIGNED_WEBHOOK_AND_AUTH_GET",
    "atomic_reservation_ready":"ATOMIC_UNIQUE_PAYOUT_RESERVATION",
}


def evaluate_money_out_gate(gate:MoneyOutGate) -> MoneyOutReadiness:
    if type(gate) is not MoneyOutGate:
        raise ValueError("Parâmetros de Money Out inválidos")
    pending=tuple(code for attr,code in _REQUIRED.items()
                  if getattr(gate,attr) is not True)
    if gate.audit_artifact_id is None:
        pending+=("INDEPENDENT_PROVIDER_ATTESTATION",)
    if gate.environment!="HOMOLOGACAO":
        pending+=("PRODUCTION_POLICY_DISABLED_UNTIL_EXTERNAL_SIGNOFF",)
    ready=not pending and gate.environment=="HOMOLOGACAO"
    # A capability preview never grants send authority, even if all
    # booleans true. The live worker has separate attested gates.
    return MoneyOutReadiness(
        contract=CONTRACT,pending=pending,
        eligible_for_manual_review=ready,
        sandbox_dryrun_allowed=ready,
    )
