"""M10300–M11000: retry identity, composite fingerprint, synthetic alias chaos.

ALL data are fabricated. No database, provider, bank, HTTP side effects or
financial authorization is exercised by this module.
"""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.mp_orders_case_integrity import (
    count_integrated_cases_for_tenant, inspect_integrated_case,
)
from app.mp_orders_evidence_discrepancy import (
    ClaimedChannel, ClaimedFinancialRecord, DiscrepancyContext,
)
from app.mp_orders_holds import HoldReason
from app.mp_orders_incident_ops import UnresolvedIncident
from app.mp_orders_incident_timeline import TimelineAction, make_timeline_event
from app.mp_orders_readonly_circuit import ReadonlyCircuitSnapshot
from app.mp_orders_recovery_scheduler import RecoverySignal, RecoverySnapshot
from app.mp_orders_tenant_queue import RecoveryCase, readonly_queue_preview
from app.pix_automation_contract import FinancialOperationBlocked


T = UUID("00000000-0000-4000-8000-0000000000a1")
OTHER = UUID("00000000-0000-4000-8000-0000000000b1")
REPORTER = UUID("00000000-0000-4000-8000-000000000001")
REVIEWER = UUID("00000000-0000-4000-8000-000000000002")
DATE = datetime(2026, 11, 5, 12, tzinfo=timezone.utc)
OP = "P_" + "a" * 32
ORDER = "ORD" + "A" * 12
PAY = "PAY" + "B" * 12


def synthetic_case(*, operation_id=OP, order_id=ORDER, payment_id=PAY,
                   tenant_id=T, attempts=0, fail_count=0,
                   signal=RecoverySignal.ORDER_PENDING):
    i = UnresolvedIncident(
        tenant_id=tenant_id, operation_id=operation_id,
        provider_account_id="2002", reason=HoldReason.BANK_MISSING,
        evidence_sha256="a" * 64, opened_at=DATE,
        reported_by=REPORTER,
    )
    opened = make_timeline_event(
        i, sequence=1, action=TimelineAction.OPENED,
        actor_id=REPORTER, recorded_at=DATE, previous_digest="0" * 64,
    )
    later = make_timeline_event(
        i, sequence=2, action=TimelineAction.BANK_PROOF_REQUESTED,
        actor_id=REVIEWER, recorded_at=DATE + timedelta(minutes=2),
        previous_digest=opened.digest,
    )
    def source(channel, number):
        return ClaimedFinancialRecord(
            channel=channel, tenant_id=tenant_id,
            provider_account_id="2002", operation_id=operation_id,
            order_id=order_id, payment_id=payment_id,
            gross_cents=15000, fee_cents=150, net_cents=14850,
            evidence_sha256=str(number) * 64,
            record_reference=f"REF-TEST-{number}",
            observed_at=DATE+timedelta(minutes=number),
        )
    evidence = DiscrepancyContext(
        provider=source(ClaimedChannel.PROVIDER_GET, 1),
        settlement=source(ClaimedChannel.SETTLEMENT_REPORT, 2),
        bank=source(ClaimedChannel.BANK_STATEMENT, 3),
        seller_revoked=False, provider_processed=True,
        dispute_pending=False, reversal_pending=False,
    )
    snap = DATE+timedelta(minutes=10)
    r = RecoverySnapshot(
        incident=i, order_id=order_id, signal=signal,
        attempts=attempts, now=snap,
        seller_approved=True, tenant_binding_verified=True,
    )
    circuit = ReadonlyCircuitSnapshot(
        tenant_id=tenant_id, provider_account_id="2002",
        operation_id=operation_id,
        observed_at=snap, failure_window_opened_at=DATE,
        failures_in_window=fail_count,
        last_failure_at=(DATE+timedelta(minutes=1) if fail_count else None),
        recovery_attempts=attempts,
        seller_approved=True, tenant_binding_verified=True,
    )
    from app.mp_orders_case_integrity import IntegratedCaseSnapshot
    return IntegratedCaseSnapshot(
        incident=i, timeline=(opened, later), claimed_evidence=evidence,
        recovery=r, circuit=circuit,
    )


def no_economic_authority(decision):
    assert decision.hold_active is True
    for key in (
        "verified_bank_source", "authenticated_operator_identity",
        "persisted_audit_trail", "get_execution_authorized",
        "mark_paid_authorized", "ledger_write_authorized",
        "hold_release_authorized", "payout_authorized",
        "financial_closing_authorized",
    ):
        assert getattr(decision, key) is False


@pytest.mark.parametrize("attempts", [0, 1, 2, 3, 5, 6, 10, 100])
def test_attempt_changes_never_reuse_composite_fingerprint(attempts):
    case=synthetic_case(attempts=attempts)
    result=inspect_integrated_case(case)
    baseline=inspect_integrated_case(synthetic_case())
    no_economic_authority(result)
    if attempts:
        assert result.case_fingerprint != baseline.case_fingerprint
    else:
        assert result.case_fingerprint == baseline.case_fingerprint


@pytest.mark.parametrize("field,value", [
    ("attempts", 1), ("attempts", 2), ("attempts", 6),
    ("attempts", 100), ("attempts", True),
])
def test_integrated_case_blocks_retry_counter_mismatch(field, value):
    case=synthetic_case()
    recovery=replace(case.recovery, **{field:value})
    with pytest.raises(FinancialOperationBlocked):
        inspect_integrated_case(replace(case,recovery=recovery))


@pytest.mark.parametrize("attempts", [1, 2, 5, 6, 10])
def test_queue_blocks_disagreeing_retry_counts(attempts):
    case=synthetic_case(attempts=0)
    circuit=replace(case.circuit,recovery_attempts=attempts)
    with pytest.raises(FinancialOperationBlocked):
        readonly_queue_preview(
            T,"2002",(RecoveryCase(case.recovery,circuit),),
        )


@pytest.mark.parametrize("fail_count", [0, 1, 2, 3, 4, 5, 8])
def test_failure_window_snapshot_modifies_case_fingerprint(fail_count):
    case=synthetic_case(fail_count=fail_count)
    decision=inspect_integrated_case(case)
    no_economic_authority(decision)
    if fail_count:
        assert decision.case_fingerprint != inspect_integrated_case(
            synthetic_case()
        ).case_fingerprint


@pytest.mark.parametrize("field,new_value", [
    ("retry_after_seconds", 55),
    ("retry_after_seconds", 600),
    ("retry_after_seconds", 0),
])
def test_retry_after_mutation_has_unique_audit_fingerprint(field,new_value):
    case=synthetic_case()
    changed=replace(case.recovery, **{field:new_value})
    a=inspect_integrated_case(case)
    b=inspect_integrated_case(replace(case,recovery=changed))
    assert a.case_fingerprint != b.case_fingerprint
    no_economic_authority(b)


def test_circuit_timestamp_does_not_vanish_from_audit():
    case=synthetic_case()
    modified=replace(
        case.circuit, failure_window_opened_at=DATE-timedelta(minutes=1),
    )
    first=inspect_integrated_case(case)
    second=inspect_integrated_case(replace(case,circuit=modified))
    assert first.case_fingerprint != second.case_fingerprint
    no_economic_authority(second)


def test_recovery_signal_modifies_fingerprint_even_for_unauthorized_get():
    case=synthetic_case(signal=RecoverySignal.GET_401)
    alt=synthetic_case(signal=RecoverySignal.GET_403)
    a=inspect_integrated_case(case)
    b=inspect_integrated_case(alt)
    assert a.case_fingerprint != b.case_fingerprint
    assert not a.read_candidate_policy_only
    assert not b.read_candidate_policy_only
    no_economic_authority(a)
    no_economic_authority(b)


def test_batch_rejects_two_operations_reusing_one_order():
    a=synthetic_case()
    b=synthetic_case(operation_id="P_"+"b"*32,payment_id="PAY"+"C"*12)
    with pytest.raises(FinancialOperationBlocked):
        count_integrated_cases_for_tenant(T,(a,b))


def test_batch_rejects_two_operations_reusing_one_payment():
    a=synthetic_case()
    b=synthetic_case(
        operation_id="P_"+"b"*32,order_id="ORD"+"Z"*12,
    )
    with pytest.raises(FinancialOperationBlocked):
        count_integrated_cases_for_tenant(T,(a,b))


def test_batch_accepts_distinct_valid_synthetic_operations():
    a=synthetic_case()
    b=synthetic_case(
        operation_id="P_"+"b"*32,order_id="ORD"+"Z"*12,
        payment_id="PAY"+"C"*12,
    )
    counts=count_integrated_cases_for_tenant(T,(a,b))
    assert counts.total_cases==2
    assert counts.get_candidates_policy_only==2
    assert counts.authenticated_source is False
    assert counts.bank_reconciled is False
    assert counts.financial_effect_applied is False


def test_batch_exact_replay_stays_deduplicated():
    a=synthetic_case()
    counts=count_integrated_cases_for_tenant(T,(a,a,a))
    assert counts.total_cases==1


def test_batch_replay_modified_snapshot_does_not_hide_under_same_id():
    a=synthetic_case()
    changed=replace(a.recovery,signal=RecoverySignal.ORDER_PROCESSED)
    with pytest.raises(FinancialOperationBlocked):
        count_integrated_cases_for_tenant(
            T,(a,replace(a,recovery=changed)),
        )


def test_queue_rejects_two_operations_sharing_one_order():
    a=synthetic_case()
    b=synthetic_case(operation_id="P_"+"b"*32,payment_id="PAY"+"C"*12)
    with pytest.raises(FinancialOperationBlocked):
        readonly_queue_preview(
            T,"2002",(RecoveryCase(a.recovery,a.circuit),
                      RecoveryCase(b.recovery,b.circuit)),
        )


def test_queue_distinct_orders_are_still_advisory_only():
    a=synthetic_case()
    b=synthetic_case(
        operation_id="P_"+"b"*32,order_id="ORD"+"Z"*12,
        payment_id="PAY"+"C"*12,
    )
    decision=readonly_queue_preview(
        T,"2002",(RecoveryCase(a.recovery,a.circuit),
                  RecoveryCase(b.recovery,b.circuit)),
    )
    assert decision.scanned==2
    assert decision.eligible_candidates==2
    assert len(decision.get_candidates)==2
    assert decision.get_execution_authorized is False
    assert decision.ledger_write_authorized is False
    assert decision.money_movement_authorized is False


@pytest.mark.parametrize("n",range(12))
def test_generated_synthetic_tenants_cannot_read_another_tenant(n):
    tenant=UUID(int=0xA1000+n+1)
    case=synthetic_case(tenant_id=tenant)
    if tenant==T:
        pytest.skip("distinct generated tenants required")
    with pytest.raises(FinancialOperationBlocked):
        count_integrated_cases_for_tenant(T,(case,))
    with pytest.raises(FinancialOperationBlocked):
        readonly_queue_preview(
            T,"2002",(RecoveryCase(case.recovery,case.circuit),),
        )


@pytest.mark.parametrize("n",range(10))
def test_generated_distinct_operations_no_collision(n):
    op="P_"+format(n+1,"032x")
    order_id="ORD"+format(n+1,"012X")
    pay_id="PAY"+format(n+1,"012X")
    case=synthetic_case(
        operation_id=op,order_id=order_id,payment_id=pay_id,
    )
    result=inspect_integrated_case(case)
    assert result.operation_id==op
    no_economic_authority(result)


def test_m11000_health_advertises_offline_not_live():
    with TestClient(app) as client:
        r=client.get("/api/health/features/m11000")
    assert r.status_code==200
    d=r.json()
    assert d["workstream"]=="AI_STUDIO"
    assert d["contract"]=="AI_STUDIO_M11000_RETRY_ALIAS_INTEGRITY_OFFLINE_V1"
    for key in (
        "complete_retry_snapshot_fingerprint",
        "strict_recovery_attempt_binding",
        "local_batch_order_payment_alias_rejected",
        "deterministic_negative_synthetic_regressions",
    ):
        assert d[key] is True,key
    for key in (
        "persisted_deduplication_registry",
        "real_provider_order_get",
        "real_bank_evidence",
        "operator_signatures_verified",
        "audit_log_persisted",
        "oci_staging_deployed",
        "real_payments_enabled",
        "bank_reconciled",
        "ledger_written",
        "financial_effect_applied",
        "payout_authorized",
        "financial_closing_authorized",
    ):
        assert d[key] is False,key
    for forbidden in ("/api/v1/orders/reconcile-and-pay",
                      "/api/v1/staging/incidents/release",
                      "/api/v1/finance/payout"):
        assert forbidden not in {route.path for route in app.routes}
