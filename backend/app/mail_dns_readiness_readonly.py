"""FR Finance M38250–M38289: inspect public sender DNS, never authorize mail.

The inputs are UNTRUSTED DNS responses; the report is deliberately redacted.
This pure policy does not query DNS, send SMTP, read credentials, publish
records, attest ownership or approve a production provider.
"""
from __future__ import annotations

from dataclasses import dataclass
from ipaddress import ip_address
import re


class MailDnsObservationBlocked(ValueError):
    """Stable, non-sensitive errors without raw DNS record values."""


@dataclass(frozen=True)
class DkimDnsObservation:
    selector: str
    record_kind: str  # CNAME | TXT | MISSING
    record_value: str | None


@dataclass(frozen=True)
class PublicMailDnsSnapshot:
    sender_domain: str
    spf_txt: tuple[str, ...]
    dmarc_txt: tuple[str, ...]
    dkim: tuple[DkimDnsObservation, ...]


@dataclass(frozen=True)
class PublicMailDnsReport:
    mode: str
    sender_domain: str
    spf_record_present: bool
    spf_policy_limited: bool
    dmarc_record_present: bool
    dmarc_policy: str
    dkim_selectors_observed: int
    dkim_records_present: int
    blockers: tuple[str, ...]
    authenticated_sender_domain_control: bool = False
    provider_dkim_verified: bool = False
    provider_smtp_authenticated: bool = False
    actual_message_delivery_verified: bool = False
    real_email_send_authorized: bool = False
    user_activation_authorized: bool = False
    production_authorized: bool = False
    cloud_mutations_performed: bool = False
    database_mutations_performed: bool = False


_SELECTOR = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\Z")
_HOST = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+\Z")


def _domain(value: object) -> bool:
    if (type(value) is not str or not 4 <= len(value) <= 253
            or _HOST.fullmatch(value) is None
            or value.endswith((".local", ".test", ".invalid",
                               ".internal", ".example", ".localhost"))):
        return False
    try:
        ip_address(value)
    except ValueError:
        return True
    return False


def _txts(value: object) -> bool:
    return (type(value) is tuple and len(value) <= 40
            and all(type(item) is str and 0 < len(item) <= 4096
                    and all(32 <= ord(c) <= 126 for c in item)
                    for item in value))


def _dmarc_policy(record: str) -> tuple[str, bool]:
    fragments = [piece.strip() for piece in record.split(";") if piece.strip()]
    if not fragments or fragments[0].lower() != "v=dmarc1":
        return "INVALID", False
    tags: dict[str, str] = {}
    for fragment in fragments:
        if "=" not in fragment:
            return "INVALID", False
        name, value = fragment.split("=", 1)
        name, value = name.strip().lower(), value.strip()
        if not name or name in tags:
            return "INVALID", False
        tags[name] = value
    policy = tags.get("p", "").lower()
    if policy not in ("none", "quarantine", "reject"):
        return "INVALID", False
    pct = tags.get("pct", "100")
    if not pct.isascii() or not pct.isdigit() or not 0 <= int(pct) <= 100:
        return "INVALID", False
    if policy == "none" or int(pct) < 100:
        return "MONITOR_OR_PARTIAL", False
    return policy.upper(), True


def assess_public_mail_dns(snapshot: PublicMailDnsSnapshot) -> PublicMailDnsReport:
    """A DNS record is a candidate observation, never provider verification."""
    if (
        type(snapshot) is not PublicMailDnsSnapshot
        or not _domain(snapshot.sender_domain)
        or not _txts(snapshot.spf_txt) or not _txts(snapshot.dmarc_txt)
        or type(snapshot.dkim) is not tuple or len(snapshot.dkim) > 2
        or any(type(item) is not DkimDnsObservation for item in snapshot.dkim)
        or len({item.selector for item in snapshot.dkim}) != len(snapshot.dkim)
    ):
        raise MailDnsObservationBlocked("M38250_MAIL_DNS_SNAPSHOT_INVALID")

    spf = [r for r in snapshot.spf_txt
           if re.match(r"(?i)^v=spf1(?:\s|$)", r)]
    dmarc = [r for r in snapshot.dmarc_txt
             if re.match(r"(?i)^v=dmarc1(?:\s*;|$)", r)]
    blockers: list[str] = []
    spf_present = len(spf) == 1
    spf_limited = False
    if len(spf) > 1:
        blockers.append("MAIL_MULTIPLE_SPF_RECORDS")
    elif not spf_present:
        blockers.append("MAIL_SPF_RECORD_NOT_OBSERVED")
    else:
        tokens=spf[0].split()
        spf_limited = (len(tokens) >= 2 and tokens[0].lower() == "v=spf1"
                       and tokens[-1] in ("-all", "~all")
                       and "+all" not in tokens and "?all" not in tokens)
        if not spf_limited:
            blockers.append("MAIL_SPF_POLICY_NEEDS_REVIEW")

    dmarc_present = len(dmarc) == 1
    policy = "NOT_ATTESTED"
    if len(dmarc) > 1:
        blockers.append("MAIL_MULTIPLE_DMARC_RECORDS")
    elif not dmarc_present:
        blockers.append("MAIL_DMARC_RECORD_NOT_OBSERVED")
    else:
        policy, enforcing = _dmarc_policy(dmarc[0])
        if not enforcing:
            blockers.append("MAIL_DMARC_POLICY_NOT_ENFORCING_OR_INVALID")

    valid_dkim = 0
    for record in snapshot.dkim:
        if (type(record.selector) is not str
                or _SELECTOR.fullmatch(record.selector) is None
                or record.record_kind not in ("TXT", "CNAME", "MISSING")
                or type(record.record_kind) is not str):
            raise MailDnsObservationBlocked("M38250_DKIM_SELECTOR_OR_TYPE_INVALID")
        if record.record_kind == "MISSING":
            if record.record_value is not None:
                raise MailDnsObservationBlocked("M38250_DKIM_RECORD_INVALID")
            blockers.append("MAIL_DKIM_SELECTOR_MISSING")
        elif (type(record.record_value) is not str
              or not 0 < len(record.record_value) <= 4096
              or not all(32 <= ord(c) <= 126 for c in record.record_value)):
            raise MailDnsObservationBlocked("M38250_DKIM_RECORD_INVALID")
        elif record.record_kind == "CNAME":
            if not _domain(record.record_value):
                raise MailDnsObservationBlocked("M38250_DKIM_RECORD_INVALID")
            valid_dkim += 1
        elif record.record_value.lower().startswith("v=dkim1;") and re.search(
            r"(?:^|;)\s*p=[a-zA-Z0-9+/=]+\s*(?:;|$)", record.record_value
        ):
            valid_dkim += 1
        else:
            blockers.append("MAIL_DKIM_PUBLIC_KEY_RECORD_INVALID")
    if len(snapshot.dkim) < 2 or valid_dkim < 2:
        blockers.append("MAIL_TWO_DKIM_SELECTORS_NOT_ATTESTED")

    # Real e-mail provider trust requires more than records existing:
    # sender-domain validation in Brevo, provider STARTTLS/auth, real receipt
    # and independent ownership/consent checks remain missing.
    blockers.extend((
        "MAIL_BREVO_SENDER_NOT_INDEPENDENTLY_VERIFIED",
        "MAIL_SMTP_STARTTLS_AUTH_NOT_TESTED",
        "MAIL_PROVIDER_DELIVERY_BOUNCE_NOT_ATTESTED",
        "MAIL_EMAIL_OWNERSHIP_AND_CONSENT_NOT_ATTESTED",
    ))
    return PublicMailDnsReport(
        mode="PUBLIC_MAIL_DNS_READ_ONLY_OBSERVATION",
        sender_domain=snapshot.sender_domain,
        spf_record_present=spf_present, spf_policy_limited=spf_limited,
        dmarc_record_present=dmarc_present,dmarc_policy=policy,
        dkim_selectors_observed=len(snapshot.dkim),
        dkim_records_present=valid_dkim,
        blockers=tuple(dict.fromkeys(blockers)),
    )
