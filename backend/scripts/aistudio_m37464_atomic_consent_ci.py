#!/usr/bin/env python3
"""M37464: disposable SaaS consent transaction holds token session row lock.

CI-only: no HTTP route, no real identity/legal consent, no PSP, no
license/activation. Two synthetic sessions and the existing M37458
append-only tables are all written to an ephemeral staging database.
"""
from __future__ import annotations

from contextlib import contextmanager
from hashlib import sha256
from uuid import UUID
import os

ENV={
    "GITHUB_ACTIONS":"true",
    "FRCAIXINHA_CI_ISOLATED":"1",
    "PGHOST":"127.0.0.1",
    "PGPORT":"5432",
    "PGDATABASE":"frcaixinha_staging",
    "PGUSER":"postgres",
    "PGPASSWORD":"ci-test-only",
    "PGOPTIONS":"-c frcaixinha.saas_atomic_ci=1 -c frcaixinha.saas_preprep_ci=1",
}
T=UUID("daba0000-0000-4000-8000-000000000010")
A=UUID("daba0000-0000-4000-8000-000000000001")
S=UUID("daba0000-0000-4000-8000-000000000664")
S_REVOKED=UUID("daba0000-0000-4000-8000-000000000665")
C=UUID("daba0000-0000-4000-8000-000000000674")
C_REVOKED=UUID("daba0000-0000-4000-8000-000000000678")
REQUEST=UUID("daba0000-0000-4000-8000-000000000675")
REQUEST_REVOKED=UUID("daba0000-0000-4000-8000-000000000677")
D=UUID("daba0000-0000-4000-8000-000000000030")
ORIGINAL_ACCEPTANCE=UUID("daba0000-0000-4000-8000-000000000040")
TOKEN="m37464-ci-only-lock-session-NEVER-REAL-01"
TOKEN_REVOKED="m37464-ci-only-pre-revoked-NEVER-REAL-02"
CONFIRM="ACEITO_CONTRATO_DE_LICENCA_FR_FINANCE"
ATOMIC_SQL=(
    "SELECT public.m37464_atomic_consent_ci("
    "%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"
)
COUNTS_TABLES=(
    "saas_preprep_challenges_m37458_ci",
    "saas_preprep_receipts_m37458_ci",
    "saas_preprep_drafts_m37458_ci",
)
FINANCIAL_TABLES=(
    "saas_payment_intents","saas_license_entitlements","ledger_entries"
)


def environment_allowed(environ:dict[str,str])->bool:
    return (all(environ.get(k)==v for k,v in ENV.items())
            and environ.get("FR_FINANCE_PIX_REAL","OFF")=="OFF"
            and environ.get("FR_FINANCE_SAAS_REAL","OFF")=="OFF")


@contextmanager
def connect(role="postgres"):
    import psycopg
    if role not in ("postgres","frcaixinha_saas_preprep_ci","frcaixinha_auth_atomic_ci"):
        raise ValueError("M37464_INVALID_CI_ROLE")
    # Explicit CI database and role, never a DSN copied from the environment.
    with psycopg.connect(
        host="127.0.0.1",port=5432,dbname="frcaixinha_staging",
        user=role,password="ci-test-only",connect_timeout=5,
        options="-c frcaixinha.saas_atomic_ci=1 -c frcaixinha.saas_preprep_ci=1",
    ) as conn:
        yield conn


def expect(actual,expected,label):
    if actual != expected:
        raise AssertionError(
            f"M37464_{label}: got {actual!r}, expected {expected!r}"
        )


def consent(conn,action,*,price:UUID,session=S,challenge=C,request=REQUEST,
            token=TOKEN,admin=A,tenant=T,doc=D,confirmation=None):
    if type(price) is not UUID or price.int==0:
        raise AssertionError("M37464_PUBLISHED_PRICE_VERSION_REQUIRED")
    hashed=sha256(token.encode("ascii")).hexdigest()
    return conn.execute(ATOMIC_SQL,(
        action,hashed,session,challenge,request,tenant,admin,
        doc,price,"MONTHLY",confirmation,
    )).fetchone()[0]


def revoke(conn,raw_token):
    return conn.execute(
        "SELECT public.auth_revoke_session(%s)",(raw_token,)
    ).fetchone()[0]


def rowcounts(conn,request=REQUEST):
    return tuple(
        conn.execute(f"SELECT count(*) FROM public.{table} WHERE request_id=%s",
                     (request,)).fetchone()[0]
        for table in COUNTS_TABLES
    )


def financial_counts(conn):
    return tuple(
        conn.execute(f"SELECT count(*) FROM public.{table} WHERE tenant_id=%s",
                     (T,)).fetchone()[0]
        for table in FINANCIAL_TABLES
    )


def original_acceptance(conn):
    return conn.execute(
        "SELECT evidence_hash FROM public.contract_acceptances WHERE id=%s",
        (ORIGINAL_ACCEPTANCE,),
    ).fetchone()


class SyntheticRollback(Exception):
    pass


def main()->int:
    if not environment_allowed(dict(os.environ)):
        print("M37464_BLOCKED=NOT_DISPOSABLE_GITHUB_CI")
        return 1
    import psycopg

    with connect() as owner:
        meta=owner.execute(
            "SELECT current_database(),session_user,current_setting('is_superuser'),"
            "current_setting('frcaixinha.saas_atomic_ci',true),"
            "current_setting('frcaixinha.saas_preprep_ci',true),inet_server_port()"
        ).fetchone()
        expect(meta,("frcaixinha_staging","postgres","on","1","1",5432),
               "DATABASE_SCOPE")
        price_row=owner.execute(
            "SELECT price_version_id FROM public.saas_enrollment_requests_staging "
            "WHERE request_id=%s",
            (UUID("daba0000-0000-4000-8000-000000000050"),),
        ).fetchone()
        if (price_row is None or type(price_row[0]) is not UUID
            or price_row[0].int==0):
            raise AssertionError("M37464_PUBLISHED_CI_PRICE_NOT_FOUND")
        price_version=price_row[0]
        before_fin=financial_counts(owner)
        before_original=original_acceptance(owner)
        expect(rowcounts(owner),(0,0,0),"EMPTY_REQUEST")
        expect(rowcounts(owner,REQUEST_REVOKED),(0,0,0),
               "EMPTY_PRE_REVOKED_REQUEST")

    # Resolve the current published staging price once, on the server side.
    # Never invent a pricing UUID or accept the version from a client.
    def act(conn,action,**kwargs):
        return consent(conn,action,price=price_version,**kwargs)

    # A revoked bearer cannot start a challenge, even if M37458
    # still has a separate, supposedly active, synthetic session record.
    with connect("frcaixinha_auth_atomic_ci") as auth:
        expect(revoke(auth,TOKEN_REVOKED),True,"FIRST_REVOKE")
    with connect("frcaixinha_saas_preprep_ci") as worker:
        expect(
            act(worker,"ISSUE",session=S_REVOKED,
                    challenge=C_REVOKED,request=REQUEST_REVOKED,
                    token=TOKEN_REVOKED),
            "DENIED_CI_TOKEN_REVOKED_OR_SCOPE","REVOKE_WINS_RACE"
        )

    # Roll back ALL three stages together: no partial challenge, receipt
    # or draft may be visible after a synthetic application failure.
    try:
        with connect("frcaixinha_saas_preprep_ci") as worker:
            expect(act(worker,"ISSUE"),
                   "CHALLENGE_ISSUED_CI","ROLLBACK_ISSUE")
            expect(act(worker,"ACCEPT",confirmation=CONFIRM),
                   "CONSENT_RECORDED_CI_NO_LEGAL_PROOF","ROLLBACK_ACCEPT")
            expect(act(worker,"PREPARE"),
                   "DRAFT_PREPARED_CI_NO_PAYMENT","ROLLBACK_PREPARE")
            raise SyntheticRollback()
    except SyntheticRollback:
        pass

    with connect() as owner:
        expect(rowcounts(owner),(0,0,0),"ATOMIC_ROLLBACK_ALL_TABLES")

    # Commit ISSUE -> ACCEPT -> PREPARE with one session row lock held
    # throughout the transaction. Competing bearer revocation cannot
    # commit in between the validation and the synthetic receipt.
    with connect("frcaixinha_saas_preprep_ci") as worker:
        expect(act(worker,"ISSUE"),"CHALLENGE_ISSUED_CI","ISSUE")
        expect(act(worker,"ACCEPT",confirmation=CONFIRM),
               "CONSENT_RECORDED_CI_NO_LEGAL_PROOF","ACCEPT")
        expect(act(worker,"PREPARE"),
               "DRAFT_PREPARED_CI_NO_PAYMENT","PREPARE")

        lock_blocked=False
        try:
            with connect("frcaixinha_auth_atomic_ci") as auth:
                auth.execute("SET LOCAL lock_timeout = '350ms'")
                revoke(auth,TOKEN)
        except psycopg.errors.LockNotAvailable as exc:
            if exc.sqlstate=="55P03":
                lock_blocked=True
            else:
                raise
        if not lock_blocked:
            raise AssertionError("M37464_CONCURRENT_REVOKER_NOT_BLOCKED")

    with connect() as owner:
        expect(rowcounts(owner),(1,1,1),"SINGLE_COMMITTED_CHAIN")
        expect(owner.execute(
            "SELECT revoked_at IS NULL FROM public.sessions WHERE id=%s",
            (S,),
        ).fetchone()[0],True,"NO_PARTIAL_REVOCATION")

    with connect("frcaixinha_saas_preprep_ci") as worker:
        expect(act(worker,"PREPARE"),
               "REPLAY_PREPARE_CI_NO_WRITE","IDEMPOTENCY")

    # After the transaction commits, revocation succeeds. The same
    # worker/token can no longer replay ACCEPT or PREPARE.
    with connect("frcaixinha_auth_atomic_ci") as auth:
        expect(revoke(auth,TOKEN),True,"REVOCATION_AFTER_COMMIT")
    with connect("frcaixinha_saas_preprep_ci") as worker:
        expect(act(worker,"ACCEPT",confirmation=CONFIRM),
               "DENIED_CI_TOKEN_REVOKED_OR_SCOPE","REVOKED_ACCEPT")
        expect(act(worker,"PREPARE"),
               "DENIED_CI_TOKEN_REVOKED_OR_SCOPE","REVOKED_PREPARE")
        expect(act(worker,"ISSUE",token=TOKEN_REVOKED),
               "DENIED_CI_TOKEN_REVOKED_OR_SCOPE","FOREIGN_TOKEN")

    with connect() as owner:
        expect(rowcounts(owner),(1,1,1),"NO_POST_REVOKE_RECORDS")
        expect(rowcounts(owner,REQUEST_REVOKED),(0,0,0),
               "NO_PRE_REVOKED_RECORDS")
        expect(financial_counts(owner),before_fin,
               "FINANCIAL_TABLES_UNCHANGED")
        expect(original_acceptance(owner),before_original,
               "ORIGINAL_CONTRACT_UNMODIFIED")
        proof=owner.execute(
            "SELECT c.server_issued_at,r.server_recorded_at,d.server_prepared_at,"
            "d.legal_consent_verified,d.payment_authorized,"
            "d.license_authorized,d.activation_authorized "
            "FROM public.saas_preprep_challenges_m37458_ci c "
            "JOIN public.saas_preprep_receipts_m37458_ci r "
            " ON r.challenge_id=c.challenge_id "
            "JOIN public.saas_preprep_drafts_m37458_ci d "
            " ON d.challenge_id=r.challenge_id "
            "WHERE c.request_id=%s",(REQUEST,)
        ).fetchone()
        if not proof or not (proof[0]<=proof[1]<=proof[2]):
            raise AssertionError("M37464_INVALID_CONSENT_CHRONOLOGY")
        expect(proof[3:],(False,False,False,False),
               "NO_REAL_AUTHORIZATION")

    print("M37464_ATOMIC_TOKEN_SESSION_LOCK=PASS")
    print("M37464_CONCURRENT_REVOKER_BLOCKED_UNTIL_COMMIT=PASS")
    print("M37464_REVOKE_FIRST_BLOCKS_ACCEPTANCE=PASS")
    print("M37464_ROLLBACK_ALL_THREE_STAGES=PASS")
    print("M37464_IDEMPOTENT_PREPARATION=PASS")
    print("M37464_FINANCIAL_TABLES_UNCHANGED=PASS")
    print("M37464_REAL_LEGAL_CONSENT_AND_IDENTITY=NOT_ATTESTED")
    print("M37464_PAYMENT_LICENSE_PIX_ACTIVATION=OFF")
    print("M37464_TERMUX_LOCAL_DATABASE=UNTOUCHED")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
