"""Headers de segurança sem credenciais, migração ou conexão de banco."""
from fastapi.testclient import TestClient
from app.main import app


def test_auth_responses_are_never_cacheable():
    with TestClient(app) as client:
        status=client.get("/api/v1/auth/status")
        assert status.status_code == 200
        assert status.headers["cache-control"]=="no-store"
        assert status.headers["pragma"]=="no-cache"
        assert status.headers["referrer-policy"]=="no-referrer"
        assert status.headers["x-frame-options"]=="DENY"

        forgot=client.post("/api/v1/auth/forgot-password",
                           json={"email":"ci@example.com"})
        assert forgot.status_code==503
        assert forgot.headers["cache-control"]=="no-store"
        assert forgot.headers["referrer-policy"]=="no-referrer"
        assert "não implementada" in forgot.json()["detail"]


def test_auth_and_invitation_routes_refuse_unauthenticated_requests():
    with TestClient(app) as client:
        for path in ("/api/v1/auth/contexts",
                     "/api/v1/auth/sessions",
                     "/api/v1/auth/me",
                     "/api/v1/master/integration-readiness",
                     "/api/v1/invitations"):
            r=client.get(path) if path!="/api/v1/invitations" else client.post(
                path, json={"target_email":"ci@example.com",
                            "target_role":"TENANT_MEMBER"})
            assert r.status_code in (401,405,503), (path,r.status_code)
            assert r.headers["cache-control"]=="no-store"
            assert r.headers["referrer-policy"]=="no-referrer"


def test_readiness_does_not_invent_activated_invitation_or_payment():
    with TestClient(app) as client:
        r=client.get("/api/health")
        assert r.status_code==200
        assert r.headers["referrer-policy"]=="no-referrer"
        # Health confirma apenas que o processo FastAPI responde; NÃO
        # afirma haver auth ou pagamentos reais ativos.
        assert "database_configured" in r.json()



def test_privileged_auth_dsn_is_refused_before_any_connection(monkeypatch):
    import pytest
    from fastapi import HTTPException
    from app.dependencies import auth_database_url, auth_verifier_database_url

    monkeypatch.setenv("FRCAIXINHA_TEST_AUTH", "1")
    monkeypatch.setenv("ENVIRONMENT", "homologation")
    monkeypatch.setenv(
        "AUTH_DATABASE_URL",
        "postgresql://frc_ai_owner:ci@127.0.0.1:5432/frcaixinha_ci",
    )
    with pytest.raises(HTTPException) as denied_owner:
        auth_database_url()
    assert denied_owner.value.status_code == 503

    monkeypatch.setenv(
        "AUTH_DATABASE_URL",
        "postgresql://frcaixinha_auth_ci:ci@127.0.0.1:5432/frcaixinha_ci",
    )
    monkeypatch.setenv(
        "AUTH_VERIFIER_DATABASE_URL",
        "postgresql://postgres:ci@127.0.0.1:5432/frcaixinha_ci",
    )
    with pytest.raises(HTTPException) as denied_verifier:
        auth_verifier_database_url()
    assert denied_verifier.value.status_code == 503

    monkeypatch.setenv(
        "AUTH_VERIFIER_DATABASE_URL",
        "postgresql://frcaixinha_auth_ci:ci@127.0.0.1:5432/frcaixinha_ci",
    )
    with pytest.raises(HTTPException) as same_user:
        auth_verifier_database_url()
    assert same_user.value.status_code == 503
