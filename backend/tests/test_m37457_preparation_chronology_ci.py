"""M37457: enforce consent-before-preparation, no retroactive authority."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

import pytest

from app.saas_preparation_chronology_ci import (
    ServerIdentityClaim, PublishedSaaSOffer, AffirmativeConsentClaim,
    SaaSPreparationClaim, assess_preparation_chronology_ci,
    assess_persisted_temporal_order_ci,
)

NOW = datetime(2026,11,10,15,0,tzinfo=timezone.utc)
T=UUID("daba0000-0000-4000-8000-000000000010")
A=UUID("daba0000-0000-4000-8000-000000000001")
P=UUID("daba0000-0000-4000-8000-000000000060")
D=UUID("daba0000-0000-4000-8000-000000000030")
S=UUID("daba0000-0000-4000-8000-000000000061")
C=UUID("daba0000-0000-4000-8000-000000000062")
Q=UUID("daba0000-0000-4000-8000-000000000050")
OTHER=UUID("daba0000-0000-4000-8000-000000000099")


def samples(state="NOT_PREPARED"):
    identity=ServerIdentityClaim(
        tenant_id=T, administrator_id=A, session_id=S,
        session_user_id=A, session_tenant_id=T,
        session_role="TENANT_ADMIN", session_active=True, email_verified=True,
        issued_at=NOW-timedelta(hours=2),
        expires_at=NOW+timedelta(hours=2),
        checked_at=NOW-timedelta(minutes=3),
    )
    offer=PublishedSaaSOffer(
        tenant_id=T, document_id=D, document_kind="PLATFORM_LICENSE",
        document_sha256="a"*64, document_version="CI-PLATFORM-01",
        published_at=NOW-timedelta(days=2),
        presented_at=NOW-timedelta(hours=1),
        price_version_id=P, billing_period="MONTHLY",
        price_cents=19937, currency="BRL",
    )
    consent=AffirmativeConsentClaim(
        challenge_id=C, tenant_id=T, administrator_id=A,
        session_id=S, document_id=D, document_sha256="a"*64,
        price_version_id=P, issued_at=NOW-timedelta(minutes=30),
        expires_at=NOW-timedelta(minutes=20),
        checked=True, confirmation_text="ACEITO_CONTRATO_DE_LICENCA_FR_FINANCE",
        confirmed_at=NOW-timedelta(minutes=26),
        receipt_recorded_at=NOW-timedelta(minutes=25),
        receipt_count=1, replay_count=0, revoked=False,
        receipt_digest="b"*64,
    )
    preparation=SaaSPreparationClaim(
        request_id=Q, tenant_id=T, administrator_id=A,
        document_id=D, price_version_id=P,
        consent_challenge_id=C, billing_period="MONTHLY", price_cents=19937,
        requested_at=NOW-timedelta(minutes=15), state=state,
        prepared_at=(NOW-timedelta(minutes=14) if state=="PREPARED_CI" else None),
        payment_count=0, entitlement_count=0,
    )
    return identity,offer,consent,preparation


def run(*,identity=None,offer=None,consent=None,preparation=None,now=NOW):
    i,o,c,p=samples()
    return assess_preparation_chronology_ci(
        identity=i if identity is None else identity,
        offer=o if offer is None else offer,
        consent=c if consent is None else consent,
        preparation=p if preparation is None else preparation,now=now,
    )


def no_real_authority(result):
    for field in (
        "real_identity_verified","legal_consent_verified",
        "contract_signature_verified","payment_authorized",
        "license_authorized","user_activation_authorized",
        "pix_authorized","production_authorized","writes_performed",
    ):
        assert getattr(result,field) is False


@pytest.mark.parametrize("state",["NOT_PREPARED","PREPARED_CI"])
def test_hypothetical_good_chronology_never_authorizes_real(state):
    i,o,c,p=samples(state)
    result=assess_preparation_chronology_ci(
        identity=i,offer=o,consent=c,preparation=p,now=NOW)
    assert result.state=="CI_PREPARATION_CHRONOLOGY_CONSISTENT_NOT_AUTHORITY"
    assert result.hypothetical_preparation_eligible is True
    no_real_authority(result)


def test_preparation_started_before_acceptance_denied_even_if_receipt_matches():
    i,o,c,p=samples("PREPARED_CI")
    pre=replace(p,prepared_at=c.receipt_recorded_at-timedelta(seconds=1),
                requested_at=c.receipt_recorded_at-timedelta(seconds=2))
    result=run(preparation=pre)
    assert result.state=="PREPARATION_PRECEDED_CONSENT_DENIED"
    no_real_authority(result)


@pytest.mark.parametrize("name,mutations,code",[
    ("wrong_role",{"session_role":"MASTER"},"CI_SESSION_NOT_ACTIVE_OR_ADMIN"),
    ("member_role",{"session_role":"TENANT_MEMBER"},"CI_SESSION_NOT_ACTIVE_OR_ADMIN"),
    ("no_email",{"email_verified":False},"CI_SESSION_NOT_ACTIVE_OR_ADMIN"),
    ("inactive",{"session_active":False},"CI_SESSION_NOT_ACTIVE_OR_ADMIN"),
    ("false_as_number",{"session_active":1},"MALFORMED_EVIDENCE"),
    ("other_tenant",{"tenant_id":OTHER},"TENANT_ADMIN_OR_SESSION_SCOPE_MISMATCH"),
    ("other_admin",{"administrator_id":OTHER},"TENANT_ADMIN_OR_SESSION_SCOPE_MISMATCH"),
    ("other_session_user",{"session_user_id":OTHER},"TENANT_ADMIN_OR_SESSION_SCOPE_MISMATCH"),
    ("session_out_of_scope",{"session_tenant_id":OTHER},"TENANT_ADMIN_OR_SESSION_SCOPE_MISMATCH"),
    ("stale",{"checked_at":NOW-timedelta(minutes=16)},"CI_SESSION_READBACK_STALE"),
    ("future",{"checked_at":NOW+timedelta(seconds=1)},"CI_SESSION_READBACK_STALE"),
    ("expired",{"expires_at":NOW},"CI_SESSION_READBACK_STALE"),
    ("session_long",{"issued_at":NOW-timedelta(days=1)},"CI_SESSION_NOT_ACTIVE_OR_ADMIN"),
    ("naive",{"issued_at":NOW.replace(tzinfo=None)},"MALFORMED_EVIDENCE"),
    ("fake_source",{"source":"CLIENT"},"UNTRUSTED_EVIDENCE_SOURCE"),
])
def test_identity_security_is_fail_closed(name,mutations,code):
    i,_,_,_=samples()
    r=run(identity=replace(i,**mutations))
    assert r.state==code,name
    no_real_authority(r)


@pytest.mark.parametrize("name,mutations,code",[
    ("wrong_tenant",{"tenant_id":OTHER},"TENANT_ADMIN_OR_SESSION_SCOPE_MISMATCH"),
    ("wrong_doc",{"document_id":OTHER},"PUBLISHED_DOCUMENT_OR_FROZEN_PRICE_MISMATCH"),
    ("draft",{"document_kind":"TENANT_MEMBERSHIP"},"PUBLISHED_DOCUMENT_OR_FROZEN_PRICE_MISMATCH"),
    ("digest",{"document_sha256":"c"*64},"PUBLISHED_DOCUMENT_OR_FROZEN_PRICE_MISMATCH"),
    ("bad_digest",{"document_sha256":"BAD"},"MALFORMED_EVIDENCE"),
    ("bad_version",{"document_version":""},"PUBLISHED_DOCUMENT_OR_FROZEN_PRICE_MISMATCH"),
    ("different_price",{"price_version_id":OTHER},"PUBLISHED_DOCUMENT_OR_FROZEN_PRICE_MISMATCH"),
    ("wrong_period",{"billing_period":"WEEKLY"},"PUBLISHED_DOCUMENT_OR_FROZEN_PRICE_MISMATCH"),
    ("wrong_price",{"price_cents":19938},"PUBLISHED_DOCUMENT_OR_FROZEN_PRICE_MISMATCH"),
    ("negative",{"price_cents":-10},"MALFORMED_EVIDENCE"),
    ("bool_price",{"price_cents":True},"MALFORMED_EVIDENCE"),
    ("wrong_currency",{"currency":"USD"},"PUBLISHED_DOCUMENT_OR_FROZEN_PRICE_MISMATCH"),
    ("present_before_publish",{"presented_at":NOW-timedelta(days=3)},"CONSENT_EVENT_ORDER_OR_EXPIRATION_INVALID"),
    ("present_after_challenge",{"presented_at":NOW},"CONSENT_EVENT_ORDER_OR_EXPIRATION_INVALID"),
    ("fake_source",{"source":"BROWSER"},"UNTRUSTED_EVIDENCE_SOURCE"),
])
def test_offer_must_match_published_canonical_terms(name,mutations,code):
    _,o,_,_=samples()
    r=run(offer=replace(o,**mutations))
    assert r.state==code,name
    no_real_authority(r)


@pytest.mark.parametrize("name,mutations,code",[
    ("wrong_tenant",{"tenant_id":OTHER},"TENANT_ADMIN_OR_SESSION_SCOPE_MISMATCH"),
    ("other_admin",{"administrator_id":OTHER},"TENANT_ADMIN_OR_SESSION_SCOPE_MISMATCH"),
    ("other_session",{"session_id":OTHER},"TENANT_ADMIN_OR_SESSION_SCOPE_MISMATCH"),
    ("wrong_challenge",{"challenge_id":OTHER},"EXPLICIT_CONSENT_OR_SINGLE_USE_NOT_MATCHED"),
    ("wrong_doc",{"document_id":OTHER},"PUBLISHED_DOCUMENT_OR_FROZEN_PRICE_MISMATCH"),
    ("wrong_sha",{"document_sha256":"c"*64},"PUBLISHED_DOCUMENT_OR_FROZEN_PRICE_MISMATCH"),
    ("wrong_price",{"price_version_id":OTHER},"PUBLISHED_DOCUMENT_OR_FROZEN_PRICE_MISMATCH"),
    ("not_checked",{"checked":False},"EXPLICIT_CONSENT_OR_SINGLE_USE_NOT_MATCHED"),
    ("integer_checked",{"checked":1},"MALFORMED_EVIDENCE"),
    ("text",{"confirmation_text":"ACEITO"},"EXPLICIT_CONSENT_OR_SINGLE_USE_NOT_MATCHED"),
    ("zero_receipt",{"receipt_count":0},"EXPLICIT_CONSENT_OR_SINGLE_USE_NOT_MATCHED"),
    ("two_receipts",{"receipt_count":2},"EXPLICIT_CONSENT_OR_SINGLE_USE_NOT_MATCHED"),
    ("replay",{"replay_count":1},"EXPLICIT_CONSENT_OR_SINGLE_USE_NOT_MATCHED"),
    ("revoked",{"revoked":True},"EXPLICIT_CONSENT_OR_SINGLE_USE_NOT_MATCHED"),
    ("late_confirmation",{"confirmed_at":NOW-timedelta(minutes=20)},"CONSENT_EVENT_ORDER_OR_EXPIRATION_INVALID"),
    ("early_confirmation",{"confirmed_at":NOW-timedelta(minutes=40)},"CONSENT_EVENT_ORDER_OR_EXPIRATION_INVALID"),
    ("issued_before_publication",{"issued_at":NOW-timedelta(days=3)},"CONSENT_EVENT_ORDER_OR_EXPIRATION_INVALID"),
    ("long_expiry",{"expires_at":NOW+timedelta(hours=1)},"CONSENT_EVENT_ORDER_OR_EXPIRATION_INVALID"),
    ("receipt_future",{"receipt_recorded_at":NOW+timedelta(minutes=1)},"CONSENT_EVENT_ORDER_OR_EXPIRATION_INVALID"),
    ("bad_hash",{"receipt_digest":"abc"},"MALFORMED_EVIDENCE"),
    ("naive_receipt",{"receipt_recorded_at":datetime(2026,11,10,12)},"MALFORMED_EVIDENCE"),
    ("fake_source",{"source":"LOCAL_STORAGE"},"UNTRUSTED_EVIDENCE_SOURCE"),
])
def test_consent_challenge_and_replay_proof_guard(name,mutations,code):
    _,_,c,_=samples()
    r=run(consent=replace(c,**mutations))
    assert r.state==code,name
    no_real_authority(r)


@pytest.mark.parametrize("name,mutations,code",[
    ("tenant",{"tenant_id":OTHER},"TENANT_ADMIN_OR_SESSION_SCOPE_MISMATCH"),
    ("admin",{"administrator_id":OTHER},"TENANT_ADMIN_OR_SESSION_SCOPE_MISMATCH"),
    ("document",{"document_id":OTHER},"PUBLISHED_DOCUMENT_OR_FROZEN_PRICE_MISMATCH"),
    ("price_version",{"price_version_id":OTHER},"PUBLISHED_DOCUMENT_OR_FROZEN_PRICE_MISMATCH"),
    ("challenge",{"consent_challenge_id":OTHER},"EXPLICIT_CONSENT_OR_SINGLE_USE_NOT_MATCHED"),
    ("period",{"billing_period":"ANNUAL"},"PUBLISHED_DOCUMENT_OR_FROZEN_PRICE_MISMATCH"),
    ("charge",{"price_cents":1},"PUBLISHED_DOCUMENT_OR_FROZEN_PRICE_MISMATCH"),
    ("too_early",{"requested_at":NOW-timedelta(hours=1)},"PREPARATION_STATE_OR_CHRONOLOGY_INVALID"),
    ("future",{"requested_at":NOW+timedelta(hours=1)},"PREPARATION_STATE_OR_CHRONOLOGY_INVALID"),
    ("fake_state",{"state":"ACTIVE"},"PREPARATION_STATE_OR_CHRONOLOGY_INVALID"),
    ("false_payment",{"payment_count":1},"FINANCIAL_OR_LICENSE_RECORD_ALREADY_PRESENT"),
    ("false_license",{"entitlement_count":1},"FINANCIAL_OR_LICENSE_RECORD_ALREADY_PRESENT"),
    ("bool_payment",{"payment_count":False},"MALFORMED_EVIDENCE"),
    ("wrong_source",{"source":"WEBHOOK"},"UNTRUSTED_EVIDENCE_SOURCE"),
])
def test_subscription_preparation_never_precedes_consent(name,mutations,code):
    _,_,_,p=samples()
    r=run(preparation=replace(p,**mutations))
    assert r.state==code,name
    no_real_authority(r)


@pytest.mark.parametrize("change,code",[
    ({"prepared_at":None},"PREPARATION_STATE_OR_CHRONOLOGY_INVALID"),
    ({"prepared_at":NOW-timedelta(minutes=21)},"PREPARATION_STATE_OR_CHRONOLOGY_INVALID"),
    ({"prepared_at":NOW+timedelta(seconds=1)},"PREPARATION_STATE_OR_CHRONOLOGY_INVALID"),
    ({"prepared_at":NOW-timedelta(minutes=26)},"PREPARATION_PRECEDED_CONSENT_DENIED"),
])
def test_prepared_existing_receipt_gate(change,code):
    _,_,_,p=samples("PREPARED_CI")
    r=run(preparation=replace(p,**change))
    assert r.state==code
    no_real_authority(r)


def test_existing_m37455_m37456_receipt_after_preparation_is_denied():
    prepared=NOW-timedelta(hours=2)
    issued=NOW-timedelta(minutes=9)
    received=NOW-timedelta(minutes=8)
    r=assess_persisted_temporal_order_ci(
        prepared_at=prepared,challenge_issued_at=issued,
        receipt_recorded_at=received,now=NOW,
    )
    assert r.state=="PREPARATION_PRECEDED_CONSENT_DENIED"
    no_real_authority(r)


def test_legacy_snapshot_never_recovers_by_forging_order():
    cases=[
        (NOW-timedelta(hours=3), NOW-timedelta(hours=2), NOW-timedelta(hours=1)),
        (NOW+timedelta(seconds=1), NOW-timedelta(minutes=2), NOW-timedelta(minutes=1)),
        (NOW-timedelta(minutes=5), NOW+timedelta(minutes=1), NOW+timedelta(minutes=2)),
    ]
    for prepared,issued,received in cases:
        r=assess_persisted_temporal_order_ci(
            prepared_at=prepared,challenge_issued_at=issued,
            receipt_recorded_at=received,now=NOW,
        )
        assert not r.hypothetical_preparation_eligible
        no_real_authority(r)


def test_invalid_snapshots_and_missing_source_are_safe():
    i,o,c,p=samples()
    for kwargs in (
        {"identity":{}},{"offer":{}},{"consent":{}},{"preparation":{}},
        {"now":NOW.replace(tzinfo=None)},
    ):
        r=assess_preparation_chronology_ci(
            identity=kwargs.get("identity",i),offer=kwargs.get("offer",o),
            consent=kwargs.get("consent",c),
            preparation=kwargs.get("preparation",p),now=kwargs.get("now",NOW),
        )
        assert r.state=="INVALID_TYPED_INPUT"
        no_real_authority(r)


def test_pure_ci_policy_has_no_sql_or_endpoints():
    body=(Path(__file__).resolve().parents[1]/"app/saas_preparation_chronology_ci.py").read_text()
    for forbidden in ("import psycopg","import httpx","import requests",
                      "INSERT INTO ","UPDATE public.","DELETE FROM ",
                      "APIRouter(","grant_license("):
        assert forbidden not in body
