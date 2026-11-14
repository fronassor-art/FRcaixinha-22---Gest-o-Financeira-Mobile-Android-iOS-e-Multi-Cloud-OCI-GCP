#!/usr/bin/env python3
"""M37455: run a synthetic transaction/replay probe in disposable GitHub PG only.

Writes only to m37455 CI fixture tables. A recorded synthetic receipt is NOT
a persisted customer acceptance, legally attested signature, SaaS payment,
entitlement, user activation, tenant ledger write, or Pix authorization.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from uuid import UUID
import os

CI_ENV = {
    "GITHUB_ACTIONS":"true",
    "FRCAIXINHA_CI_ISOLATED":"1",
    "PGHOST":"127.0.0.1",
    "PGPORT":"5432",
    "PGDATABASE":"frcaixinha_staging",
    "PGUSER":"postgres",
    "PGPASSWORD":"ci-test-only",
    "PGOPTIONS":"-c frcaixinha.saas_consent_ci=1",
}
R=UUID("daba0000-0000-4000-8000-000000000050")
T=UUID("daba0000-0000-4000-8000-000000000010")
A=UUID("daba0000-0000-4000-8000-000000000001")
DOC=UUID("daba0000-0000-4000-8000-000000000030")
OTHER_DOC=UUID("daba0000-0000-4000-8000-000000000031")
SESSION=UUID("daba0000-0000-4000-8000-000000000091")
CHALLENGE=UUID("daba0000-0000-4000-8000-000000000092")
OTHER_CHALLENGE=UUID("daba0000-0000-4000-8000-000000000093")
OTHER_T=UUID("daba0000-0000-4000-8000-000000000020")
OTHER_A=UUID("daba0000-0000-4000-8000-000000000002")
DIGEST="a1"*32
DOC_SHA="a"*64
CONFIRM="ACEITO_CONTRATO_DE_LICENCA_FR_FINANCE"
ISSUE_SQL=("SELECT public.m37455_issue_challenge_ci("
           "%s,%s,%s,%s,%s,%s,%s,%s)")
RECORD_SQL=("SELECT public.m37455_record_affirmation_ci("
            "%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)")


def environment_allowed(env: dict[str,str]) -> bool:
    return all(env.get(key) == expected for key,expected in CI_ENV.items())


def _assert(actual: object, expected: object, label: str) -> None:
    if actual != expected:
        raise AssertionError(f"M37455_{label}: expected {expected!r}, got {actual!r}")


@contextmanager
def connect(user="postgres"):
    import psycopg
    # All authentication in this runner is an ephemeral GitHub Actions fixture.
    with psycopg.connect(
        host="127.0.0.1",port=5432,dbname="frcaixinha_staging",
        user=user,password="ci-test-only",connect_timeout=5,
        options="-c frcaixinha.saas_consent_ci=1",
    ) as conn:
        yield conn


def issue(conn,*,challenge=CHALLENGE,request=R,tenant=T,
          admin=A,session=SESSION,document=DOC,sha=DOC_SHA,price=None):
    if price is None:
        raise AssertionError("VERSION_REQUIRED")
    return conn.execute(ISSUE_SQL,(challenge,request,tenant,admin,session,
                                   document,sha,price)).fetchone()[0]


def record(conn,*,challenge=CHALLENGE,request=R,tenant=T,
           admin=A,session=SESSION,document=DOC,sha=DOC_SHA,
           price=None,confirmation=CONFIRM,digest=DIGEST):
    if price is None:
        raise AssertionError("VERSION_REQUIRED")
    return conn.execute(RECORD_SQL,(challenge,request,tenant,admin,session,
                    document,sha,price,confirmation,digest)).fetchone()[0]


def main() -> int:
    if not environment_allowed(dict(os.environ)):
        print("M37455_BLOCKED=NOT_DISPOSABLE_GITHUB_CI")
        return 1

    import psycopg
    with connect() as admin_conn:
        with admin_conn.cursor() as cur:
            cur.execute("SELECT current_database(),session_user,"
                        "current_setting('is_superuser'),"
                        "current_setting('frcaixinha.saas_consent_ci',true),"
                        "inet_server_port()")
            _assert(cur.fetchone(),("frcaixinha_staging","postgres","on","1",5432),
                    "DB_IDENTITY")
            price=cur.execute(
                "SELECT price_version_id FROM public.saas_enrollment_requests_staging"
                " WHERE request_id=%s",(R,)).fetchone()
            if price is None:
                raise AssertionError("M37455_M30900_FIXTURE_ABSENT")
            price=price[0]
            before=cur.execute(
                "SELECT evidence_hash FROM public.contract_acceptances "
                "WHERE id=%s",(UUID("daba0000-0000-4000-8000-000000000040"),)
            ).fetchone()
            _assert(before,("b"*64,),"PLACEHOLDER_ACCEPTANCE_EXPECTED")
            _assert(cur.execute(
                "SELECT has_function_privilege('frcaixinha_app_role',"
                "'public.m37455_record_affirmation_ci(uuid,uuid,uuid,uuid,uuid,uuid,text,uuid,text,text)',"
                "'EXECUTE')"
            ).fetchone()[0],False,"NO_PUBLIC_APP_EXECUTE")
            _assert(cur.execute(
                "SELECT has_table_privilege('frcaixinha_saas_consent_ci',"
                "'public.saas_consent_receipts_m37455_ci','INSERT')"
            ).fetchone()[0],False,"NO_DIRECT_INSERT")

    with connect("frcaixinha_saas_consent_ci") as worker:
        _assert(issue(worker,price=price,tenant=OTHER_T),"DENIED_CI","WRONG_TENANT")
        _assert(issue(worker,price=price,admin=OTHER_A),"DENIED_CI","WRONG_ADMIN")
        _assert(issue(worker,price=price,document=OTHER_DOC),"DENIED_CI","WRONG_DOCUMENT")
        _assert(issue(worker,price=price,sha="c"*64),"DENIED_CI","WRONG_SHA")
        _assert(issue(worker,price=price,request=OTHER_CHALLENGE),"DENIED_CI","WRONG_REQUEST")
        _assert(issue(worker,price=price),"ISSUED_CI_NO_REAL_INVITATION","ISSUE")
        _assert(issue(worker,price=price),"REPLAY_ISSUE_CI_NO_WRITE","ISSUE_REPLAY")
        _assert(issue(worker,price=price,challenge=OTHER_CHALLENGE),
                "COLLISION_CI_DENIED","CONCURRENT_CHALLENGE_COLLISION")
        _assert(record(worker,price=price,admin=OTHER_A),"DENIED_CI","RECORD_ADMIN_MISMATCH")
        _assert(record(worker,price=price,document=OTHER_DOC),"DENIED_CI","RECORD_DOCUMENT_MISMATCH")
        _assert(record(worker,price=price,session=OTHER_CHALLENGE),"DENIED_CI","RECORD_SESSION_MISMATCH")
        _assert(record(worker,price=price,confirmation="ACEITO"),"DENIED_CI","RECORD_NEGATIVE_CONSENT")
        _assert(record(worker,price=price,digest="malformed"),"DENIED_CI","INVALID_DIGEST")

    # Multi-connection race against the same challenge: exactly one durable
    # insert; all subsequent identical calls are harmless replays.
    def simultaneous_record(_):
        with connect("frcaixinha_saas_consent_ci") as worker:
            return record(worker,price=price)
    with ThreadPoolExecutor(max_workers=5) as pool:
        results=list(pool.map(simultaneous_record,range(5)))
    _assert(results.count("RECORDED_CI_NOT_LEGAL_CONSENT"),1,"ONE_INSERT")
    _assert(results.count("REPLAY_CI_NO_WRITE"),4,"CONCURRENT_REPLAY")
    with connect("frcaixinha_saas_consent_ci") as worker:
        _assert(record(worker,price=price,digest="f"*64),
                "RECEIPT_COLLISION_CI_DENIED","REPLAY_DIGEST_COLLISION")
        _assert(record(worker,price=price),
                "REPLAY_CI_NO_WRITE","IDEMPOTENT_RECEIPT")
        try:
            worker.execute("SELECT count(*) FROM public.saas_consent_receipts_m37455_ci")
        except psycopg.errors.InsufficientPrivilege:
            worker.rollback()
        else:
            raise AssertionError("M37455_WORKER_CAN_READ_RAW_RECEIPTS")
        try:
            worker.execute(
                "INSERT INTO public.saas_consent_receipts_m37455_ci "
                "(challenge_id,request_id,tenant_id,administrator_id,session_id,"
                "document_id,document_sha256,price_version_id,confirmation_text,evidence_digest) "
                "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (OTHER_CHALLENGE,R,T,A,SESSION,DOC,DOC_SHA,price,CONFIRM,DIGEST))
        except psycopg.errors.InsufficientPrivilege:
            worker.rollback()
        else:
            raise AssertionError("M37455_WORKER_CAN_INSERT_RAW_RECEIPTS")

    with connect() as admin_conn:
        cur=admin_conn.cursor()
        _assert(cur.execute(
            "SELECT count(*) FROM public.saas_consent_challenges_m37455_ci"
        ).fetchone()[0],1,"CHALLENGE_COUNT")
        _assert(cur.execute(
            "SELECT count(*) FROM public.saas_consent_receipts_m37455_ci"
        ).fetchone()[0],1,"RECEIPT_COUNT")
        _assert(cur.execute(
            "SELECT confirmation_text,evidence_digest,tenant_id,administrator_id,"
            "document_id,document_sha256,price_version_id "
            "FROM public.saas_consent_receipts_m37455_ci"
        ).fetchone(),(CONFIRM,DIGEST,T,A,DOC,DOC_SHA,price),"STORED_EVIDENCE_SCOPE")
        after=cur.execute(
            "SELECT evidence_hash FROM public.contract_acceptances "
            "WHERE id=%s",(UUID("daba0000-0000-4000-8000-000000000040"),)
        ).fetchone()
        _assert(after,("b"*64,),"ORIGINAL_ACCEPTANCE_UNCHANGED")
        for table in ("saas_payment_intents","saas_license_entitlements"):
            _assert(cur.execute(
                f"SELECT count(*) FROM public.{table} WHERE tenant_id=%s",(T,)
            ).fetchone()[0],0,"NO_REAL_"+table)
        _assert(cur.execute(
            "SELECT count(*) FROM public.ledger_entries WHERE tenant_id=%s",(T,)
        ).fetchone()[0],0,"NO_LEDGER")

        # Owner DML is deliberately rejected by append-only triggers too.
        for sql in (
            "UPDATE public.saas_consent_receipts_m37455_ci SET evidence_digest=evidence_digest",
            "DELETE FROM public.saas_consent_receipts_m37455_ci",
            "TRUNCATE public.saas_consent_receipts_m37455_ci",
        ):
            try:
                with admin_conn.transaction():
                    cur.execute(sql)
            except psycopg.errors.RaiseException as exc:
                if "M37455_APPEND_ONLY_CI" not in str(exc):
                    raise
            else:
                raise AssertionError("M37455_APPEND_ONLY_NOT_ENFORCED")
    print("M37455_DISPOSABLE_CONSENT_PERSISTENCE=PASS")
    print("M37455_DUPLICATE_AND_CONCURRENT_REPLAY=PASS")
    print("M37455_EXISTING_CONTRACT_ACCEPTANCE=UNMODIFIED")
    print("M37455_EVIDENCE=CI_SYNTHETIC_NOT_LEGAL_PROOF")
    print("M37455_SAAS_PAYMENT_AND_LICENSE=OFF")
    print("M37455_PIX_REAL=OFF")
    print("M37455_ORIGINAL_LOCAL_DATABASE=UNTOUCHED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
