"""M8000-M8600 adversarial, offline-only financial boundary tests."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.mp_orders_evidence_discrepancy import (
    CONTRACT as EVIDENCE, ClaimedChannel, ClaimedFinancialRecord,
    DiscrepancyContext, ReviewOutcome, review_claimed_three_source,
)
from app.mp_orders_readonly_circuit import (
    CONTRACT as CIRCUIT, ReadonlyAction, ReadonlyCircuitSnapshot,
    decide_readonly_circuit,
)
from app.pix_automation_contract import FinancialOperationBlocked


T = UUID("00000000-0000-4000-8000-0000000000a1")
B = UUID("00000000-0000-4000-8000-0000000000b1")
DATE = datetime(2026, 11, 5, tzinfo=timezone.utc)
OP = "P_" + "a" * 32
ORDER = "ORD" + "A" * 12
PAY = "PAY" + "B" * 12


def record(channel, index):
    return ClaimedFinancialRecord(
        channel=channel, tenant_id=T, provider_account_id="2002",
        operation_id=OP, order_id=ORDER, payment_id=PAY,
        gross_cents=15000, fee_cents=150, net_cents=14850,
        evidence_sha256=str(index)*64, record_reference="RECORD-000" + str(index),
        observed_at=DATE + timedelta(days=index),
    )


def context(**updates):
    data=dict(
        provider=record(ClaimedChannel.PROVIDER_GET,1),
        settlement=record(ClaimedChannel.SETTLEMENT_REPORT,2),
        bank=record(ClaimedChannel.BANK_STATEMENT,3),
        seller_revoked=False, provider_processed=True,
        dispute_pending=False, reversal_pending=False,
    )
    data.update(updates)
    return DiscrepancyContext(**data)


def circuit(**updates):
    data=dict(
        tenant_id=T, provider_account_id="2002", operation_id=OP,
        observed_at=DATE + timedelta(minutes=3),
        failure_window_opened_at=DATE,
        failures_in_window=1, last_failure_at=DATE + timedelta(minutes=1),
        recovery_attempts=1, seller_approved=True,
        tenant_binding_verified=True,
    )
    data.update(updates)
    return ReadonlyCircuitSnapshot(**data)


def assert_no_financial_authority(d):
    for key in ("bank_reconciled","ledger_written","mark_paid_authorized",
                "payout_authorized","financial_closing_authorized",
                "independent_origin_verified"):
        assert getattr(d,key) is False, key
    assert d.hold_required is True


@pytest.mark.parametrize("changes,outcome",[
    ({},ReviewOutcome.UNVERIFIED_SOURCE),
    ({"seller_revoked":True},ReviewOutcome.SELLER_REVOKED),
    ({"provider_processed":False},ReviewOutcome.PROVIDER_NOT_PROCESSED),
    ({"dispute_pending":True},ReviewOutcome.DISPUTE_PENDING),
    ({"reversal_pending":True},ReviewOutcome.REVERSAL_PENDING),
    ({"bank":replace(record(ClaimedChannel.BANK_STATEMENT,3),
                      evidence_sha256="2"*64)},ReviewOutcome.DUPLICATE_EVIDENCE),
    ({"bank":replace(record(ClaimedChannel.BANK_STATEMENT,3),
                      fee_cents=100,net_cents=14900)},ReviewOutcome.AMOUNT_MISMATCH),
    ({"bank":replace(record(ClaimedChannel.BANK_STATEMENT,3),
                      observed_at=DATE+timedelta(days=35))},
       ReviewOutcome.SETTLEMENT_DATE_REVIEW),
])
def test_all_evidence_outcomes_remain_on_hold(changes,outcome):
    result=review_claimed_three_source(context(**changes))
    assert result.outcome is outcome
    assert len(result.case_fingerprint)==64
    assert_no_financial_authority(result)


@pytest.mark.parametrize("field,value",[
    ("tenant_id",B),
    ("provider_account_id","9999"),
    ("operation_id","P_"+"b"*32),
    ("order_id","ORD"+"Z"*12),
    ("payment_id","PAY"+"Z"*12),
])
def test_cross_binding_is_never_accepted(field,value):
    altered=replace(record(ClaimedChannel.BANK_STATEMENT,3),**{field:value})
    with pytest.raises(FinancialOperationBlocked):
        review_claimed_three_source(context(bank=altered))


@pytest.mark.parametrize("field,value",[
    ("gross_cents",True),
    ("gross_cents",0),
    ("fee_cents",-1),
    ("net_cents",10000),
    ("evidence_sha256","G"*64),
    ("evidence_sha256","a"*63),
    ("record_reference","../secret?"),
    ("observed_at",datetime(2026,11,5)),
    ("channel","BANK_STATEMENT"),
])
def test_forged_or_invalid_source_metadata_rejected(field,value):
    altered=replace(record(ClaimedChannel.BANK_STATEMENT,3),**{field:value})
    with pytest.raises(FinancialOperationBlocked):
        review_claimed_three_source(context(bank=altered))


def test_three_claims_have_no_authentication_even_when_consistent():
    r=review_claimed_three_source(context())
    assert r.outcome is ReviewOutcome.UNVERIFIED_SOURCE
    assert_no_financial_authority(r)
    assert r==review_claimed_three_source(context())
    altered=replace(record(ClaimedChannel.BANK_STATEMENT,3),
                    record_reference="RECORD-CHANGED")
    changed=review_claimed_three_source(context(bank=altered))
    assert changed.case_fingerprint != r.case_fingerprint


def test_source_labels_cannot_be_interchanged():
    forged=replace(record(ClaimedChannel.BANK_STATEMENT,3),
                   channel=ClaimedChannel.PROVIDER_GET)
    with pytest.raises(FinancialOperationBlocked):
        review_claimed_three_source(context(bank=forged))


@pytest.mark.parametrize("updates,action",[
    ({},ReadonlyAction.GET_CANDIDATE_ONLY),
    ({"seller_approved":False},ReadonlyAction.SELLER_BLOCKED),
    ({"tenant_binding_verified":False},ReadonlyAction.SELLER_BLOCKED),
    ({"recovery_attempts":6},ReadonlyAction.HUMAN_PROVIDER_REVIEW),
    ({"failures_in_window":5},ReadonlyAction.CIRCUIT_OPEN),
    ({"failures_in_window":5,
      "observed_at":DATE+timedelta(minutes=40)},
      ReadonlyAction.HUMAN_PROVIDER_REVIEW),
    ({"observed_at":DATE+timedelta(minutes=1,seconds=3)},
      ReadonlyAction.WAIT_COOLDOWN),
])
def test_recovery_circuit_is_advisory_only(updates,action):
    d=decide_readonly_circuit(circuit(**updates))
    assert d.action is action
    for key in ("can_execute_get","can_post_order","can_mark_paid",
                "can_release_hold","can_write_ledger","can_issue_payout"):
        assert getattr(d,key) is False,key


@pytest.mark.parametrize("changes",[
    {"tenant_id":UUID(int=0)},
    {"provider_account_id":"1;DROP"},
    {"operation_id":"P_bad"},
    {"observed_at":datetime(2026,11,5)},
    {"failure_window_opened_at":datetime(2026,11,5)},
    {"failure_window_opened_at":DATE+timedelta(days=1)},
    {"failures_in_window":True},
    {"failures_in_window":-1},
    {"failures_in_window":0},
    {"last_failure_at":DATE+timedelta(days=1)},
    {"recovery_attempts":True},
    {"seller_approved":1},
    {"tenant_binding_verified":1},
])
def test_circuit_invalid_state_is_blocked(changes):
    with pytest.raises(FinancialOperationBlocked):
        decide_readonly_circuit(circuit(**changes))


def test_circuit_clean_window_yields_only_candidate_not_permission():
    d=decide_readonly_circuit(circuit(
        failures_in_window=0,last_failure_at=None,recovery_attempts=0
    ))
    assert d.action is ReadonlyAction.GET_CANDIDATE_ONLY
    assert not d.can_execute_get


def test_circuit_backoff_is_deterministic_and_not_later_than_5m():
    a=decide_readonly_circuit(circuit(
        failures_in_window=4,
        observed_at=DATE+timedelta(minutes=1,seconds=1),
    ))
    b=decide_readonly_circuit(circuit(
        failures_in_window=4,
        observed_at=DATE+timedelta(minutes=1,seconds=1),
    ))
    assert a==b
    assert a.action is ReadonlyAction.WAIT_COOLDOWN
    assert a.retry_not_before==DATE+timedelta(minutes=3)


def test_health_gate_m8600_and_absence_of_live_routes():
    with TestClient(app) as client:
        r=client.get("/api/health/features/m8600")
    assert r.status_code==200
    d=r.json()
    assert d["workstream"]=="AI_STUDIO"
    assert d["contract"]=="AI_STUDIO_M8600_DISCREPANCY_CIRCUIT_OFFLINE_V1"
    assert d["evidence_contract"]==EVIDENCE
    assert d["circuit_contract"]==CIRCUIT
    for key in ("three_source_claim_comparison_only",
                "readonly_circuit_policy_only",
                "cross_tenant_evidence_rejected"):
        assert d[key] is True
    for key in ("real_provider_connected","real_bank_statement_reader_connected",
                "recovery_circuit_persistent","review_digest_persisted",
                "real_payments_enabled","bank_reconciled","ledger_written",
                "financial_effect_applied","payout_authorized",
                "financial_closing_authorized","oci_staging_deployed"):
        assert d[key] is False,key
    assert "/api/v1/financial/settle" not in {route.path for route in app.routes}
