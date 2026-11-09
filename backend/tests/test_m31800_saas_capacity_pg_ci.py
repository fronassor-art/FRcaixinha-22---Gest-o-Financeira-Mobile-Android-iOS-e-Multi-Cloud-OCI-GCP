"""Disposable PG concurrency proof (CI only), never Termux/OCI.

Executed ONLY with CI_SAAS_CAPACITY_DB_URL in the disposable staging job.
Two competing requests race for the last available capacity; row locking
must permit exactly one hold.
"""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import os
from uuid import uuid4
import pytest

def test_capacity_race_last_slot_serialized():
    if os.environ.get("FRCAIXINHA_CI_ISOLATED")!="1" or        os.environ.get("GITHUB_ACTIONS")!="true":
        pytest.skip("Disallowed outside GitHub disposable CI")
    url=os.environ.get("CI_SAAS_CAPACITY_DB_URL")
    if not url:
        pytest.fail("CI_SAAS_CAPACITY_DB_URL required in disposable staging job")
    import psycopg
    tenant="daba0000-0000-4000-8000-000000000020"
    admin="daba0000-0000-4000-8000-000000000002"
    def write(quantity):
        with psycopg.connect(url,options="-c frcaixinha.saas_capacity_ci=1") as conn:
            result=conn.execute(
                "SELECT public.saas_capacity_hold_ci(%s,%s,%s,%s,%s)",
                (uuid4(),tenant,admin,"MEMBER",quantity)
            ).fetchone()[0]
            return result["state"]
    assert write(19)=="HELD_CI_NO_REAL_ALLOCATION"
    barrier=Barrier(2)
    def concurrent():
        barrier.wait(timeout=10)
        return write(1)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures=[pool.submit(concurrent) for _ in range(2)]
        results=[f.result(timeout=30) for f in futures]
    assert sorted(results)==["CAPACITY_EXCEEDED","HELD_CI_NO_REAL_ALLOCATION"]
    # Re-read using the privileged disposable CI database only; the app
    # user cannot query the staging event table.
    admin_url=os.environ["CI_SAAS_CAPACITY_DB_ADMIN_URL"]
    with psycopg.connect(admin_url) as conn:
        n=conn.execute("""
            SELECT coalesce(sum(h.quantity),0)
            FROM public.saas_capacity_events_staging h
            WHERE h.tenant_id=%s AND h.category='MEMBER' AND h.action='HOLD'
            AND NOT EXISTS (
              SELECT 1 FROM public.saas_capacity_events_staging r
              WHERE r.action='RELEASE' AND r.related_hold_event_id=h.event_id
            )
        """,(tenant,)).fetchone()[0]
    assert n==20
