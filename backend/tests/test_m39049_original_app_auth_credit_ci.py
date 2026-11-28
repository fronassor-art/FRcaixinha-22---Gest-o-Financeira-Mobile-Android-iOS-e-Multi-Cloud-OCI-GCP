"""FR Finance M39049 — FastAPI PRINCIPAL e Android: autenticação offline.

Usa o único backend.app.main.app, roteadores reais e dependências simuladas.
NÃO configura banco de dados, não chama PostgreSQL, não cria sessões, não
usa socket externo, não ativa Pix ou campanhas, não faz migrações.
TestClient é utilizado SEM context manager para não executar startup workers.
"""
from __future__ import annotations

from pathlib import Path
from uuid import UUID

import asyncpg
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.dependencies import AuthenticatedSession
from backend.app.routers import special_credit

TENANT_A = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
TENANT_B = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
USER_A = UUID("11111111-1111-4111-8111-111111111111")
PREFIX = f"/api/v1/tenants/{TENANT_A}/special-credit"


@pytest.fixture(autouse=True)
def deny_all_original_database_calls(monkeypatch):
    monkeypatch.setenv("FR_FINANCE_SPECIAL_CREDIT_SANDBOX", "NO")
    monkeypatch.setenv("FR_FINANCE_PIX_REAL", "OFF")
    monkeypatch.setenv("FR_FINANCE_ACCESS_MAIL_ENABLE", "OFF")
    monkeypatch.setenv("FR_FINANCE_ACCESS_MAIL_WORKER", "OFF")

    async def reject(*_args, **_kwargs):
        raise AssertionError("M39049_DATABASE_ACCESS_FORBIDDEN")
    monkeypatch.setattr(asyncpg, "connect", reject)
    monkeypatch.setattr(asyncpg, "create_pool", reject)

    before = dict(app.dependency_overrides)
    yield
    app.dependency_overrides.clear()
    app.dependency_overrides.update(before)


def _session(role: str, tenant: UUID | None) -> AuthenticatedSession:
    return AuthenticatedSession(
        str(USER_A), role, str(tenant) if tenant else None,
        "synthetic@example.invalid", "Pessoa fictícia", role == "MASTER",
    )


def _fake_auth(role: str, tenant: UUID | None) -> None:
    app.dependency_overrides[special_credit.get_current_session] = lambda: _session(role, tenant)
    # If SQL is requested, this object has no fetch/execute methods: test fails.
    app.dependency_overrides[special_credit.get_rls_db_connection] = lambda: object()


def test_real_app_exposes_exact_routes_used_by_android():
    routes = {(route.path, method)
              for route in app.routes
              for method in getattr(route, "methods", [])}
    expected = {
        ("/api/v1/auth/status", "GET"),
        ("/api/v1/auth/login", "POST"),
        ("/api/v1/auth/logout", "POST"),
        ("/api/v1/auth/me", "GET"),
        ("/api/v1/auth/contexts", "GET"),
        (PREFIX + "/capabilities", "GET"),
        (PREFIX + "/grants", "GET"),
        (PREFIX + "/grants", "POST"),
        (PREFIX + "/campaigns", "GET"),
        (PREFIX + "/campaigns", "POST"),
        (PREFIX + "/opportunities", "GET"),
        (PREFIX + "/preferences", "GET"),
        (PREFIX + "/preferences", "POST"),
    }
    # Actual special_credit routes contain {tenant_id}, not a literal UUID.
    normalized = {(path.replace(str(TENANT_A), "{tenant_id}"), method)
                  for path, method in expected}
    assert normalized.issubset(routes)


def test_original_api_without_bearer_denies_sensitive_reads():
    client = TestClient(app)
    for path in (PREFIX + "/capabilities",
                 PREFIX + "/members",
                 "/api/v1/auth/me",
                 "/api/v1/auth/contexts"):
        response = client.get(path)
        assert response.status_code == 401, (path, response.status_code)
        assert response.headers.get("Cache-Control") == "no-store"
        assert response.headers.get("X-Frame-Options") == "DENY"


def test_original_fastapi_authenticated_fake_session_sandbox_off():
    _fake_auth("TENANT_ADMIN", TENANT_A)
    client = TestClient(app)
    result = client.get(PREFIX + "/capabilities")
    assert result.status_code == 200
    response = result.json()
    assert response["sandbox_enabled"] is False
    assert response["grants_allow_request_only"] is True
    assert response["real_credit_enabled"] is False
    assert response["pix_real_enabled"] is False
    assert set(response["channels"]) == {"PUSH", "EMAIL", "WHATSAPP", "SMS"}
    assert all(channel["real_delivery_enabled"] is False
               for channel in response["channels"].values())

    # Mesmo uma sessão simulada e válida não permite criar campanhas desativadas.
    grant = client.post(PREFIX + "/grants", json={
        "member_ids": ["aaaaeeee-aaaa-4aaa-8aaa-aaaaaaaaaaaa"],
        "ceiling_brl": "5000.00",
        "expires_at": "2027-05-01T12:00:00+00:00",
        "reason": "Análise exclusivamente sintética para homologação.",
        "request_id": "00000000-0000-4000-8000-000000000049",
    })
    assert grant.status_code == 503
    assert client.get(PREFIX + "/members").status_code == 503
    assert result.headers.get("Cache-Control") == "no-store"
    assert result.headers.get("Referrer-Policy") == "no-referrer"


def test_tenant_isolation_and_master_denied_by_original_app():
    client = TestClient(app)
    _fake_auth("TENANT_ADMIN", TENANT_A)
    assert client.get(
        f"/api/v1/tenants/{TENANT_B}/special-credit/capabilities"
    ).status_code == 403
    _fake_auth("MASTER", None)
    assert client.get(PREFIX + "/capabilities").status_code == 403
    _fake_auth("TENANT_MEMBER", TENANT_A)
    assert client.get(PREFIX + "/members").status_code == 403


def test_cookie_cross_origin_blocked_before_auth_or_database():
    # Requisição de escrita com cookie já presente e Origin não autorizado.
    client = TestClient(app)
    _fake_auth("TENANT_ADMIN", TENANT_A)
    response = client.post(
        PREFIX + "/grants",
        json={},
        headers={"Origin": "https://unauthorized.invalid"},
        cookies={"frcaixinha_session": "ci-fake-cookie"},
    )
    assert response.status_code == 403
    assert response.headers["Cache-Control"] == "no-store"


def test_auth_status_contract_matches_real_route_without_database():
    response = TestClient(app).get("/api/v1/auth/status")
    assert response.status_code == 200
    data = response.json()
    assert data["requires_authentication"] is True
    assert isinstance(data["configured"], bool)
    assert isinstance(data["status"], str)
    assert isinstance(data["server_time"], str)
    assert "token" not in data
    assert "password" not in data


def test_android_paths_and_original_app_routing():
    api = Path("src/services/specialCreditApi.ts").read_text()
    boundary = Path("src/services/specialCreditRequestBoundary.ts").read_text()
    auth = Path("src/services/authService.ts").read_text()
    assert "scopedCreditPath(tenantId)" in boundary
    assert "/api/v1/tenants/" in boundary
    for suffix in ("/capabilities", "/members", "/grants", "/campaigns",
                   "/opportunities", "/preferences"):
        assert suffix in api
    for path in ("/api/v1/auth/status", "/api/v1/auth/login",
                 "/api/v1/auth/me", "/api/v1/auth/contexts"):
        assert path in auth
    assert "invalidateSessionIfCurrent" in api
    assert "assertSandboxCreditCapabilities" in api
