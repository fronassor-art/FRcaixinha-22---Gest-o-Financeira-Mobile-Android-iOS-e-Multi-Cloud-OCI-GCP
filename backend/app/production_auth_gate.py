"""M22000 OCI production auth configuration gate, no network or database IO."""
from dataclasses import dataclass, field
from urllib.parse import urlsplit, parse_qsl
from typing import Mapping
import ipaddress

from .config import safe_public_https_origin


class ProductionAuthBlocked(Exception):
    pass


@dataclass(frozen=True, repr=False)
class ProductionAuthConfig:
    auth_dsn: str = field(repr=False)
    verifier_dsn: str = field(repr=False)

    def __repr__(self):
        return "ProductionAuthConfig(redacted=True,operationally_unverified=True)"


def _dsn(text: str, role: str) -> tuple[str, int, str]:
    try:
        if not isinstance(text, str) or len(text) > 4096 or any(c.isspace() for c in text):
            raise ValueError()
        p=urlsplit(text)
        q=parse_qsl(p.query, keep_blank_values=True, strict_parsing=True)
        host=p.hostname
        if (p.scheme!="postgresql" or p.username!=role or not p.password
                or len(p.password)<16 or p.fragment or host is None
                or p.port!=5432 or host=="localhost" or "." not in host
                or host.endswith((".invalid",".example",".test"))
                or not p.path.startswith("/") or "/" in p.path[1:]
                or not p.path[1:].endswith("_prod")
                or not p.path[1:-5].replace("_","").isalnum()
                or q!=[("sslmode","verify-full")]):
            raise ValueError()
        try:
            ipaddress.ip_address(host)
        except ValueError:
            pass
        else:
            raise ValueError()
        return (host.lower(),p.port,p.path)
    except (ValueError,TypeError,AttributeError):
        raise ProductionAuthBlocked("UNSAFE_OR_INCOMPLETE_PRODUCTION_DSN") from None


def require_production_auth(env: Mapping[str,str]) -> ProductionAuthConfig:
    if (env.get("ENVIRONMENT")!="production"
            or env.get("FR_FINANCE_AUTH_PRODUCTION_GATE")!="OCI_STAGING_REVIEWED"
            or env.get("FRCAIXINHA_TERMUX_LOCAL_API")=="1"
            or env.get("FRCAIXINHA_TEST_AUTH")=="1"
            or safe_public_https_origin(env.get("APP_URL","")) is None):
        raise ProductionAuthBlocked("OCI_PRODUCTION_GATE_NOT_APPROVED")
    auth_secret=env.get("AUTH_SECRET","")
    hmac_secret=env.get("AUTH_RATE_LIMIT_HMAC_KEY","")
    if (len(auth_secret.encode("utf-8"))<32
            or len(hmac_secret.encode("utf-8"))<32
            or auth_secret==hmac_secret):
        raise ProductionAuthBlocked("PRODUCTION_KEYS_MISSING_OR_REUSED")
    auth=env.get("AUTH_DATABASE_URL","")
    verifier=env.get("AUTH_VERIFIER_DATABASE_URL","")
    app=env.get("DATABASE_URL","")
    a=_dsn(auth,"frc_ai_auth")
    b=_dsn(verifier,"frc_ai_verifier")
    c=_dsn(app,"frc_ai_app")
    if a!=b or b!=c or len({auth,verifier,app})!=3:
        raise ProductionAuthBlocked("PRODUCTION_DB_ROLES_NOT_SEGREGATED")
    return ProductionAuthConfig(auth_dsn=auth,verifier_dsn=verifier)
