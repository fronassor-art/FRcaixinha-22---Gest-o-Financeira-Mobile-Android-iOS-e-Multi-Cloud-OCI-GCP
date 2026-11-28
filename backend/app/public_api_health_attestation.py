"""M38170–M38209: opt-in PUBLIC HTTPS GET /api/health; no credentials.

No OCI/SMTP/MP/database mutation. This verifies a limited health response
at an explicitly configured public origin. Does NOT attest runtime SHA, VM
ownership, DB RLS, actual email, authentication, payment or production.
"""
from __future__ import annotations

from dataclasses import dataclass
from http.client import HTTPResponse
import json
import socket
import ssl
from typing import Callable
from urllib.parse import urlsplit

from .config import safe_public_https_origin
from .public_https_attestation import _resolve_public

MAX_RESPONSE_BYTES = 8192
PUBLIC_HEALTH_PATH = "/api/health"


class PublicApiHealthBlocked(ValueError):
    """A sanitized, non-secret denial with no backend response attached."""


def _deny() -> PublicApiHealthBlocked:
    return PublicApiHealthBlocked("M38170_PUBLIC_API_HEALTH_UNVERIFIED")


@dataclass(frozen=True)
class PublicApiHealthObservation:
    scope: str = "PUBLIC_HTTPS_HEALTH_READ_ONLY"
    public_dns_and_tls_observed: bool = True
    http_get_observed: bool = True
    health_contract_observed: bool = True
    cache_protection_observed: bool = True
    environment_claim: str = "sandbox-development"
    database_configured_claim: bool = False
    actual_database_verified: bool = False
    deployment_sha_verified: bool = False
    production_auth_verified: bool = False
    cloud_vm_identity_verified: bool = False
    provider_attested: bool = False
    production_authorized: bool = False
    real_user_activation_authorized: bool = False
    real_pix_authorized: bool = False
    writes_performed: bool = False


def _public_get(hostname: str, ip: str) -> tuple[int, tuple[tuple[str, str], ...], bytes]:
    """Pin the peer to the prevalidated DNS IP while checking the hostname.

    Never trust proxies, follow redirects, send cookies, authentication or
    POST. TLS verifies public CA and the expected hostname through SNI.
    """
    context = ssl.create_default_context(purpose=ssl.Purpose.SERVER_AUTH)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    with socket.create_connection((ip, 443), timeout=4) as tcp:
        with context.wrap_socket(tcp, server_hostname=hostname) as secured:
            secured.settimeout(4)
            request = (
                "GET /api/health HTTP/1.1\r\n"
                "Host: " + hostname + "\r\n"
                "Accept: application/json\r\n"
                "Accept-Encoding: identity\r\n"
                "Cache-Control: no-store\r\n"
                "Connection: close\r\n\r\n"
            ).encode("ascii")
            secured.sendall(request)
            response = HTTPResponse(secured)
            response.begin()
            headers = tuple(response.getheaders())
            if len(headers) > 48:
                raise _deny()
            if response.length is not None and response.length > MAX_RESPONSE_BYTES:
                raise _deny()
            body = response.read(MAX_RESPONSE_BYTES + 1)
            return response.status, headers, body


def _single_header(headers: tuple[tuple[str, str], ...], name: str) -> str:
    values = [value for key, value in headers if key.lower() == name]
    if len(values) != 1 or type(values[0]) is not str or len(values[0]) > 256:
        raise _deny()
    return values[0].strip().lower()


def _strict_json(text: bytes) -> dict:
    def _unique(pairs: list[tuple[str, object]]) -> dict:
        result = {}
        for key, value in pairs:
            if key in result:
                raise _deny()
            result[key] = value
        return result
    try:
        payload = json.loads(text.decode("utf-8"), object_pairs_hook=_unique)
        if type(payload) is not dict:
            raise _deny()
        return payload
    except (ValueError, UnicodeError, TypeError):
        raise _deny() from None


def _evaluate(response: object) -> PublicApiHealthObservation:
    if (type(response) is not tuple or len(response) != 3
            or type(response[0]) is not int or response[0] != 200
            or type(response[1]) is not tuple or len(response[1]) > 48
            or any(type(x) is not tuple or len(x) != 2
                   or type(x[0]) is not str or type(x[1]) is not str
                   for x in response[1])
            or type(response[2]) is not bytes
            or not 0 < len(response[2]) <= MAX_RESPONSE_BYTES):
        raise _deny()
    _, headers, body = response
    content_type = _single_header(headers, "content-type")
    if content_type not in ("application/json", "application/json; charset=utf-8"):
        raise _deny()
    if _single_header(headers, "cache-control") != "no-store":
        raise _deny()
    if _single_header(headers, "pragma") != "no-cache":
        raise _deny()
    if _single_header(headers, "x-content-type-options") != "nosniff":
        raise _deny()
    if any(key.lower() == "content-encoding" and value.strip().lower() != "identity"
           for key, value in headers):
        raise _deny()
    data = _strict_json(body)
    # Current M37980 contract explicitly states a development-only mode.
    if (data.get("status") != "ONLINE" or data.get("app") != "FR Finance"
            or data.get("framework") != "FastAPI (Python)"
            or data.get("environment") != "sandbox-development"
            or type(data.get("database_configured")) is not bool
            or data.get("database_backend")
               != "PostgreSQL com Row-Level Security (RLS)"):
        raise _deny()
    return PublicApiHealthObservation(
        database_configured_claim=data["database_configured"],
    )


def probe_public_api_health(
    origin: str, *,
    resolver: Callable = socket.getaddrinfo,
    exchange: Callable = _public_get,
) -> PublicApiHealthObservation:
    """Public DNS pinned to IP; require all resolved IPs to pass.

    No HTTP redirection, arbitrary URL or GET path can be supplied by a
    client. CI injects a synthetic resolver and response exchange.
    """
    if type(origin) is not str or safe_public_https_origin(origin) != origin:
        raise _deny()
    try:
        hostname = urlsplit(origin).hostname
        if not hostname:
            raise _deny()
        ips = _resolve_public(hostname, resolver)
        # Avoid performing an unbounded number of network connections.
        if len(ips) > 4:
            raise _deny()
        observations = [_evaluate(exchange(hostname, ip)) for ip in ips]
        if not observations:
            raise _deny()
        # A mixed set of DNS backends is not acceptable, even if all are
        # reachable: require consistent (non-authoritative) DB config claims.
        if len({item.database_configured_claim for item in observations}) != 1:
            raise _deny()
        return observations[0]
    except Exception:
        raise _deny() from None
