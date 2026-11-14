#!/usr/bin/env python3
"""M37458: synthetic consent BEFORE SaaS draft, disposable PG only.

CI fixture session is NOT real authentication. Draft is NOT a paid SaaS
subscription. No contract_acceptances, payment, entitlements or ledger writes.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from uuid import UUID
import os

CI_ENV={
    "GITHUB_ACTIONS":"true","FRCAIXINHA_CI_ISOLATED":"1",
    "PGHOST":"127.0.0.1","PGPORT":"5432",
    "PGDATABASE":"frcaixinha_staging","PGUSER":"postgres",
    "PGPASSWORD":"ci-test-only",
    "PGOPTIONS":"-c frcaixinha.saas_preprep_ci=1",
}
T=UUID("daba0000-0000-4000-8000-000000000010")
A=UUID("daba0000-0000-4000-8000-000000000001")
S=UUID("daba0000-0000-4000-8000-000000000581")
C=UUID("daba0000-0000-4000-8000-000000000582")
REQUEST=UUID("daba0000-0000-4000-8000-000000000583")
D=UUID("daba0000-0000-4000-8000-000000000030")
OTHER=UUID("daba0000-0000-4000-8000-000000000099")
ACCEPTANCE=UUID("daba0000-0000-4000-8000-000000000040")
CONFIRM="ACEITO_CONTRATO_DE_LICENCA_FR_FINANCE"
TRANSITION="SELECT public.m37458_transition_ci(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"


def environment_allowed(env:dict[str,str])->bool:
    return all(env.get(k)==v for k,v in CI_ENV.items())


def expect(got,want,label):
    if got!=want:
        raise AssertionError(f"M37458_{label}: expected {want!r}, got {got!r}")


@contextmanager
def connect(user="postgres"):
    import psycopg
    with psycopg.connect(
        host="127.0.0.1",port=5432,dbname="frcaixinha_staging",
        user=user,password="ci-test-only",connect_timeout=5,
        options="-c frcaixinha.saas_preprep_ci=1",
    ) as conn:
        yield conn


def transition(conn,*,action,price,session=S,challenge=C,request=REQUEST,
               tenant=T,admin=A,document=D,period="MONTHLY",confirmation=None):
    return conn.execute(TRANSITION,(
        action,session,challenge,request,tenant,admin,document,price,
        period,confirmation,
    )).fetchone()[0]


def main()->int:
    if not environment_allowed(dict(os.environ)):
        print("M37458_BLOCKED=NOT_DISPOSABLE_GITHUB_CI")
        return 1
    import psycopg
    with connect() as owner:
        expect(owner.execute(
            "SELECT current_database(),session_user,current_setting('is_superuser'),"
            "current_setting('frcaixinha.saas_preprep_ci',true),inet_server_port()"
        ).fetchone(),("frcaixinha_staging","postgres","on","1",5432),"IDENTITY")
        price=owner.execute(
            "SELECT price_version_id FROM public.saas_enrollment_requests_staging "
            "WHERE request_id=%s",
            (UUID("daba0000-0000-4000-8000-000000000050"),)
        ).fetchone()[0]
        before=owner.execute(
            "SELECT evidence_hash FROM public.contract_acceptances WHERE id=%s",
            (ACCEPTANCE,)
        ).fetchone()[0]
        expect(before,"b"*64,"PLACEHOLDER_UNMODIFIED_BEFORE")
        for role in ("frcaixinha_app_role","frcaixinha_auth_role",
                     "frcaixinha_saas_preprep_ci"):
            for table in ("saas_preprep_sessions_m37458_ci",
                          "saas_preprep_challenges_m37458_ci",
                          "saas_preprep_receipts_m37458_ci",
                          "saas_preprep_drafts_m37458_ci"):
                for privilege in ("SELECT","INSERT","UPDATE","DELETE"):
                    expect(owner.execute(
                        "SELECT has_table_privilege(%s,%s,%s)",
                        (role,"public."+table,privilege)
                    ).fetchone()[0],False,"NO_DIRECT_TABLE_ACCESS")
        expect(owner.execute(
            "SELECT has_function_privilege('frcaixinha_app_role',"
            "'public.m37458_transition_ci(text,uuid,uuid,uuid,uuid,uuid,uuid,uuid,text,text)',"
            "'EXECUTE')"
        ).fetchone()[0],False,"NO_APP_EXECUTION")

    with connect("frcaixinha_saas_preprep_ci") as worker:
        # A preparation cannot be issued before consent, or without challenge.
        expect(transition(worker,action="PREPARE",price=price),
               "DENIED_CI","NO_CHALLENGE")
        expect(transition(worker,action="ISSUE",price=price,tenant=OTHER),
               "DENIED_CI","WRONG_TENANT")
        expect(transition(worker,action="ISSUE",price=price,admin=OTHER),
               "DENIED_CI","WRONG_ADMIN")
        expect(transition(worker,action="ISSUE",price=OTHER),
               "DENIED_CI","WRONG_PRICE")
        expect(transition(worker,action="ISSUE",price=price,document=OTHER),
               "DENIED_CI","WRONG_CONTRACT")
        expect(transition(worker,action="ISSUE",price=price,session=OTHER),
               "DENIED_CI","WRONG_SESSION")
        expect(transition(worker,action="ISSUE",price=price),
               "CHALLENGE_ISSUED_CI","CHALLENGE")
        expect(transition(worker,action="ISSUE",price=price),
               "REPLAY_ISSUE_CI_NO_WRITE","REPLAY_ISSUE")
        expect(transition(worker,action="ISSUE",price=price,challenge=OTHER),
               "CHALLENGE_COLLISION_CI_DENIED","ISSUE_COLLISION")
        expect(transition(worker,action="PREPARE",price=price),
               "CONSENT_BEFORE_PREPARATION_REQUIRED","NO_RECEIPT")
        expect(transition(worker,action="ACCEPT",price=price,confirmation="ACEITO"),
               "DENIED_CI","MISSING_EXPLICIT_CONSENT")
        expect(transition(worker,action="ACCEPT",price=price,confirmation=CONFIRM,
                          tenant=OTHER),"DENIED_CI","FOREIGN_TENANT_ACCEPT")
        expect(transition(worker,action="ACCEPT",price=price,confirmation=CONFIRM),
               "CONSENT_RECORDED_CI_NO_LEGAL_PROOF","ACCEPT")
        expect(transition(worker,action="ACCEPT",price=price,confirmation=CONFIRM),
               "REPLAY_ACCEPT_CI_NO_WRITE","REPLAY_ACCEPT")
        expect(transition(worker,action="ACCEPT",price=price,confirmation=CONFIRM,
                          challenge=OTHER),"DENIED_CI","OTHER_CHALLENGE")
        expect(transition(worker,action="PREPARE",price=price,request=OTHER),
               "DENIED_CI","WRONG_REQUEST_PREPARE")

    # Multiple independent worker sessions race on the same request.
    def prepare(_):
        with connect("frcaixinha_saas_preprep_ci") as w:
            return transition(w,action="PREPARE",price=price)
    with ThreadPoolExecutor(max_workers=5) as pool:
        outcomes=list(pool.map(prepare,range(5)))
    expect(outcomes.count("DRAFT_PREPARED_CI_NO_PAYMENT"),1,"ONE_DRAFT")
    expect(outcomes.count("REPLAY_PREPARE_CI_NO_WRITE"),4,"REPLAY_DRAFT")

    with connect("frcaixinha_saas_preprep_ci") as worker:
        expect(transition(worker,action="PREPARE",price=price),
               "REPLAY_PREPARE_CI_NO_WRITE","STABLE_PREPARATION")
        try:
            worker.execute("SELECT count(*) FROM public.saas_preprep_drafts_m37458_ci")
        except psycopg.errors.InsufficientPrivilege:
            worker.rollback()
        else:
            raise AssertionError("M37458_WORKER_RAW_DRAFT_READ_ALLOWED")

    with connect() as owner:
        rows=owner.execute(
            "SELECT s.server_issued_at,c.server_issued_at,c.server_expires_at,"
            "r.server_recorded_at,p.server_prepared_at,p.status,"
            "p.legal_consent_verified,p.payment_authorized,"
            "p.license_authorized,p.activation_authorized "
            "FROM public.saas_preprep_sessions_m37458_ci s "
            "JOIN public.saas_preprep_challenges_m37458_ci c ON c.session_id=s.session_id "
            "JOIN public.saas_preprep_receipts_m37458_ci r ON r.challenge_id=c.challenge_id "
            "JOIN public.saas_preprep_drafts_m37458_ci p ON p.challenge_id=r.challenge_id"
        ).fetchall()
        if len(rows)!=1:
            raise AssertionError("M37458_MISSING_SINGLE_ATOMIC_CHAIN")
        si,ch,ex,re,pr,state,legal,payment,license_,activation=rows[0]
        if not(si<=ch<=re<=pr and re<ex):
            raise AssertionError("M37458_CONSENT_DID_NOT_PRECEDE_PREPARATION")
        expect((state,legal,payment,license_,activation),
               ("CI_DRAFT_NO_PAYMENT",False,False,False,False),
               "DRAFT_NOT_FINANCIAL_AUTHORITY")
        for table in ("saas_preprep_challenges_m37458_ci",
                      "saas_preprep_receipts_m37458_ci",
                      "saas_preprep_drafts_m37458_ci"):
            expect(owner.execute(
                "SELECT count(*) FROM public."+table
            ).fetchone()[0],1,"SINGLE_ROW_"+table)
        expect(owner.execute(
            "SELECT evidence_hash FROM public.contract_acceptances WHERE id=%s",
            (ACCEPTANCE,)
        ).fetchone()[0],before,"CONTRACT_ACCEPTANCE_UNTOUCHED")
        for table in ("saas_payment_intents","saas_license_entitlements"):
            expect(owner.execute(
                "SELECT count(*) FROM public."+table+" WHERE tenant_id=%s",
                (T,)
            ).fetchone()[0],0,"NO_MONEY_OR_LICENSE")
        expect(owner.execute(
            "SELECT count(*) FROM public.ledger_entries WHERE tenant_id=%s",(T,)
        ).fetchone()[0],0,"NO_LEDGER")
        for statement in (
            "UPDATE public.saas_preprep_drafts_m37458_ci SET status=status",
            "DELETE FROM public.saas_preprep_drafts_m37458_ci",
            "TRUNCATE public.saas_preprep_drafts_m37458_ci",
        ):
            try:
                with owner.transaction():
                    owner.execute(statement)
            except psycopg.errors.RaiseException as exc:
                if "M37455_APPEND_ONLY_CI" not in str(exc):
                    raise
            else:
                raise AssertionError("M37458_APPEND_ONLY_BYPASS")
    print("M37458_DISPOSABLE_PREPARATION_AFTER_CONSENT=PASS")
    print("M37458_CI_SESSION_READBACK=PASS_NOT_REAL_IDENTITY")
    print("M37458_CONCURRENT_SINGLE_DRAFT=PASS")
    print("M37458_ORIGINAL_ACCEPTANCE=UNMODIFIED")
    print("M37458_REAL_PAYMENT_LICENSE_PIX_ACTIVATION=OFF")
    print("M37458_LOCAL_DATABASE=UNTOUCHED")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
