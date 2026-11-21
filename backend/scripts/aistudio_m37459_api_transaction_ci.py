#!/usr/bin/env python3
"""M37459: disposable PG atomic rollback and CI-only API-contract adapter.

No real route is mounted, no user session is authenticated, and no SaaS
payment/entitlement/activation is permitted. Only preprep M37458 CI tables
may be written. Never run this script outside GitHub disposable staging.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID
import os

from app.saas_acceptance_api_contract_ci import (
    CIPrincipal, CIPublishedOffer, CITransition, evaluate_api_contract_ci,
)

EXPECTED_ENV={
    "GITHUB_ACTIONS":"true",
    "FRCAIXINHA_CI_ISOLATED":"1",
    "PGHOST":"127.0.0.1",
    "PGPORT":"5432",
    "PGDATABASE":"frcaixinha_staging",
    "PGUSER":"postgres",
    "PGPASSWORD":"ci-test-only",
    "PGOPTIONS":"-c frcaixinha.saas_preprep_ci=1",
}
API_ENV={"GITHUB_ACTIONS":"true","FRCAIXINHA_CI_ISOLATED":"1",
         "ENVIRONMENT":"ci","FR_FINANCE_SAAS_REAL":"OFF",
         "FR_FINANCE_PIX_REAL":"OFF"}
T=UUID("daba0000-0000-4000-8000-000000000010")
A=UUID("daba0000-0000-4000-8000-000000000001")
S=UUID("daba0000-0000-4000-8000-000000000581")
C=UUID("daba0000-0000-4000-8000-000000000595")
REQUEST=UUID("daba0000-0000-4000-8000-000000000594")
D=UUID("daba0000-0000-4000-8000-000000000030")
ACCEPTANCE=UUID("daba0000-0000-4000-8000-000000000040")
CONFIRM="ACEITO_CONTRATO_DE_LICENCA_FR_FINANCE"
SQL="SELECT public.m37458_transition_ci(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"


def environment_allowed(env:dict[str,str])->bool:
    return all(env.get(k)==v for k,v in EXPECTED_ENV.items())


@contextmanager
def connect(user="postgres"):
    import psycopg
    with psycopg.connect(
        host="127.0.0.1",port=5432,dbname="frcaixinha_staging",
        user=user,password="ci-test-only",connect_timeout=5,
        options="-c frcaixinha.saas_preprep_ci=1",
    ) as conn:
        yield conn


def assert_eq(actual,want,reason):
    if actual!=want:
        raise AssertionError(f"M37459_{reason}: expected {want!r}, got {actual!r}")


def _execute(conn,action,price,confirmation=None):
    return conn.execute(SQL,(action,S,C,REQUEST,T,A,D,price,
                             "MONTHLY",confirmation)).fetchone()[0]


class DisposablePostgresAdapter:
    """CI test adapter. Not a real network client or license executor."""
    def transition(self,*,action,request_id,challenge_id,principal,offer,confirmation):
        if (request_id!=REQUEST or challenge_id!=C
            or principal.user_id!=A or principal.tenant_id!=T
            or principal.session_id!=S or offer.tenant_id!=T
            or offer.document_id!=D or offer.billing_period!="MONTHLY"):
            return CITransition("DENIED_CI")
        with connect("frcaixinha_saas_preprep_ci") as worker:
            result=worker.execute(SQL,(
                action,principal.session_id,challenge_id,request_id,
                principal.tenant_id,principal.user_id,offer.document_id,
                offer.price_version_id,offer.billing_period,confirmation,
            )).fetchone()[0]
        return CITransition(result)


def _record_counts(conn):
    return tuple(conn.execute(f"SELECT count(*) FROM public.{name} WHERE request_id=%s",
                    (REQUEST,)).fetchone()[0] for name in (
        "saas_preprep_challenges_m37458_ci",
        "saas_preprep_receipts_m37458_ci",
        "saas_preprep_drafts_m37458_ci",
    ))


def _api(action,*,principal,offer,executor):
    body={"action":action,"request_id":str(REQUEST)}
    if action in ("ACCEPT","PREPARE"):
        body["challenge_id"]=str(C)
    if action=="ACCEPT":
        body["confirmation"]=CONFIRM
    return evaluate_api_contract_ci(
        body=body,principal=principal,offer=offer,
        request_id_server=REQUEST,challenge_id_server=C,
        executor=executor,env=API_ENV,now=datetime.now(timezone.utc),
    )


class IntentionalRollback(Exception):
    pass


def main()->int:
    if not environment_allowed(dict(os.environ)):
        print("M37459_BLOCKED=NOT_DISPOSABLE_GITHUB_CI")
        return 1

    import psycopg
    with connect() as owner:
        meta=owner.execute(
            "SELECT current_database(),session_user,current_setting('is_superuser'),"
            "current_setting('frcaixinha.saas_preprep_ci',true),inet_server_port()"
        ).fetchone()
        assert_eq(meta,("frcaixinha_staging","postgres","on","1",5432),"DB_IDENTITY")
        row=owner.execute(
            "SELECT s.session_id,s.tenant_id,s.admin_id,s.role,"
            "s.session_active,s.email_verified,s.server_expires_at,"
            "d.id,d.sha256,d.published_at,v.id,v.monthly_price "
            "FROM public.saas_preprep_sessions_m37458_ci s "
            "JOIN public.contract_documents d ON d.id=%s "
            "JOIN public.platform_license_price_versions v ON v.id=("
            " SELECT price_version_id FROM public.saas_enrollment_requests_staging"
            " WHERE request_id=%s) "
            "WHERE s.session_id=%s",(D,UUID("daba0000-0000-4000-8000-000000000050"),S)
        ).fetchone()
        if not row:
            raise AssertionError("M37459_M37458_BASELINE_ABSENT")
        sid,tenant,admin,role,active,email,expiry,doc,sha,pub,price,amount=row
        price_cents=amount*Decimal(100)
        if price_cents!=price_cents.to_integral_value():
            raise AssertionError("M37459_INVALID_CENT_AMOUNT")
        principal=CIPrincipal(
            user_id=admin,tenant_id=tenant,session_id=sid,
            active_role=role,active=active,email_verified=email,
            server_checked_at=datetime.now(timezone.utc),expires_at=expiry,
        )
        offer=CIPublishedOffer(
            tenant_id=tenant,document_id=doc,document_sha256=sha,
            price_version_id=price,billing_period="MONTHLY",
            price_cents=int(price_cents),published_at=pub,state="ACTIVE",
        )
        assert_eq(_record_counts(owner),(0,0,0),"EMPTY_CI_REQUEST_BEFORE_ROLLBACK")

    # One transaction for challenge, receipt and draft. Emulate a failure
    # after successful steps. All effects MUST disappear on rollback.
    try:
        with connect("frcaixinha_saas_preprep_ci") as worker:
            assert_eq(_execute(worker,"ISSUE",price),"CHALLENGE_ISSUED_CI","TX_ISSUE")
            assert_eq(_execute(worker,"ACCEPT",price,CONFIRM),
                      "CONSENT_RECORDED_CI_NO_LEGAL_PROOF","TX_ACCEPT")
            assert_eq(_execute(worker,"PREPARE",price),
                      "DRAFT_PREPARED_CI_NO_PAYMENT","TX_PREPARE")
            raise IntentionalRollback()
    except IntentionalRollback:
        pass

    with connect() as owner:
        assert_eq(_record_counts(owner),(0,0,0),"FULL_ROLLBACK_ALL_TABLES")
        for table in ("saas_payment_intents","saas_license_entitlements"):
            assert_eq(owner.execute(
                "SELECT count(*) FROM public."+table+" WHERE tenant_id=%s",
                (T,)
            ).fetchone()[0],0,"NO_REAL_PAYMENT_OR_LICENSE")

    adapter=DisposablePostgresAdapter()
    blocked=_api("PREPARE",principal=principal,offer=offer,executor=adapter)
    assert_eq((blocked.status_code,blocked.state),
              (409,"CI_TRANSACTION_DENIED"),"PREPARE_BEFORE_ACCEPT_REJECTED")
    issue=_api("ISSUE",principal=principal,offer=offer,executor=adapter)
    assert_eq((issue.status_code,issue.state),
              (202,"CI_CHALLENGE_ISSUED_CI"),"API_ISSUE")
    accept=_api("ACCEPT",principal=principal,offer=offer,executor=adapter)
    assert_eq((accept.status_code,accept.state),
              (202,"CI_CONSENT_RECORDED_CI_NO_LEGAL_PROOF"),"API_ACCEPT")
    draft=_api("PREPARE",principal=principal,offer=offer,executor=adapter)
    assert_eq((draft.status_code,draft.state),
              (202,"CI_DRAFT_PREPARED_CI_NO_PAYMENT"),"API_PREPARE")

    replay=_api("PREPARE",principal=principal,offer=offer,executor=adapter)
    assert_eq((replay.status_code,replay.state),
              (202,"CI_REPLAY_PREPARE_CI_NO_WRITE"),"API_IDEMPOTENT_REPLAY")
    for result in (blocked,issue,accept,draft,replay):
        if any((
            result.real_identity_verified,result.legal_consent_verified,
            result.payment_authorized,result.license_authorized,
            result.pix_authorized,result.real_activation_authorized,
            result.production_authorized,result.real_writes_performed,
        )):
            raise AssertionError("M37459_REAL_AUTHORIZATION_CANNOT_BE_GRANTED")

    with connect() as owner:
        assert_eq(_record_counts(owner),(1,1,1),"COMMITTED_ATOMIC_CI_COUNTS")
        times=owner.execute(
            "SELECT c.server_issued_at,r.server_recorded_at,"
            "p.server_prepared_at,p.status,p.legal_consent_verified,"
            "p.payment_authorized,p.license_authorized,p.activation_authorized "
            "FROM public.saas_preprep_challenges_m37458_ci c "
            "JOIN public.saas_preprep_receipts_m37458_ci r ON r.challenge_id=c.challenge_id "
            "JOIN public.saas_preprep_drafts_m37458_ci p ON p.challenge_id=r.challenge_id "
            "WHERE c.request_id=%s",(REQUEST,)
        ).fetchone()
        issued,accepted,prepared,status,legal,paid,licensed,activated=times
        if not (issued<=accepted<=prepared):
            raise AssertionError("M37459_PREPARATION_PRECEDED_CONSENT")
        assert_eq((status,legal,paid,licensed,activated),
                  ("CI_DRAFT_NO_PAYMENT",False,False,False,False),
                  "NO_REAL_AUTHORITY_CI_DRAFT")
        assert_eq(owner.execute(
            "SELECT evidence_hash FROM public.contract_acceptances WHERE id=%s",
            (ACCEPTANCE,)
        ).fetchone()[0],"b"*64,"ORIGINAL_CONTRACT_PRESERVED")
        for table in ("saas_payment_intents","saas_license_entitlements"):
            assert_eq(owner.execute(
                "SELECT count(*) FROM public."+table+" WHERE tenant_id=%s",
                (T,)
            ).fetchone()[0],0,"ZERO_REAL_FINANCIAL_RECORDS")
        assert_eq(owner.execute(
            "SELECT count(*) FROM public.ledger_entries WHERE tenant_id=%s",
            (T,)
        ).fetchone()[0],0,"ZERO_ORIGINAL_LEDGER")
    print("M37459_API_CONTRACT_CI=PASS")
    print("M37459_TRANSACTION_FULL_ROLLBACK=PASS")
    print("M37459_CONSENT_BEFORE_DRAFT=PASS")
    print("M37459_IDEMPOTENT_REPLAY=PASS")
    print("M37459_REAL_IDENTITY_OR_LEGAL_CONSENT=NOT_ATTESTED")
    print("M37459_REAL_PAYMENT_LICENSE_PIX_ACTIVATION=OFF")
    print("M37459_LOCAL_DATABASE=UNTOUCHED")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
