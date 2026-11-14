"""FR Finance M38450-M38489: public DNS transport diagnosis (NO TXT values).

Only accepts exactly frfinance.com.br root TXT and _dmarc TXT. The caller
must supply a resolver; this pure module does not import dns, initiate IO,
read secrets or grant sender authentication. Input resolver observations may
be attacker-controlled, so no returned status authorizes any real action.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

_HOSTS = (
    ("ROOT_TXT", "frfinance.com.br"),
    ("DMARC_TXT", "_dmarc.frfinance.com.br"),
)
_KNOWN_ERRORS = {
    "NoResolverConfiguration": "SYSTEM_RESOLVER_NOT_CONFIGURED",
    "NoNameservers": "DNS_SERVERS_UNAVAILABLE_OR_REFUSED",
    "Timeout": "DNS_QUERY_TIMEOUT",
    "LifetimeTimeout": "DNS_QUERY_TIMEOUT",
    "NXDOMAIN": "DNS_NAME_NOT_FOUND",
    "NoAnswer": "DNS_NO_TXT_ANSWER",
    "NoRootSOA": "DNS_SERVER_PROTOCOL_ERROR",
    "YXDOMAIN": "DNS_NAME_TOO_LONG",
    "DNSException": "DNS_PROTOCOL_ERROR",
    "gaierror": "SYSTEM_NETWORK_RESOLUTION_ERROR",
    "OSError": "SYSTEM_NETWORK_ERROR",
}


@dataclass(frozen=True)
class DnsTransportObservation:
    mode: str
    resolver_status: str
    root_txt_status: str
    dmarc_txt_status: str
    queries_requested: int
    third_party_resolver_selected: bool
    record_values_printed: bool = False
    domain_authenticated_by_provider: bool = False
    email_delivery_verified: bool = False
    actual_dkim_verified: bool = False
    production_authorized: bool = False
    real_user_activation_authorized: bool = False
    real_pix_authorized: bool = False
    database_mutations_performed: bool = False
    cloud_mutations_performed: bool = False


def _safe_error_kind(error: Exception) -> str:
    """Only fixed codes; exception message/args/traceback never surfaced."""
    return _KNOWN_ERRORS.get(type(error).__name__, "DNS_ERROR_UNCLASSIFIED")


def diagnose_dns_transport(
    mode: str,
    resolver_factory: Callable[[str], object],
) -> DnsTransportObservation:
    if mode not in ("SYSTEM", "CLOUDFLARE", "GOOGLE"):
        raise ValueError("M38450_INVALID_RESOLVER_MODE")
    result: dict[str,str] = {}
    try:
        resolver = resolver_factory(mode)
        if not callable(getattr(resolver, "resolve", None)):
            raise TypeError("resolver object invalid")
    except Exception as exc:
        return DnsTransportObservation(
            mode=mode,resolver_status=_safe_error_kind(exc),
            root_txt_status="NOT_QUERIED",dmarc_txt_status="NOT_QUERIED",
            queries_requested=0,third_party_resolver_selected=mode!="SYSTEM",
        )
    attempted = 0
    for label, domain in _HOSTS:
        attempted += 1
        try:
            answer=resolver.resolve(domain, "TXT", raise_on_no_answer=False)
            rrset=getattr(answer,"rrset",None)
            result[label]="TXT_ANSWER_OBSERVED" if rrset is not None else "DNS_NO_TXT_ANSWER"
        except Exception as exc:
            result[label]=_safe_error_kind(exc)
    return DnsTransportObservation(
        mode=mode,resolver_status="CONFIGURED_FOR_QUERY",
        root_txt_status=result["ROOT_TXT"],
        dmarc_txt_status=result["DMARC_TXT"],
        queries_requested=attempted,
        third_party_resolver_selected=mode!="SYSTEM",
    )


def is_transport_complete(report: DnsTransportObservation) -> bool:
    """Only network query completed; missing TXT is not transport failure."""
    if type(report) is not DnsTransportObservation:
        return False
    complete = {"TXT_ANSWER_OBSERVED", "DNS_NO_TXT_ANSWER", "DNS_NAME_NOT_FOUND"}
    return (
        report.resolver_status=="CONFIGURED_FOR_QUERY"
        and report.queries_requested==2
        and report.root_txt_status in complete
        and report.dmarc_txt_status in complete
    )
