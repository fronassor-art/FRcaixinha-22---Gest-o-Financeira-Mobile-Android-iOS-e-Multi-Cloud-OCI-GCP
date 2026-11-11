"""M38290-M38329: Brevo-specific *public DNS* readiness, never authorization.

Brevo domain authentication requires its verification-code TXT, DKIM (one
TXT or two CNAME) and DMARC (p=none is allowed initially). SPF is NOT required
for shared Brevo sender-domain authentication. See Brevo official help:
https://help.brevo.com/hc/en-us/articles/12163873383186

Inputs are untrusted resolver observations. Even every public record being
visible does not prove ownership, provider control, signature alignment,
SMTP credentials, message delivery, user identity, or production readiness.
"""
from __future__ import annotations

from dataclasses import dataclass
import re

from .mail_dns_readiness_readonly import (
    PublicMailDnsSnapshot, MailDnsObservationBlocked,
    assess_public_mail_dns, _domain, _dmarc_policy,
)

_TARGET = "frfinance.com.br"
_CODE = re.compile(r"(?i)^brevo-code:[a-z0-9_-]{8,128}$")
_DKIM_KEY = re.compile(
    r"(?:^|;)\s*p=([A-Za-z0-9+/]{24,4096}={0,2})\s*(?:;|$)"
)
_RUA = re.compile(
    r"(?:^|;)\s*rua=mailto:[a-z0-9_.+-]+@[a-z0-9.-]+\s*(?:;|$)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class BrevoPublicDnsReport:
    mode: str
    sender_domain: str
    brevo_code_record_observed: bool
    spf_optional: bool
    spf_status: str
    dmarc_status: str
    dmarc_rua_observed: bool
    dkim_mode: str
    public_dns_candidates_complete: bool
    blockers: tuple[str, ...]
    brevo_account_authenticated: bool = False
    brevo_code_matched_to_account: bool = False
    dkim_signature_verified: bool = False
    dmarc_alignment_verified: bool = False
    smtp_tls_login_verified: bool = False
    real_email_delivery_verified: bool = False
    domain_ownership_authenticated: bool = False
    real_email_authorized: bool = False
    real_user_activation_authorized: bool = False
    real_pix_authorized: bool = False
    production_authorized: bool = False
    network_queries_performed_by_policy: bool = False
    cloud_mutations_performed: bool = False
    database_mutations_performed: bool = False


def assess_brevo_public_dns(snapshot: PublicMailDnsSnapshot) -> BrevoPublicDnsReport:
    """Inspect the public DNS *shape*; no network or secrets allowed."""
    base = assess_public_mail_dns(snapshot)
    if snapshot.sender_domain != _TARGET:
        raise MailDnsObservationBlocked("M38290_UNEXPECTED_SENDER_DOMAIN")

    blockers: list[str] = []
    root_txt = snapshot.spf_txt
    codes = [item for item in root_txt if item.lower().startswith("brevo-code:")]
    code_observed = len(codes) == 1 and _CODE.fullmatch(codes[0]) is not None
    if len(codes) > 1:
        blockers.append("BREVO_CODE_DUPLICATE")
    elif not code_observed:
        blockers.append("BREVO_CODE_NOT_OBSERVED_OR_INVALID")
    # Code shape is visible; matching it to the account is NOT possible here.

    spf = [item for item in root_txt
           if re.match(r"(?i)^v=spf1(?:\s|$)", item)]
    if not spf:
        spf_status = "ABSENT_OPTIONAL_ON_SHARED_BREVO"
    elif len(spf) > 1:
        spf_status = "DUPLICATE_INVALID"
        blockers.append("BREVO_EXISTING_SPF_DUPLICATED")
    elif base.spf_policy_limited:
        spf_status = "SINGLE_LIMITED_RECORD_OBSERVED"
    else:
        spf_status = "PRESENT_REQUIRES_SEPARATE_REVIEW"
        blockers.append("BREVO_EXISTING_SPF_POLICY_REVIEW")

    dmarc = [item for item in snapshot.dmarc_txt
             if re.match(r"(?i)^v=dmarc1(?:\s*;|$)", item)]
    dmarc_rua = False
    if len(dmarc) == 0:
        dmarc_status = "MISSING"
        blockers.append("BREVO_DMARC_NOT_OBSERVED")
    elif len(dmarc) > 1:
        dmarc_status = "DUPLICATE"
        blockers.append("BREVO_DMARC_DUPLICATE")
    else:
        policy, enforcing = _dmarc_policy(dmarc[0])
        if policy == "INVALID":
            dmarc_status = "INVALID"
            blockers.append("BREVO_DMARC_INVALID")
        else:
            dmarc_status = (
                "ENFORCING" if enforcing else "MONITOR_OR_PARTIAL_ACCEPTED"
            )
            dmarc_rua = _RUA.search(dmarc[0]) is not None
            if not dmarc_rua:
                blockers.append("BREVO_DMARC_RUA_NOT_OBSERVED")

    selectors = snapshot.dkim
    if not selectors:
        dkim_mode = "NOT_QUERIED"
        blockers.append("BREVO_DKIM_SELECTORS_NOT_QUERIED")
    elif (
        len(selectors) == 1 and selectors[0].record_kind == "TXT"
        and type(selectors[0].record_value) is str
        and selectors[0].record_value.lower().startswith("v=dkim1;")
        and _DKIM_KEY.search(selectors[0].record_value)
    ):
        dkim_mode = "ONE_TXT_PUBLISHED_CANDIDATE"
    elif (
        len(selectors) == 2
        and all(item.record_kind == "CNAME"
                and _domain(item.record_value)
                for item in selectors)
    ):
        dkim_mode = "TWO_CNAME_PUBLISHED_CANDIDATES"
    else:
        dkim_mode = "INCOMPLETE_OR_MIXED"
        blockers.append("BREVO_DKIM_CONFIGURATION_INCOMPLETE")

    # The report never asserts that these records were signed by Brevo,
    # belong to an authenticated sender, or authorize dispatch.
    return BrevoPublicDnsReport(
        mode="PUBLIC_BREVO_DNS_OBSERVATION_ONLY",
        sender_domain=_TARGET,
        brevo_code_record_observed=code_observed,
        spf_optional=True,
        spf_status=spf_status,
        dmarc_status=dmarc_status,
        dmarc_rua_observed=dmarc_rua,
        dkim_mode=dkim_mode,
        public_dns_candidates_complete=not blockers,
        blockers=tuple(blockers) + (
            "BREVO_ACCOUNT_DOMAIN_NOT_AUTHENTICATED_BY_DNS_SNAPSHOT",
            "BREVO_SMTP_TLS_AND_SEND_RECEIPT_NOT_ATTESTED",
            "BREVO_DKIM_SIGNATURE_AND_DMARC_ALIGNMENT_NOT_ATTESTED",
            "REAL_RECIPIENT_OWNERSHIP_AND_CONSENT_NOT_ATTESTED",
        ),
    )
