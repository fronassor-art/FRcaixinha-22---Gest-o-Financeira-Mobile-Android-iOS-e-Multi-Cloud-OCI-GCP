"""M22000 production auth OCI guard; synthetic credentials only."""
import pytest
from fastapi import HTTPException
from app.production_auth_gate import require_production_auth, ProductionAuthBlocked
from app.dependencies import auth_database_url, auth_verifier_database_url


def safe_env():
    host="db.frfinance.internal:5432/frfinance_prod?sslmode=verify-full"
    return dict(
        ENVIRONMENT="production",FR_FINANCE_AUTH_PRODUCTION_GATE="OCI_STAGING_REVIEWED",
        APP_URL="https://app.frfinance.com.br",AUTH_SECRET="s"*48,
        AUTH_RATE_LIMIT_HMAC_KEY="h"*48,
        AUTH_DATABASE_URL="postgresql://frc_ai_auth:"+("a"*24)+"@"+host,
        AUTH_VERIFIER_DATABASE_URL="postgresql://frc_ai_verifier:"+("v"*24)+"@"+host,
        DATABASE_URL="postgresql://frc_ai_app:"+("p"*24)+"@"+host)


def test_prod_is_blocked_by_default(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT","production")
    monkeypatch.delenv("FR_FINANCE_AUTH_PRODUCTION_GATE",raising=False)
    with pytest.raises(HTTPException) as e:
        auth_database_url()
    assert e.value.status_code==503


def test_synthetic_production_configuration_is_not_e2e_proof(monkeypatch):
    env=safe_env()
    for k,v in env.items():
        monkeypatch.setenv(k,v)
    cfg=require_production_auth(env)
    assert "redacted" in repr(cfg)
    assert "operationally_unverified" in repr(cfg)
    assert auth_database_url()==env["AUTH_DATABASE_URL"]
    assert auth_verifier_database_url()==env["AUTH_VERIFIER_DATABASE_URL"]
    from app.routers.auth import get_auth_status
    result=get_auth_status()
    assert result.status=="PRODUCTION_CONFIGURED_UNVERIFIED"
    assert result.requires_authentication


@pytest.mark.parametrize("bad",[
    {"ENVIRONMENT":"development"},
    {"FR_FINANCE_AUTH_PRODUCTION_GATE":"YES"},
    {"FRCAIXINHA_TERMUX_LOCAL_API":"1"},
    {"FRCAIXINHA_TEST_AUTH":"1"},
    {"APP_URL":"http://localhost:3000"},
    {"AUTH_SECRET":"short"},
    {"AUTH_RATE_LIMIT_HMAC_KEY":"short"},
    {"AUTH_RATE_LIMIT_HMAC_KEY":"s"*48},
    {"AUTH_DATABASE_URL":"postgresql://postgres:12345678901234567890@db.frfinance.internal:5432/frfinance_prod?sslmode=verify-full"},
    {"AUTH_DATABASE_URL":"postgresql://frc_ai_auth:12345678901234567890@127.0.0.1:5432/frfinance_prod?sslmode=verify-full"},
    {"AUTH_DATABASE_URL":"postgresql://frc_ai_auth:12345678901234567890@db.frfinance.internal:5433/frfinance_prod?sslmode=verify-full"},
    {"AUTH_DATABASE_URL":"postgresql://frc_ai_auth:12345678901234567890@db.frfinance.internal:5432/frfinance_dev?sslmode=verify-full"},
    {"AUTH_DATABASE_URL":"postgresql://frc_ai_auth:12345678901234567890@db.frfinance.internal:5432/frfinance_prod?sslmode=require"},
    {"AUTH_VERIFIER_DATABASE_URL":"postgresql://frc_ai_auth:12345678901234567890@db.frfinance.internal:5432/frfinance_prod?sslmode=verify-full"},
    {"DATABASE_URL":"postgresql://frc_ai_owner:12345678901234567890@db.frfinance.internal:5432/frfinance_prod?sslmode=verify-full"},
])
def test_unsafe_configuration_denied(bad):
    data=safe_env()
    data.update(bad)
    with pytest.raises(ProductionAuthBlocked):
        require_production_auth(data)


def test_cross_database_auth_denied():
    data=safe_env()
    data["AUTH_VERIFIER_DATABASE_URL"]=data["AUTH_VERIFIER_DATABASE_URL"].replace(
        "db.frfinance.internal","other.frfinance.internal")
    with pytest.raises(ProductionAuthBlocked):
        require_production_auth(data)


# M40958 — production-auth configuration remains only a syntax check.
@pytest.mark.parametrize("host", [
    "db.frfinance.internal,other.frfinance.internal",
    "db.frfinance.internal.",
    "db%2efrfinance.internal",
    "db._frfinance.internal",
    "-db.frfinance.internal",
    "db.localhost",
    "127.000.000.001",
])
def test_m40958_rejects_ambiguous_or_local_dns(host):
    env = safe_env()
    for name in ("AUTH_DATABASE_URL", "AUTH_VERIFIER_DATABASE_URL", "DATABASE_URL"):
        env[name] = env[name].replace("db.frfinance.internal", host)
    with pytest.raises(ProductionAuthBlocked):
        require_production_auth(env)


@pytest.mark.parametrize("password", ["%61"*6, "%00"+"a"*24, "%FF"+"a"*24,
                                       "%ZZ"+"a"*24, "%20"*24, "a"*24+"@extra"])
def test_m40958_invalid_decoded_password_is_denied(password):
    env = safe_env()
    env["AUTH_DATABASE_URL"] = env["AUTH_DATABASE_URL"].replace("a"*24, password)
    with pytest.raises(ProductionAuthBlocked) as err:
        require_production_auth(env)
    assert password not in str(err.value)


@pytest.mark.parametrize("field,password", [
    ("AUTH_VERIFIER_DATABASE_URL", "a"*24),
    ("AUTH_VERIFIER_DATABASE_URL", "%61"*24),
    ("DATABASE_URL", "v"*24),
    ("DATABASE_URL", "%73"*48),
    ("AUTH_DATABASE_URL", "h"*48),
])
def test_m40958_reused_secrets_across_roles_or_signers_denied(field, password):
    env = safe_env()
    prior = {"AUTH_VERIFIER_DATABASE_URL": "v"*24,
             "DATABASE_URL": "p"*24, "AUTH_DATABASE_URL": "a"*24}[field]
    env[field] = env[field].replace(prior, password)
    with pytest.raises(ProductionAuthBlocked) as err:
        require_production_auth(env)
    assert password not in str(err.value)


@pytest.mark.parametrize("value", [None, 3, " "*48, "\x00"+"s"*48, "\ud800"*48])
def test_m40958_invalid_signing_key_fails_closed(value):
    env = safe_env()
    env["AUTH_SECRET"] = value
    with pytest.raises(ProductionAuthBlocked):
        require_production_auth(env)


def test_m40958_valid_encoded_distinct_password_is_syntax_only():
    env = safe_env()
    env["AUTH_DATABASE_URL"] = env["AUTH_DATABASE_URL"].replace("a"*24, "%61"*24)
    config = require_production_auth(env)
    assert config.auth_dsn == env["AUTH_DATABASE_URL"]
    assert "%61" not in repr(config)
    assert "operationally_unverified" in repr(config)


# M40959 — strict shared URI subset and canonical public origin.
@pytest.mark.parametrize("old,new", [
    ("sslmode=verify-full", "sslmode=%76erify-full"),
    ("sslmode=verify-full", "%73slmode=verify-full"),
    ("sslmode=verify-full", "sslmode=verify-full&"),
    ("sslmode=verify-full", "sslmode=verify-full;"),
    (":5432/", ":05432/"),
    ("a"*24, "a"*24 + ":reserved"),
    ("a"*24, "a"*24 + "+reserved"),
    ("a"*24, "a"*24 + "\\reserved"),
    ("a"*24, "a"*24 + "é"),
    ("a"*24, "a"*24 + "\ud800"),
])
def test_m40959_noncanonical_dsn_rejected(old, new):
    env = safe_env()
    env["AUTH_DATABASE_URL"] = env["AUTH_DATABASE_URL"].replace(old, new)
    with pytest.raises(ProductionAuthBlocked) as err:
        require_production_auth(env)
    assert str(err.value) == "UNSAFE_OR_INCOMPLETE_PRODUCTION_DSN"


@pytest.mark.parametrize("suffix", ["%3A", "%2B", "%5C", "%C3%A9", "%40"])
def test_m40959_encoded_password_accepted_as_syntax_only(suffix):
    env = safe_env()
    env["AUTH_DATABASE_URL"] = env["AUTH_DATABASE_URL"].replace("a"*24, "a"*24 + suffix)
    assert require_production_auth(env).auth_dsn == env["AUTH_DATABASE_URL"]


@pytest.mark.parametrize("origin", [
    "https://app.frfinance.com.br?",
    "https://app.frfinance.com.br#",
    "https://app.frfinance.com.br:",
    "https://app.frfinance.com.br:0443",
    "https://app.frfinance.com.br/\t",
    "https://app.\tfrfinance.com.br",
    "https://app.frfinancé.com.br",
    "https://app." + "a"*64 + ".com.br",
    "https://app.frfinance.com.br/?",
])
def test_m40959_ambiguous_origin_denied(origin):
    env = safe_env()
    env["APP_URL"] = origin
    with pytest.raises(ProductionAuthBlocked, match="OCI_PRODUCTION_GATE_NOT_APPROVED"):
        require_production_auth(env)


@pytest.mark.parametrize("suffix", ["", "/", ":443", ":443/"])
def test_m40959_canonical_origin_syntax_only(suffix):
    env = safe_env()
    env["APP_URL"] += suffix
    assert require_production_auth(env).auth_dsn == env["AUTH_DATABASE_URL"]


@pytest.mark.parametrize("flag", ["FRCAIXINHA_TEST_AUTH", "FRCAIXINHA_TERMUX_LOCAL_API"])
@pytest.mark.parametrize("value", ["true", "yes", " 1", "False", None])
def test_m40959_noncanonical_test_flags_fail_closed(flag, value):
    env = safe_env()
    env[flag] = value
    with pytest.raises(ProductionAuthBlocked, match="OCI_PRODUCTION_GATE_NOT_APPROVED"):
        require_production_auth(env)


@pytest.mark.parametrize("flag", ["FRCAIXINHA_TEST_AUTH", "FRCAIXINHA_TERMUX_LOCAL_API"])
@pytest.mark.parametrize("value", ["", "0"])
def test_m40959_explicit_disabled_test_flags(flag, value):
    env = safe_env()
    env[flag] = value
    assert require_production_auth(env).auth_dsn == env["AUTH_DATABASE_URL"]


# M40960 — the shared CORS origin gate also rejects browser IPv4 aliases
# and parser normalization ambiguity. All inputs are synthetic.
@pytest.mark.parametrize("origin", [
    "https://127.0.0.01",
    "https://127.1",
    "https://0x7f.0.0.1",
    "https://127.0.0.0x1",
    "https://0177.0.0.1",
    "https://example.123",
    "https://app.frfinance.com.br:",
    "https://app.frfinance.com.br:0443",
    "https://app.frfinance.com.br?",
    "https://app.frfinance.com.br/#",
    "https://app.\tfrfinance.com.br",
    "https://app.frfinance.com.br/\n",
    "https://app.frfinance.com.br/\\",
    "https://app.frfinancé.com.br",
    "https://app." + "a"*64 + ".com.br",
])
def test_m40960_shared_origin_and_production_auth_fail_closed(origin):
    from app.config import safe_public_https_origin, cors_origins_for
    assert safe_public_https_origin(origin) is None
    env = safe_env()
    env["APP_URL"] = origin
    assert cors_origins_for(env) == []
    with pytest.raises(ProductionAuthBlocked, match="OCI_PRODUCTION_GATE_NOT_APPROVED"):
        require_production_auth(env)


@pytest.mark.parametrize("origin,expected", [
    ("https://app.frfinance.com.br", "https://app.frfinance.com.br"),
    ("https://app.frfinance.com.br/", "https://app.frfinance.com.br"),
    ("https://app.frfinance.com.br:443/", "https://app.frfinance.com.br"),
    ("https://APP.FRFINANCE.COM.BR", "https://app.frfinance.com.br"),
    ("https://app.xn--p1ai", "https://app.xn--p1ai"),
])
def test_m40960_shared_origin_normalization(origin, expected):
    from app.config import safe_public_https_origin, cors_origins_for
    assert safe_public_https_origin(origin) == expected
    assert cors_origins_for({"ENVIRONMENT": "production", "APP_URL": origin}) == [expected]
