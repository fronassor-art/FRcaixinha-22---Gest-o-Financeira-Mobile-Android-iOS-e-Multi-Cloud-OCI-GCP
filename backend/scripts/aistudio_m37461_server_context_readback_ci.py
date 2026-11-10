#!/usr/bin/env python3
"""M37461: reconstruct CI server session+offer via SELECT-only disposable PG.

NOT a real authenticated token/session lookup: the fixture session_id is
not bound to a verified bearer-token hash. Does not enable the FastAPI route,
persist consent, create a payment, issue a license, or mutate original DB.
"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID
import os

from app.dependencies import AuthenticatedSession
from app.routers.saas_authenticated_contract_ci import check_server_identity_binding
from app.saas_server_context_readback_ci import (
    READBACK_SQL, build_ci_trusted_context,
)

EXPECTED_ENV={
    "GITHUB_ACTIONS":"true","FRCAIXINHA_CI_ISOLATED":"1",
    "PGHOST":"127.0.0.1","PGPORT":"5432",
    "PGDATABASE":"frcaixinha_staging","PGUSER":"postgres",
    "PGPASSWORD":"ci-test-only",
    "PGOPTIONS":"-c frcaixinha.saas_preprep_ci=1",
}
S=UUID("daba0000-0000-4000-8000-000000000581")
T=UUID("daba0000-0000-4000-8000-000000000010")
A=UUID("daba0000-0000-4000-8000-000000000001")
R=UUID("daba0000-0000-4000-8000-000000000594")
OTHER_T=UUID("daba0000-0000-4000-8000-000000000020")
OTHER_A=UUID("daba0000-0000-4000-8000-000000000002")
OTHER_R=UUID("daba0000-0000-4000-8000-000000000050")


def environment_allowed(environ:dict[str,str])->bool:
    return all(environ.get(k)==v for k,v in EXPECTED_ENV.items())


def main() -> int:
    if not environment_allowed(dict(os.environ)):
        print("M37461_BLOCKED=NON_DISPOSABLE_CI_DATABASE")
        return 1

    import psycopg
    from psycopg.rows import dict_row
    with psycopg.connect(
        host="127.0.0.1",port=5432,dbname="frcaixinha_staging",
        user="postgres",password="ci-test-only",connect_timeout=5,
        options="-c default_transaction_read_only=on -c frcaixinha.saas_preprep_ci=1",
        row_factory=dict_row,
    ) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT current_database() AS db, session_user AS actor,"
                " current_setting('transaction_read_only') AS ro,"
                " current_setting('is_superuser') AS root,"
                " inet_server_port() AS port"
            )
            identity=cur.fetchone()
            if (identity is None or identity["db"]!="frcaixinha_staging"
                or identity["actor"]!="postgres" or identity["ro"]!="on"
                or identity["root"]!="on" or identity["port"]!=5432):
                print("M37461_BLOCKED=DATABASE_OR_READ_ONLY_IDENTITY")
                return 1

            # Session, document, price, and challenge are ALL fetched from
            # server-owned disposable SQL rows, never from a client body.
            cur.execute(READBACK_SQL,(S,T,A,R))
            rows=cur.fetchall()
            if len(rows)!=1:
                print("M37461_BLOCKED=SERVER_CONTEXT_MISSING_OR_DUPLICATE")
                return 1
            now=datetime.now(timezone.utc)
            state, context=build_ci_trusted_context(
                dict(rows[0]),session_id=S,tenant_id=T,
                admin_id=A,request_id=R,checked_at=now,
            )
            if state!="CI_DISPOSABLE_SERVER_CONTEXT_READBACK_ONLY" or context is None:
                print("M37461_BLOCKED="+state)
                return 1
            if context.request_id!=R or context.offer.tenant_id!=T:
                print("M37461_BLOCKED=SERVER_CONTEXT_SCOPE_MISMATCH")
                return 1

            # This AuthenticatedSession is an artificial principal provided
            # to the CI runner, NOT an invocation of get_current_session.
            synthetic=AuthenticatedSession(
                user_id=str(A),role="TENANT_ADMIN",tenant_id=str(T),
                email="ci@example.invalid",name="CI fixture",is_master=False,
            )
            principal=check_server_identity_binding(synthetic,context,now=now)
            if (principal is None or principal.user_id!=A
                or principal.tenant_id!=T or principal.session_id!=S):
                print("M37461_BLOCKED=CI_PRINCIPAL_BINDING")
                return 1
            for role,tenant,user,master in (
                ("MASTER",None,A,True),
                ("TENANT_MEMBER",T,A,False),
                ("TENANT_ADMIN",OTHER_T,A,False),
                ("TENANT_ADMIN",T,OTHER_A,False),
            ):
                bogus=AuthenticatedSession(
                    user_id=str(user),role=role,
                    tenant_id=str(tenant) if tenant is not None else None,
                    email="ci@example.invalid",name="CI fixture",is_master=master,
                )
                if check_server_identity_binding(bogus,context,now=now) is not None:
                    print("M37461_BLOCKED=IMPERSONATION_NOT_DENIED")
                    return 1

            for tenant,admin,request in (
                (OTHER_T,A,R),(T,OTHER_A,R),(OTHER_T,OTHER_A,R),
                (T,A,OTHER_R),
            ):
                cur.execute(READBACK_SQL,(S,tenant,admin,request))
                if cur.fetchall():
                    print("M37461_BLOCKED=CROSS_TENANT_ADMIN_OR_REQUEST_LEAK")
                    return 1

            for table in ("saas_payment_intents","saas_license_entitlements"):
                cur.execute(f"SELECT count(*) FROM public.{table} WHERE tenant_id=%s",(T,))
                if cur.fetchone()["count"]!=0:
                    print("M37461_BLOCKED=FINANCIAL_OR_LICENSE_ACTIVITY_PRESENT")
                    return 1
            cur.execute("SELECT count(*) FROM public.ledger_entries WHERE tenant_id=%s",(T,))
            if cur.fetchone()["count"]!=0:
                print("M37461_BLOCKED=TENANT_LEDGER_ACTIVITY_PRESENT")
                return 1

    print("M37461_DISPOSABLE_SERVER_SESSION_AND_OFFER_READBACK=PASS")
    print("M37461_ROLE_TENANT_REQUEST_ISOLATION=PASS")
    print("M37461_PRICING_AND_DOCUMENT_FROM_DATABASE=PASS")
    print("M37461_POSTGRESQL_TRANSACTION=READ_ONLY")
    print("M37461_BEARER_SESSION_IDENTITY=NOT_VERIFIED")
    print("M37461_CONSENT_AND_LICENSE_REAL=OFF")
    print("M37461_PAYMENT_PIX_ACTIVATION_REAL=OFF")
    print("M37461_ORIGINAL_LOCAL_DATABASE=UNTOUCHED")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
