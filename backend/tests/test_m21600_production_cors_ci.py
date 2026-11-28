"""M21600: production API CORS hardening before OCI (no network/secret)."""
import pytest

from app.config import cors_origins_for, safe_public_https_origin


@pytest.mark.parametrize("url", [
    "", "MY_APP_URL", "http://frfinance.com.br",
    "http://localhost:3000", "https://localhost",
    "https://127.0.0.1", "https://10.77.10.20",
    "https://[::1]", "https://host.local",
    "https://host.internal", "https://example.invalid",
    "https://api.frfinance.com.br:8443",
    "https://user:password@api.frfinance.com.br",
    "https://api.frfinance.com.br/auth",
    "https://api.frfinance.com.br/?token=x",
    "https://api.frfinance.com.br/#secret",
    "https://api.frfinance.com.br:bad",
    " https://api.frfinance.com.br",
])
def test_production_rejects_insecure_origins(url):
    assert safe_public_https_origin(url) is None


def test_real_https_domain_only_and_normalized():
    assert safe_public_https_origin("https://API.FRFINANCE.COM.BR/") == (
        "https://api.frfinance.com.br")
    assert safe_public_https_origin("https://app.frfinance.com.br") == (
        "https://app.frfinance.com.br")


def test_production_cors_never_admits_android_loopback():
    env = {"ENVIRONMENT": "production", "APP_URL": "https://app.frfinance.com.br",
           "FRCAIXINHA_TERMUX_LOCAL_API": "1"}
    assert cors_origins_for(env) == ["https://app.frfinance.com.br"]


@pytest.mark.parametrize("env", [
    {"ENVIRONMENT": "production"},
    {"ENVIRONMENT": "production", "APP_URL": "http://localhost:3000"},
    {"ENVIRONMENT": "production", "APP_URL": "https://api.frfinance.com.br/path"},
    {"ENVIRONMENT": "production", "APP_URL": "https://example.invalid"},
])
def test_production_invalid_origin_is_empty_instead_of_localhost(env):
    assert cors_origins_for(env) == []


def test_termux_and_web_dev_preserved_without_granting_prod_privileges():
    assert cors_origins_for({"ENVIRONMENT": "development"}) == [
        "http://localhost:3000", "http://localhost:8080"]
    assert cors_origins_for({"FRCAIXINHA_TERMUX_LOCAL_API": "1"}) == [
        "http://localhost:3000", "http://localhost:8080", "http://localhost"]
    assert cors_origins_for({"ENVIRONMENT": "homologation",
                             "APP_URL": "https://stage.frfinance.com.br"}) == [
        "http://localhost:3000", "http://localhost:8080",
        "https://stage.frfinance.com.br"]
