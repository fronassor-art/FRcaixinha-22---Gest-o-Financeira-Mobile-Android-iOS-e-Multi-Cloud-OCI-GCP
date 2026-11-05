"""AI Studio M12100-M13000: restart checkpoint / staging readiness safety."""
from dataclasses import replace, fields
from datetime import timedelta
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.mp_orders_replay_checkpoint import (
    CONTRACT as CHECKPOINT_CONTRACT,
    OfflineCheckpoint, make_offline_checkpoint, validate_offline_restart,
)
from app.mp_orders_staging_readiness import (
    CONTRACT as READINESS_CONTRACT, REQUIRED_EVIDENCE,
    StagingReadinessClaims, inspect_readiness_claims,
    summarize_readiness_claims,
)
from app.pix_automation_contract import FinancialOperationBlocked
from test_m12000_replay_rollback_ci import (
    case, T, OTHER, OP, ORDER, PAY,
)


def test_offline_checkpoint_is_deterministic_but_not_authenticated():
    sequence=(case(),case(minute=11,attempts=1))
    a=make_offline_checkpoint(sequence)
    b=make_offline_checkpoint(sequence)
    assert a==b
    assert len(a.checksum)==64 and a.unique_steps==2
    assert a.snapshot_count==2
    assert a.claimed_order_id==ORDER and a.claimed_payment_id==PAY
    assert a.hold_active
    assert a.trust_anchor_authenticated is False
    assert a.checkpoint_persisted is False
    assert a.operator_authenticated is False
    assert a.externally_signed is False
    assert a.get_execution_authorized is False
    assert a.financial_effect_authorized is False
    assert a.ledger_write_authorized is False
    assert a.payout_authorized is False


def test_restart_accepts_identical_prefix_and_appended_progress():
    first=(case(),case(minute=11,attempts=1))
    continued=first+(case(minute=12,attempts=2),)
    review=validate_offline_restart(
        make_offline_checkpoint(first),first,continued,
    )
    assert review.prefix_verified_against_supplied_claim
    assert review.new_unique_steps==1
    assert review.new_exact_replays==0
    assert review.hold_active
    for key in (
        "trusted_checkpoint_source_verified","crash_consistency_proven",
        "durable_store_updated","operator_authenticated",
        "get_execution_authorized","ledger_write_authorized",
        "financial_effect_authorized","payout_authorized",
    ):
        assert getattr(review,key) is False


def test_restart_with_no_new_snapshots_does_not_claim_persistence():
    before=(case(),)
    r=validate_offline_restart(make_offline_checkpoint(before),before,before)
    assert r.new_unique_steps==0
    assert r.new_exact_replays==0
    assert r.durable_store_updated is False


def test_restart_deduplicates_exact_replayed_snapshot():
    before=(case(),)
    resumed=before+(before[-1],)
    r=validate_offline_restart(make_offline_checkpoint(before),before,resumed)
    assert r.new_unique_steps==0
    assert r.new_exact_replays==1
    assert r.get_execution_authorized is False


@pytest.mark.parametrize("field,value",[
    ("history_head_digest","a"*64),
    ("checksum","b"*64),
    ("last_attempts",2),
    ("snapshot_count",0),
    ("unique_steps",100),
    ("exact_replays",999),
    ("tenant_id",OTHER),
    ("operation_id","P_"+"b"*32),
    ("claimed_order_id","ORD"+"Z"*12),
    ("claimed_payment_id","PAY"+"Z"*12),
    ("checkpoint_persisted",True),
    ("trust_anchor_authenticated",True),
    ("get_execution_authorized",True),
    ("financial_effect_authorized",True),
    ("ledger_write_authorized",True),
    ("payout_authorized",True),
])
def test_any_mutated_checkpoint_field_fails_closed(field,value):
    prior=(case(),)
    original=make_offline_checkpoint(prior)
    poisoned=replace(original,**{field:value})
    with pytest.raises(FinancialOperationBlocked):
        validate_offline_restart(poisoned,prior,prior)


def test_prefix_reorder_or_older_prefix_rejected():
    first=(case(),case(minute=11,attempts=1))
    expected=make_offline_checkpoint(first)
    with pytest.raises(FinancialOperationBlocked):
        validate_offline_restart(
            expected,first,(first[1],first[0]),
        )


def test_prefix_changed_snapshot_rejected():
    first=(case(),)
    modified=(case(attempts=1),)
    with pytest.raises(FinancialOperationBlocked):
        validate_offline_restart(
            make_offline_checkpoint(first),first,modified,
        )


@pytest.mark.parametrize("variation",[
    {"operation_id":"P_"+"b"*32},
    {"tenant_id":OTHER},
    {"order_id":"ORD"+"Z"*12},
    {"payment_id":"PAY"+"Z"*12},
])
def test_restart_identity_change_on_new_snapshot_rejected(variation):
    first=(case(),)
    newest=case(minute=11,**variation)
    with pytest.raises(FinancialOperationBlocked):
        validate_offline_restart(
            make_offline_checkpoint(first),first,first+(newest,),
        )


@pytest.mark.parametrize("variation",[
    {"minute":9},
    {"minute":10, "attempts":1},
    {"minute":11,"attempts":3},
])
def test_restart_time_rollback_or_retry_jump_rejected(variation):
    first=(case(),)
    next_one=case(**variation)
    with pytest.raises(FinancialOperationBlocked):
        validate_offline_restart(
            make_offline_checkpoint(first),first,first+(next_one,),
        )


@pytest.mark.parametrize("bad",[
    None, "", [], {}, 1, True, (case(),), object(),
])
def test_checkpoint_type_and_prefix_type_fail_closed(bad):
    first=(case(),)
    with pytest.raises(FinancialOperationBlocked):
        validate_offline_restart(bad,first,first)
    with pytest.raises(FinancialOperationBlocked):
        validate_offline_restart(
            make_offline_checkpoint(first),bad,first,
        )


def test_checkpoints_over_64_snapshots_rejected():
    first=(case(),)
    with pytest.raises(FinancialOperationBlocked):
        make_offline_checkpoint(first*65)
    with pytest.raises(FinancialOperationBlocked):
        validate_offline_restart(
            make_offline_checkpoint(first),first,first*65,
        )


def test_readiness_defaults_are_all_missing_and_fail_closed():
    c=StagingReadinessClaims(tenant_id=T,provider_account_id="2002")
    r=inspect_readiness_claims(c)
    assert r.claims_true==0
    assert r.requirements_total==len(REQUIRED_EVIDENCE)==24
    assert r.claims_missing==REQUIRED_EVIDENCE
    assert r.all_requirements_claimed is False
    assert not any((
        r.all_evidence_authenticated,r.apply_migration_authorized,
        r.oci_deploy_authorized,r.authenticated_persistence_ready,
        r.independent_bank_reconciliation_passed,r.real_payment_authorized,
        r.financial_closing_authorized,r.ledger_write_authorized,
        r.payout_authorized,
    ))


def test_even_all_true_self_attested_requirements_do_not_authorize_anything():
    c=StagingReadinessClaims(
        tenant_id=T,provider_account_id="2002",
        **dict.fromkeys(REQUIRED_EVIDENCE,True),
    )
    r=inspect_readiness_claims(c)
    assert r.claims_true==len(REQUIRED_EVIDENCE)
    assert r.all_requirements_claimed
    assert r.claims_missing==()
    assert r.all_evidence_authenticated is False
    assert r.apply_migration_authorized is False
    assert r.oci_deploy_authorized is False
    assert r.authenticated_persistence_ready is False
    assert r.independent_bank_reconciliation_passed is False
    assert r.real_payment_authorized is False
    assert r.financial_closing_authorized is False
    assert r.ledger_write_authorized is False
    assert r.payout_authorized is False


@pytest.mark.parametrize("requirement",REQUIRED_EVIDENCE)
def test_each_required_control_is_missing_when_not_self_declared(requirement):
    all_claims=dict.fromkeys(REQUIRED_EVIDENCE,True)
    all_claims[requirement]=False
    c=StagingReadinessClaims(
        tenant_id=T,provider_account_id="2002",**all_claims,
    )
    r=inspect_readiness_claims(c)
    assert r.claims_true==23
    assert r.claims_missing==(requirement,)
    assert r.all_requirements_claimed is False
    assert r.apply_migration_authorized is False


@pytest.mark.parametrize("invalid",[
    {"tenant_id":UUID(int=0)},
    {"provider_account_id":""},
    {"provider_account_id":"x2002"},
    {"provider_account_id":"2002\\n"},
    {"provider_account_id":"2002"*11},
    {"tenant_rls_forced":1},
    {"bank_source_independently_authenticated":"true"},
    {"operator_revocation_tested":None},
])
def test_staging_readiness_invalid_claims_rejected(invalid):
    c=StagingReadinessClaims(
        tenant_id=T,provider_account_id="2002",
    )
    with pytest.raises(FinancialOperationBlocked):
        inspect_readiness_claims(replace(c,**invalid))


def test_readiness_report_redacts_seller_and_is_only_counts():
    c=StagingReadinessClaims(
        tenant_id=T,provider_account_id="2002",tenant_rls_enabled=True,
    )
    report=inspect_readiness_claims(c)
    assert "2002" not in repr(report)
    assert "2002" not in report.claims_missing


def test_batch_rejects_duplicate_tenant_and_shared_seller():
    a=StagingReadinessClaims(tenant_id=T,provider_account_id="2002")
    b=StagingReadinessClaims(tenant_id=OTHER,provider_account_id="2002")
    with pytest.raises(FinancialOperationBlocked):
        summarize_readiness_claims((a,a))
    with pytest.raises(FinancialOperationBlocked):
        summarize_readiness_claims((a,b))


def test_batch_allows_two_distinct_tenants_but_never_authorizes_deploy():
    a=StagingReadinessClaims(
        tenant_id=T,provider_account_id="2002",
        tenant_rls_enabled=True,
    )
    b=StagingReadinessClaims(
        tenant_id=OTHER,provider_account_id="3003",
        **dict.fromkeys(REQUIRED_EVIDENCE,True),
    )
    r=summarize_readiness_claims((a,b))
    assert r.tenant_count==2
    assert r.requirements_total==48
    assert r.claims_true_total==25
    assert r.claimed_complete_tenants==1
    assert r.all_evidence_authenticated is False
    assert r.deployment_authorized is False
    assert r.real_payment_authorized is False
    assert r.ledger_write_authorized is False


def test_batch_empty_is_not_authority():
    r=summarize_readiness_claims(())
    assert r.tenant_count==0
    assert r.deployment_authorized is False
    assert r.real_payment_authorized is False


def test_batch_over_100_tenants_rejected():
    c=StagingReadinessClaims(tenant_id=T,provider_account_id="2002")
    with pytest.raises(FinancialOperationBlocked):
        summarize_readiness_claims((c,)*101)


def test_health_contract_m13000_is_explicitly_non_authoritative():
    with TestClient(app) as client:
        response=client.get("/api/health/features/m13000")
    assert response.status_code==200
    d=response.json()
    assert d["workstream"]=="AI_STUDIO"
    assert d["contract"]=="AI_STUDIO_M13000_CHECKPOINT_READINESS_OFFLINE_V1"
    assert d["restart_contract"]==CHECKPOINT_CONTRACT
    assert d["readiness_contract"]==READINESS_CONTRACT
    for key in (
        "snapshot_prefix_consistency_checked",
        "claimed_high_watermark_compared",
        "staging_requirements_enumerated",
        "readiness_claims_typed",
    ):
        assert d[key] is True,key
    for key in (
        "checkpoint_persisted","checkpoint_source_authenticated",
        "operator_identity_authenticated","globally_unique_idempotency",
        "real_bank_reconciled","independent_bank_evidence_verified",
        "oci_staging_deployed","real_payments_enabled","ledger_written",
        "financial_effect_applied","payout_authorized",
        "financial_closing_authorized","migration_apply_authorized",
    ):
        assert d[key] is False,key
    all_paths={route.path for route in app.routes}
    assert "/api/v1/staging/migrations/apply" not in all_paths
    assert "/api/v1/orders/mark-paid" not in all_paths
