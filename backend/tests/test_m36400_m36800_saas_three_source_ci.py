"""FR Finance M36400-M36800: three-source SaaS reconciliation, never a release."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from uuid import uuid4
import pytest

from app.saas_persisted_license_preflight import LicenseReadback
from app.saas_three_source_review_ci import (
    SaaSIntentFixture,SaaSGetFixture,SaaSStatementFixture,
    SaaSReviewHistoryFixture,SaaSReviewOperators,
    SaaSSettlementReview,evaluate_saas_staging_three_source,
)

NOW=datetime(2026,11,9,15,0,tzinfo=timezone.utc)

def example():
    tenant,payment,admin=uuid4(),uuid4(),uuid4()
    intent=SaaSIntentFixture(
        tenant_id=tenant,payment_intent_id=payment,administrator_id=admin,
        provider_payment_id="456789",collector_id="12345",
        external_reference="saas:ci-m36800",amount_cents=8990,
        price_version_cents=8990)
    readback=LicenseReadback("RLS_PRICE_PROVIDER_MATCH_REVIEW_ONLY",
        matched=True,digest="a"*64)
    provider=SaaSGetFixture(
        tenant_id=tenant,payment_intent_id=payment,provider_payment_id="456789",
        collector_id="12345",external_reference="saas:ci-m36800",
        amount_cents=8990,refunded_cents=0,
        checked_at=NOW-timedelta(minutes=4),evidence_sha256="a"*64)
    statement=SaaSStatementFixture(
        tenant_id=tenant,payment_intent_id=payment,provider_payment_id="456789",
        collector_id="12345",external_reference="saas:ci-m36800",
        gross_cents=8990,fee_cents=190,net_cents=8800,
        bank_reference="STMT-CI-M36800",
        settled_at=NOW-timedelta(hours=1),
        observed_at=NOW-timedelta(minutes=10),evidence_sha256="b"*64)
    h=(SaaSReviewHistoryFixture(
        tenant_id=tenant,payment_intent_id=payment,
        provider_payment_id="456789",kind="GET_MATCH_CANDIDATE",
        digest="a"*64,created_at=NOW-timedelta(minutes=2)),)
    operators=SaaSReviewOperators(
        administrator_id=admin,provider_observer_id=uuid4(),
        statement_observer_id=uuid4(),independent_reviewer_id=uuid4())
    return dict(intent=intent,readback=readback,provider=provider,
                statement=statement,history=h,operators=operators,now=NOW)

def evaluate(**overrides):
    d=example()
    d.update(overrides)
    return evaluate_saas_staging_three_source(**d)

def patched(key,**values):
    d=example()
    d[key]=replace(d[key],**values)
    return evaluate_saas_staging_three_source(**d)

def test_congruent_fixtures_remain_all_synthetic():
    args=example()
    a=evaluate_saas_staging_three_source(**args)
    b=evaluate_saas_staging_three_source(**args)
    assert a==b
    assert a.state=="CI_THREE_SOURCE_CONGRUENCE_REVIEW_ONLY"
    assert a.consistent_in_ci and len(a.evidence_digest)==64
    assert a.all_sources_synthetic
    assert not any(getattr(a,name) for name in (
        "independent_real_provider_attested",
        "bank_settlement_operationally_attested",
        "reviewer_identity_operationally_verified",
        "payment_marked_paid","license_activated","new_users_activated",
        "pix_authorized","production_authorized","writes_performed",
    ))
    assert "saas:ci-m36800" not in repr(a)
    assert "456789" not in repr(a)

@pytest.mark.parametrize("key,update,reason",[
    ("intent",{"price_version_cents":8991},"PAYMENT_PRICE_REFUND_OR_SETTLEMENT_MISMATCH"),
    ("intent",{"amount_cents":True},"PAYMENT_PRICE_REFUND_OR_SETTLEMENT_MISMATCH"),
    ("intent",{"status":"CANCELED"},"PAYMENT_PRICE_REFUND_OR_SETTLEMENT_MISMATCH"),
    ("intent",{"currency":"USD"},"LIVE_OR_CURRENCY_SCOPE_DENIED"),
    ("intent",{"live_mode":True},"LIVE_OR_CURRENCY_SCOPE_DENIED"),
    ("intent",{"collector_id":"12346"},"COLLECTOR_REFERENCE_OR_PAYMENT_ID_MISMATCH"),
    ("intent",{"provider_payment_id":"9/../../"},"COLLECTOR_REFERENCE_OR_PAYMENT_ID_MISMATCH"),
    ("intent",{"external_reference":"pix:tenant"},"COLLECTOR_REFERENCE_OR_PAYMENT_ID_MISMATCH"),
    ("intent",{"tenant_id":uuid4()},"CROSS_TENANT_OR_PAYMENT_MISMATCH"),
    ("intent",{"payment_intent_id":uuid4()},"CROSS_TENANT_OR_PAYMENT_MISMATCH"),
    ("intent",{"source":"WEBHOOK_CLIENT_JSON"},"UNTRUSTED_OR_LIVE_SOURCE"),
    ("provider",{"amount_cents":8991},"PAYMENT_PRICE_REFUND_OR_SETTLEMENT_MISMATCH"),
    ("provider",{"refunded_cents":1},"PAYMENT_PRICE_REFUND_OR_SETTLEMENT_MISMATCH"),
    ("provider",{"refunded_cents":False},"PAYMENT_PRICE_REFUND_OR_SETTLEMENT_MISMATCH"),
    ("provider",{"status":"charged_back"},"PAYMENT_PRICE_REFUND_OR_SETTLEMENT_MISMATCH"),
    ("provider",{"live_mode":True},"LIVE_OR_CURRENCY_SCOPE_DENIED"),
    ("provider",{"currency":"USD"},"LIVE_OR_CURRENCY_SCOPE_DENIED"),
    ("provider",{"collector_id":"99999"},"COLLECTOR_REFERENCE_OR_PAYMENT_ID_MISMATCH"),
    ("provider",{"external_reference":"saas:other-id"},"COLLECTOR_REFERENCE_OR_PAYMENT_ID_MISMATCH"),
    ("provider",{"tenant_id":uuid4()},"CROSS_TENANT_OR_PAYMENT_MISMATCH"),
    ("provider",{"payment_intent_id":uuid4()},"CROSS_TENANT_OR_PAYMENT_MISMATCH"),
    ("provider",{"checked_at":NOW-timedelta(minutes=16)},"STALE_FUTURE_OR_INVALID_EVIDENCE_TIME"),
    ("provider",{"checked_at":NOW+timedelta(seconds=1)},"STALE_FUTURE_OR_INVALID_EVIDENCE_TIME"),
    ("provider",{"checked_at":NOW.replace(tzinfo=None)},"STALE_FUTURE_OR_INVALID_EVIDENCE_TIME"),
    ("provider",{"evidence_sha256":"x"*64},"PROVIDER_READBACK_OR_DIGEST_NOT_BOUND"),
    ("provider",{"source":"UNVERIFIED_LIVE_MP"},"UNTRUSTED_OR_LIVE_SOURCE"),
    ("statement",{"source":"UNVERIFIED_BANK_API"},"UNTRUSTED_OR_LIVE_SOURCE"),
    ("statement",{"gross_cents":9000},"PAYMENT_PRICE_REFUND_OR_SETTLEMENT_MISMATCH"),
    ("statement",{"fee_cents":191},"PAYMENT_PRICE_REFUND_OR_SETTLEMENT_MISMATCH"),
    ("statement",{"net_cents":0},"PAYMENT_PRICE_REFUND_OR_SETTLEMENT_MISMATCH"),
    ("statement",{"fee_cents":-1},"PAYMENT_PRICE_REFUND_OR_SETTLEMENT_MISMATCH"),
    ("statement",{"tenant_id":uuid4()},"CROSS_TENANT_OR_PAYMENT_MISMATCH"),
    ("statement",{"payment_intent_id":uuid4()},"CROSS_TENANT_OR_PAYMENT_MISMATCH"),
    ("statement",{"provider_payment_id":"123"},"COLLECTOR_REFERENCE_OR_PAYMENT_ID_MISMATCH"),
    ("statement",{"currency":"USD"},"LIVE_OR_CURRENCY_SCOPE_DENIED"),
    ("statement",{"evidence_sha256":"a"*64},"PROVIDER_READBACK_OR_DIGEST_NOT_BOUND"),
    ("statement",{"bank_reference":"BAD"},"STALE_FUTURE_OR_INVALID_EVIDENCE_TIME"),
    ("statement",{"observed_at":NOW-timedelta(days=2)},"STALE_FUTURE_OR_INVALID_EVIDENCE_TIME"),
    ("statement",{"observed_at":NOW+timedelta(minutes=1)},"STALE_FUTURE_OR_INVALID_EVIDENCE_TIME"),
    ("statement",{"settled_at":NOW},"STALE_FUTURE_OR_INVALID_EVIDENCE_TIME"),
    ("statement",{"settled_at":NOW.replace(tzinfo=None)},"STALE_FUTURE_OR_INVALID_EVIDENCE_TIME"),
])
def test_reject_mismatch_and_stale_evidence(key,update,reason):
    result=patched(key,**update)
    assert result.state==reason and not result.consistent_in_ci
    assert not result.production_authorized and not result.writes_performed

def test_provider_review_is_bound_to_existing_m35800_result():
    for changed,reason in [
        ({"state":"AUTHENTICATED_GET_UNAVAILABLE_OR_BLOCKED"},"PROVIDER_READBACK_OR_DIGEST_NOT_BOUND"),
        ({"matched":False},"PROVIDER_READBACK_OR_DIGEST_NOT_BOUND"),
        ({"digest":"f"*64},"PROVIDER_READBACK_OR_DIGEST_NOT_BOUND"),
        ({"license_activated":True},"PROVIDER_READBACK_OR_DIGEST_NOT_BOUND"),
        ({"writes_performed":True},"PROVIDER_READBACK_OR_DIGEST_NOT_BOUND"),
    ]:
        assert patched("readback",**changed).state==reason

def test_no_double_control_or_fake_reviewer():
    d=example()
    for field in ("provider_observer_id","statement_observer_id","independent_reviewer_id"):
        d=example()
        d["operators"]=replace(d["operators"],**{field:d["operators"].administrator_id})
        assert evaluate_saas_staging_three_source(**d).state=="SEPARATION_OF_DUTIES_DENIED"
    d=example()
    d["operators"]=replace(d["operators"],source="USER_SUPPLIED_ROLE_FLAG")
    assert evaluate_saas_staging_three_source(**d).state=="UNTRUSTED_OR_LIVE_SOURCE"
    d=example()
    d["operators"]=replace(d["operators"],administrator_id=uuid4())
    assert evaluate_saas_staging_three_source(**d).state=="SEPARATION_OF_DUTIES_DENIED"

def test_append_only_history_and_hold_always_win():
    d=example()
    item=d["history"][0]
    for kind in ("REVERSAL_HOLD","PROVIDER_UNAVAILABLE_HOLD"):
        hold=replace(item,kind=kind,digest="c"*64,created_at=NOW-timedelta(minutes=1))
        d["history"]=(item,hold)
        out=evaluate_saas_staging_three_source(**d)
        assert out.state=="RECONCILIATION_HOLD_ACTIVE"
        assert not out.consistent_in_ci
    d["history"]=()
    assert evaluate_saas_staging_three_source(**d).state=="APPEND_ONLY_GET_CANDIDATE_ABSENT_OR_MISMATCHED"
    d["history"]=(replace(item,digest="c"*64),)
    assert evaluate_saas_staging_three_source(**d).state=="APPEND_ONLY_GET_CANDIDATE_ABSENT_OR_MISMATCHED"
    d["history"]=(item,item)
    assert evaluate_saas_staging_three_source(**d).state=="DUPLICATED_REVIEW_EVIDENCE"
    d["history"]=(replace(item,tenant_id=uuid4()),)
    assert evaluate_saas_staging_three_source(**d).state=="REVIEW_LOG_SCOPE_OR_INTEGRITY_DENIED"
    d["history"]=(replace(item,created_at=NOW+timedelta(seconds=1)),)
    assert evaluate_saas_staging_three_source(**d).state=="REVIEW_LOG_SCOPE_OR_INTEGRITY_DENIED"

def test_no_real_io_or_financial_mutation():
    from pathlib import Path
    source=(Path(__file__).resolve().parents[2]/
            "backend/app/saas_three_source_review_ci.py").read_text()
    for token in ("APIRouter","asyncpg.connect(","psycopg.connect(","httpx.",
                  "INSERT INTO ","UPDATE public.","DELETE FROM ",
                  "create_platform_pix","get_rls_db_connection("):
        assert token not in source
    assert "production_authorized: bool = False" in source
    assert "all_sources_synthetic: bool = True" in source
