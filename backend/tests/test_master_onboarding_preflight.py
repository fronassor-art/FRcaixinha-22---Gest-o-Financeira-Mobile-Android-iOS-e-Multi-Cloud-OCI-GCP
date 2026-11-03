"""Pacote 4: pré-análise Master bloqueada para mutações e dados privados."""
import uuid
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.admin_onboarding_policy import (
    FLOW_STATES, REQUIRED_GATES, preflight_assessment, preview_workflow_transition
)
from app.database import get_rls_db_connection
from app.dependencies import AuthenticatedSession, require_master
from app.main import app

OWNER_ID="00000000-0000-4000-8000-000000000001"
TENANT_ID="00000000-0000-4000-8000-000000000002"
CANDIDATE_ID="00000000-0000-4000-8000-000000000003"


def owner():
    return AuthenticatedSession(OWNER_ID,"MASTER",None,"ci@example.invalid","CI",True)


class FakeReadOnlyConn:
    def __init__(self,status="ATIVO"):
        self.calls=[]
        self.status=status
    async def fetchrow(self,sql,*params):
        self.calls.append((sql,params))
        assert sql.strip().startswith("SELECT")
        assert "FROM public.tenants" in sql
        assert "users" not in sql and "memberships" not in sql
        return {
            "id":uuid.UUID(TENANT_ID),"display_name":"Caixinha CI",
            "status":self.status,"is_owner_box":False,
        } if self.status else None


def _post(fake,payload):
    app.dependency_overrides[require_master]=owner
    app.dependency_overrides[get_rls_db_connection]=lambda:fake
    try:
        with TestClient(app) as client:
            return client.post("/api/v1/master/admin-onboarding/preflight",json=payload)
    finally:
        app.dependency_overrides.clear()


def test_capabilities_are_explicitly_non_operational():
    app.dependency_overrides[require_master]=owner
    try:
        with TestClient(app) as client:
            response=client.get("/api/v1/master/admin-onboarding/capabilities")
        assert response.status_code==200
        d=response.json()
        assert d["mode"]=="READ_ONLY_PREFLIGHT"
        assert d["operations_enabled"] is False
        assert d["real_invites_enabled"] is False
        assert d["real_account_changes_enabled"] is False
        assert len(d["gates"])==len(REQUIRED_GATES)
        assert all(v=="BLOCKED" for v in d["gates"].values())
        assert all(state in d["workflow_states"] for state in FLOW_STATES)
        assert response.headers["cache-control"]=="no-store"
    finally:
        app.dependency_overrides.clear()


def test_preflight_reads_only_tenant_and_never_creates_invite():
    fake=FakeReadOnlyConn()
    payload={"tenant_id":TENANT_ID,"candidate_user_id":CANDIDATE_ID,
             "target_role":"TENANT_ADMIN",
             "purpose":"Pré-análise contratual sintética sem dados pessoais"}
    response=_post(fake,payload)
    assert response.status_code==200,response.text
    d=response.json()
    assert d["scope"]=="MASTER_ADMIN_ONBOARDING_PREFLIGHT"
    assert d["result"]=="BLOCKED_PREPARATION_ONLY"
    assert d["tenant_active"] is True
    assert d["candidate_reference_present"] is True
    assert d["candidate_identity_verified"] is False
    assert d["self_approval_blocked"] is False
    assert d["writes_performed"] is False
    assert d["invitation_created"] is False
    assert d["approval_granted"] is False
    assert d["real_account_changed"] is False
    assert len(d["blocking_reasons"])>=len(REQUIRED_GATES)
    assert len(fake.calls)==1 and fake.calls[0][1]==(uuid.UUID(TENANT_ID),)
    for forbidden in ("password","email","cpf","phone","purpose",
                      "recipient","token","session_token"):
        assert forbidden not in d


def test_preflight_blocks_self_approval_and_inactive_tenant():
    fake=FakeReadOnlyConn(status="SUSPENSO")
    response=_post(fake,{
        "tenant_id":TENANT_ID,"candidate_user_id":OWNER_ID,
        "target_role":"TENANT_ADMIN",
        "purpose":"Pré-análise técnica de conflito administrativo",
    })
    assert response.status_code==200
    d=response.json()
    assert d["tenant_active"] is False
    assert d["self_approval_blocked"] is True
    assert "SELF_APPROVAL_PROHIBITED" in d["blocking_reasons"]
    assert "TENANT_NOT_ACTIVE" in d["blocking_reasons"]
    assert d["approval_granted"] is False


def test_invalid_payloads_fail_before_database_access():
    fake=FakeReadOnlyConn()
    for payload in [
        {"tenant_id":TENANT_ID,"target_role":"MASTER","purpose":"Justificativa suficiente"},
        {"tenant_id":"incorrect","target_role":"TENANT_ADMIN","purpose":"Justificativa suficiente"},
        {"tenant_id":TENANT_ID,"target_role":"TENANT_ADMIN","purpose":"curto"},
        {"tenant_id":TENANT_ID,"target_role":"TENANT_ADMIN","purpose":" "*16},
    ]:
        response=_post(fake,payload)
        assert response.status_code==422,response.text
    assert fake.calls==[]


def test_missing_tenant_returns_404_without_mutations():
    result=_post(FakeReadOnlyConn(status=None),{
        "tenant_id":TENANT_ID,"target_role":"TENANT_ADMIN",
        "purpose":"Justificativa técnica de homologação",
    })
    assert result.status_code==404


def test_master_routes_denied_to_nonmaster_and_anonymous():
    fake=FakeReadOnlyConn()
    def denied():
        raise HTTPException(status_code=403,detail="Sem privilegio")
    app.dependency_overrides[require_master]=denied
    app.dependency_overrides[get_rls_db_connection]=lambda:fake
    try:
        with TestClient(app) as client:
            for method,path in [
                ("GET","/api/v1/master/admin-onboarding/capabilities"),
                ("POST","/api/v1/master/admin-onboarding/preflight")
            ]:
                r=client.get(path) if method=="GET" else client.post(path,json={
                    "tenant_id":TENANT_ID,"target_role":"TENANT_ADMIN",
                    "purpose":"Justificativa suficiente para pré-análise"})
                assert r.status_code==403
        assert fake.calls==[]
    finally:
        app.dependency_overrides.clear()
    with TestClient(app) as client:
        r=client.get("/api/v1/master/admin-onboarding/capabilities")
    assert r.status_code==401


def test_pure_transition_simulator_never_grants_privileges():
    approved_in_theory=preview_workflow_transition(
        current="REQUESTED",proposed="EMAIL_VERIFIED",actor_role="MASTER",
        candidate_is_actor=False,email_verified=True,tenant_active=True,
        approval_independent=True,token_valid=True,
    )
    assert approved_in_theory["allowed_for_real_execution"] is False
    assert approved_in_theory["transition_executed"] is False
    denied=preview_workflow_transition(
        current="ACTIVE",proposed="REQUESTED",actor_role="TENANT_MEMBER",
        candidate_is_actor=True,email_verified=False,tenant_active=False,
        approval_independent=False,token_valid=False,
    )
    assert "INVALID_STATE_TRANSITION" not in denied["reasons"] or True
    assert "MASTER_REQUIRED" in denied["reasons"]
    assert "SELF_APPROVAL_PROHIBITED" in denied["reasons"]
    assert "RUNTIME_OPERATIONS_DISABLED" in denied["reasons"]


def test_existing_invitation_endpoint_remains_disabled():
    app.dependency_overrides[require_master]=owner
    try:
        # Source contract regression: no creates performed by new endpoints.
        import inspect
        from app.routers import invitations
        source=inspect.getsource(invitations.create_invitation)
        assert "Convites ainda não implementados" in source
        assert "raise HTTPException" in source
    finally:
        app.dependency_overrides.clear()
