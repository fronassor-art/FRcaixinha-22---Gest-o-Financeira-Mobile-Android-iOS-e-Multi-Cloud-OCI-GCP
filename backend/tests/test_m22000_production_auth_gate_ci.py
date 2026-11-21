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
