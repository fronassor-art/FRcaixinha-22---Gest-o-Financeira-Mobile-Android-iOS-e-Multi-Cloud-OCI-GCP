"""AI Studio M9500-M10200: offline case-binding and queue integrity tests."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.mp_orders_holds import HoldReason
from app.mp_orders_incident_ops import UnresolvedIncident
from app.mp_orders_incident_timeline import (
    TimelineAction, make_timeline_event,
)
from app.mp_orders_evidence_discrepancy import (
    ClaimedChannel, ClaimedFinancialRecord, DiscrepancyContext, ReviewOutcome,
)
from app.mp_orders_recovery_scheduler import (
    RecoverySnapshot, RecoverySignal, SafeRecoveryAction,
)
from app.mp_orders_readonly_circuit import (
    ReadonlyCircuitSnapshot, ReadonlyAction,
)
from app.mp_orders_tenant_queue import RecoveryCase, readonly_queue_preview
from app.mp_orders_case_integrity import (
    CONTRACT, IntegratedCaseSnapshot, inspect_integrated_case,
    count_integrated_cases_for_tenant,
)
from app.pix_automation_contract import FinancialOperationBlocked

TENANT = UUID("00000000-0000-4000-8000-0000000000a1")
OTHER = UUID("00000000-0000-4000-8000-0000000000b1")
REPORTER = UUID("00000000-0000-4000-8000-000000000001")
REVIEWER = UUID("00000000-0000-4000-8000-000000000002")
START = datetime(2026, 11, 5, 12, tzinfo=timezone.utc)
OP = "P_" + "a" * 32
ORDER = "ORD" + "A" * 12
PAY = "PAY" + "B" * 12


def claim(channel, index, **updates):
    payload = dict(
        channel=channel, tenant_id=TENANT, provider_account_id="2002",
        operation_id=OP, order_id=ORDER, payment_id=PAY,
        gross_cents=15000, fee_cents=150, net_cents=14850,
        evidence_sha256=str(index) * 64, record_reference=f"REF-SYNTH-{index}",
        observed_at=START+timedelta(minutes=index),
    )
    payload.update(updates)
    return ClaimedFinancialRecord(**payload)


def make_case(**updates):
    incident = UnresolvedIncident(
        tenant_id=TENANT, operation_id=OP, provider_account_id="2002",
        reason=HoldReason.BANK_MISSING, evidence_sha256="a"*64,
        opened_at=START, reported_by=REPORTER,
    )
    first = make_timeline_event(
        incident, sequence=1, action=TimelineAction.OPENED,
        actor_id=REPORTER, recorded_at=START, previous_digest="0"*64,
    )
    second = make_timeline_event(
        incident, sequence=2, action=TimelineAction.BANK_PROOF_REQUESTED,
        actor_id=REVIEWER, recorded_at=START+timedelta(minutes=4),
        previous_digest=first.digest,
    )
    evidence=DiscrepancyContext(
        provider=claim(ClaimedChannel.PROVIDER_GET,1),
        settlement=claim(ClaimedChannel.SETTLEMENT_REPORT,2),
        bank=claim(ClaimedChannel.BANK_STATEMENT,3),
        seller_revoked=False,provider_processed=True,
        dispute_pending=False,reversal_pending=False,
    )
    recovery=RecoverySnapshot(
        incident=incident,order_id=ORDER,signal=RecoverySignal.ORDER_PENDING,
        attempts=0,now=START+timedelta(minutes=10),seller_approved=True,
        tenant_binding_verified=True,
    )
    circuit=ReadonlyCircuitSnapshot(
        tenant_id=TENANT,provider_account_id="2002",operation_id=OP,
        observed_at=START+timedelta(minutes=10),
        failure_window_opened_at=START,
        failures_in_window=0,last_failure_at=None,recovery_attempts=0,
        seller_approved=True,tenant_binding_verified=True,
    )
    data=dict(incident=incident,timeline=(first,second),
              claimed_evidence=evidence,recovery=recovery,circuit=circuit)
    data.update(updates)
    return IntegratedCaseSnapshot(**data)


def assert_no_economic_authority(d):
    assert d.hold_active
    for field in (
        "verified_bank_source","authenticated_operator_identity",
        "persisted_audit_trail","get_execution_authorized",
        "mark_paid_authorized","ledger_write_authorized",
        "hold_release_authorized","payout_authorized",
        "financial_closing_authorized",
    ):
        assert getattr(d,field) is False,field


def test_consistent_unverified_case_remains_on_hold():
    case=make_case()
    decision=inspect_integrated_case(case)
    assert decision.evidence_outcome is ReviewOutcome.UNVERIFIED_SOURCE
    assert decision.recovery_action is SafeRecoveryAction.READ_ORDER_ONLY
    assert decision.circuit_action is ReadonlyAction.GET_CANDIDATE_ONLY
    assert decision.read_candidate_policy_only
    assert decision == inspect_integrated_case(case)
    assert len(decision.case_fingerprint)==64
    assert_no_economic_authority(decision)


@pytest.mark.parametrize("field,value", [
    ("tenant_id",OTHER),
    ("operation_id","P_"+"b"*32),
    ("provider_account_id","9999"),
])
def test_claims_cannot_belong_to_other_tenant_operation_or_seller(field,value):
    case=make_case()
    evidence=case.claimed_evidence
    sources = [
        replace(evidence.provider,**{field:value}),
        replace(evidence.settlement,**{field:value}),
        replace(evidence.bank,**{field:value}),
    ]
    forged=replace(case,claimed_evidence=replace(
        evidence,provider=sources[0],settlement=sources[1],bank=sources[2]))
    with pytest.raises(FinancialOperationBlocked):
        inspect_integrated_case(forged)


def test_recovery_order_must_match_claimed_order():
    case=make_case()
    recovery=replace(case.recovery,order_id="ORD"+"Z"*12)
    with pytest.raises(FinancialOperationBlocked):
        inspect_integrated_case(replace(case,recovery=recovery))


def test_circuit_identity_cannot_cross_tenant_seller_or_operation():
    for k,v in (
        ("tenant_id",OTHER),
        ("provider_account_id","9999"),
        ("operation_id","P_"+"c"*32),
    ):
        case=make_case()
        with pytest.raises(FinancialOperationBlocked):
            inspect_integrated_case(replace(
                case,circuit=replace(case.circuit,**{k:v})))


@pytest.mark.parametrize("field,value", [
    ("seller_approved",False),("tenant_binding_verified",False),
])
def test_contradictory_auth_claims_fail_closed(field,value):
    case=make_case()
    circuit=replace(case.circuit,**{field:value})
    with pytest.raises(FinancialOperationBlocked):
        inspect_integrated_case(replace(case,circuit=circuit))


def test_inconsistent_snapshot_times_fail_closed():
    case=make_case()
    with pytest.raises(FinancialOperationBlocked):
        inspect_integrated_case(replace(
            case,circuit=replace(
                case.circuit,observed_at=case.circuit.observed_at+timedelta(seconds=1)
            )))
    with pytest.raises(FinancialOperationBlocked):
        inspect_integrated_case(replace(
            case,recovery=replace(case.recovery,now=START+timedelta(minutes=3))
        ))


def test_future_claim_is_rejected_even_if_individually_well_formed():
    case=make_case()
    future=replace(case.claimed_evidence.bank,
                   observed_at=START+timedelta(days=2))
    with pytest.raises(FinancialOperationBlocked):
        inspect_integrated_case(replace(
            case,claimed_evidence=replace(case.claimed_evidence,bank=future)))


def test_incident_in_recovery_must_match_entire_incident():
    case=make_case()
    different=replace(case.incident,evidence_sha256="b"*64)
    with pytest.raises(FinancialOperationBlocked):
        inspect_integrated_case(replace(
            case,recovery=replace(case.recovery,incident=different)))


def test_replayed_timeline_with_modified_action_rejected():
    case=make_case()
    altered=replace(case.timeline[1], action=TimelineAction.SECURITY_ESCALATED)
    with pytest.raises(FinancialOperationBlocked):
        inspect_integrated_case(replace(case,timeline=(case.timeline[0],altered)))


@pytest.mark.parametrize("flag",[
    "seller_revoked","dispute_pending","reversal_pending",
])
def test_security_and_dispute_claims_never_propose_simple_get(flag):
    case=make_case()
    evidence=replace(case.claimed_evidence,**{flag:True})
    d=inspect_integrated_case(replace(case,claimed_evidence=evidence))
    assert d.read_candidate_policy_only is False
    assert_no_economic_authority(d)


def test_processed_order_never_proposes_get_candidate():
    case=make_case()
    recovery=replace(case.recovery,signal=RecoverySignal.ORDER_PROCESSED)
    d=inspect_integrated_case(replace(case,recovery=recovery))
    assert not d.read_candidate_policy_only
    assert d.recovery_action is SafeRecoveryAction.VERIFY_BANK_INDEPENDENTLY
    assert_no_economic_authority(d)


def test_absent_order_id_forces_manual_provider_investigation():
    case=make_case()
    recovery=replace(case.recovery,order_id=None)
    d=inspect_integrated_case(replace(case,recovery=recovery))
    assert not d.read_candidate_policy_only
    assert d.recovery_action is SafeRecoveryAction.ESCALATE_HUMAN_PROVIDER


def test_duplicate_claimed_evidence_does_not_propose_get():
    case=make_case()
    duplicate=replace(
        case.claimed_evidence.bank,evidence_sha256="2"*64,
    )
    d=inspect_integrated_case(replace(
        case,claimed_evidence=replace(case.claimed_evidence,bank=duplicate)))
    assert d.evidence_outcome is ReviewOutcome.DUPLICATE_EVIDENCE
    assert not d.read_candidate_policy_only
    assert_no_economic_authority(d)


def test_batch_summary_deduplicates_without_leaking_ids():
    case=make_case()
    summary=count_integrated_cases_for_tenant(TENANT,(case,case))
    assert summary.total_cases==1
    assert (summary.critical_cases,summary.high_cases,summary.review_cases)==(0,0,1)
    assert summary.get_candidates_policy_only==1
    assert summary.blocked_or_manual_cases==0
    assert not summary.contains_case_ids
    assert OP not in repr(summary) and ORDER not in repr(summary)
    assert "2002" not in repr(summary)


def test_batch_mixed_tenants_and_conflicting_replay_rejected():
    case=make_case()
    with pytest.raises(FinancialOperationBlocked):
        count_integrated_cases_for_tenant(OTHER,(case,))
    different=replace(case,recovery=replace(
        case.recovery,signal=RecoverySignal.ORDER_PROCESSED))
    with pytest.raises(FinancialOperationBlocked):
        count_integrated_cases_for_tenant(TENANT,(case,different))
    with pytest.raises(FinancialOperationBlocked):
        count_integrated_cases_for_tenant(TENANT,(case,)*101)


def test_empty_summary_is_not_a_financial_clearance():
    summary=count_integrated_cases_for_tenant(TENANT,())
    assert summary.total_cases == 0
    assert summary.bank_reconciled is False
    assert summary.financial_effect_applied is False
    assert summary.authenticated_source is False


@pytest.mark.parametrize("field,value",[
    ("observed_at",START+timedelta(minutes=11)),
    ("seller_approved",False),
    ("tenant_binding_verified",False),
])
def test_m9400_queue_new_cross_snapshot_binding_rejects(field,value):
    case=make_case()
    circuit=replace(case.circuit,**{field:value})
    candidate=RecoveryCase(case.recovery,circuit)
    with pytest.raises(FinancialOperationBlocked):
        readonly_queue_preview(TENANT,"2002",(candidate,))


def test_m9400_queue_counts_deferred_candidates_distinctly():
    case=make_case()
    one=RecoveryCase(case.recovery,case.circuit)
    other_incident=replace(case.incident,operation_id="P_"+"b"*32)
    other_recovery=replace(case.recovery,incident=other_incident)
    other_circuit=replace(case.circuit,operation_id=other_incident.operation_id)
    two=RecoveryCase(other_recovery,other_circuit)
    preview=readonly_queue_preview(TENANT,"2002",(one,two),max_candidates=1)
    assert preview.scanned==2
    assert preview.eligible_candidates==2
    assert preview.deferred_candidates==1
    assert preview.blocked_cases==0
    assert preview.pending_or_blocked==1
    assert preview.get_execution_authorized is False


def test_health_contract_m10200_and_forbidden_financial_routes():
    with TestClient(app) as client:
        response=client.get("/api/health/features/m10200")
    assert response.status_code==200
    data=response.json()
    assert data["workstream"]=="AI_STUDIO"
    assert data["contract"]=="AI_STUDIO_M10200_CASE_INTEGRITY_BOUNDARIES_V1"
    assert data["integrity_contract"]==CONTRACT
    assert data["cross_component_binding_preflight"] is True
    assert data["queue_snapshot_consistency_preflight"] is True
    for flag in (
        "case_audit_persisted","case_sources_authenticated",
        "distributed_recovery_lease_active","real_orders_get_active",
        "real_bank_statement_connected","oci_staging_deployed",
        "real_payments_enabled","bank_reconciled","ledger_written",
        "financial_effect_applied","financial_closing_authorized",
        "payout_authorized",
    ):
        assert data[flag] is False,flag
    paths={route.path for route in app.routes}
    assert "/api/v1/orders/incidents/resolve-and-pay" not in paths
    assert "/api/v1/staging/incidents/release" not in paths
