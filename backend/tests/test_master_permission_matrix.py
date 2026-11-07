"""Matriz Master declarativa e endpoint protegido: nenhuma concessão real."""
import inspect
from fastapi import HTTPException
from fastapi.testclient import TestClient
from app.dependencies import require_master, AuthenticatedSession
from app.main import app
from app.onboarding_permission_matrix import (
    ROLES, RESOURCES, MATRIX, ACCESS, permission_matrix_contract,
)


def owner():
    return AuthenticatedSession(
        "00000000-0000-4000-8000-000000000001", "MASTER",
        None, "ci@example.invalid", "CI", True,
    )


def test_matrix_enumerates_every_role_resource_without_escalation():
    d = permission_matrix_contract()
    assert d["source"] == "DECLARED_POLICY_NOT_RUNTIME_AUTHORITY"
    assert d["operations_enabled"] is False
    assert d["grants_changed"] is False
    assert d["database_migration_required"] is False
    assert set(d["roles"]) == set(ROLES)
    assert set(d["resources"]) == set(RESOURCES)
    assert len(d["permissions"]) == len(RESOURCES)
    for resource in RESOURCES:
        assert set(d["permissions"][resource]) == set(ROLES)
        assert set(d["permissions"][resource].values()) <= set(ACCESS)
    assert d["permissions"]["TENANT_FINANCIAL_DATA"]["MASTER"] == "DENIED"
    assert d["permissions"]["MEMBER_PRIVATE_DATA"]["MASTER"] == "DENIED"
    for resource in (
        "INVITATION_TOKEN_STORAGE", "INVITATION_ISSUANCE",
        "MEMBERSHIP_ROLE_CHANGE", "DIRECT_AUDIT_MUTATION",
    ):
        assert all(value == "DENIED" for value in d["permissions"][resource].values())
    for resource in ("PLATFORM_TENANT_REGISTRY", "PLATFORM_ADMIN_REFERENCES"):
        assert d["permissions"][resource]["TENANT_ADMIN"] == "DENIED"
        assert d["permissions"][resource]["TENANT_MEMBER"] == "DENIED"
    assert all(d["permissions"][r]["ANONYMOUS"] == "DENIED" for r in RESOURCES)


def test_matrix_is_declarative_not_an_authentication_function():
    import app.onboarding_permission_matrix as policy
    source = inspect.getsource(policy)
    assert "conn.execute" not in source
    assert "grant " not in source.lower().split('"""')[-1]
    assert "await " not in source
    before = permission_matrix_contract()
    before["permissions"]["INVITATION_ISSUANCE"]["MASTER"] = "METADATA_ONLY"
    assert permission_matrix_contract()["permissions"]["INVITATION_ISSUANCE"]["MASTER"] == "DENIED"


def test_endpoint_accessible_only_to_server_verified_master():
    app.dependency_overrides[require_master] = owner
    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/master/admin-onboarding/permission-matrix")
        assert response.status_code == 200
        assert response.json()["operations_enabled"] is False
        assert response.headers["cache-control"] == "no-store"
    finally:
        app.dependency_overrides.clear()
    def denied():
        raise HTTPException(status_code=403, detail="Somente Master")
    app.dependency_overrides[require_master] = denied
    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/master/admin-onboarding/permission-matrix")
        assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()
    with TestClient(app) as client:
        assert client.get("/api/v1/master/admin-onboarding/permission-matrix").status_code == 401
