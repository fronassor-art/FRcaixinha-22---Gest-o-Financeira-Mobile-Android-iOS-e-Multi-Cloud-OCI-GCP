"""M38530-M38569 Brevo account sender-domain status assessment (pure).

This assesses a *claimed* response to the official GET
/v3/senders/domains/frfinance.com.br. Only the opt-in TLS HTTPS client can
connect it to an account. DNS publication alone is not enough. A Brevo
account saying authenticated is still NOT a production email release gate.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

DOMAIN = "frfinance.com.br"
_RECORD_KEYS = ("brevo_code", "dkim_record", "dmarc_record")


class BrevoDomainStatusBlocked(ValueError):
    """Fixed error codes; never include server JSON, secrets or creator info."""


@dataclass(frozen=True)
class BrevoDomainAccountReport:
    mode: str
    account_domain_present: bool
    account_domain_verified: bool
    account_domain_authenticated: bool
    brevo_code_status: str
    dkim_status: str
    dmarc_status: str
    blockers: tuple[str, ...]
    real_smtp_authenticated: bool = False
    delivery_receipt_verified: bool = False
    dkim_signature_and_alignment_verified: bool = False
    real_email_send_authorized: bool = False
    real_user_activation_authorized: bool = False
    real_pix_authorized: bool = False
    production_authorized: bool = False
    database_mutations_performed: bool = False
    provider_mutations_performed: bool = False


def _record_status(records: Mapping[str, Any], key: str) -> str:
    if key not in records:
        return "NOT_RETURNED"
    item = records[key]
    if type(item) is not dict:
        raise BrevoDomainStatusBlocked("M38530_DNS_RECORD_STATUS_INVALID")
    value = item.get("status")
    if value is True:
        return "REPORTED_VALID"
    if value is False:
        return "REPORTED_INVALID"
    return "NOT_RETURNED"


def assess_brevo_account_response(payload: object) -> BrevoDomainAccountReport:
    if type(payload) is not dict or len(payload) > 60:
        raise BrevoDomainStatusBlocked("M38530_PROVIDER_RESPONSE_INVALID")
    observed_domain = payload.get("domain", payload.get("domain_name"))
    if (
        observed_domain != DOMAIN
        or type(observed_domain) is not str
        or "domain" in payload and "domain_name" in payload
           and payload["domain"] != payload["domain_name"]
        or type(payload.get("verified")) is not bool
        or type(payload.get("authenticated")) is not bool
    ):
        raise BrevoDomainStatusBlocked("M38530_PROVIDER_DOMAIN_UNVERIFIED")
    records=payload.get("dns_records",{})
    if type(records) is not dict or len(records)>20:
        raise BrevoDomainStatusBlocked("M38530_DNS_RECORD_STATUS_INVALID")
    statuses=[_record_status(records,k) for k in _RECORD_KEYS]
    blockers=[]
    if not payload["verified"]:
        blockers.append("BREVO_ACCOUNT_DOMAIN_NOT_VERIFIED")
    if not payload["authenticated"]:
        blockers.append("BREVO_ACCOUNT_DOMAIN_NOT_AUTHENTICATED")
    for label,status in zip(("BREVO_CODE","DKIM","DMARC"),statuses):
        if status=="REPORTED_INVALID":
            blockers.append("BREVO_ACCOUNT_"+label+"_REPORTED_INVALID")
        if status=="NOT_RETURNED":
            blockers.append("BREVO_ACCOUNT_"+label+"_STATUS_NOT_RETURNED")
    blockers.extend((
        "BREVO_SMTP_STARTTLS_AUTH_NOT_ATTESTED",
        "BREVO_CONTROLLED_DELIVERY_NOT_ATTESTED",
        "BREVO_SIGNATURE_ALIGNMENT_NOT_ATTESTED",
        "REAL_RECIPIENT_OWNERSHIP_AND_CONSENT_NOT_ATTESTED",
    ))
    return BrevoDomainAccountReport(
        mode="BREVO_AUTHENTICATED_GET_ACCOUNT_CLAIM",
        account_domain_present=True,
        account_domain_verified=payload["verified"],
        account_domain_authenticated=payload["authenticated"],
        brevo_code_status=statuses[0],
        dkim_status=statuses[1],
        dmarc_status=statuses[2],
        blockers=tuple(blockers),
    )
