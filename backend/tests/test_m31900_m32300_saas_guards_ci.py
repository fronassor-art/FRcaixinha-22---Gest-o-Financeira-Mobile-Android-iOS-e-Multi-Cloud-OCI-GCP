"""M31900-M32300 static and adversarial SaaS checks."""
from dataclasses import replace
from datetime import datetime,timedelta,timezone
from pathlib import Path
from uuid import UUID
import pytest
from app.saas_runtime_preflight import CapacitySnapshot,RenewalSnapshot,preview_capacity,preview_renewal

NOW=datetime(2027,5,3,tzinfo=timezone.utc)
T=UUID("daba0000-0000-4000-8000-000000000010")
OTHER=UUID("daba0000-0000-4000-8000-000000000020")
ADMIN=UUID("daba0000-0000-4000-8000-000000000001")
ROOT=Path(__file__).resolve().parents[2]
SQL=(ROOT/"backend/staging_migrations/061_saas_renewal_review_staging_only.sql").read_text()

def capacity(**kw):
    s=CapacitySnapshot(T,T,ADMIN,ADMIN,True,True,True,True,False,
        NOW-timedelta(days=1),NOW+timedelta(days=1),NOW,True,
        19,38,0,1,20,40,"MEMBER",1)
    return replace(s,**kw)

def renewal(**kw):
    s=RenewalSnapshot(capacity(),UUID("daba0000-0000-4000-8000-000000000090"),
        UUID("daba0000-0000-4000-8000-000000000099"),"MONTHLY","BRL",3000,
        "a"*64,"a"*64,False)
    return replace(s,**kw)

def safe(d):
    assert not any((d.persisted,d.real_members_authorized,d.real_quotas_authorized,
        d.real_charge_authorized,d.real_renewal_authorized,d.pix_authorized,
        d.tenant_ledger_authorized,d.production_authorized))

def test_capacity_and_renewal_review_never_activate():
    a=preview_capacity(capacity())
    b=preview_capacity(capacity(category="QUOTA"))
    c=preview_renewal(renewal())
    assert a.review_only and b.review_only and c.review_only
    assert c.term_key and len(c.term_key)==64
    for d in (a,b,c):safe(d)

@pytest.mark.parametrize("kw,state",[
    ({"source":"CLIENT"},"UNTRUSTED_SOURCE"),
    ({"licensed_tenant":OTHER},"CROSS_TENANT_LICENSE"),
    ({"actor":OTHER},"ADMIN_DENIED"),
    ({"tenant_active":False},"ADMIN_DENIED"),
    ({"plan_active":False},"UNVERIFIED_PLAN"),
    ({"max_quotas":None},"UNVERIFIED_PLAN"),
    ({"license_active":False},"UNVERIFIED_LICENSE_PAYMENT"),
    ({"payment_verified":False},"UNVERIFIED_LICENSE_PAYMENT"),
    ({"refund":True},"UNVERIFIED_LICENSE_PAYMENT"),
    ({"now":NOW+timedelta(days=1)},"ZERO_GRACE_LICENSE_EXPIRED"),
    ({"category":"WRONG"},"INVALID_CATEGORY"),
    ({"members":20},"CAPACITY_EXCEEDED"),
    ({"category":"QUOTA","quotas":39},"CAPACITY_EXCEEDED"),
])
def test_capacity_denies_every_invalid_gate(kw,state):
    d=preview_capacity(capacity(**kw))
    assert d.state==state and not d.review_only
    safe(d)

@pytest.mark.parametrize("kw",[
    {"quantity":True},{"quantity":0},{"quantity":101},{"members":-1},
    {"max_members":0},{"now":NOW.replace(tzinfo=None)},
    {"payment_verified":"true"},{"tenant":"tenant"}])
def test_invalid_types_raise(kw):
    with pytest.raises(ValueError,match="INVALID_CAPACITY_SNAPSHOT"):
        preview_capacity(capacity(**kw))

@pytest.mark.parametrize("kw,state",[
    ({"source":"WEBHOOK"},"UNTRUSTED_SOURCE"),
    ({"period":"WEEKLY"},"INVALID_RENEWAL_OFFER"),
    ({"currency":"USD"},"INVALID_RENEWAL_OFFER"),
    ({"contract_accepted_sha":"b"*64},"CONSENT_UNVERIFIED"),
    ({"pending_term":True},"DUPLICATE_TERM"),
])
def test_renewal_rejections(kw,state):
    d=preview_renewal(renewal(**kw))
    assert d.state==state and not d.review_only
    safe(d)

def test_term_key_cannot_be_bypassed_by_request_pricing_or_timezone():
    x=renewal()
    a=preview_renewal(x).term_key
    b=preview_renewal(replace(x,amount_cents=5000,price_version=OTHER)).term_key
    changed=replace(x.capacity,valid_until=x.capacity.valid_until.astimezone(
        timezone(timedelta(hours=-3))))
    c=preview_renewal(replace(x,capacity=changed)).term_key
    assert a==b==c

@pytest.mark.parametrize("s",["M32300_DISPOSABLE_CI_ONLY","M32300_CI_ROLE_DENIED",
    "FOR UPDATE","FORCE ROW LEVEL SECURITY","UNIQUE(tenant_id,entitlement_id,billing_period)",
    "REQUEST_COLLISION_DENIED","DUPLICATE_TERM_DENIED",
    "REPLAY_CI_NO_CHARGE","RENEWAL_REVIEW_CI_NO_CHARGE",
    "M32300_APPEND_ONLY","CHECK(NOT real_charge_created)"])
def test_staging_schema_and_pipeline(s):
    assert s in SQL
    script=(ROOT/"backend/scripts/aistudio_staging_chain_ci.sh").read_text()
    assert "061_saas_renewal_review_staging_only.sql" in script
    assert "M32300_RENEWAL_PG=PASS" in script

def test_no_real_effects_or_direct_write():
    assert "GRANT INSERT ON public.saas_renewal_reviews_staging" not in SQL
    p=(ROOT/"backend/app/saas_runtime_preflight.py").read_text()
    assert "INSERT INTO" not in p and "requests.post" not in p
