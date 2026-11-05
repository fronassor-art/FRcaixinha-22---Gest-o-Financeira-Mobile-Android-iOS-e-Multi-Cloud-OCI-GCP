"""M7300-M7900: adversarial offline-only incident/recovery contract."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from uuid import UUID
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.mp_orders_holds import HoldReason
from app.mp_orders_incident_ops import (
    CONTRACT as INCIDENT_CONTRACT, IncidentNextStep, IncidentPriority,
    UnresolvedIncident, triage_incident, triage_tenant_page,
    review_incident,
)
from app.mp_orders_recovery_scheduler import (
    CONTRACT as RECOVERY_CONTRACT, RecoverySignal, SafeRecoveryAction,
    RecoverySnapshot, plan_readonly_recovery,
)
from app.pix_automation_contract import FinancialOperationBlocked


T = UUID("00000000-0000-4000-8000-0000000000a1")
OTHER = UUID("00000000-0000-4000-8000-0000000000b1")
REPORTER = UUID("00000000-0000-4000-8000-000000000001")
R1 = UUID("00000000-0000-4000-8000-000000000002")
R2 = UUID("00000000-0000-4000-8000-000000000003")
D = datetime(2026, 11, 4, 12, 0, tzinfo=timezone.utc)
O = "P_" + "a" * 32


def case(**overrides):
    d = dict(
        tenant_id=T, operation_id=O, provider_account_id="2002",
        reason=HoldReason.BANK_MISSING, evidence_sha256="a"*64,
        opened_at=D, reported_by=REPORTER,
    )
    d.update(overrides)
    return UnresolvedIncident(**d)


def retry(**overrides):
    d = dict(
        incident=case(), order_id="ORD" + "A"*12,
        signal=RecoverySignal.GET_TIMEOUT, attempts=1,
        now=D + timedelta(minutes=5),
        seller_approved=True, tenant_binding_verified=True,
    )
    d.update(overrides)
    return RecoverySnapshot(**d)


@pytest.mark.parametrize("reason,priority,step", [
    (HoldReason.SELLER_REVOKED, IncidentPriority.CRITICAL,
     IncidentNextStep.ESCALATE_SECURITY),
    (HoldReason.ORDER_REPLAY, IncidentPriority.CRITICAL,
     IncidentNextStep.ESCALATE_SECURITY),
    (HoldReason.STATEMENT_DUPLICATE, IncidentPriority.CRITICAL,
     IncidentNextStep.ESCALATE_SECURITY),
    (HoldReason.TIMEOUT_UNKNOWN, IncidentPriority.HIGH,
     IncidentNextStep.PROVIDER_SUPPORT_ONLY),
    (HoldReason.PROVIDER_MISMATCH, IncidentPriority.HIGH,
     IncidentNextStep.PROVIDER_SUPPORT_ONLY),
    (HoldReason.STATUS_CONFLICT, IncidentPriority.HIGH,
     IncidentNextStep.PROVIDER_SUPPORT_ONLY),
    (HoldReason.BANK_MISSING, IncidentPriority.REVIEW,
     IncidentNextStep.CHECK_INDEPENDENT_STATEMENT),
    (HoldReason.FEE_MISMATCH, IncidentPriority.REVIEW,
     IncidentNextStep.CHECK_INDEPENDENT_STATEMENT),
    (HoldReason.REVERSAL_PENDING, IncidentPriority.REVIEW,
     IncidentNextStep.CHECK_INDEPENDENT_STATEMENT),
])
def test_all_reasons_remain_blocked(reason, priority, step):
    result = triage_incident(case(reason=reason))
    assert (result.priority, result.next_step) == (priority, step)
    assert result.hold_active
    assert not any((
        result.bank_reconciled, result.mark_paid_authorized,
        result.ledger_write_authorized, result.payout_authorized,
        result.financial_closing_authorized,
    ))


@pytest.mark.parametrize("change", [
    dict(tenant_id=UUID(int=0)),
    dict(operation_id="P_invalid"),
    dict(provider_account_id="2002;DROP"),
    dict(provider_account_id=""),
    dict(reason="BANK_MISSING"),
    dict(evidence_sha256="A"*64),
    dict(evidence_sha256="0"*63),
    dict(opened_at=datetime(2026, 11, 4)),
    dict(reported_by=UUID(int=0)),
])
def test_malformed_holds_fail_closed(change):
    with pytest.raises(FinancialOperationBlocked):
        triage_incident(case(**change))


def test_review_requires_two_distinct_reviewers_not_reporter():
    with pytest.raises(FinancialOperationBlocked):
        review_incident(case(), reviewer_one=R1, reviewer_two=R1,
                        reviewed_at=D, previous_audit_sha256="0"*64)
    with pytest.raises(FinancialOperationBlocked):
        review_incident(case(), reviewer_one=REPORTER, reviewer_two=R2,
                        reviewed_at=D, previous_audit_sha256="0"*64)


def test_review_is_hash_chained_but_never_a_proof_of_payment():
    args=dict(reviewer_one=R1,reviewer_two=R2,reviewed_at=D,
              previous_audit_sha256="0"*64)
    a=review_incident(case(), **args)
    b=review_incident(case(), **args)
    assert a==b and len(a.audit_sha256)==64
    assert a.outcome=="REVIEW_RECORDED_HOLD_REMAINS"
    assert not any((a.can_release_hold,a.can_mark_paid,
                    a.can_post_ledger,a.can_payout))
    changed=review_incident(case(evidence_sha256="b"*64), **args)
    assert a.audit_sha256!=changed.audit_sha256
    chained=review_incident(case(), **{**args,
                             "previous_audit_sha256":a.audit_sha256})
    assert a.audit_sha256!=chained.audit_sha256


@pytest.mark.parametrize("change", [
    {"reviewed_at":D-timedelta(seconds=1)},
    {"reviewed_at":datetime(2026,11,4)},
    {"previous_audit_sha256":"?"*64},
    {"reviewer_two":UUID(int=0)},
])
def test_review_rejects_bad_time_hash_and_identity(change):
    args=dict(reviewer_one=R1,reviewer_two=R2,reviewed_at=D,
              previous_audit_sha256="0"*64)
    args.update(change)
    with pytest.raises(FinancialOperationBlocked):
        review_incident(case(), **args)


def test_tenant_page_prioritizes_and_deduplicates():
    incidents=(
        case(),
        case(reason=HoldReason.ORDER_REPLAY,operation_id="P_"+"b"*32),
        case(),
    )
    result=triage_tenant_page(T,incidents,limit=1)
    assert len(result)==1
    assert result[0].priority is IncidentPriority.CRITICAL
    assert len(triage_tenant_page(T,incidents))==2


def test_tenant_page_rejects_cross_tenant_and_conflicts():
    with pytest.raises(FinancialOperationBlocked):
        triage_tenant_page(T,(case(),case(tenant_id=OTHER)))
    with pytest.raises(FinancialOperationBlocked):
        triage_tenant_page(T,(case(),case(evidence_sha256="b"*64)))


@pytest.mark.parametrize("offset,limit",[(True,10),(-1,10),(0,101),(0,0)])
def test_invalid_page_bounds_are_refused(offset,limit):
    with pytest.raises(FinancialOperationBlocked):
        triage_tenant_page(T,(case(),),offset=offset,limit=limit)


@pytest.mark.parametrize("signal,action",[
    (RecoverySignal.GET_401,SafeRecoveryAction.BLOCK_SELLER),
    (RecoverySignal.GET_403,SafeRecoveryAction.BLOCK_SELLER),
    (RecoverySignal.ORDER_PROCESSED,
     SafeRecoveryAction.VERIFY_BANK_INDEPENDENTLY),
    (RecoverySignal.ORDER_PENDING,SafeRecoveryAction.READ_ORDER_ONLY),
    (RecoverySignal.NOT_ATTEMPTED,SafeRecoveryAction.READ_ORDER_ONLY),
    (RecoverySignal.UNKNOWN_REMOTE,
     SafeRecoveryAction.ESCALATE_HUMAN_PROVIDER),
])
def test_get_signals_never_settle_anything(signal,action):
    result=plan_readonly_recovery(retry(signal=signal))
    assert result.action is action
    assert not any((result.can_post_order,result.can_mark_paid,
                    result.can_write_ledger,result.can_release_hold,
                    result.can_payout,result.can_close_financial_cycle))


def test_retry_delay_is_stable_and_bounded():
    state=retry(signal=RecoverySignal.GET_429,retry_after_seconds=600)
    a=plan_readonly_recovery(state)
    b=plan_readonly_recovery(state)
    assert a==b
    assert a.action is SafeRecoveryAction.RETRY_GET_LATER
    assert a.next_get_at==state.now+timedelta(seconds=600)


@pytest.mark.parametrize("changes",[
    {"attempts":6},
    {"attempts":50},
    {"now":D+timedelta(hours=3)},
    {"order_id":None},
])
def test_retry_budget_expiry_and_unknown_order_escalate(changes):
    d=plan_readonly_recovery(retry(**changes))
    assert d.action is SafeRecoveryAction.ESCALATE_HUMAN_PROVIDER
    assert d.next_get_at is None


@pytest.mark.parametrize("changes",[
    {"seller_approved":False},
    {"tenant_binding_verified":False},
    {"signal":RecoverySignal.GET_403},
])
def test_revoked_seller_or_invalid_tenant_blocks(changes):
    assert plan_readonly_recovery(retry(**changes)).action is SafeRecoveryAction.BLOCK_SELLER


@pytest.mark.parametrize("changes",[
    {"attempts":True},
    {"seller_approved":1},
    {"order_id":"INVALID"},
    {"retry_after_seconds":601},
    {"now":D-timedelta(seconds=1)},
    {"now":datetime(2026,11,4)},
    {"signal":"GET_TIMEOUT"},
])
def test_bad_recovery_context_fails_closed(changes):
    with pytest.raises(FinancialOperationBlocked):
        plan_readonly_recovery(retry(**changes))


def test_health_endpoint_advertises_only_preflight_and_no_live_routes():
    with TestClient(app) as cli:
        r=cli.get("/api/health/features/m7900")
    assert r.status_code==200
    d=r.json()
    assert d["workstream"]=="AI_STUDIO"
    assert d["contract"]=="AI_STUDIO_M7900_INCIDENT_REVIEW_READONLY_RECOVERY_V1"
    assert d["incident_contract"]==INCIDENT_CONTRACT
    assert d["recovery_contract"]==RECOVERY_CONTRACT
    for key in ("immutable_review_preview","bounded_get_retry_policy",
                "cross_tenant_case_rejected","two_reviewer_preview"):
        assert d[key] is True
    for key in ("real_provider_connected","real_bank_statement_reader_connected",
                "incident_review_persisted_in_staging","real_payments_enabled",
                "bank_reconciled","ledger_written","financial_effect_applied",
                "financial_closing_authorized","payout_authorized",
                "oci_staging_deployed","staging_m039_applied_locally"):
        assert d[key] is False,key
    paths={route.path for route in app.routes}
    assert "/api/v1/staging/incident/release" not in paths
    assert "/api/v1/financial/settle" not in paths
