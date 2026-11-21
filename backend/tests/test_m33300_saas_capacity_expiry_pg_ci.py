"""M33300 PG disposable CI: expire stale unclaimed holds; no production writes."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4
import os
import pytest

T="daba0000-0000-4000-8000-000000000010"
OTHER="daba0000-0000-4000-8000-000000000020"
ADMIN="daba0000-0000-4000-8000-000000000001"
ENT="daba0000-0000-4000-8000-000000000090"

def test_recover_stale_unclaimed_hold_with_tenant_lock():
    if os.getenv("GITHUB_ACTIONS")!="true" or os.getenv("FRCAIXINHA_CI_ISOLATED")!="1":
        pytest.skip("Disposable CI only")
    url=os.getenv("CI_SAAS_EXPIRY_DB_URL")
    claim_url=os.getenv("CI_SAAS_EXPIRY_CLAIM_URL")
    admin_url=os.getenv("CI_SAAS_EXPIRY_DB_ADMIN_URL")
    if not all((url,claim_url,admin_url)):
        pytest.fail("Missing disposable CI DB credentials")
    import psycopg
    with psycopg.connect(admin_url) as conn:
        baseline=conn.execute("SELECT (SELECT count(*) FROM public.saas_payment_intents),"
            "(SELECT count(*) FROM public.saas_license_entitlements),"
            "(SELECT count(*) FROM public.ledger_entries),"
            "(SELECT count(*) FROM public.memberships),"
            "(SELECT count(*) FROM public.quotas)").fetchone()
        def fixture(age):
            return conn.execute("""INSERT INTO public.saas_capacity_events_staging
                (request_id,tenant_id,admin_user_id,action,category,quantity,created_at)
                VALUES (%s,%s,%s,'HOLD','MEMBER',1,clock_timestamp()-(%s * interval '1 hour'))
                RETURNING event_id""",(uuid4(),T,ADMIN,age)).fetchone()[0]
        old=fixture(2)
        recent=fixture(0)
        claimed=fixture(2)
        conn.execute("""INSERT INTO public.saas_capacity_claims_staging
            (request_id,hold_event_id,tenant_id,admin_user_id,entitlement_id,category,quantity)
            VALUES (%s,%s,%s,%s,%s,'MEMBER',1)""",(uuid4(),claimed,T,ADMIN,ENT))

    def recover(rid,hold=old,tenant=T,admin=ADMIN,options="-c frcaixinha.saas_capacity_ci=1 -c frcaixinha.saas_expiry_ci=1"):
        with psycopg.connect(url,options=options) as conn:
            return conn.execute("SELECT public.saas_capacity_expire_ci(%s,%s,%s,%s)",
                 (rid,tenant,admin,hold)).fetchone()[0]
    def claim(rid,hold=old):
        with psycopg.connect(claim_url,options="-c frcaixinha.saas_claim_ci=1") as conn:
            return conn.execute("SELECT public.saas_capacity_claim_ci(%s,%s,%s,%s,%s,%s)",
               (rid,T,ADMIN,ENT,hold,"MEMBER")).fetchone()[0]["state"]

    assert claim(uuid4())=="EXPIRED_HOLD_DENIED"
    assert recover(uuid4(),tenant=OTHER)["state"]=="DENIED"
    assert recover(uuid4(),admin=uuid4())["state"]=="DENIED"
    assert recover(uuid4(),hold=uuid4())["state"]=="INVALID_HOLD"
    assert recover(uuid4(),hold=recent)["state"]=="TOO_EARLY"
    assert recover(uuid4(),hold=claimed)["state"]=="CLAIMED_HOLD_DENIED"
    with pytest.raises(psycopg.Error,match="M32900_CI_WORKER_DENIED"):
        recover(uuid4(),options="-c frcaixinha.saas_capacity_ci=1")

    sync=Barrier(2)
    def attempt():
        sync.wait(timeout=10)
        return recover(uuid4())["state"]
    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs=[pool.submit(attempt) for _ in range(2)]
        answers=[j.result(timeout=30) for j in jobs]
    assert sorted(answers)==["ALREADY_RELEASED_DENIED","RECOVERED_CI_NO_REAL_CREATION"]
    with psycopg.connect(admin_url) as conn:
        prior=conn.execute("SELECT request_id,release_event_id FROM public.saas_capacity_expiry_events_staging WHERE hold_event_id=%s",(old,)).fetchone()
        assert prior is not None
        assert conn.execute("SELECT count(*) FROM public.saas_capacity_events_staging WHERE event_id=%s AND action='RELEASE' AND related_hold_event_id=%s",(prior[1],old)).fetchone()[0]==1
        assert conn.execute("SELECT count(*) FROM public.saas_capacity_expiry_events_staging").fetchone()[0]==1
    assert recover(prior[0])["state"]=="REPLAY_RECOVERY_CI"
    assert recover(prior[0],hold=recent)["state"]=="REQUEST_COLLISION_DENIED"
    assert recover(uuid4())["state"]=="ALREADY_RELEASED_DENIED"
    assert claim(uuid4())=="RELEASED_HOLD_DENIED"

    with psycopg.connect(admin_url) as conn:
        assert conn.execute("SELECT bool_and(ci_only AND NOT real_member_created "
            "AND NOT real_quota_created AND NOT real_charge_created AND NOT real_ledger_changed) "
            "FROM public.saas_capacity_expiry_events_staging").fetchone()[0] is True
        after=conn.execute("SELECT (SELECT count(*) FROM public.saas_payment_intents),"
            "(SELECT count(*) FROM public.saas_license_entitlements),"
            "(SELECT count(*) FROM public.ledger_entries),"
            "(SELECT count(*) FROM public.memberships),"
            "(SELECT count(*) FROM public.quotas)").fetchone()
        assert baseline==after
        with pytest.raises(psycopg.Error,match="M33200_EXPIRY_HISTORY_IMMUTABLE"):
            with conn.transaction():
                conn.execute("DELETE FROM public.saas_capacity_expiry_events_staging")
        with pytest.raises(psycopg.Error,match="M33200_EXPIRY_HISTORY_IMMUTABLE"):
            with conn.transaction():
                conn.execute("TRUNCATE public.saas_capacity_expiry_events_staging")
    with psycopg.connect(url,options="-c frcaixinha.saas_capacity_ci=1 -c frcaixinha.saas_expiry_ci=1") as conn:
        with pytest.raises(psycopg.Error):
            with conn.transaction():
                conn.execute("SELECT * FROM public.saas_capacity_expiry_events_staging")
