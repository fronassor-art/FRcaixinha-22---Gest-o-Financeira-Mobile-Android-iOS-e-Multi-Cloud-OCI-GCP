"""M28200 — opt-in, read-only DNS and HTTPS certificate preflight.

No HTTP requests, SMTP, credentials, redirects, database, Oracle or Mercado
Pago API calls. Domain input is read only from the approved public manifest.
DNS answers are screened BEFORE a connection to a pinned public IP, avoiding
private-address SSRF and DNS rebinding between verification and TLS connect.
Passing DNS/TLS is *not* ownership, account activation or real provider proof.
"""
from __future__ import annotations

from dataclasses import dataclass
import ipaddress
import socket
import ssl
from typing import Callable
from urllib.parse import urlsplit

from .config import safe_public_https_origin


class PublicTlsProbeBlocked(ValueError):
    pass


@dataclass(frozen=True)
class PublicTlsProbeResult:
    scope: str = "PUBLIC_DNS_AND_TLS_ONLY"
    dns_public: bool = True
    hostname_certificate_valid: bool = True
    http_requested: bool = False
    secret_used: bool = False
    smtp_submission: bool = False
    email_ownership_verified: bool = False
    mp_connected: bool = False
    production_ready: bool = False
    user_activation_enabled: bool = False
    pix_enabled: bool = False


def _deny() -> PublicTlsProbeBlocked:
    return PublicTlsProbeBlocked("M28200_DNS_OR_TLS_BLOCKED")


def _resolve_public(hostname: str, resolver: Callable) -> list[str]:
    try:
        addresses = resolver(hostname, 443, type=socket.SOCK_STREAM)
    except Exception:
        raise _deny() from None
    if type(addresses) not in (list,tuple) or not addresses or len(addresses)>32:
        raise _deny()
    public = set()
    for entry in addresses:
        try:
            family,_,_,_,sockaddr=entry
            if family not in (socket.AF_INET,socket.AF_INET6):
                raise _deny()
            raw = sockaddr[0]
            ip = ipaddress.ip_address(raw)
            if not ip.is_global or ip.is_multicast or ip.is_unspecified:
                raise _deny()
            public.add(str(ip))
        except (IndexError,TypeError,ValueError,AttributeError):
            raise _deny() from None
    if not public or len(public)>16:
        raise _deny()
    return sorted(public)


def _tls_verify(hostname: str, ip: str) -> bool:
    """Connect to verified IP and validate TLS certificate for hostname."""
    context=ssl.create_default_context(purpose=ssl.Purpose.SERVER_AUTH)
    context.minimum_version=ssl.TLSVersion.TLSv1_2
    # Only a TLS ClientHello is sent: never an HTTP request.
    with socket.create_connection((ip,443), timeout=4) as tcp:
        with context.wrap_socket(tcp,server_hostname=hostname) as secured:
            if secured.getpeercert() is None:
                raise _deny()
            return True


def probe_public_https_origin(
    origin: str, *, resolver: Callable = socket.getaddrinfo,
    tls_verify: Callable = _tls_verify,
) -> PublicTlsProbeResult:
    if (type(origin) is not str or
            safe_public_https_origin(origin) != origin):
        raise _deny()
    try:
        host=urlsplit(origin).hostname
        if not host:
            raise _deny()
        public_ips=_resolve_public(host,resolver)
        ok=False
        for ip in public_ips:
            if tls_verify(host,ip) is True:
                ok=True
                break
        if not ok:
            raise _deny()
        return PublicTlsProbeResult()
    except Exception:
        raise _deny() from None
