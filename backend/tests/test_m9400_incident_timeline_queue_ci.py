"""M8700-M9400: immutable timeline and bounded read-only queue regression."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.mp_orders_holds import HoldReason
from app.mp_orders_incident_ops import UnresolvedIncident
from app.mp_orders_incident_timeline import (
    CONTRACT as TIMELINE, TimelineAction, make_timeline_event,
    verify_timeline, review_priority_is_not_a_payment_decision,
)
from app.mp_orders_recovery_scheduler import (
    RecoverySnapshot, RecoverySignal,
)
from app.mp_orders_readonly_circuit import ReadonlyCircuitSnapshot
from app.mp_orders_tenant_queue import (
    CONTRACT as QUEUE, RecoveryCase, summary_for_tenant,
    readonly_queue_preview,
)
from app.pix_automation_contract import FinancialOperationBlocked


T = UUID("00000000-0000-4000-8000-0000000000a1")
OTHER = UUID("00000000-0000-4000-8000-0000000000b1")
REPORTER = UUID("00000000-0000-4000-8000-000000000001")
REVIEW1 = UUID("00000000-0000-4000-8000-000000000002")
REVIEW2 = UUID("00000000-0000-4000-8000-000000000003")
DATE = datetime(2026, 11, 5, 12, tzinfo=timezone.utc)
OP = "P_" + "a"*32


def incident(**changes):
    data=dict(tenant_id=T, operation_id=OP,
              provider_account_id="2002", reason=HoldReason.BANK_MISSING,
              evidence_sha256="a"*64, opened_at=DATE,
              reported_by=REPORTER)
    data.update(changes)
    return UnresolvedIncident(**data)


def event_chain(i=None):
    i=i or incident()
    first=make_timeline_event(
        i, sequence=1, action=TimelineAction.OPENED,
        actor_id=REPORTER, recorded_at=DATE,
        previous_digest="0"*64)
    second=make_timeline_event(
        i, sequence=2, action=TimelineAction.BANK_PROOF_REQUESTED,
        actor_id=REVIEW1, recorded_at=DATE+timedelta(minutes=1),
        previous_digest=first.digest)
    third=make_timeline_event(
        i, sequence=3, action=TimelineAction.DUAL_REVIEW_RECORDED,
        actor_id=REVIEW1, second_reviewer_id=REVIEW2,
        recorded_at=DATE+timedelta(minutes=2),
        previous_digest=second.digest)
    return (first,second,third)


def test_valid_timeline_keeps_hold_without_authenticated_audit_claim():
    i=incident()
    events=event_chain(i)
    r=verify_timeline(i,events)
    assert r.event_count==3 and r.head_digest==events[-1].digest
    assert r.last_action is TimelineAction.DUAL_REVIEW_RECORDED
    assert r.hold_active and not any((
        r.authenticated_audit_log,r.independently_verified_bank_proof,
        r.ledger_write_authorized,r.mark_paid_authorized,
        r.release_hold_authorized,r.payout_authorized,
    ))
    assert review_priority_is_not_a_payment_decision(i,events)


@pytest.mark.parametrize("field,value",[
    ("sequence",True),("sequence",2),("action","OPENED"),
    ("actor_id",UUID(int=0)),("actor_id",REVIEW1),
    ("previous_digest","f"*64),
    ("recorded_at",datetime(2026,11,5)),
    ("recorded_at",DATE-timedelta(seconds=1)),
])
def test_first_event_must_be_reporter_genesis(field,value):
    args=dict(sequence=1,action=TimelineAction.OPENED,
              actor_id=REPORTER,recorded_at=DATE,
              previous_digest="0"*64)
    args[field]=value
    with pytest.raises(FinancialOperationBlocked):
        make_timeline_event(incident(),**args)


@pytest.mark.parametrize("changes",[
    {"sequence":1}, {"action":TimelineAction.OPENED},
    {"recorded_at":DATE-timedelta(seconds=1)},
    {"previous_digest":"G"*64},
    {"second_reviewer_id":REPORTER},
    {"second_reviewer_id":REVIEW1},
    {"second_reviewer_id":UUID(int=0)},
])
def test_dual_review_guard_rejects_forged_event(changes):
    args=dict(sequence=3,action=TimelineAction.DUAL_REVIEW_RECORDED,
              actor_id=REVIEW1,second_reviewer_id=REVIEW2,
              recorded_at=DATE+timedelta(minutes=2),
              previous_digest="b"*64)
    args.update(changes)
    with pytest.raises(FinancialOperationBlocked):
        make_timeline_event(incident(),**args)


@pytest.mark.parametrize("field,value",[
    ("digest","c"*64),("evidence_sha256","b"*64),
    ("reason_code","STATUS_CONFLICT"),("sequence",3),
    ("tenant_id",OTHER),("actor_id",REVIEW2),
    ("hold_active",False),("financial_effect_applied",True),
])
def test_mutation_of_existing_event_is_rejected(field,value):
    i=incident()
    chain=list(event_chain(i))
    chain[1]=replace(chain[1],**{field:value})
    with pytest.raises(FinancialOperationBlocked):
        verify_timeline(i,tuple(chain))


def test_timeline_rejects_wrong_tenant_and_reordered_events():
    with pytest.raises(FinancialOperationBlocked):
        verify_timeline(incident(tenant_id=OTHER),event_chain())
    with pytest.raises(FinancialOperationBlocked):
        verify_timeline(incident(),event_chain()[::-1])
    with pytest.raises(FinancialOperationBlocked):
        verify_timeline(incident(),())
    with pytest.raises(FinancialOperationBlocked):
        verify_timeline(incident(),event_chain()[:2]+event_chain()[1:2])


def test_time_alias_is_canonicalized_to_same_digest():
    i=incident()
    d=DATE.astimezone(timezone(timedelta(hours=-3)))
    first=make_timeline_event(i,sequence=1,action=TimelineAction.OPENED,
         actor_id=REPORTER,recorded_at=DATE,previous_digest="0"*64)
    equivalent=make_timeline_event(i,sequence=1,action=TimelineAction.OPENED,
         actor_id=REPORTER,recorded_at=d,previous_digest="0"*64)
    assert first.digest==equivalent.digest


def test_summary_only_contains_counts_and_no_sensitive_case_details():
    data=(incident(),incident(),incident(
        operation_id="P_"+"b"*32,reason=HoldReason.ORDER_REPLAY))
    s=summary_for_tenant(T,data)
    assert (s.total,s.critical,s.high,s.review)==(2,1,0,1)
    assert s.sanitized_counts_only and not s.source_authenticated
    assert not s.bank_reconciled and not s.financial_effect_applied
    raw=repr(s)
    assert OP not in raw and "2002" not in raw and "a"*64 not in raw


def test_summary_rejects_two_tenants_and_conflicting_duplicate():
    with pytest.raises(FinancialOperationBlocked):
        summary_for_tenant(T,(incident(),incident(tenant_id=OTHER)))
    with pytest.raises(FinancialOperationBlocked):
        summary_for_tenant(T,(incident(),incident(evidence_sha256="b"*64)))
    with pytest.raises(FinancialOperationBlocked):
        summary_for_tenant(T,(incident(),)*1001)


def case(**updates):
    r=RecoverySnapshot(
        incident=incident(),order_id="ORD"+"A"*12,
        signal=RecoverySignal.ORDER_PENDING,
        attempts=0,now=DATE+timedelta(minutes=3),
        seller_approved=True,tenant_binding_verified=True)
    c=ReadonlyCircuitSnapshot(
        tenant_id=T,provider_account_id="2002",operation_id=OP,
        observed_at=DATE+timedelta(minutes=3),
        failure_window_opened_at=DATE,
        failures_in_window=0,last_failure_at=None,
        recovery_attempts=0,seller_approved=True,
        tenant_binding_verified=True)
    d={"recovery":r,"circuit":c}
    d.update(updates)
    return RecoveryCase(**d)


def test_recovery_queue_proposes_only_bounded_get_candidates():
    c=case()
    p=readonly_queue_preview(T,"2002",(c,c),max_candidates=1)
    assert p.scanned==1 and p.get_candidates==(OP,)
    assert p.pending_or_blocked==0 and p.safety_hold_active
    assert not any((
        p.tenant_authentication_performed,p.rate_limit_persisted,
        p.get_execution_authorized,p.money_movement_authorized,
        p.ledger_write_authorized,
    ))


@pytest.mark.parametrize("changes",[
    {"seller_approved":False}, {"tenant_binding_verified":False},
    {"signal":RecoverySignal.GET_401},
    {"signal":RecoverySignal.ORDER_PROCESSED},
])
def test_untrusted_get_signal_does_not_enter_queue(changes):
    old=case()
    recovery=replace(old.recovery,**changes)
    p=readonly_queue_preview(T,"2002",(case(recovery=recovery),))
    assert p.get_candidates==() and p.pending_or_blocked==1


def test_open_circuit_is_not_a_get_candidate():
    old=case()
    c=replace(old.circuit,failures_in_window=5,
        last_failure_at=DATE+timedelta(minutes=2))
    p=readonly_queue_preview(T,"2002",(case(circuit=c),))
    assert p.get_candidates==()


@pytest.mark.parametrize("case_change",[
    {"tenant_id":OTHER}, {"provider_account_id":"3003"},
    {"operation_id":"P_"+"b"*32},
])
def test_queue_rejects_cross_tenant_seller_and_operation(case_change):
    old=case()
    c=replace(old.circuit,**case_change)
    with pytest.raises(FinancialOperationBlocked):
        readonly_queue_preview(T,"2002",(case(circuit=c),))


def test_queue_rejects_duplicate_with_conflicting_state():
    a=case()
    b=case(recovery=replace(a.recovery,attempts=1))
    with pytest.raises(FinancialOperationBlocked):
        readonly_queue_preview(T,"2002",(a,b))


@pytest.mark.parametrize("max_candidates",[-1,0,11,True])
def test_queue_rejects_invalid_candidate_bounds(max_candidates):
    with pytest.raises(FinancialOperationBlocked):
        readonly_queue_preview(T,"2002",(case(),),max_candidates=max_candidates)


def test_gate_route_m9400_advertises_no_real_authority():
    with TestClient(app) as client:
        response=client.get("/api/health/features/m9400")
    assert response.status_code==200
    d=response.json()
    assert d["workstream"]=="AI_STUDIO"
    assert d["contract"]=="AI_STUDIO_M9400_CASE_TIMELINE_QUEUE_PREFLIGHT_V1"
    assert d["timeline_contract"]==TIMELINE
    assert d["queue_contract"]==QUEUE
    for key in ("deterministic_chain_preview","bounded_per_tenant_get_candidates",
                "cross_tenant_queue_rejected"):
        assert d[key] is True
    for key in ("audit_event_persisted","operator_identity_authenticated",
                "get_worker_live","oci_staging_deployed",
                "real_payments_enabled","bank_reconciled","ledger_written",
                "financial_effect_applied","financial_closing_authorized",
                "payout_authorized"):
        assert d[key] is False,key
    assert "/api/v1/staging/incidents/release" not in {
        route.path for route in app.routes
    }
