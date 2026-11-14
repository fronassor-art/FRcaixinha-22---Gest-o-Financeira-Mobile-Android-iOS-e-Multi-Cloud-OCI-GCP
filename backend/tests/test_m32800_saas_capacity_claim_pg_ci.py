"""M32800: concurrency, idempotency, release lock, immutable audit (CI PG)."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4
import os
import pytest

T="daba0000-0000-4000-8000-000000000010"
OTHER="daba0000-0000-4000-8000-000000000020"
ADMIN="daba0000-0000-4000-8000-000000000001"
OTHER_ADMIN="daba0000-0000-4000-8000-000000000002"
ENT="daba0000-0000-4000-8000-000000000090"

def test_atomic_claim_prevents_double_use_or_release():
    if os.getenv("GITHUB_ACTIONS")!="true" or os.getenv("FRCAIXINHA_CI_ISOLATED")!="1":
        pytest.skip("Disposable GitHub CI only")
    url=os.getenv("CI_SAAS_CLAIM_DB_URL")
    admin_url=os.getenv("CI_SAAS_CLAIM_DB_ADMIN_URL")
    capacity_url=os.getenv("CI_SAAS_CLAIM_CAPACITY_URL")
    if not all((url,admin_url,capacity_url)):
        pytest.fail("Required disposable CI database URLs absent")
    import psycopg
    with psycopg.connect(admin_url) as conn:
        def hold(request):
            return conn.execute("SELECT event_id FROM public.saas_capacity_events_staging WHERE request_id=%s",
                (request,)).fetchone()[0]
        member_hold=hold("daba0000-0000-4000-8000-000000000067")
        quota_hold=hold("daba0000-0000-4000-8000-000000000063")
        released_hold=hold("daba0000-0000-4000-8000-000000000060")
        baseline=conn.execute("SELECT (SELECT count(*) FROM public.saas_payment_intents),"
            "(SELECT count(*) FROM public.saas_license_entitlements),"
            "(SELECT count(*) FROM public.ledger_entries),"
            "(SELECT count(*) FROM public.memberships),"
            "(SELECT count(*) FROM public.quotas)").fetchone()

    def claim(rid,hold=member_hold,tenant=T,admin=ADMIN,ent=ENT,cat="MEMBER"):
        with psycopg.connect(url,options="-c frcaixinha.saas_claim_ci=1") as conn:
            return conn.execute("SELECT public.saas_capacity_claim_ci(%s,%s,%s,%s,%s,%s)",
                (rid,tenant,admin,ent,hold,cat)).fetchone()[0]

    assert claim(uuid4(),tenant=OTHER)["state"]=="DENIED"
    assert claim(uuid4(),admin=OTHER_ADMIN)["state"]=="DENIED"
    assert claim(uuid4(),ent=uuid4())["state"]=="LICENSE_UNVERIFIED"
    assert claim(uuid4(),hold=released_hold)["state"]=="RELEASED_HOLD_DENIED"
    assert claim(uuid4(),cat="QUOTA")["state"]=="INVALID_HOLD"
    assert claim(uuid4(),hold=uuid4())["state"]=="INVALID_HOLD"

    barrier=Barrier(2)
    def race():
        barrier.wait(timeout=10)
        return claim(uuid4())["state"]
    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs=[pool.submit(race) for _ in range(2)]
        states=[j.result(timeout=30) for j in jobs]
    assert sorted(states)==["CLAIMED_CI_NO_REAL_CREATION","HOLD_ALREADY_CLAIMED"]

    with psycopg.connect(admin_url) as conn:
        rid=conn.execute("SELECT request_id FROM public.saas_capacity_claims_staging WHERE hold_event_id=%s",
            (member_hold,)).fetchone()[0]
    assert claim(rid)["state"]=="REPLAY_CI_NO_REAL_CREATION"
    assert claim(rid,hold=quota_hold,cat="QUOTA")["state"]=="REQUEST_COLLISION_DENIED"
    assert claim(uuid4())["state"]=="HOLD_ALREADY_CLAIMED"
    q=claim(uuid4(),hold=quota_hold,cat="QUOTA")
    assert q["state"]=="CLAIMED_CI_NO_REAL_CREATION"
    assert q["quantity"]==40 and q["real_authorized"] is False

    with psycopg.connect(capacity_url,options="-c frcaixinha.saas_capacity_ci=1") as conn:
        with pytest.raises(psycopg.Error,match="M32700_CLAIMED_HOLD_RELEASE_DENIED"):
            with conn.transaction():
                conn.execute("SELECT public.saas_capacity_release_ci(%s,%s,%s,%s)",
                    (uuid4(),T,ADMIN,member_hold))

    with psycopg.connect(admin_url) as conn:
        assert conn.execute("SELECT count(*) FROM public.saas_capacity_claims_staging").fetchone()[0]==2
        assert conn.execute("SELECT bool_and(ci_only AND NOT real_member_created "
            "AND NOT real_quota_created AND NOT real_charge_created AND NOT real_ledger_changed) "
            "FROM public.saas_capacity_claims_staging").fetchone()[0] is True
        after=conn.execute("SELECT (SELECT count(*) FROM public.saas_payment_intents),"
            "(SELECT count(*) FROM public.saas_license_entitlements),"
            "(SELECT count(*) FROM public.ledger_entries),"
            "(SELECT count(*) FROM public.memberships),"
            "(SELECT count(*) FROM public.quotas)").fetchone()
        assert baseline==after
        with pytest.raises(psycopg.Error,match="M32800_IMMUTABLE_CLAIM_HISTORY"):
            with conn.transaction():
                conn.execute("DELETE FROM public.saas_capacity_claims_staging")
        with pytest.raises(psycopg.Error,match="M32800_IMMUTABLE_CLAIM_HISTORY"):
            with conn.transaction():
                conn.execute("TRUNCATE public.saas_capacity_claims_staging")

    with psycopg.connect(url,options="-c frcaixinha.saas_claim_ci=1") as conn:
        with pytest.raises(psycopg.Error):
            with conn.transaction():
                conn.execute("SELECT count(*) FROM public.saas_capacity_claims_staging")
        with pytest.raises(psycopg.Error):
            with conn.transaction():
                conn.execute("INSERT INTO public.saas_capacity_claims_staging DEFAULT VALUES")
