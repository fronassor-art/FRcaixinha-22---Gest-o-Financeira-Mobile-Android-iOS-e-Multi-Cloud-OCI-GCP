"""Verificacao de acesso proprietario sem banco real ou migrations."""
from fastapi.testclient import TestClient
from app.main import app
from app.dependencies import AuthenticatedSession, get_current_session


def _session(role, is_master, tenant_id=None):
    return AuthenticatedSession(
        "00000000-0000-4000-8000-000000000001",
        role, tenant_id, "ci@example.invalid", "Pessoa CI", is_master,
    )


def _request_as(session):
    app.dependency_overrides[get_current_session] = lambda: session
    try:
        with TestClient(app) as client:
            return client.get("/api/v1/master/owner-access")
    finally:
        app.dependency_overrides.pop(get_current_session, None)


def test_owner_access_confirmed_for_master_only():
    result = _request_as(_session("MASTER", True))
    assert result.status_code == 200
    assert result.json() == {
        "verified": True, "role": "MASTER",
        "scope": "PLATFORM_GOVERNANCE_ONLY",
    }
    assert result.headers["cache-control"] == "no-store"


def test_owner_access_rejected_for_other_roles_and_tenant_bound_master():
    for role, is_master, tenant_id in [
        ("TENANT_ADMIN", False, "00000000-0000-4000-8000-000000000002"),
        ("TENANT_MEMBER", False, "00000000-0000-4000-8000-000000000002"),
        ("MASTER", False, None),
        ("MASTER", True, "00000000-0000-4000-8000-000000000002"),
    ]:
        result = _request_as(_session(role, is_master, tenant_id))
        assert result.status_code == 403, (role, is_master, tenant_id)


def test_owner_access_requires_authentication():
    with TestClient(app) as client:
        result = client.get("/api/v1/master/owner-access")
    assert result.status_code == 401
