#!/usr/bin/env python3
"""M37466 — read-only post-commit audit in isolated GitHub PostgreSQL.

No Termux/local DB, no migrations, no financial writes, no legal consent.
M37464/M37465 must have committed & revoked the synthetic bearer first.
"""
from __future__ import annotations

from datetime import datetime,timezone
from uuid import UUID
import os

from app.saas_post_commit_audit_ci import (
    POST_COMMIT_AUDIT_SQL,audit_post_commit_ci,
)

CI_ENV={
    "GITHUB_ACTIONS":"true",
    "FRCAIXINHA_CI_ISOLATED":"1",
    "PGHOST":"127.0.0.1",
    "PGPORT":"5432",
    "PGDATABASE":"frcaixinha_staging",
    "PGUSER":"postgres",
    "PGPASSWORD":"ci-test-only",
    "PGOPTIONS":"-c frcaixinha.saas_atomic_ci=1 -c frcaixinha.saas_preprep_ci=1",
}
REQUEST=UUID("daba0000-0000-4000-8000-000000000675")
OTHER_REQUEST=UUID("daba0000-0000-4000-8000-000000000677")
TENANT=UUID("daba0000-0000-4000-8000-000000000010")
OTHER_TENANT=UUID("daba0000-0000-4000-8000-000000000020")
ADMIN=UUID("daba0000-0000-4000-8000-000000000001")
OTHER_ADMIN=UUID("daba0000-0000-4000-8000-000000000002")
SESSION=UUID("daba0000-0000-4000-8000-000000000664")
OTHER_SESSION=UUID("daba0000-0000-4000-8000-000000000665")
AUDIT_TABLES=(
    "saas_preprep_challenges_m37458_ci",
    "saas_preprep_receipts_m37458_ci",
    "saas_preprep_drafts_m37458_ci",
)
GUARD_TRIGGER_NAMES=(
    "m37458_challenge_no_update_delete_ci",
    "m37458_receipt_no_update_delete_ci",
    "m37458_draft_no_update_delete_ci",
    "m37458_challenge_no_truncate_ci",
    "m37458_receipt_no_truncate_ci",
    "m37458_draft_no_truncate_ci",
)


def environment_allowed(env:dict[str,str])->bool:
    return (
        all(env.get(k)==v for k,v in CI_ENV.items())
        and env.get("FR_FINANCE_PIX_REAL","OFF")=="OFF"
        and env.get("FR_FINANCE_SAAS_REAL","OFF")=="OFF"
        and env.get("FR_FINANCE_LICENSE_REAL","OFF")=="OFF"
    )


def expect(actual,expected,reason:str)->None:
    if actual!=expected:
        raise AssertionError("M37466_"+reason)


def main()->int:
    if not environment_allowed(dict(os.environ)):
        print("M37466_BLOCKED=GITHUB_DISPOSABLE_POSTGRES_ONLY")
        return 1
    import psycopg
    from psycopg.rows import dict_row

    with psycopg.connect(
        host="127.0.0.1",port=5432,dbname="frcaixinha_staging",
        user="postgres",password="ci-test-only",connect_timeout=5,
        options="-c default_transaction_read_only=on",
        row_factory=dict_row,
    ) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT current_database() AS db,session_user AS actor,"
                "current_setting('transaction_read_only') AS ro,"
                "current_setting('is_superuser') AS root,inet_server_port() AS port"
            )
            meta=cur.fetchone()
            if (meta is None or meta["db"]!="frcaixinha_staging"
                or meta["actor"]!="postgres" or meta["ro"]!="on"
                or meta["root"]!="on" or meta["port"]!=5432):
                print("M37466_BLOCKED=POSTGRESQL_IDENTITY_READONLY")
                return 1

            cur.execute(POST_COMMIT_AUDIT_SQL,(REQUEST,TENANT,ADMIN,SESSION))
            rows=cur.fetchall()
            if len(rows)!=1:
                print("M37466_BLOCKED=HISTORICAL_RECORD_MISSING_OR_DUPLICATE")
                return 1
            baseline=dict(rows[0])
            audit=audit_post_commit_ci(
                baseline,request_id=REQUEST,tenant_id=TENANT,
                administrator_id=ADMIN,session_id=SESSION,
                observed_at=datetime.now(timezone.utc),
            )
            if (audit.state!="CI_POST_COMMIT_SYNTHETIC_HISTORY_CONSISTENT_NOT_AUTHORITY"
                or audit.historical_consistency is not True
                or audit.synthetic_record_count!=3
                or audit.issuer_session_revoked is not True
                or any((
                    audit.legal_consent_verified,audit.real_identity_verified,
                    audit.payment_authorized,audit.license_authorized,
                    audit.pix_authorized,audit.activation_authorized,
                    audit.production_authorized,audit.financial_writes_performed,
                ))):
                print("M37466_BLOCKED=POST_COMMIT_NOT_CONSISTENT_OR_AUTHORIZED")
                return 1

            # A past record is not permission for a now-revoked session;
            # historical readback must be scoped to all four identifiers.
            for args in (
                (OTHER_REQUEST,TENANT,ADMIN,SESSION),
                (REQUEST,OTHER_TENANT,ADMIN,SESSION),
                (REQUEST,TENANT,OTHER_ADMIN,SESSION),
                (REQUEST,TENANT,ADMIN,OTHER_SESSION),
            ):
                cur.execute(POST_COMMIT_AUDIT_SQL,args)
                if cur.fetchall():
                    raise AssertionError("M37466_CROSS_REQUEST_TENANT_ADMIN_SESSION_LEAK")

            # Exactly 1 record per stage after commit/replay and zero rows
            # for a pre-revoked token. All reads; never modify a fixture.
            for table in AUDIT_TABLES:
                cur.execute(
                    "SELECT count(*) AS n FROM public."+table+" WHERE request_id=%s",
                    (REQUEST,),
                )
                expect(cur.fetchone()["n"],1,"ONE_SYNTHETIC_RECORD_PER_STAGE")
                cur.execute(
                    "SELECT count(*) AS n FROM public."+table+" WHERE request_id=%s",
                    (OTHER_REQUEST,),
                )
                expect(cur.fetchone()["n"],0,"PRE_REVOKED_SESSION_HAS_NO_RECORD")

            cur.execute(
                "SELECT count(*) AS n FROM pg_trigger"
                " WHERE tgname=ANY(%s) AND NOT tgisinternal",
                (list(GUARD_TRIGGER_NAMES),),
            )
            expect(cur.fetchone()["n"],len(GUARD_TRIGGER_NAMES),
                   "APPEND_ONLY_TRIGGERS_PRESENT")
            cur.execute(
                "SELECT has_table_privilege('frcaixinha_app_role',"
                "'public.saas_preprep_receipts_m37458_ci','SELECT') AS app_receipts,"
                "has_table_privilege('frcaixinha_auth_role',"
                "'public.saas_preprep_receipts_m37458_ci','UPDATE') AS auth_mutation,"
                "has_table_privilege('frcaixinha_saas_preprep_ci',"
                "'public.saas_preprep_receipts_m37458_ci','UPDATE') AS worker_mutation"
            )
            p=cur.fetchone()
            if p["app_receipts"] or p["auth_mutation"] or p["worker_mutation"]:
                raise AssertionError("M37466_IMMUTABLE_RECEIPT_PERMISSIONS_BROKEN")

            # Historical source evidence remains stored; current revocation
            # is NOT evidence of a real administrator's legal consent.
            print("M37466_POST_COMMIT_HISTORICAL_READBACK=PASS")
            print("M37466_CONTRACT_DOCUMENT_PRICE_AND_SEQUENCE=PASS")
            print("M37466_REVOKED_SESSION_HISTORY_IMMUTABLE=PASS")
            print("M37466_CROSS_TENANT_AND_REQUEST_READBACK=DENIED")
            print("M37466_APPEND_ONLY_TRIGGERS=PASS")
            print("M37466_POSTGRESQL_TRANSACTION=READ_ONLY")
            print("M37466_EVIDENCE_DIGEST=DIAGNOSTIC_NOT_AUTHORITY")
            print("M37466_REAL_IDENTITY_AND_LEGAL_CONSENT=NOT_ATTESTED")
            print("M37466_LICENSE_PAYMENT_PIX_ACTIVATION=OFF")
            print("M37466_TERMUX_ORIGINAL_DATABASE=UNTOUCHED")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
