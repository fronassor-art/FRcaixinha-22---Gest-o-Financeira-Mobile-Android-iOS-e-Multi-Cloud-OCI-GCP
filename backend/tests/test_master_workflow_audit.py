"""Pacote 5: simulação de transições imutável e testes adversariais de API."""
import uuid
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.admin_onboarding_workflow import (
    STATES, EDGES, TRANSACTION_GUARDS, workflow_contract,
    preview_transition,
)
from app.dependencies import AuthenticatedSession, require_master
from app.main import app

KEY=uuid.UUID("00000000-0000-4000-8000-000000000001")
OTHER=uuid.UUID("00000000-0000-4000-8000-000000000002")


def master():
    return AuthenticatedSession(str(OTHER),"MASTER",None,
                                "ci@example.invalid","CI",True)


def preview_data(**kw):
    payload={
        "current_state":"REQUESTED","proposed_state":"EMAIL_VERIFIED",
        "simulated_actor_role":"MASTER","candidate_is_actor":False,
        "email_verified":True,"tenant_active":True,
        "independent_approval":True,"token_valid":True,
        "expected_revision":1,"observed_revision":1,
        "idempotency_key":str(KEY),"previously_used_keys":[],
    }
    payload.update(kw)
    return payload


def _request(payload):
    app.dependency_overrides[require_master]=master
    try:
        with TestClient(app) as client:
            return client.post("/api/v1/master/admin-onboarding/transition-preview",
                               json=payload)
    finally:
        app.dependency_overrides.clear()


def test_contract_is_read_only_and_contains_all_states_and_guards():
    app.dependency_overrides[require_master]=master
    try:
        with TestClient(app) as client:
            response=client.get("/api/v1/master/admin-onboarding/workflow-contract")
        assert response.status_code==200,response.text
        d=response.json()
        assert d["mode"]=="SPECIFICATION_AND_SIMULATION_ONLY"
        assert d["operations_enabled"] is False
        assert d["audit_persisted"] is False
        assert d["states"]==list(STATES)
        assert d["edges"]=={k:list(v) for k,v in EDGES.items()}
        assert len(d["transaction_guards"])==len(TRANSACTION_GUARDS)
        assert d["max_previous_keys"]==32
        assert response.headers["cache-control"]=="no-store"
    finally:
        app.dependency_overrides.clear()


def test_even_hypothetically_perfect_transition_is_never_authorized():
    response=_request(preview_data())
    assert response.status_code==200,response.text
    d=response.json()
    assert d["graph_valid"] is True
    assert d["result"]=="EXECUTION_DENIED"
    assert d["state_unchanged"] is True
    assert d["projected_next_state"] is None
    assert d["writes_performed"] is False
    assert d["audit_persisted"] is False
    assert d["fingerprint_is_audit_proof"] is False
    assert d["invitation_created"] is False
    assert d["account_changed"] is False
    assert d["allowed_for_real_execution"] is False
    assert d["reasons"]==["RUNTIME_OPERATIONS_DISABLED"]
    assert len(d["scenario_fingerprint"])==64
    for field in ("email","password","token","cpf","phone","name","tenant_id"):
        assert field not in d


def test_replay_and_optimistic_concurrency_detected():
    response=_request(preview_data(
        expected_revision=4,observed_revision=6,
        previously_used_keys=[str(KEY)],
    ))
    assert response.status_code==200,response.text
    d=response.json()
    assert d["revision_conflict"] is True
    assert d["idempotency_replay_detected"] is True
    assert "REVISION_CONFLICT" in d["reasons"]
    assert "IDEMPOTENCY_REPLAY" in d["reasons"]
    assert d["writes_performed"] is False


def test_attack_paths_are_blocked():
    for payload,expected in [
        (preview_data(current_state="ACTIVE",proposed_state="REQUESTED"),
         "FINAL_STATE_IMMUTABLE"),
        (preview_data(current_state="APPROVED",proposed_state="ACTIVE"),
         "INVALID_STATE_TRANSITION"),
        (preview_data(simulated_actor_role="TENANT_MEMBER"),
         "MASTER_ROLE_REQUIRED"),
        (preview_data(candidate_is_actor=True),
         "SELF_APPROVAL_PROHIBITED"),
        (preview_data(email_verified=False),"EMAIL_NOT_VERIFIED"),
        (preview_data(tenant_active=False),"TENANT_INACTIVE"),
        (preview_data(independent_approval=False),"INDEPENDENT_APPROVAL_REQUIRED"),
        (preview_data(token_valid=False),"TOKEN_EXPIRED_OR_INVALID"),
        (preview_data(current_state="REVOKED",proposed_state="ACTIVE"),
         "FINAL_STATE_IMMUTABLE"),
    ]:
        res=_request(payload)
        assert res.status_code==200
        assert expected in res.json()["reasons"]
        assert res.json()["allowed_for_real_execution"] is False


def test_fingerprint_reproducible_for_identical_scenario_and_changes():
    baseline=_request(preview_data()).json()["scenario_fingerprint"]
    replay=_request(preview_data()).json()["scenario_fingerprint"]
    different=_request(preview_data(idempotency_key=str(OTHER))).json()["scenario_fingerprint"]
    assert baseline==replay
    assert baseline!=different


def test_invalid_payloads_return_422_and_do_not_create_users():
    for broken in [
        {"expected_revision":-1}, {"observed_revision":1000001},
        {"current_state":"MASTER"}, {"proposed_state":"INVALID"},
        {"simulated_actor_role":"SUPERADMIN"},
        {"idempotency_key":"not-a-uuid"},
        {"previously_used_keys":[str(KEY)]*33},
    ]:
        result=_request(preview_data(**broken))
        assert result.status_code==422,result.text


def test_master_auth_required_for_both_routes():
    def denied():
        raise HTTPException(status_code=403,detail="Sem privilégios")
    app.dependency_overrides[require_master]=denied
    try:
        with TestClient(app) as client:
            assert client.get("/api/v1/master/admin-onboarding/workflow-contract").status_code==403
            assert client.post("/api/v1/master/admin-onboarding/transition-preview",
                               json=preview_data()).status_code==403
    finally:
        app.dependency_overrides.clear()
    with TestClient(app) as client:
        assert client.get("/api/v1/master/admin-onboarding/workflow-contract").status_code==401


def test_pure_function_no_shared_memory_or_mutation():
    kwargs=dict(current="REQUESTED",proposed="EMAIL_VERIFIED",actor_role="MASTER",
                candidate_is_actor=False,email_verified=True,tenant_active=True,
                independent_approval=True,token_valid=True,
                expected_revision=1,observed_revision=1,
                idempotency_key=KEY,previously_used_keys=[])
    first=preview_transition(**kwargs)
    second=preview_transition(**kwargs)
    assert first==second
    assert first["allowed_for_real_execution"] is False
    assert workflow_contract()["audit_persisted"] is False
