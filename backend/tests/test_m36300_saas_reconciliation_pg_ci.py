"""M36300 CI-only PostgreSQL: immutable replay-safe SaaS review evidence."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4
import os
import pytest

def test_saas_review_replay_concurrency_reversal_and_permission_barriers():
    if os.getenv("GITHUB_ACTIONS")!="true" or os.getenv("FRCAIXINHA_CI_ISOLATED")!="1":
        pytest.skip("Disposable CI PostgreSQL only")
    owner_url=os.getenv("CI_SAAS_REVIEW_OWNER_URL")
    worker_url=os.getenv("CI_SAAS_REVIEW_WORKER_URL")
    app_url=os.getenv("CI_SAAS_REVIEW_APP_URL")
    assert owner_url and worker_url and app_url, "Disposable CI database URLs required"
    import psycopg
    with psycopg.connect(owner_url) as owner:
        p=owner.execute(
            "SELECT id,tenant_id,provider_payment_id "
            "FROM public.saas_payment_intents "
            "WHERE external_reference LIKE 'ci-m34800-%' AND live_mode=false "
            "ORDER BY created_at DESC LIMIT 1").fetchone()
        assert p is not None, "M34800 synthetic fixture must run first"
        payment,tenant,provider_id=p
        before=owner.execute(
            "SELECT (SELECT count(*) FROM public.memberships),"
            "(SELECT count(*) FROM public.quotas),"
            "(SELECT count(*) FROM public.saas_payment_intents),"
            "(SELECT count(*) FROM public.saas_license_entitlements),"
            "(SELECT count(*) FROM public.saas_provider_webhook_receipts),"
            "(SELECT count(*) FROM public.ledger_entries)").fetchone()
        assert owner.execute(
            "SELECT relrowsecurity AND relforcerowsecurity "
            "FROM pg_class WHERE oid='public.saas_reconciliation_reviews_staging'::regclass"
        ).fetchone()[0] is True
        for role in ("frcaixinha_app_role","frcaixinha_auth_role",
                     "frcaixinha_saas_review_ci"):
            for privilege in ("INSERT","UPDATE","DELETE","SELECT","TRUNCATE"):
                assert owner.execute(
                    "SELECT has_table_privilege(%s,'public.saas_reconciliation_reviews_staging',%s)",
                    (role,privilege)).fetchone()[0] is False

    def review(event_id,request_key,kind,digest,selected_tenant=tenant,
               selected_provider=provider_id,flags=True):
        with psycopg.connect(worker_url,
            options="-c frcaixinha.saas_review_ci=1" if flags else
            "-c frcaixinha.saas_review_ci=0") as connection:
            return connection.execute(
                "SELECT public.saas_reconciliation_review_ci("
                "%s,%s,%s,%s,%s,%s,%s)",
                (event_id,payment,selected_tenant,selected_provider,
                 request_key,kind,digest)).fetchone()[0]

    request=str(uuid4()).replace("-","")
    e=uuid4()
    digest="a"*64
    assert review(uuid4(),str(uuid4()).replace("-",""),"BOGUS",digest)["state"]=="INVALID_SIMULATED_EVIDENCE"
    assert review(uuid4(),str(uuid4()).replace("-",""),"GET_MATCH_CANDIDATE","notasha")["state"]=="INVALID_SIMULATED_EVIDENCE"
    assert review(uuid4(),str(uuid4()).replace("-",""),"GET_MATCH_CANDIDATE",digest,
                  selected_tenant=uuid4())["state"]=="TENANT_NOT_FOUND"
    assert review(uuid4(),str(uuid4()).replace("-",""),"GET_MATCH_CANDIDATE",digest,
                  selected_provider="987654321")["state"]=="PAYMENT_SCOPE_OR_TEST_MODE_DENIED"
    with pytest.raises(psycopg.errors.InsufficientPrivilege,match="M35900_REVIEW_WORKER_DENIED"):
        review(uuid4(),str(uuid4()).replace("-",""),"GET_MATCH_CANDIDATE",digest,flags=False)
    with psycopg.connect(app_url) as app:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with app.transaction():
                app.execute("SELECT public.saas_reconciliation_review_ci("
                    "%s,%s,%s,%s,%s,%s,%s)",
                    (uuid4(),payment,tenant,provider_id,str(uuid4()).replace("-",""),
                     "GET_MATCH_CANDIDATE",digest))

    # Two concurrent, differently keyed events with the SAME evidence:
    # exactly one can be recorded.
    barrier=Barrier(2)
    def competing():
        barrier.wait(timeout=10)
        return review(uuid4(),str(uuid4()).replace("-",""),
                      "GET_MATCH_CANDIDATE",digest)["state"]
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures=[pool.submit(competing) for _ in range(2)]
        results=sorted(f.result(timeout=30) for f in futures)
    assert results==["DUPLICATE_EVIDENCE_DENIED","READBACK_CANDIDATE_RECORDED_CI"]

    # The next event is an explicit reversal hold. It cannot silently
    # mutate or erase the earlier candidate.
    reversal_id,reversal_key=uuid4(),str(uuid4()).replace("-","")
    reversal=review(reversal_id,reversal_key,"REVERSAL_HOLD","b"*64)
    assert reversal["state"]=="HOLD_RECORDED_CI"
    assert reversal["activation_authorized"] is False
    assert review(reversal_id,reversal_key,"REVERSAL_HOLD","b"*64)["state"]=="REPLAY_NO_FINANCIAL_WRITE"
    assert review(reversal_id,reversal_key,"REVERSAL_HOLD","c"*64)["state"]=="REVIEW_REQUEST_COLLISION_DENIED"
    assert review(uuid4(),str(uuid4()).replace("-",""),
                  "GET_MATCH_CANDIDATE","c"*64)["state"]=="REVERSAL_HOLD_ACTIVE"
    outage=review(uuid4(),str(uuid4()).replace("-",""),
                  "PROVIDER_UNAVAILABLE_HOLD","d"*64)
    assert outage["state"]=="HOLD_RECORDED_CI"

    with psycopg.connect(worker_url) as worker:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with worker.transaction():
                worker.execute("SELECT count(*) FROM public.saas_reconciliation_reviews_staging")

    with psycopg.connect(owner_url) as owner:
        assert owner.execute(
            "SELECT count(*) FROM public.saas_reconciliation_reviews_staging").fetchone()[0]==3
        for flags in owner.execute(
            "SELECT ci_only,provider_readback_live_attested,real_license_activated,"
            "real_payment_settled,real_pix_authorized "
            "FROM public.saas_reconciliation_reviews_staging"):
            assert flags==(True,False,False,False,False)
        after=owner.execute(
            "SELECT (SELECT count(*) FROM public.memberships),"
            "(SELECT count(*) FROM public.quotas),"
            "(SELECT count(*) FROM public.saas_payment_intents),"
            "(SELECT count(*) FROM public.saas_license_entitlements),"
            "(SELECT count(*) FROM public.saas_provider_webhook_receipts),"
            "(SELECT count(*) FROM public.ledger_entries)").fetchone()
        assert after==before
        with pytest.raises(psycopg.Error,match="M36200_REVIEW_APPEND_ONLY"):
            with owner.transaction():
                owner.execute("DELETE FROM public.saas_reconciliation_reviews_staging")
        with pytest.raises(psycopg.Error,match="M36200_REVIEW_APPEND_ONLY"):
            with owner.transaction():
                owner.execute("TRUNCATE public.saas_reconciliation_reviews_staging")
