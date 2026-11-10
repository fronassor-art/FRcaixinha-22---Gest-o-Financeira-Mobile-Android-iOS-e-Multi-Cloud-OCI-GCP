"""M37454: consent linkage is hypothetical and never activates anything."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest

from app.saas_consent_linkage_ci import (
    SessionFixture,ChallengeFixture,AffirmationFixture,ReceiptFixture,
    synthetic_evidence_mac,review_saas_consent_ci,
)

NOW = datetime(2026,11,10,16,tzinfo=timezone.utc)
T=UUID("daba0000-0000-4000-8000-000000000010")
A=UUID("daba0000-0000-4000-8000-000000000001")
R=UUID("daba0000-0000-4000-8000-000000000050")
PREP=UUID("daba0000-0000-4000-8000-000000000051")
DOC=UUID("daba0000-0000-4000-8000-000000000030")
ACC=UUID("daba0000-0000-4000-8000-000000000040")
PRICE=UUID("daba0000-0000-4000-8000-000000000060")
SESSION=UUID("daba0000-0000-4000-8000-000000000061")
CHALLENGE=UUID("daba0000-0000-4000-8000-000000000062")
OTHER=UUID("daba0000-0000-4000-8000-000000000099")
KEY=b"M37454-deterministic-ci-only-secret-32bytes-not-production"
CONFIRM="ACEITO_CONTRATO_DE_LICENCA_FR_FINANCE"


def fixture_row():
    return {
        "request_id":R,"tenant_id":T,"admin_user_id":A,
        "price_version_id":PRICE,"contract_acceptance_id":ACC,
        "preparation_id":PREP,"billing_period":"MONTHLY",
        "payment_created":False,"entitlement_created":False,
        "prepared_tenant":T,"prepared_admin":A,"prepared_price":PRICE,
        "prepared_acceptance":ACC,"prepared_period":"MONTHLY",
        "prepared_tier":"ESSENCIAL","preparation_status":"PENDING_PAYMENT",
        "prepared_at":NOW-timedelta(hours=1),
        "accepted_document_id":DOC,"accepted_by":A,"accepted_tenant":None,
        "accepted_kind":"PLATFORM_LICENSE",
        "accepted_at":NOW-timedelta(hours=2,minutes=20),
        "evidence_method":"CI_VERIFIED_IDENTITY","evidence_hash":"b"*64,
        "published_document_id":DOC,"published_kind":"PLATFORM_LICENSE",
        "published_at":NOW-timedelta(days=2),"published_sha":"a"*64,
        "version_id":PRICE,"version_tier":"ESSENCIAL",
        "monthly_price":Decimal("199.37"),"annual_price":Decimal("1993.70"),
        "plan_tier":"ESSENCIAL","plan_status":"ACTIVE",
        "tenant_admin":A,"tenant_status":"ATIVO","admin_status":"ACTIVE",
        "admin_membership_active":True,"payment_count":0,
        "license_count":0,"tenant_ledger_entries":0,
    }


def fixtures():
    session=SessionFixture(
        session_id=SESSION,tenant_id=T,user_id=A,role="TENANT_ADMIN",
        issued_at=NOW-timedelta(hours=3),
        expires_at=NOW+timedelta(hours=3),
        active=True,email_verified=True,
    )
    challenge=ChallengeFixture(
        challenge_id=CHALLENGE,tenant_id=T,user_id=A,session_id=SESSION,
        document_id=DOC,document_sha256="a"*64,
        price_version_id=PRICE,preparation_id=PREP,
        issued_at=NOW-timedelta(hours=2,minutes=30),
        expires_at=NOW-timedelta(hours=2,minutes=25),
    )
    affirmation=AffirmationFixture(
        challenge_id=CHALLENGE,tenant_id=T,user_id=A,session_id=SESSION,
        document_id=DOC,document_sha256="a"*64,
        confirmation_text=CONFIRM,checked=True,
        occurred_at=NOW-timedelta(hours=2,minutes=29),
    )
    mac=synthetic_evidence_mac(ci_key=KEY,session=session,
        challenge=challenge,affirmation=affirmation)
    receipt=ReceiptFixture(
        challenge_id=CHALLENGE,tenant_id=T,user_id=A,evidence_mac=mac,
        recorded_at=NOW-timedelta(hours=2,minutes=28),
        consume_count=1,replay_count=0,revoked=False,append_only_claim=True,
    )
    row=fixture_row()
    row["evidence_hash"]=mac
    return row,session,challenge,affirmation,receipt


def evaluate(*, row=None, session=None, challenge=None, affirmation=None,
             receipt=None, ci_key=KEY, now=NOW):
    d,s,c,a,r=fixtures()
    return review_saas_consent_ci(
        row=d if row is None else row,
        request_id=R,tenant_id=T,admin_id=A,
        session=s if session is None else session,
        challenge=c if challenge is None else challenge,
        affirmation=a if affirmation is None else affirmation,
        receipt=r if receipt is None else receipt,
        ci_key=ci_key,now=now,
    )


def no_real_effects(x):
    for field in (
        "document_integrity_operationally_verified",
        "user_action_operationally_verified",
        "durable_unique_consumption_verified",
        "legal_consent_accepted","billing_authorized",
        "license_activated","user_activated","pix_authorized",
        "production_authorized","writes_performed",
    ):
        assert getattr(x,field) is False


def test_full_synthetic_linkage_is_a_review_not_legal_consent():
    x=evaluate()
    assert x.state=="CI_CONSENT_LINKAGE_REVIEW_ONLY"
    assert x.hypothetical_binding_consistent is True
    assert x==evaluate()
    no_real_effects(x)


def test_m30900_placeholder_hash_is_not_proof():
    x=evaluate(row=fixture_row())
    assert x.state=="ACCEPTANCE_EVIDENCE_NOT_CRYPTOGRAPHICALLY_BOUND"
    assert x.hypothetical_binding_consistent is False
    no_real_effects(x)


def test_missing_preparation_blocks_even_valid_mac():
    d,s,c,a,r=fixtures()
    d["preparation_status"]="CANCELED"
    x=evaluate(row=d)
    assert x.state=="PERSISTED_PREPARATION_NOT_VERIFIED"
    no_real_effects(x)


@pytest.mark.parametrize("change,reason",[
    ({"source":"HTTP_REQUEST"},"UNTRUSTED_EVIDENCE_SOURCE"),
    ({"role":"MASTER"},"ADMIN_SESSION_NOT_VERIFIED_IN_CI"),
    ({"role":"TENANT_MEMBER"},"ADMIN_SESSION_NOT_VERIFIED_IN_CI"),
    ({"active":False},"ADMIN_SESSION_NOT_VERIFIED_IN_CI"),
    ({"active":1},"MALFORMED_EVIDENCE"),
    ({"email_verified":False},"ADMIN_SESSION_NOT_VERIFIED_IN_CI"),
    ({"tenant_id":OTHER},"ADMIN_SESSION_NOT_VERIFIED_IN_CI"),
    ({"user_id":OTHER},"ADMIN_SESSION_NOT_VERIFIED_IN_CI"),
    ({"issued_at":NOW},"EXPIRED_OUT_OF_ORDER_OR_UNPUBLISHED_CONSENT"),
    ({"expires_at":NOW-timedelta(hours=2,minutes=30)},"EXPIRED_OUT_OF_ORDER_OR_UNPUBLISHED_CONSENT"),
    ({"issued_at":datetime(2026,11,10)},"MALFORMED_EVIDENCE"),
])
def test_session_not_a_proof_of_consent(change,reason):
    d,s,c,a,r=fixtures()
    x=evaluate(session=replace(s,**change))
    assert x.state==reason
    no_real_effects(x)


@pytest.mark.parametrize("change,reason",[
    ({"source":"WEB_CLIENT"},"UNTRUSTED_EVIDENCE_SOURCE"),
    ({"tenant_id":OTHER},"CONTRACT_PRICE_OR_TENANT_BINDING_MISMATCH"),
    ({"user_id":OTHER},"CONTRACT_PRICE_OR_TENANT_BINDING_MISMATCH"),
    ({"session_id":OTHER},"CONTRACT_PRICE_OR_TENANT_BINDING_MISMATCH"),
    ({"document_id":OTHER},"CONTRACT_PRICE_OR_TENANT_BINDING_MISMATCH"),
    ({"document_sha256":"f"*64},"CONTRACT_PRICE_OR_TENANT_BINDING_MISMATCH"),
    ({"price_version_id":OTHER},"CONTRACT_PRICE_OR_TENANT_BINDING_MISMATCH"),
    ({"preparation_id":OTHER},"CONTRACT_PRICE_OR_TENANT_BINDING_MISMATCH"),
    ({"document_sha256":"not-a-sha"},"MALFORMED_EVIDENCE"),
    ({"expires_at":NOW-timedelta(hours=2,minutes=30)},"EXPIRED_OUT_OF_ORDER_OR_UNPUBLISHED_CONSENT"),
    ({"expires_at":NOW+timedelta(hours=1)},"EXPIRED_OUT_OF_ORDER_OR_UNPUBLISHED_CONSENT"),
    ({"issued_at":NOW},"EXPIRED_OUT_OF_ORDER_OR_UNPUBLISHED_CONSENT"),
])
def test_challenge_scope_expiry_and_price_linkage(change,reason):
    d,s,c,a,r=fixtures()
    x=evaluate(challenge=replace(c,**change))
    assert x.state==reason
    no_real_effects(x)


@pytest.mark.parametrize("change,reason",[
    ({"source":"HTTP_REQUEST"},"UNTRUSTED_EVIDENCE_SOURCE"),
    ({"challenge_id":OTHER},"AFFIRMATION_BINDING_MISMATCH"),
    ({"tenant_id":OTHER},"AFFIRMATION_BINDING_MISMATCH"),
    ({"user_id":OTHER},"AFFIRMATION_BINDING_MISMATCH"),
    ({"session_id":OTHER},"AFFIRMATION_BINDING_MISMATCH"),
    ({"document_id":OTHER},"AFFIRMATION_BINDING_MISMATCH"),
    ({"document_sha256":"f"*64},"AFFIRMATION_BINDING_MISMATCH"),
    ({"checked":False},"EXPLICIT_AFFIRMATIVE_ACTION_ABSENT"),
    ({"checked":1},"MALFORMED_EVIDENCE"),
    ({"confirmation_text":"ACEITO"},"EXPLICIT_AFFIRMATIVE_ACTION_ABSENT"),
    ({"occurred_at":NOW},"EXPIRED_OUT_OF_ORDER_OR_UNPUBLISHED_CONSENT"),
    ({"occurred_at":NOW-timedelta(days=4)},"EXPIRED_OUT_OF_ORDER_OR_UNPUBLISHED_CONSENT"),
    ({"occurred_at":datetime(2026,11,10)},"MALFORMED_EVIDENCE"),
])
def test_affirmative_action_requirements(change,reason):
    d,s,c,a,r=fixtures()
    x=evaluate(affirmation=replace(a,**change))
    assert x.state==reason
    no_real_effects(x)


@pytest.mark.parametrize("change,reason",[
    ({"source":"BROWSER"},"UNTRUSTED_EVIDENCE_SOURCE"),
    ({"challenge_id":OTHER},"REPLAY_REVOKED_OR_RECEIPT_SCOPE"),
    ({"tenant_id":OTHER},"REPLAY_REVOKED_OR_RECEIPT_SCOPE"),
    ({"user_id":OTHER},"REPLAY_REVOKED_OR_RECEIPT_SCOPE"),
    ({"consume_count":0},"REPLAY_REVOKED_OR_RECEIPT_SCOPE"),
    ({"consume_count":2},"REPLAY_REVOKED_OR_RECEIPT_SCOPE"),
    ({"consume_count":True},"MALFORMED_EVIDENCE"),
    ({"replay_count":1},"REPLAY_REVOKED_OR_RECEIPT_SCOPE"),
    ({"revoked":True},"REPLAY_REVOKED_OR_RECEIPT_SCOPE"),
    ({"revoked":1},"MALFORMED_EVIDENCE"),
    ({"append_only_claim":False},"REPLAY_REVOKED_OR_RECEIPT_SCOPE"),
    ({"recorded_at":NOW},"EXPIRED_OUT_OF_ORDER_OR_UNPUBLISHED_CONSENT"),
    ({"evidence_mac":"f"*64},"ACCEPTANCE_EVIDENCE_NOT_CRYPTOGRAPHICALLY_BOUND"),
    ({"evidence_mac":"malformed"},"MALFORMED_EVIDENCE"),
])
def test_receipt_single_use_or_collision(change,reason):
    d,s,c,a,r=fixtures()
    x=evaluate(receipt=replace(r,**change))
    assert x.state==reason
    no_real_effects(x)


@pytest.mark.parametrize("change,reason",[
    ({"published_sha":"f"*64},"CONTRACT_PRICE_OR_TENANT_BINDING_MISMATCH"),
    ({"evidence_hash":"f"*64},"ACCEPTANCE_EVIDENCE_NOT_CRYPTOGRAPHICALLY_BOUND"),
    ({"accepted_at":NOW},"EXPIRED_OUT_OF_ORDER_OR_UNPUBLISHED_CONSENT"),
    ({"payment_count":1},"PERSISTED_PREPARATION_NOT_VERIFIED"),
    ({"license_count":1},"PERSISTED_PREPARATION_NOT_VERIFIED"),
    ({"tenant_ledger_entries":1},"PERSISTED_PREPARATION_NOT_VERIFIED"),
    ({"prepared_price":OTHER},"PERSISTED_PREPARATION_NOT_VERIFIED"),
])
def test_persisted_record_must_match_claims(change,reason):
    d,s,c,a,r=fixtures()
    d.update(change)
    x=evaluate(row=d)
    assert x.state==reason
    no_real_effects(x)


def test_key_wrong_or_missing_never_verifies():
    for key in (b"short",b"A"*32,b"B"*32):
        x=evaluate(ci_key=key)
        assert x.state in ("INVALID_INPUT","ACCEPTANCE_EVIDENCE_NOT_CRYPTOGRAPHICALLY_BOUND")
        no_real_effects(x)
    d,s,c,a,r=fixtures()
    for key in (None,"A"*40,b"short"):
        with pytest.raises(ValueError):
            synthetic_evidence_mac(ci_key=key,session=s,challenge=c,affirmation=a)


def test_synthetic_receipt_digest_is_domain_bound_and_utc_stable():
    d,s,c,a,r=fixtures()
    stable=synthetic_evidence_mac(ci_key=KEY,session=s,challenge=c,affirmation=a)
    assert stable==r.evidence_mac==d["evidence_hash"]
    altered=replace(a,occurred_at=a.occurred_at+timedelta(seconds=1))
    assert synthetic_evidence_mac(ci_key=KEY,session=s,challenge=c,
                                  affirmation=altered)!=stable


def test_invalid_types_no_implicit_coercion():
    for change in ({"receipt":{}},{"session":{}},{"challenge":{}},
                   {"affirmation":{}},{"now":NOW.replace(tzinfo=None)},
                   {"ci_key":b"short"}):
        x=evaluate(**change)
        assert x.state in ("INVALID_INPUT","INVALID_TYPED_EVIDENCE")
        no_real_effects(x)


def test_policy_has_no_real_io_and_cannot_activate():
    root=Path(__file__).resolve().parents[2]
    src=(root/"backend/app/saas_consent_linkage_ci.py").read_text()
    for forbidden in (
        "import httpx","import psycopg","import requests",
        "INSERT INTO ","UPDATE public.","DELETE FROM ",
        "APIRouter(","create_user(","grant_license(","issue_payment(",
    ):
        assert forbidden not in src
