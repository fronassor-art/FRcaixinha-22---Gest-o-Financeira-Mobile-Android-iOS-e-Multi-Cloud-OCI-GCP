"""M40800: financial database DSN identity gate (pure, no DB/network).

Shape checks are NOT authentication of a PostgreSQL server, a role/ACL audit,
or a repair of custom GUC spoofing; do not use as production release evidence.
"""
from __future__ import annotations

from ipaddress import ip_address
from typing import Mapping
from urllib.parse import urlsplit, parse_qsl

class FinancialDSNBlocked(ValueError):
    """No secret/DSN values in errors."""

def _parse(value: object) -> tuple[str, str, str, int, str, list[tuple[str, str]]]:
    if (type(value) is not str or not 16 <= len(value) <= 4096
            or any(c.isspace() or ord(c) < 32 for c in value)):
        raise FinancialDSNBlocked("M40800_UNSAFE_FINANCIAL_DSN")
    try:
        parsed = urlsplit(value)
        opts = parse_qsl(parsed.query, keep_blank_values=True, strict_parsing=True)
        if (parsed.scheme not in ("postgresql", "postgres")
                or not parsed.username or not parsed.password
                or parsed.hostname is None or parsed.port is None
                # M40951: asyncpg decodes URI identity components and accepts
                # multi-host addresses; do not validate a different target
                # than the driver. Encoded passwords remain supported.
                or any("%" in part for part in (
                    parsed.username, parsed.hostname, parsed.path))
                or any(c in parsed.hostname for c in (",", "\\"))
                or parsed.hostname.endswith(".")
                or parsed.fragment or parsed.path.count("/") != 1
                or not parsed.path[1:]
                or len(opts) != len({key for key, _ in opts})
                or any(key not in {"sslmode", "connect_timeout"} for key, _ in opts)):
            raise ValueError("DSN")
        return (parsed.scheme, parsed.username, parsed.hostname.lower(),
                parsed.port, parsed.path[1:], opts)
    except (ValueError, TypeError, AttributeError, OverflowError):
        raise FinancialDSNBlocked("M40800_UNSAFE_FINANCIAL_DSN") from None

def _is_loopback(host: str) -> bool:
    if host == "localhost":
        return True
    try:
        addr = ip_address(host)
    except ValueError:
        return False
    mapped = getattr(addr, "ipv4_mapped", None)
    return addr.is_loopback or (mapped is not None and mapped.is_loopback)


def require_financial_dsn_shape(dsn: object, env: Mapping[str, str]) -> str:
    """Fail closed for a known Termux or production runtime before pooling.

    No requirement is assumed for unrelated CI/dev pools. Non-production
    without FRCAIXINHA_TERMUX_LOCAL_API=1 stays UNATTESTED, never 'PASS'.
    """
    if env is None or not hasattr(env, "get"):
        raise FinancialDSNBlocked("M40800_ENV_INVALID")
    scheme, user, host, port, db, params = _parse(dsn)
    environment = env.get("ENVIRONMENT", "development")
    if environment == "production":
        if (scheme != "postgresql" or user != "frc_ai_app"
                or _is_loopback(host)
                or "." not in host or port != 5432
                or not db.endswith("_prod")
                or params != [("sslmode", "verify-full")]
                or env.get("DATABASE_URL") != dsn):
            raise FinancialDSNBlocked("M40800_PRODUCTION_FINANCIAL_ROLE_DENIED")
        return "PRODUCTION_SHAPE_REQUIRES_EXTERNAL_REVIEW"
    # M40850: a forged "development" environment must never make an
    # apparent production target or privileged DB role acceptable.
    # This is a DSN syntax gate, NOT a network/server identity proof.
    if (
        user in {"postgres", "root", "frc_ai_owner", "frc_ai_auth", "frc_ai_verifier"}
        or db in {"postgres", "template0", "template1"}
        or db.endswith(("_prod", "_production"))
        or db.startswith(("frcaixinha_2_2", "frcaixinha22"))
        or (_is_loopback(host) and port == 5433
            and (user != "frc_ai_app"
                 or db != "frcaixinha_aistudio_dev"))
    ):
        raise FinancialDSNBlocked("M40850_UNTRUSTED_NONPROD_DB_TARGET")
    if env.get("FRCAIXINHA_TERMUX_LOCAL_API") != "1":
        return "NONPRODUCTION_UNATTESTED"
    if (user != "frc_ai_app" or host != "127.0.0.1"
            or port != 5433 or db != "frcaixinha_aistudio_dev"
            or any(k == "sslmode" and v not in ("disable", "prefer")
                   or k == "connect_timeout" and
                   (not v.isascii() or not v.isdecimal() or not 1 <= int(v) <= 30)
                   for k, v in params)):
        raise FinancialDSNBlocked("M40800_TERMUX_FINANCIAL_ROLE_DENIED")
    for name, expected in (
        ("AUTH_DATABASE_URL", "frc_ai_auth"),
        ("AUTH_VERIFIER_DATABASE_URL", "frc_ai_verifier"),
    ):
        other = env.get(name)
        if other:
            _, role, other_host, other_port, other_db, _ = _parse(other)
            if (role != expected or other_host != host or other_port != port
                    or other_db != db or other == dsn):
                raise FinancialDSNBlocked("M40800_TERMUX_ROLE_SEPARATION_DENIED")
    return "TERMUX_DSN_SHAPE_ONLY_NOT_DB_ATTESTED"
