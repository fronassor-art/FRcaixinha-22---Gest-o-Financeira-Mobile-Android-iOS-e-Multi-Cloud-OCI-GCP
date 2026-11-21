"""M11100-M12000: synthetic retry / crash-recovery / rollback regression."""
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
    ClaimedFinancialRecord, ClaimedChannel, DiscrepancyContext,
)
from app.mp_orders_recovery_scheduler import (
    RecoverySnapshot, RecoverySignal,
)
from app.mp_orders_readonly_circuit import ReadonlyCircuitSnapshot
from app.mp_orders_case_integrity import IntegratedCaseSnapshot
from app.mp_orders_replay_history import (
    CONTRACT, ReplayHistory, replay_unresolved_history,
    verify_replayed_history, summarize_tenant_replay_histories,
)
from app.pix_automation_contract import FinancialOperationBlocked

T = UUID("00000000-0000-4000-8000-0000000000a1")
OTHER = UUID("00000000-0000-4000-8000-0000000000b1")
REPORTER = UUID("00000000-0000-4000-8000-000000000001")
REVIEWER = UUID("00000000-0000-4000-8000-000000000002")
START = datetime(2026, 11, 5, 12, tzinfo=timezone.utc)
OP = "P_" + "a" * 32
ORDER = "ORD" + "A" * 12
PAY = "PAY" + "B" * 12


def case(*, minute=10, attempts=0, signal=RecoverySignal.ORDER_PENDING,
         operation_id=OP, order_id=ORDER, payment_id=PAY, tenant_id=T,
         seller_approved=True, tenant_binding_verified=True,
         failures=0, window=None, note=False):
    incident=UnresolvedIncident(
        tenant_id=tenant_id, operation_id=operation_id,
        provider_account_id="2002", reason=HoldReason.BANK_MISSING,
        evidence_sha256="a"*64, opened_at=START, reported_by=REPORTER,
    )
    first=make_timeline_event(
        incident,sequence=1,action=TimelineAction.OPENED,
        actor_id=REPORTER,recorded_at=START,previous_digest="0"*64)
    events=(first,)
    if note:
        second=make_timeline_event(
            incident,sequence=2,action=TimelineAction.BANK_PROOF_REQUESTED,
            actor_id=REVIEWER,recorded_at=START+timedelta(minutes=2),
            previous_digest=first.digest)
        events=(first,second)
    records=tuple(
        ClaimedFinancialRecord(
            channel=channel,tenant_id=tenant_id,
            provider_account_id="2002",operation_id=operation_id,
            order_id=order_id,payment_id=payment_id,
            gross_cents=15000,fee_cents=150,net_cents=14850,
            evidence_sha256=str(n)*64,
            record_reference=f"REF-SYNTH-{n}",
            observed_at=START+timedelta(minutes=n),
        )
        for n,channel in enumerate(ClaimedChannel,1)
    )
    evidence=DiscrepancyContext(
        provider=records[0],settlement=records[1],bank=records[2],
        seller_revoked=False,provider_processed=True,
        dispute_pending=False,reversal_pending=False,
    )
    now=START+timedelta(minutes=minute)
    recovery=RecoverySnapshot(
        incident=incident,order_id=order_id,
        signal=signal,attempts=attempts,now=now,
        seller_approved=seller_approved,
        tenant_binding_verified=tenant_binding_verified,
    )
    window = window if window is not None else START
    circuit=ReadonlyCircuitSnapshot(
        tenant_id=tenant_id,provider_account_id="2002",
        operation_id=operation_id,observed_at=now,
        failure_window_opened_at=window,
        failures_in_window=failures,
        last_failure_at=(
            window+timedelta(seconds=5) if failures else None
        ),
        recovery_attempts=attempts,seller_approved=seller_approved,
        tenant_binding_verified=tenant_binding_verified,
    )
    return IntegratedCaseSnapshot(
        incident=incident,timeline=events,claimed_evidence=evidence,
        recovery=recovery,circuit=circuit,
    )


def assert_all_financial_flags_false(history):
    assert history.hold_active
    assert not any((
        history.history_persisted,history.signature_verified,
        history.operator_identity_authenticated,
        history.distributed_lease_held,
        history.get_execution_authorized,
        history.mark_paid_authorized,
        history.ledger_write_authorized,history.payout_authorized,
        history.financial_closing_authorized,
    ))
    for step in history.steps:
        assert step.hold_active
        assert not step.bank_origin_verified
        assert not step.network_get_executed
        assert not step.paid_authorized


def test_single_snapshot_keeps_hold_no_authenticity_claim():
    s=case()
    history=replay_unresolved_history((s,))
    assert history.unique_snapshots == 1
    assert history.exact_replays_suppressed == 0
    assert history.operation_id == OP
    assert history.steps[0].previous_digest == "0"*64
    assert history.last_digest == history.steps[0].audit_digest
    assert_all_financial_flags_false(history)


def test_monotonic_history_with_append_only_revision():
    seq=(case(minute=10),case(minute=11,attempts=1,note=True),
         case(minute=12,attempts=2,note=True))
    h=replay_unresolved_history(seq)
    assert h.unique_snapshots==3
    assert [s.attempts for s in h.steps] == [0,1,2]
    assert h.steps[1].previous_digest == h.steps[0].audit_digest
    assert h.steps[2].previous_digest == h.steps[1].audit_digest
    assert_all_financial_flags_false(h)
    assert verify_replayed_history(seq,h) == h


def test_exact_replay_same_timestamp_is_ignored_in_memory():
    a=case()
    b=case(minute=11,attempts=1)
    h=replay_unresolved_history((a,a,b,b))
    assert h.unique_snapshots==2
    assert h.exact_replays_suppressed==2
    assert_all_financial_flags_false(h)


@pytest.mark.parametrize("attempts",[2,3,4,5,6,20,100])
def test_retry_jump_is_blocked(attempts):
    with pytest.raises(FinancialOperationBlocked):
        replay_unresolved_history((case(),case(minute=11,attempts=attempts)))


def test_retry_count_rollback_is_rejected():
    with pytest.raises(FinancialOperationBlocked):
        replay_unresolved_history((
            case(attempts=2),case(minute=11,attempts=1),
        ))


def test_old_snapshot_after_newer_snapshot_is_rejected():
    with pytest.raises(FinancialOperationBlocked):
        replay_unresolved_history((
            case(minute=12),case(minute=11),
        ))


def test_equal_timestamp_with_distinct_content_is_rejected():
    with pytest.raises(FinancialOperationBlocked):
        replay_unresolved_history((
            case(),case(attempts=1),
        ))


def test_old_review_events_cannot_be_replaced():
    first=case(note=True)
    later=case(minute=11,note=False)
    with pytest.raises(FinancialOperationBlocked):
        replay_unresolved_history((first,later))


def test_new_review_can_only_append():
    first=case(note=False)
    later=case(minute=11,note=True)
    h=replay_unresolved_history((first,later))
    assert h.unique_snapshots==2
    assert_all_financial_flags_false(h)


@pytest.mark.parametrize("signal",[RecoverySignal.GET_401,RecoverySignal.GET_403])
def test_auth_terminal_cannot_recover_silently(signal):
    first=case(signal=signal)
    later=case(minute=11,signal=RecoverySignal.ORDER_PENDING)
    with pytest.raises(FinancialOperationBlocked):
        replay_unresolved_history((first,later))


def test_auth_terminal_repeated_is_still_blocked():
    h=replay_unresolved_history((
        case(signal=RecoverySignal.GET_401),
        case(minute=11,signal=RecoverySignal.GET_401),
    ))
    assert h.unique_snapshots==2
    assert not h.steps[-1].read_candidate_policy_only
    assert_all_financial_flags_false(h)


def test_processed_claim_cannot_downgrade_to_pending():
    with pytest.raises(FinancialOperationBlocked):
        replay_unresolved_history((
            case(signal=RecoverySignal.ORDER_PROCESSED),
            case(minute=11,signal=RecoverySignal.ORDER_PENDING),
        ))


def test_processed_claim_never_grants_payment():
    h=replay_unresolved_history((
        case(signal=RecoverySignal.ORDER_PENDING),
        case(minute=11,signal=RecoverySignal.ORDER_PROCESSED),
    ))
    assert h.unique_snapshots==2
    assert not h.steps[-1].read_candidate_policy_only
    assert_all_financial_flags_false(h)


def test_seller_revocation_cannot_restore_without_authenticated_reset():
    with pytest.raises(FinancialOperationBlocked):
        replay_unresolved_history((
            case(seller_approved=False),
            case(minute=11,seller_approved=True),
        ))


def test_tenant_binding_revocation_cannot_restore():
    with pytest.raises(FinancialOperationBlocked):
        replay_unresolved_history((
            case(tenant_binding_verified=False),
            case(minute=11,tenant_binding_verified=True),
        ))


def test_revocation_can_continue_in_read_only_hold():
    h=replay_unresolved_history((
        case(seller_approved=True),
        case(minute=11,seller_approved=False),
        case(minute=12,seller_approved=False),
    ))
    assert h.unique_snapshots==3
    assert not h.steps[-1].read_candidate_policy_only
    assert_all_financial_flags_false(h)


@pytest.mark.parametrize("key,override",[
    ("tenant_id",OTHER),
    ("operation_id","P_"+"b"*32),
    ("order_id","ORD"+"Z"*12),
    ("payment_id","PAY"+"Z"*12),
])
def test_identity_switch_mid_history_is_rejected(key,override):
    base=case()
    updates={key:override}
    altered=case(minute=11,**updates)
    with pytest.raises(FinancialOperationBlocked):
        replay_unresolved_history((base,altered))


def test_circuit_window_cannot_regress():
    first=case(minute=10,window=START+timedelta(minutes=1))
    second=case(minute=11,window=START)
    with pytest.raises(FinancialOperationBlocked):
        replay_unresolved_history((first,second))


def test_failure_counter_cannot_reset_within_same_window():
    with pytest.raises(FinancialOperationBlocked):
        replay_unresolved_history((
            case(failures=2),case(minute=11,failures=1),
        ))


def test_new_window_may_reset_failures_but_not_hold():
    h=replay_unresolved_history((
        case(failures=2),
        case(minute=11,failures=0,window=START+timedelta(minutes=1)),
    ))
    assert h.unique_snapshots==2
    assert_all_financial_flags_false(h)


def test_chain_is_deterministic_and_tamper_check_fails():
    seq=(case(),case(minute=11,attempts=1))
    h1=replay_unresolved_history(seq)
    h2=replay_unresolved_history(seq)
    assert h1==h2
    poisoned=replace(
        h1,steps=(replace(h1.steps[0],audit_digest="f"*64),)
                 +h1.steps[1:],
    )
    with pytest.raises(FinancialOperationBlocked):
        verify_replayed_history(seq,poisoned)
    assert verify_replayed_history(seq,h1)==h1


@pytest.mark.parametrize("n",[0,65,66,70])
def test_invalid_history_size_is_rejected(n):
    snaps=(case(),)*n
    with pytest.raises(FinancialOperationBlocked):
        replay_unresolved_history(snaps)


def test_history_cannot_be_garbage_type():
    for bad in ([],None,"",{},(object(),)):
        with pytest.raises(FinancialOperationBlocked):
            replay_unresolved_history(bad)


def test_batch_aggregates_only_counts_and_holds():
    a=case()
    b=case(
        operation_id="P_"+"b"*32,
        order_id="ORD"+"Z"*12,
        payment_id="PAY"+"Z"*12,
    )
    s=summarize_tenant_replay_histories(
        T,((a,a),(b,)),
    )
    assert s.histories==2
    assert s.unique_snapshots==2
    assert s.exact_replays_suppressed==1
    assert s.cases_needing_independent_bank_proof==2
    assert s.all_financial_effects_blocked
    assert not s.history_persisted
    assert not s.independent_bank_proof
    assert not s.contains_operation_ids
    assert OP not in repr(s) and ORDER not in repr(s)


def test_batch_exact_history_replay_is_deduplicated():
    a=(case(),)
    s=summarize_tenant_replay_histories(T,(a,a))
    assert s.histories==1


def test_batch_conflicting_operation_history_is_rejected():
    a=case()
    b=case(minute=11,attempts=1)
    with pytest.raises(FinancialOperationBlocked):
        summarize_tenant_replay_histories(T,((a,),(a,b)))


@pytest.mark.parametrize("collision",["order","payment"])
def test_batch_rejects_order_or_payment_alias(collision):
    a=case()
    updates=dict(
        operation_id="P_"+"b"*32,
        order_id=ORDER if collision=="order" else "ORD"+"Z"*12,
        payment_id=PAY if collision=="payment" else "PAY"+"Z"*12,
    )
    b=case(**updates)
    with pytest.raises(FinancialOperationBlocked):
        summarize_tenant_replay_histories(T,((a,),(b,)))


def test_missing_recovery_order_does_not_bypass_claimed_order_alias():
    a=case()
    b=case(operation_id="P_"+"b"*32,payment_id="PAY"+"Z"*12)
    # Neither recovery has a verified remote Order ID. The claims still
    # advertise the same Order, which must not silently bypass alias guard.
    a=replace(a,recovery=replace(a.recovery,order_id=None))
    b=replace(b,recovery=replace(b.recovery,order_id=None))
    h=replay_unresolved_history((a,))
    assert h.order_id == ORDER
    assert not h.steps[0].read_candidate_policy_only
    assert_all_financial_flags_false(h)
    with pytest.raises(FinancialOperationBlocked):
        summarize_tenant_replay_histories(T,((a,),(b,)))


def test_batch_cross_tenant_is_rejected():
    with pytest.raises(FinancialOperationBlocked):
        summarize_tenant_replay_histories(T,((case(tenant_id=OTHER),),))


@pytest.mark.parametrize("n",range(15))
def test_generated_tenants_never_mix(n):
    t=UUID(int=0xB0000+n+1)
    with pytest.raises(FinancialOperationBlocked):
        summarize_tenant_replay_histories(
            T,((case(tenant_id=t),),),
        )


@pytest.mark.parametrize("n",range(15))
def test_generated_operations_have_separate_history(n):
    op="P_"+format(n+1,"032x")
    order="ORD"+format(n+1,"012X")
    payment="PAY"+format(n+1,"012X")
    h=replay_unresolved_history((
        case(operation_id=op,order_id=order,payment_id=payment),
    ))
    assert h.operation_id==op
    assert_all_financial_flags_false(h)


def test_diagnostic_m12000_says_no_persistence_or_payments():
    with TestClient(app) as client:
        r=client.get("/api/health/features/m12000")
    assert r.status_code == 200
    d=r.json()
    assert d["workstream"]=="AI_STUDIO"
    assert d["contract"]=="AI_STUDIO_M12000_REPLAY_ROLLBACK_GUARD_OFFLINE_V1"
    assert d["history_contract"]==CONTRACT
    for flag in (
        "offline_monotonic_history_guard",
        "rollback_and_duplicate_snapshot_rejected",
        "cross_tenant_order_payment_alias_rejected",
        "closed_auth_state_remains_blocked",
    ):
        assert d[flag] is True,flag
    for flag in (
        "history_persisted", "operator_authenticated",
        "distributed_idempotency_registry",
        "real_provider_connected",
        "real_bank_statement_connected",
        "real_payments_enabled", "bank_reconciled",
        "ledger_written", "financial_effect_applied",
        "financial_closing_authorized", "payout_authorized",
        "oci_staging_deployed",
    ):
        assert d[flag] is False,flag
    urls={route.path for route in app.routes}
    assert "/api/v1/orders/mark-paid" not in urls
    assert "/api/v1/staging/incidents/release" not in urls
