"""M22000 OCI production auth configuration gate, no network or database IO."""
from dataclasses import dataclass, field
from urllib.parse import urlsplit, unquote
from typing import Mapping
import ipaddress
import re

from .config import safe_public_https_origin


class ProductionAuthBlocked(Exception):
    pass


@dataclass(frozen=True, repr=False)
class ProductionAuthConfig:
    auth_dsn: str = field(repr=False)
    verifier_dsn: str = field(repr=False)

    def __repr__(self):
        return "ProductionAuthConfig(redacted=True,operationally_unverified=True)"


# M40958: compare decoded credentials, not distinct URI strings. A syntactic
# success is not a live identity, DNS, certificate or ACL attestation.
_DNS_LABEL = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\Z")
_DB = re.compile(r"[a-zA-Z0-9_]{1,58}_prod\Z")
# M40959: use a strict URI subset shared by Python, asyncpg and libpq.
# Reserved password characters must be percent-encoded; no query aliases.
_URI = re.compile(
    r"postgresql://[a-z_]+:(?:[A-Za-z0-9._~-]|%[0-9a-fA-F]{2})+"
    r"@[a-zA-Z0-9.-]+:5432/[a-zA-Z0-9_]+[?]sslmode=verify-full\Z"
)


def _dsn(text: str, role: str) -> tuple[tuple[str, int, str], str]:
    try:
        if (type(text) is not str or len(text) > 4096
                or not _URI.fullmatch(text)):
            raise ValueError()
        p = urlsplit(text)
        host = p.hostname
        if (p.scheme != "postgresql" or p.username != role or not p.password
                or p.netloc.count("@") != 1 or "#" in text or host is None
                or p.port != 5432 or len(host) > 253 or "." not in host
                or any(not _DNS_LABEL.fullmatch(label) for label in host.split("."))
                or not any(c.isalpha() for c in host.rsplit(".", 1)[-1])
                or host.endswith((".invalid", ".example", ".test", ".localhost", ".local"))
                or not p.path.startswith("/") or not _DB.fullmatch(p.path[1:])
                or p.query != "sslmode=verify-full"):
            raise ValueError()
        try:
            ipaddress.ip_address(host)
        except ValueError:
            pass
        else:
            raise ValueError()
        password = unquote(p.password, encoding="utf-8", errors="strict")
        if (len(password) < 16 or not password.strip()
                or any(ord(c) < 32 or ord(c) == 127 for c in password)):
            raise ValueError()
        return (host.lower(), p.port, p.path), password
    except (ValueError, TypeError, AttributeError, OverflowError):
        raise ProductionAuthBlocked("UNSAFE_OR_INCOMPLETE_PRODUCTION_DSN") from None


def _valid_secret(value: object) -> bool:
    if (type(value) is not str or not value.strip()
            or any(ord(c) < 32 or ord(c) == 127 for c in value)):
        return False
    try:
        return len(value.encode("utf-8")) >= 32
    except UnicodeError:
        return False


def _strict_public_origin(value: object) -> bool:
    # urlsplit can silently strip ASCII controls and accept empty delimiters.
    # Require an exact, canonical ASCII public origin before accepting it.
    if type(value) is not str or not value.isascii():
        return False
    origin = safe_public_https_origin(value)
    if origin is None:
        return False
    if not all(_DNS_LABEL.fullmatch(label)
               for label in origin.removeprefix("https://").split(".")):
        return False
    return value in (origin, origin + "/", origin + ":443", origin + ":443/")


def require_production_auth(env: Mapping[str,str]) -> ProductionAuthConfig:
    if (not isinstance(env, Mapping) or env.get("ENVIRONMENT")!="production"
            or env.get("FR_FINANCE_AUTH_PRODUCTION_GATE")!="OCI_STAGING_REVIEWED"
            or env.get("FRCAIXINHA_TERMUX_LOCAL_API", "") not in ("", "0")
            or env.get("FRCAIXINHA_TEST_AUTH", "") not in ("", "0")
            or not _strict_public_origin(env.get("APP_URL", ""))):
        raise ProductionAuthBlocked("OCI_PRODUCTION_GATE_NOT_APPROVED")
    auth_secret=env.get("AUTH_SECRET","")
    hmac_secret=env.get("AUTH_RATE_LIMIT_HMAC_KEY","")
    if (not _valid_secret(auth_secret) or not _valid_secret(hmac_secret)
            or auth_secret==hmac_secret):
        raise ProductionAuthBlocked("PRODUCTION_KEYS_MISSING_OR_REUSED")
    auth=env.get("AUTH_DATABASE_URL","")
    verifier=env.get("AUTH_VERIFIER_DATABASE_URL","")
    app=env.get("DATABASE_URL","")
    a, a_password = _dsn(auth,"frc_ai_auth")
    b, b_password = _dsn(verifier,"frc_ai_verifier")
    c, c_password = _dsn(app,"frc_ai_app")
    if (a!=b or b!=c or len({a_password,b_password,c_password,auth_secret,hmac_secret})!=5):
        raise ProductionAuthBlocked("PRODUCTION_DB_ROLES_NOT_SEGREGATED")
    return ProductionAuthConfig(auth_dsn=auth,verifier_dsn=verifier)
