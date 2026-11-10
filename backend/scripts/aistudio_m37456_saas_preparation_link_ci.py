#!/usr/bin/env python3
"""M37456: disposable-only, post-preparation synthetic consent link probe.

This writes a CI linkage record, never a contract acceptance, SaaS payment,
licence, activation or ledger entry. Exits before DB import unless isolated.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from uuid import UUID
import os

CI_ENV = {
    "GITHUB_ACTIONS": "true",
    "FRCAIXINHA_CI_ISOLATED": "1",
    "PGHOST": "127.0.0.1",
    "PGPORT": "5432",
    "PGDATABASE": "frcaixinha_staging",
    "PGUSER": "postgres",
    "PGPASSWORD": "ci-test-only",
    "PGOPTIONS": "-c frcaixinha.saas_consent_ci=1",
}
REQUEST = UUID("daba0000-0000-4000-8000-000000000050")
TENANT = UUID("daba0000-0000-4000-8000-000000000010")
ADMIN = UUID("daba0000-0000-4000-8000-000000000001")
CHALLENGE = UUID("daba0000-0000-4000-8000-000000000092")
OTHER = UUID("daba0000-0000-4000-8000-000000000020")
ACCEPTANCE = UUID("daba0000-0000-4000-8000-000000000040")
DIGEST = "a1" * 32
QUERY = "SELECT public.m37456_link_consent_to_preparation_ci(%s,%s,%s,%s,%s,%s,%s)"


def environment_allowed(env: dict[str,str]) -> bool:
    return all(env.get(k) == v for k,v in CI_ENV.items())


@contextmanager
def connect(user="postgres"):
    import psycopg
    with psycopg.connect(
        host="127.0.0.1",port=5432,dbname="frcaixinha_staging",
        user=user,password="ci-test-only",connect_timeout=5,
        options="-c frcaixinha.saas_consent_ci=1",
    ) as conn:
        yield conn


def assert_equal(actual,expected,label):
    if actual!=expected:
        raise AssertionError(f"M37456_{label}: expected {expected!r}, got {actual!r}")


def link(conn,*,request,preparation,challenge=CHALLENGE,
         tenant=TENANT,admin=ADMIN,price,digest=DIGEST):
    return conn.execute(QUERY,(
        request,preparation,challenge,tenant,admin,price,digest,
    )).fetchone()[0]


def main() -> int:
    if not environment_allowed(dict(os.environ)):
        print("M37456_BLOCKED=NOT_DISPOSABLE_GITHUB_CI")
        return 1

    import psycopg
    with connect() as conn:
        meta=conn.execute(
            "SELECT current_database(),session_user,current_setting('is_superuser'),"
            "current_setting('frcaixinha.saas_consent_ci',true),inet_server_port()"
        ).fetchone()
        assert_equal(meta,("frcaixinha_staging","postgres","on","1",5432),"IDENTITY")
        setup=conn.execute(
            "SELECT e.preparation_id,e.price_version_id FROM "
            "public.saas_enrollment_requests_staging e WHERE e.request_id=%s",
            (REQUEST,),
        ).fetchone()
        if setup is None:
            raise AssertionError("M37456_PREPARATION_NOT_FOUND")
        preparation, price = setup
        acceptance_hash=conn.execute(
            "SELECT evidence_hash FROM public.contract_acceptances WHERE id=%s",
            (ACCEPTANCE,),
        ).fetchone()[0]
        assert_equal(acceptance_hash,"b"*64,"ORIGINAL_ACCEPTANCE_EXPECTED")
        receipt=conn.execute(
            "SELECT challenge_id,evidence_digest FROM "
            "public.saas_consent_receipts_m37455_ci WHERE challenge_id=%s",
            (CHALLENGE,),
        ).fetchone()
        assert_equal(receipt,(CHALLENGE,DIGEST),"M37455_RECEIPT_EXPECTED")
        for role in ("frcaixinha_app_role","frcaixinha_auth_role",
                     "frcaixinha_saas_consent_ci"):
            for privilege in ("INSERT","SELECT","UPDATE","DELETE"):
                permitted=conn.execute(
                    "SELECT has_table_privilege(%s,"
                    "'public.saas_consent_preparation_links_m37456_ci',%s)",
                    (role,privilege),
                ).fetchone()[0]
                assert_equal(permitted,False,"DIRECT_ACCESS_DENIED")

    with connect("frcaixinha_saas_consent_ci") as worker:
        for kwargs in (
            {"tenant":OTHER},
            {"admin":OTHER},
            {"price":OTHER},
            {"preparation":OTHER},
            {"request":OTHER},
            {"challenge":OTHER},
            {"digest":"f"*64},
            {"digest":"not-a-digest"},
        ):
            params={"request":REQUEST,"preparation":preparation,"price":price}
            params.update(kwargs)
            assert_equal(link(worker,**params),
                         "DENIED_CI_UNATTESTED_OR_SCOPE_MISMATCH" if kwargs.get(
                             "digest")!="not-a-digest" else "DENIED_CI",
                         "FAIL_CLOSED_SCOPE")

    # The last test uses parallel separate database sessions. Only one write.
    def simultaneous_link(_):
        with connect("frcaixinha_saas_consent_ci") as worker:
            return link(worker,request=REQUEST,preparation=preparation,price=price)
    with ThreadPoolExecutor(max_workers=5) as pool:
        results=list(pool.map(simultaneous_link,range(5)))
    assert_equal(results.count("LINKED_POST_PREPARATION_CI_UNATTESTED"),
                 1,"SINGLE_LINKED_WRITE")
    assert_equal(results.count("REPLAY_CI_NO_WRITE"),4,"CONCURRENT_REPLAY")
    with connect("frcaixinha_saas_consent_ci") as worker:
        assert_equal(link(worker,request=REQUEST,preparation=preparation,price=price),
                     "REPLAY_CI_NO_WRITE","IDEMPOTENT_READBACK")
        assert_equal(link(worker,request=REQUEST,preparation=preparation,
                          price=price,challenge=OTHER),
                     "DENIED_CI_UNATTESTED_OR_SCOPE_MISMATCH","COLLISION_BLOCK")
        try:
            worker.execute("SELECT count(*) FROM public.saas_consent_preparation_links_m37456_ci")
        except psycopg.errors.InsufficientPrivilege:
            worker.rollback()
        else:
            raise AssertionError("M37456_WORKER_CAN_READ_RAW_LINK")
        try:
            worker.execute("INSERT INTO public.saas_consent_preparation_links_m37456_ci "
                           "(request_id,preparation_id,challenge_id,tenant_id,administrator_id,"
                           "price_version_id,document_id,receipt_digest) "
                           "SELECT request_id,preparation_id,%s,tenant_id,admin_user_id,"
                           "price_version_id,%s,%s FROM public.saas_enrollment_requests_staging "
                           "WHERE request_id=%s",(CHALLENGE,OTHER,DIGEST,REQUEST))
        except psycopg.errors.InsufficientPrivilege:
            worker.rollback()
        else:
            raise AssertionError("M37456_WORKER_CAN_INSERT_RAW_LINK")

    with connect() as conn:
        row=conn.execute(
            "SELECT request_id,preparation_id,challenge_id,tenant_id,"
            "administrator_id,price_version_id,receipt_digest,evidence_state,"
            "legal_consent_verified,payment_authorized,license_authorized,"
            "real_activation_authorized "
            "FROM public.saas_consent_preparation_links_m37456_ci"
        ).fetchall()
        assert_equal(row,[(
            REQUEST,preparation,CHALLENGE,TENANT,ADMIN,price,DIGEST,
            "POST_PREPARATION_CI_UNATTESTED",False,False,False,False,
        )],"LINK_STATE_IS_NOT_ENTITLEMENT")
        assert_equal(conn.execute(
            "SELECT evidence_hash FROM public.contract_acceptances WHERE id=%s",
            (ACCEPTANCE,),
        ).fetchone()[0],"b"*64,"ACCEPTANCE_UNCHANGED")
        for table in ("saas_payment_intents","saas_license_entitlements"):
            assert_equal(conn.execute(
                f"SELECT count(*) FROM public.{table} WHERE tenant_id=%s",(TENANT,),
            ).fetchone()[0],0,"NO_FINANCIAL_RECORDS")
        assert_equal(conn.execute(
            "SELECT count(*) FROM public.ledger_entries WHERE tenant_id=%s",
            (TENANT,),
        ).fetchone()[0],0,"NO_TENANT_LEDGER")
        for query in (
            "UPDATE public.saas_consent_preparation_links_m37456_ci "
            "SET evidence_state=evidence_state",
            "DELETE FROM public.saas_consent_preparation_links_m37456_ci",
            "TRUNCATE public.saas_consent_preparation_links_m37456_ci",
        ):
            try:
                with conn.transaction():
                    conn.execute(query)
            except psycopg.errors.RaiseException as exc:
                if "M37455_APPEND_ONLY_CI" not in str(exc):
                    raise
            else:
                raise AssertionError("M37456_APPEND_ONLY_NOT_ENFORCED")

    print("M37456_DISPOSABLE_CONSENT_PREPARATION_LINK=PASS")
    print("M37456_CONCURRENT_IDEMPOTENCY=PASS")
    print("M37456_POST_PREPARATION_EVIDENCE=CI_UNATTESTED")
    print("M37456_ORIGINAL_ACCEPTANCE=UNMODIFIED")
    print("M37456_PAYMENT_LICENSE_ACTIVATION_PIX_REAL=OFF")
    print("M37456_LOCAL_DATABASE=UNTOUCHED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
