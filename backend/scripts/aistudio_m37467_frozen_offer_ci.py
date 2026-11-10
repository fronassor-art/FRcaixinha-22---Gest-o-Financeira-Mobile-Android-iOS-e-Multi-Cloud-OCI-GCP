#!/usr/bin/env python3
"""M37467: disposable CI frozen offer/version/price idempotence + lock race.

No production billing, legal consent or local DB access. This runner
creates synthetic acceptances only inside frcaixinha_staging on GH Actions.
"""
from __future__ import annotations

from contextlib import contextmanager
from decimal import Decimal
from hashlib import sha256
from uuid import UUID
import os

ENV={
    "GITHUB_ACTIONS":"true","FRCAIXINHA_CI_ISOLATED":"1",
    "PGHOST":"127.0.0.1","PGPORT":"5432",
    "PGDATABASE":"frcaixinha_staging","PGUSER":"postgres",
    "PGPASSWORD":"ci-test-only",
    "PGOPTIONS":"-c frcaixinha.saas_frozen_ci=1 -c frcaixinha.saas_atomic_ci=1 -c frcaixinha.saas_preprep_ci=1",
}
S=UUID("daba0000-0000-4000-8000-000000000686")
R=UUID("daba0000-0000-4000-8000-000000000687")
C=UUID("daba0000-0000-4000-8000-000000000688")
T=UUID("daba0000-0000-4000-8000-000000000010")
A=UUID("daba0000-0000-4000-8000-000000000001")
D=UUID("daba0000-0000-4000-8000-000000000030")
TOKEN="m37467-ci-frozen-offer-NEVER-REAL-01"
CONFIRM="ACEITO_CONTRATO_DE_LICENCA_FR_FINANCE"
FUNC=(
    "SELECT public.m37467_frozen_offer_transition_ci("
    "%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"
)
STAGES=(
    "saas_preprep_challenges_m37458_ci",
    "saas_preprep_receipts_m37458_ci",
    "saas_preprep_drafts_m37458_ci",
)
MONEY=("saas_payment_intents","saas_license_entitlements","ledger_entries")


def allowed(env:dict[str,str])->bool:
    return (all(env.get(k)==v for k,v in ENV.items())
        and env.get("FR_FINANCE_PIX_REAL","OFF")=="OFF"
        and env.get("FR_FINANCE_SAAS_REAL","OFF")=="OFF"
        and env.get("FR_FINANCE_LICENSE_REAL","OFF")=="OFF")


@contextmanager
def connect(role="postgres"):
    import psycopg
    if role not in ("postgres","frcaixinha_saas_preprep_ci",
                   "frcaixinha_auth_atomic_ci"):
        raise ValueError("M37467_CI_ROLE_NOT_ALLOWED")
    with psycopg.connect(
        host="127.0.0.1",port=5432,dbname="frcaixinha_staging",
        user=role,password="ci-test-only",connect_timeout=5,
        options="-c frcaixinha.saas_frozen_ci=1 -c frcaixinha.saas_atomic_ci=1 -c frcaixinha.saas_preprep_ci=1",
    ) as db:
        yield db


def expect(actual,expected,label):
    if actual!=expected:
        raise AssertionError(f"M37467_{label}: {actual!r} != {expected!r}")


def transition(conn,action,price_id,document_sha,price_cents, *,
               request=R,challenge=C,session=S,tenant=T,admin=A,
               document=D,token=TOKEN,period="MONTHLY",confirmation=None):
    return conn.execute(FUNC,(
        action,sha256(token.encode("ascii")).hexdigest(),
        session,challenge,request,tenant,admin,document,price_id,
        period,confirmation,document_sha,price_cents,
    )).fetchone()[0]


def read_rows(conn):
    return tuple(conn.execute(
        "SELECT count(*) FROM public."+name+" WHERE request_id=%s",(R,)
    ).fetchone()[0] for name in STAGES)


def financial(conn):
    return tuple(conn.execute(
        "SELECT count(*) FROM public."+name+" WHERE tenant_id=%s",(T,)
    ).fetchone()[0] for name in MONEY)


def snapshot(conn):
    return conn.execute(
        "SELECT challenge_id,session_id,tenant_id,admin_id,document_id,"
        "document_sha,price_version_id,billing_period,frozen_price_cents,"
        "recorded_at,evidence_source "
        "FROM public.saas_frozen_offer_m37467_ci WHERE request_id=%s",
        (R,),
    ).fetchone()


def main()->int:
    if not allowed(dict(os.environ)):
        print("M37467_BLOCKED=DISPOSABLE_GITHUB_ONLY")
        return 1
    import psycopg
    from psycopg.errors import LockNotAvailable

    # All authoritative values are read from the existing CI published
    # contract and price tables. No price UUID or cents are invented.
    with connect() as owner:
        meta=owner.execute(
            "SELECT current_database(),session_user,current_setting('is_superuser'),"
            "current_setting('frcaixinha.saas_frozen_ci',true),inet_server_port()"
        ).fetchone()
        expect(meta,("frcaixinha_staging","postgres","on","1",5432),
               "DATABASE_IDENTITY")
        price=owner.execute(
            "SELECT v.id,v.monthly_price,d.sha256,d.version_label "
            "FROM public.saas_enrollment_requests_staging q "
            "JOIN public.platform_license_price_versions v "
            " ON v.id=q.price_version_id "
            "JOIN public.contract_documents d ON d.id=%s "
            "WHERE q.request_id=%s AND d.published_at IS NOT NULL",
            (D,UUID("daba0000-0000-4000-8000-000000000050")),
        ).fetchone()
        if price is None or type(price[1]) is not Decimal:
            raise AssertionError("M37467_PUBLISHED_OFFER_ABSENT")
        price_id,amount,doc_sha,version_label=price
        cents=amount*Decimal("100")
        if (type(price_id) is not UUID or price_id.int==0
            or cents!=cents.to_integral_value() or cents<=0):
            raise AssertionError("M37467_PUBLISHED_PRICE_NOT_EXACT_CENTS")
        cents=int(cents)
        baseline_money=financial(owner)
        expect(read_rows(owner),(0,0,0),"NEW_REQUEST_EMPTY")
        expect(snapshot(owner),None,"NO_FROZEN_OFFER_BEFORE_ISSUE")

    # M37467 must not accept a client-modified price or contract hash.
    # ISSUE, ACCEPT and PREPARE hold one SQL transaction and the
    # SELECT ... FOR SHARE locks on published price/doc rows.
    with connect("frcaixinha_saas_preprep_ci") as worker:
        def call(action,**kwargs):
            return transition(worker,action,price_id,doc_sha,cents,**kwargs)
        expect(call("ISSUE"),"CHALLENGE_ISSUED_CI","FIRST_ISSUE")
        expect(call("ISSUE"),"REPLAY_ISSUE_CI_NO_WRITE","REPLAY_ISSUE")
        expect(
            call("ISSUE",challenge=UUID("daba0000-0000-4000-8000-000000000699")),
            "DENIED_CI_FROZEN_REQUEST_COLLISION","CHALLENGE_COLLISION"
        )
        expect(transition(worker,"ACCEPT",price_id,doc_sha,cents+1,
                          confirmation=CONFIRM),
               "DENIED_CI_FROZEN_PUBLISHED_OFFER_DRIFT",
               "PRICE_CHANGED_BETWEEN_READS")
        expect(transition(worker,"ACCEPT",price_id,"b"*64,cents,
                          confirmation=CONFIRM),
               "DENIED_CI_FROZEN_PUBLISHED_OFFER_DRIFT",
               "DOCUMENT_CHANGED_BETWEEN_READS")
        expect(transition(worker,"ACCEPT",price_id,doc_sha,cents,
                          token="m37467-unrecognized-token-NEVER-REAL",
                          confirmation=CONFIRM),
               "DENIED_CI_TOKEN_REVOKED_OR_SCOPE","UNVERIFIED_TOKEN")
        expect(call("ACCEPT",confirmation=CONFIRM),
               "CONSENT_RECORDED_CI_NO_LEGAL_PROOF","ACCEPT")
        expect(call("ACCEPT",confirmation=CONFIRM),
               "REPLAY_ACCEPT_CI_NO_WRITE","ACCEPT_REPLAY")
        expect(call("PREPARE"),"DRAFT_PREPARED_CI_NO_PAYMENT","PREPARE")
        expect(call("PREPARE"),"REPLAY_PREPARE_CI_NO_WRITE","PREPARE_REPLAY")
        # A concurrent admin update of the canonical published price
        # and contract MUST block until this transaction finishes.
        for table,update,args in (
            ("price",
             "UPDATE public.platform_license_price_versions "
             "SET monthly_price=monthly_price+1 WHERE id=%s",
             (price_id,)),
            ("document",
             "UPDATE public.contract_documents "
             "SET version_label=version_label||'-RACE' WHERE id=%s",
             (D,)),
        ):
            locked=False
            try:
                with connect() as owner:
                    owner.execute("SET LOCAL lock_timeout = '350ms'")
                    owner.execute(update,args)
            except LockNotAvailable as exc:
                if exc.sqlstate=="55P03":
                    locked=True
                else:
                    raise
            if not locked:
                raise AssertionError("M37467_PUBLISHED_"+table+"_LOCK_NOT_HELD")

    # Commit completed. Confirm one append-only quote, receipt and draft.
    with connect() as owner:
        expect(read_rows(owner),(1,1,1),"SINGLE_COMMITTED_CHAIN")
        snap=snapshot(owner)
        if snap is None:
            raise AssertionError("M37467_FROZEN_SNAPSHOT_MISSING")
        expect(
            snap[:9],
            (C,S,T,A,D,doc_sha,price_id,"MONTHLY",cents),
            "IMMUTABLE_FROZEN_CONTRACT_AND_PRICE",
        )
        expect(snap[-1],"CI_FROZEN_SYNTHETIC_NOT_LEGAL","NONLEGAL_SOURCE")
        persisted=owner.execute(
            "SELECT v.monthly_price,d.sha256,d.version_label "
            "FROM public.platform_license_price_versions v "
            "JOIN public.contract_documents d ON d.id=%s "
            "WHERE v.id=%s",(D,price_id),
        ).fetchone()
        expect(persisted,(amount,doc_sha,version_label),
               "PUBLISHED_OFFER_NOT_CHANGED_BY_RACE")
        expect(financial(owner),baseline_money,"FINANCIAL_UNCHANGED")

    # Separate transaction: same request/offer only replays and never
    # changes the frozen contract even after the original commit.
    with connect("frcaixinha_saas_preprep_ci") as worker:
        expect(transition(worker,"PREPARE",price_id,doc_sha,cents),
               "REPLAY_PREPARE_CI_NO_WRITE","AFTER_COMMIT_IDEMPOTENT")
        expect(transition(worker,"ISSUE",price_id,doc_sha,cents,
                          challenge=UUID("daba0000-0000-4000-8000-000000000699")),
               "DENIED_CI_FROZEN_REQUEST_COLLISION","AFTER_COMMIT_COLLISION")
        expect(transition(worker,"PREPARE",price_id,doc_sha,cents+1),
               "DENIED_CI_FROZEN_PUBLISHED_OFFER_DRIFT","AFTER_COMMIT_PRICE_DRIFT")

    # Revocation blocks even an otherwise valid frozen quote.
    with connect("frcaixinha_auth_atomic_ci") as revoker:
        expect(revoker.execute(
            "SELECT public.auth_revoke_session(%s)",(TOKEN,)
        ).fetchone()[0],True,"REVOCATION")
    with connect("frcaixinha_saas_preprep_ci") as worker:
        expect(transition(worker,"PREPARE",price_id,doc_sha,cents),
               "DENIED_CI_TOKEN_REVOKED_OR_SCOPE","REVOKED_REPLAY")

    with connect() as owner:
        expect(read_rows(owner),(1,1,1),"AFTER_REVOKE_SINGLE_CHAIN")
        expect(snapshot(owner),snap,"FROZEN_SNAPSHOT_UNCHANGED")
        expect(financial(owner),baseline_money,"AFTER_REVOKE_NO_MONEY")
        expect(owner.execute(
            "SELECT legal_consent_verified,payment_authorized,"
            "license_authorized,activation_authorized "
            "FROM public.saas_preprep_drafts_m37458_ci WHERE request_id=%s",
            (R,),
        ).fetchone(),(False,False,False,False),
               "REAL_PERMISSIONS_ALL_OFF")

    print("M37467_FROZEN_DOCUMENT_PRICE_CENTS=PASS")
    print("M37467_SAME_REQUEST_REPLAY_NO_DUPLICATE=PASS")
    print("M37467_CHANGED_PRICE_SHA_OR_CHALLENGE=DENIED")
    print("M37467_CONCURRENT_PRICE_AND_DOCUMENT_UPDATES=LOCKED_OUT")
    print("M37467_REVOKED_SESSION_REPLAY=DENIED")
    print("M37467_APPEND_ONLY_QUOTE_AFTER_COMMIT=PASS")
    print("M37467_FINANCIAL_TABLES_UNCHANGED=PASS")
    print("M37467_IDENTITY_AND_LEGAL_CONSENT=CI_SYNTHETIC_NOT_REAL")
    print("M37467_LICENSE_PAYMENT_PIX_ACTIVATION=OFF")
    print("M37467_TERMUX_ORIGINAL_DATABASE=UNTOUCHED")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
