"""M32300 PG disposable CI: two racing renewals, no new payments."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4
import os
import pytest

def test_concurrent_renewal_review_only():
    if os.getenv("GITHUB_ACTIONS")!="true" or os.getenv("FRCAIXINHA_CI_ISOLATED")!="1":
        pytest.skip("CI-only")
    url=os.getenv("CI_SAAS_RENEWAL_DB_URL")
    admin_url=os.getenv("CI_SAAS_RENEWAL_DB_ADMIN_URL")
    if not url or not admin_url:
        pytest.fail("Required disposable DB URL absent")
    import psycopg
    t="daba0000-0000-4000-8000-000000000010"
    a="daba0000-0000-4000-8000-000000000001"
    e="daba0000-0000-4000-8000-000000000090"
    accept="daba0000-0000-4000-8000-000000000040"
    with psycopg.connect(admin_url) as conn:
        price=conn.execute("SELECT price_version_id FROM public.saas_subscription_preparations WHERE tenant_id=%s",(t,)).fetchone()[0]
        prior=conn.execute("SELECT count(*) FROM public.saas_payment_intents").fetchone()[0]
        prev_ent=conn.execute("SELECT count(*) FROM public.saas_license_entitlements").fetchone()[0]
    def review(rid,tenant=t,admin=a,acc=accept,period="MONTHLY"):
        with psycopg.connect(url,options="-c frcaixinha.saas_renewal_ci=1") as conn:
            return conn.execute("SELECT public.saas_renewal_review_ci(%s,%s,%s,%s,%s,%s,%s)",
                (rid,tenant,admin,e,price,acc,period)).fetchone()[0]["state"]
    assert review(uuid4(),tenant="daba0000-0000-4000-8000-000000000020")=="DENIED"
    assert review(uuid4(),acc="daba0000-0000-4000-8000-000000000041")=="CONSENT_UNVERIFIED"
    sync=Barrier(2)
    def race():
        sync.wait(timeout=10)
        return review(uuid4())
    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs=[pool.submit(race) for _ in range(2)]
        answers=[j.result(timeout=30) for j in jobs]
    assert sorted(answers)==["DUPLICATE_TERM_DENIED","RENEWAL_REVIEW_CI_NO_CHARGE"]
    with psycopg.connect(admin_url) as conn:
        rid=conn.execute("SELECT request_id FROM public.saas_renewal_reviews_staging").fetchone()[0]
    assert review(rid)=="REPLAY_CI_NO_CHARGE"
    assert review(rid,period="ANNUAL")=="REQUEST_COLLISION_DENIED"
    assert review(uuid4())=="DUPLICATE_TERM_DENIED"
    with psycopg.connect(admin_url) as conn:
        assert conn.execute("SELECT count(*) FROM public.saas_renewal_reviews_staging").fetchone()[0]==1
        assert conn.execute("SELECT count(*) FROM public.saas_payment_intents").fetchone()[0]==prior
        assert conn.execute("SELECT count(*) FROM public.saas_license_entitlements").fetchone()[0]==prev_ent
        assert conn.execute("SELECT bool_and(NOT real_charge_created AND NOT entitlement_extended) FROM public.saas_renewal_reviews_staging").fetchone()[0] is True
        with pytest.raises(psycopg.Error):
            with conn.transaction():
                conn.execute("DELETE FROM public.saas_renewal_reviews_staging")
    with psycopg.connect(url,options="-c frcaixinha.saas_renewal_ci=1") as conn:
        with pytest.raises(psycopg.Error):
            with conn.transaction():
                conn.execute("SELECT * FROM public.saas_renewal_reviews_staging")
