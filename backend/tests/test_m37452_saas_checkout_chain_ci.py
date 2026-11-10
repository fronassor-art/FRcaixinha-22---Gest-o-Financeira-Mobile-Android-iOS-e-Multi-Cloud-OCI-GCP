"""M37452 checkout chain: synthetic, immutable, fail-closed regression tests."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

import pytest

from app.saas_checkout_chain_ci import (
    ContractProof, OfferProof, ProviderProof, ReconciliationProof, review_checkout,
)

NOW = datetime(2026, 11, 10, 14, 0, tzinfo=timezone.utc)
T = UUID("a7410000-0000-4000-8000-000000000001")
ADMIN = UUID("a7410000-0000-4000-8000-000000000002")
VERSION = UUID("a7410000-0000-4000-8000-000000000003")
DOC = UUID("a7410000-0000-4000-8000-000000000004")
INTENT = UUID("a7410000-0000-4000-8000-000000000005")
OTHER = UUID("a7410000-0000-4000-8000-000000000006")
PROVIDER_OBSERVER = UUID("a7410000-0000-4000-8000-000000000007")
STATEMENT_OBSERVER = UUID("a7410000-0000-4000-8000-000000000008")
REVIEWER = UUID("a7410000-0000-4000-8000-000000000009")


def fixtures(period="MONTHLY"):
    contract = ContractProof(
        tenant_id=T, administrator_id=ADMIN, published_document_id=DOC,
        accepted_document_id=DOC, accepted_by=ADMIN,
        published_sha256="a"*64, accepted_sha256="a"*64,
        published_at=NOW-timedelta(days=3),
        accepted_at=NOW-timedelta(days=2), explicit_consent=True,
    )
    offer = OfferProof(
        tenant_id=T, administrator_id=ADMIN,
        price_version_id=VERSION, preparation_price_version_id=VERSION,
        tier="ESSENCIAL", preparation_tier="ESSENCIAL",
        plan_status="ACTIVE", period=period, monthly_cents=19937,
        annual_cents=199370, expected_cents=19937 if period=="MONTHLY" else 199370,
        currency="BRL", preparation_status="PENDING_PAYMENT",
        prepared_at=NOW-timedelta(days=1),
    )
    provider = ProviderProof(
        tenant_id=T, administrator_id=ADMIN, payment_intent_id=INTENT,
        price_version_id=VERSION, provider_payment_id="12345678",
        collector_id="12345", platform_collector_id="12345",
        external_reference=f"saas:{INTENT}",
        provider_amount_cents=offer.expected_cents, refunded_cents=0,
        status="approved", live_mode=False,
        checked_at=NOW-timedelta(minutes=5), evidence_sha256="b"*64,
    )
    reconciliation = ReconciliationProof(
        tenant_id=T, payment_intent_id=INTENT, provider_payment_id="12345678",
        provider_digest="b"*64, statement_digest="c"*64,
        review_digest="d"*64, gross_cents=offer.expected_cents,
        fee_cents=90, net_cents=offer.expected_cents-90,
        observed_at=NOW-timedelta(minutes=2),
        administrator_id=ADMIN, provider_observer_id=PROVIDER_OBSERVER,
        statement_observer_id=STATEMENT_OBSERVER,
        independent_reviewer_id=REVIEWER,
        state="CI_THREE_SOURCE_CONGRUENCE_REVIEW_ONLY",
    )
    return contract, offer, provider, reconciliation


def evaluate(*, contract=None, offer=None, provider="include",
             reconciliation="include", now=NOW):
    c, o, p, r = fixtures()
    if contract is not None:
        c=contract
    if offer is not None:
        o=offer
    if provider != "include":
        p=provider
    if reconciliation != "include":
        r=reconciliation
    return review_checkout(contract=c, offer=o, provider=p,
                           reconciliation=r, now=now)


def deny_all_real_effects(result):
    assert result.contract_legally_verified is False
    assert result.provider_operationally_verified is False
    assert result.payment_settled is False
    assert result.license_created is False
    assert result.user_activated is False
    assert result.pix_authorized is False
    assert result.production_authorized is False
    assert result.writes_performed is False


@pytest.mark.parametrize("period", ["MONTHLY", "ANNUAL"])
def test_complete_hypothetical_chain_has_no_financial_authority(period):
    c,o,p,r=fixtures(period)
    result=review_checkout(contract=c,offer=o,provider=p,reconciliation=r,now=NOW)
    assert result.state=="CI_CHECKOUT_CHAIN_CONSISTENT_REVIEW_ONLY"
    assert result.hypothetical_consistency is True
    assert len(result.evidence_digest)==64
    assert result == review_checkout(contract=c,offer=o,provider=p,
                                     reconciliation=r,now=NOW)
    deny_all_real_effects(result)


def test_no_payment_is_not_a_paid_or_licensed_subscription():
    c,o,_,_=fixtures()
    result=review_checkout(contract=c,offer=o,now=NOW)
    assert result.state=="CONTRACT_OFFER_REVIEW_CI_ONLY"
    assert result.hypothetical_consistency is True
    assert result.evidence_digest is None
    deny_all_real_effects(result)


def test_provider_only_cannot_grant_license():
    c,o,p,_=fixtures()
    result=review_checkout(contract=c,offer=o,provider=p,now=NOW)
    assert result.state=="PROVIDER_MATCH_REVIEW_CI_ONLY"
    deny_all_real_effects(result)


def test_reconciliation_without_provider_is_denied():
    result=evaluate(provider=None)
    assert result.state=="MISSING_OR_INVALID_PROVIDER_EVIDENCE"
    deny_all_real_effects(result)


@pytest.mark.parametrize("changes,code",[
    ({"source":"HTTP_JSON"},"UNTRUSTED_SOURCE"),
    ({"accepted_by":OTHER},"TENANT_OR_ADMIN_SCOPE_MISMATCH"),
    ({"tenant_id":OTHER},"TENANT_OR_ADMIN_SCOPE_MISMATCH"),
    ({"accepted_document_id":OTHER},"CONTRACT_CONSENT_UNVERIFIED"),
    ({"accepted_sha256":"c"*64},"CONTRACT_CONSENT_UNVERIFIED"),
    ({"explicit_consent":False},"CONTRACT_CONSENT_UNVERIFIED"),
    ({"explicit_consent":1},"INVALID_CONTRACT_OR_OFFER_TYPES"),
    ({"accepted_at":NOW+timedelta(days=1)},"CONTRACT_CONSENT_UNVERIFIED"),
    ({"published_at":NOW},"CONTRACT_CONSENT_UNVERIFIED"),
    ({"accepted_at":datetime(2026,11,9)},"INVALID_CONTRACT_OR_OFFER_TYPES"),
    ({"published_sha256":"invalid"},"CONTRACT_CONSENT_UNVERIFIED"),
])
def test_contract_attestation_fail_closed(changes,code):
    c,_,_,_=fixtures()
    result=evaluate(contract=replace(c,**changes))
    assert result.state==code
    deny_all_real_effects(result)


@pytest.mark.parametrize("changes,code",[
    ({"source":"BROWSER"},"UNTRUSTED_SOURCE"),
    ({"tenant_id":OTHER},"TENANT_OR_ADMIN_SCOPE_MISMATCH"),
    ({"administrator_id":OTHER},"TENANT_OR_ADMIN_SCOPE_MISMATCH"),
    ({"price_version_id":OTHER},"UNBOUND_OR_INVALID_PRICE_VERSION"),
    ({"preparation_tier":"AMPLIADO"},"UNBOUND_OR_INVALID_PRICE_VERSION"),
    ({"plan_status":"BLOCKED"},"UNBOUND_OR_INVALID_PRICE_VERSION"),
    ({"period":"WEEKLY"},"UNBOUND_OR_INVALID_PRICE_VERSION"),
    ({"annual_cents":199371},"UNBOUND_OR_INVALID_PRICE_VERSION"),
    ({"expected_cents":10000},"UNBOUND_OR_INVALID_PRICE_VERSION"),
    ({"expected_cents":True},"UNBOUND_OR_INVALID_PRICE_VERSION"),
    ({"currency":"USD"},"UNBOUND_OR_INVALID_PRICE_VERSION"),
    ({"preparation_status":"ACTIVE"},"UNBOUND_OR_INVALID_PRICE_VERSION"),
    ({"prepared_at":NOW-timedelta(days=10)},"CONTRACT_CONSENT_UNVERIFIED"),
])
def test_price_and_preparation_fail_closed(changes,code):
    _,o,_,_=fixtures()
    result=evaluate(offer=replace(o,**changes))
    assert result.state==code
    deny_all_real_effects(result)


@pytest.mark.parametrize("changes,code",[
    ({"source":"WEBHOOK_JSON"},"UNTRUSTED_PROVIDER_SOURCE"),
    ({"tenant_id":OTHER},"PROVIDER_TENANT_ADMIN_OR_PRICE_MISMATCH"),
    ({"administrator_id":OTHER},"PROVIDER_TENANT_ADMIN_OR_PRICE_MISMATCH"),
    ({"price_version_id":OTHER},"PROVIDER_TENANT_ADMIN_OR_PRICE_MISMATCH"),
    ({"live_mode":True},"PROVIDER_PAYMENT_NOT_ATTESTED_IN_CI"),
    ({"live_mode":1},"INVALID_PROVIDER_FIELDS"),
    ({"collector_id":"999"},"PROVIDER_PAYMENT_NOT_ATTESTED_IN_CI"),
    ({"external_reference":"saas:invalid"},"PROVIDER_PAYMENT_NOT_ATTESTED_IN_CI"),
    ({"provider_amount_cents":19938},"PROVIDER_PAYMENT_NOT_ATTESTED_IN_CI"),
    ({"refunded_cents":1},"PROVIDER_PAYMENT_NOT_ATTESTED_IN_CI"),
    ({"status":"pending"},"PROVIDER_PAYMENT_NOT_ATTESTED_IN_CI"),
    ({"checked_at":NOW-timedelta(minutes=16)},"PROVIDER_PAYMENT_NOT_ATTESTED_IN_CI"),
    ({"checked_at":NOW+timedelta(minutes=1)},"PROVIDER_PAYMENT_NOT_ATTESTED_IN_CI"),
    ({"evidence_sha256":"not a digest"},"INVALID_PROVIDER_FIELDS"),
])
def test_provider_mismatch_never_pays(changes,code):
    _,_,p,_=fixtures()
    result=evaluate(provider=replace(p,**changes))
    assert result.state==code
    deny_all_real_effects(result)


@pytest.mark.parametrize("changes,code",[
    ({"source":"API_CLIENT"},"UNTRUSTED_RECONCILIATION_SOURCE"),
    ({"tenant_id":OTHER},"RECONCILIATION_INCONSISTENT_OR_UNATTESTED"),
    ({"payment_intent_id":OTHER},"RECONCILIATION_INCONSISTENT_OR_UNATTESTED"),
    ({"provider_payment_id":"87654321"},"RECONCILIATION_INCONSISTENT_OR_UNATTESTED"),
    ({"independent_reviewer_id":ADMIN},"RECONCILIATION_INCONSISTENT_OR_UNATTESTED"),
    ({"provider_digest":"c"*64},"RECONCILIATION_INCONSISTENT_OR_UNATTESTED"),
    ({"statement_digest":"b"*64},"RECONCILIATION_INCONSISTENT_OR_UNATTESTED"),
    ({"gross_cents":19938},"RECONCILIATION_INCONSISTENT_OR_UNATTESTED"),
    ({"fee_cents":91},"RECONCILIATION_INCONSISTENT_OR_UNATTESTED"),
    ({"state":"PAID"},"RECONCILIATION_INCONSISTENT_OR_UNATTESTED"),
    ({"observed_at":NOW-timedelta(days=2)},"RECONCILIATION_INCONSISTENT_OR_UNATTESTED"),
    ({"observed_at":NOW+timedelta(minutes=2)},"RECONCILIATION_INCONSISTENT_OR_UNATTESTED"),
    ({"net_cents":False},"INVALID_RECONCILIATION_FIELDS"),
    ({"review_digest":"bad"},"INVALID_RECONCILIATION_FIELDS"),
])
def test_reconciliation_mismatch_never_grants(changes,code):
    _,_,_,r=fixtures()
    result=evaluate(reconciliation=replace(r,**changes))
    assert result.state==code
    deny_all_real_effects(result)


def test_malformed_input_denied_and_no_sql_or_network_ports():
    c,o,p,r=fixtures()
    assert review_checkout(contract=c,offer=o,provider=p,
                           reconciliation=r,now=NOW.replace(tzinfo=None)
                          ).state=="INVALID_TYPED_SNAPSHOT"
    assert review_checkout(contract={},offer=o,now=NOW).state=="INVALID_TYPED_SNAPSHOT"
    path=Path(__file__).resolve().parents[1]/"app/saas_checkout_chain_ci.py"
    code=path.read_text()
    for forbidden in (
        "import httpx", "import requests", "import psycopg",
        "INSERT INTO ", "UPDATE public.", "DELETE FROM ", "CREATE DATABASE",
        "FR_FINANCE_PIX_REAL=true",
    ):
        assert forbidden not in code
