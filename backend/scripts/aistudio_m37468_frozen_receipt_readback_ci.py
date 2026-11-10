#!/usr/bin/env python3
"""M37468: CI-only post-revocation frozen quote -> receipt reconciliation.

Runs only against disposable GitHub PostgreSQL. No mutations and no production
endpoints. The output is diagnostic historical evidence, NOT legal consent.
"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID
import os

from app.saas_frozen_receipt_audit_ci import (
    FROZEN_RECEIPT_AUDIT_SQL,
    verify_frozen_receipt_ci,
    historical_receipt_view_ci,
)

CI_ENV = {
    "GITHUB_ACTIONS": "true",
    "FRCAIXINHA_CI_ISOLATED": "1",
    "PGHOST": "127.0.0.1",
    "PGPORT": "5432",
    "PGDATABASE": "frcaixinha_staging",
    "PGUSER": "postgres",
    "PGPASSWORD": "ci-test-only",
    "PGOPTIONS":
        "-c frcaixinha.saas_frozen_ci=1 "
        "-c frcaixinha.saas_atomic_ci=1 "
        "-c frcaixinha.saas_preprep_ci=1",
}
REQUEST = UUID("daba0000-0000-4000-8000-000000000687")
TENANT = UUID("daba0000-0000-4000-8000-000000000010")
ADMIN = UUID("daba0000-0000-4000-8000-000000000001")
SESSION = UUID("daba0000-0000-4000-8000-000000000686")
OTHER = UUID("daba0000-0000-4000-8000-000000000699")
TABLES = (
    "saas_preprep_challenges_m37458_ci",
    "saas_preprep_receipts_m37458_ci",
    "saas_preprep_drafts_m37458_ci",
    "saas_frozen_offer_m37467_ci",
)
FROZEN_TRIGGERS = (
    "m37467_frozen_no_update_delete_ci",
    "m37467_frozen_no_truncate_ci",
)


def allowed(env: dict[str, str]) -> bool:
    return (all(env.get(k) == v for k, v in CI_ENV.items())
            and env.get("FR_FINANCE_SAAS_REAL", "OFF") == "OFF"
            and env.get("FR_FINANCE_PIX_REAL", "OFF") == "OFF"
            and env.get("FR_FINANCE_LICENSE_REAL", "OFF") == "OFF")


def main() -> int:
    if not allowed(dict(os.environ)):
        print("M37468_BLOCKED=DISPOSABLE_GITHUB_ONLY")
        return 1

    import psycopg
    from psycopg.rows import dict_row

    with psycopg.connect(
        host="127.0.0.1", port=5432, dbname="frcaixinha_staging",
        user="postgres", password="ci-test-only", connect_timeout=5,
        options="-c default_transaction_read_only=on",
        row_factory=dict_row,
    ) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT current_database() AS db, session_user AS actor, "
                "current_setting('transaction_read_only') AS ro, "
                "current_setting('is_superuser') AS super, "
                "inet_server_port() AS port"
            )
            ident = cur.fetchone()
            if (ident is None or ident["db"] != "frcaixinha_staging"
                    or ident["actor"] != "postgres" or ident["ro"] != "on"
                    or ident["super"] != "on" or ident["port"] != 5432):
                print("M37468_BLOCKED=POSTGRESQL_READONLY_IDENTITY")
                return 1

            params = (REQUEST, TENANT, ADMIN, SESSION)
            cur.execute(FROZEN_RECEIPT_AUDIT_SQL, params)
            results = cur.fetchall()
            if len(results) != 1:
                raise AssertionError("M37468_FROZEN_RECEIPT_MISSING_OR_DUPLICATE")
            row = dict(results[0])
            evidence = verify_frozen_receipt_ci(
                row, request_id=REQUEST, tenant_id=TENANT,
                administrator_id=ADMIN, session_id=SESSION,
                observed_at=datetime.now(timezone.utc),
            )
            if (not evidence.historical_consistency
                    or not evidence.frozen_offer_consistent
                    or not evidence.issuer_session_revoked
                    or evidence.synthetic_record_count != 4):
                raise AssertionError("M37468_FROZEN_RECEIPT_NOT_RECONCILED")
            summary = historical_receipt_view_ci(evidence, env={
                "GITHUB_ACTIONS": "true",
                "FRCAIXINHA_CI_ISOLATED": "1",
                "ENVIRONMENT": "ci",
                "FR_FINANCE_SAAS_REAL": "OFF",
                "FR_FINANCE_PIX_REAL": "OFF",
                "FR_FINANCE_LICENSE_REAL": "OFF",
            })
            if (summary.get("real_authorization") is not False
                    or summary.get("historical_price_cents")
                    != row["frozen_price_cents"]
                    or summary.get("kind")
                    != "CI_SYNTHETIC_HISTORICAL_ONLY"):
                raise AssertionError("M37468_EVIDENCE_VIEW_GRANTED_AUTHORITY")

            # An identical read is deterministic. This is not a signature.
            cur.execute(FROZEN_RECEIPT_AUDIT_SQL, params)
            identical = cur.fetchall()
            if len(identical) != 1 or dict(identical[0]) != row:
                raise AssertionError("M37468_REPEAT_READBACK_DIVERGED")

            # Other sessions/tenants/request identifiers cannot retrieve
            # the historical quote+receipt even through the privileged CI DB.
            for foreign in (
                (OTHER, TENANT, ADMIN, SESSION),
                (REQUEST, OTHER, ADMIN, SESSION),
                (REQUEST, TENANT, OTHER, SESSION),
                (REQUEST, TENANT, ADMIN, OTHER),
            ):
                cur.execute(FROZEN_RECEIPT_AUDIT_SQL, foreign)
                if cur.fetchall():
                    raise AssertionError("M37468_CROSS_SCOPE_HISTORICAL_READ_LEAK")

            for table in TABLES:
                cur.execute(
                    "SELECT count(*) AS n FROM public." + table
                    + " WHERE request_id=%s", (REQUEST,),
                )
                if cur.fetchone()["n"] != 1:
                    raise AssertionError("M37468_DUPLICATE_OR_MISSING_STAGE")

            cur.execute(
                "SELECT count(*) AS n FROM pg_trigger WHERE "
                "tgname=ANY(%s) AND NOT tgisinternal",
                (list(FROZEN_TRIGGERS),),
            )
            if cur.fetchone()["n"] != len(FROZEN_TRIGGERS):
                raise AssertionError("M37468_APPEND_ONLY_GUARD_MISSING")

            cur.execute(
                "SELECT c.relrowsecurity AS rls, "
                "c.relforcerowsecurity AS forced, "
                "has_table_privilege('frcaixinha_app_role',"
                "'public.saas_frozen_offer_m37467_ci','SELECT') AS app_read,"
                "has_table_privilege('frcaixinha_saas_preprep_ci',"
                "'public.saas_frozen_offer_m37467_ci','SELECT') AS worker_read,"
                "has_table_privilege('frcaixinha_saas_preprep_ci',"
                "'public.saas_frozen_offer_m37467_ci','UPDATE') AS worker_write "
                "FROM pg_class c "
                "WHERE c.oid='public.saas_frozen_offer_m37467_ci'::regclass"
            )
            perm = cur.fetchone()
            if (not perm or perm["rls"] is not True
                    or perm["forced"] is not True
                    or perm["app_read"] or perm["worker_read"]
                    or perm["worker_write"]):
                raise AssertionError("M37468_FROZEN_SNAPSHOT_RLS_BROKEN")

            # This cursor runs with default_transaction_read_only=on.
            # Its historical view does NOT attest any real identity.
            print("M37468_FROZEN_OFFER_TO_RECEIPT_READBACK=PASS")
            print("M37468_DOCUMENT_HASH_PRICE_VERSION_CENTS=PASS")
            print("M37468_REVOKED_SESSION_HISTORY=CONSISTENT")
            print("M37468_REPLAY_NO_DUPLICATE_FOUR_RECORDS=PASS")
            print("M37468_CROSS_SCOPE_HISTORICAL_READBACK=DENIED")
            print("M37468_RLS_APPEND_ONLY=PASS")
            print("M37468_POSTGRESQL_READ_ONLY=PASS")
            print("M37468_DIGEST=DIAGNOSTIC_NOT_SIGNATURE")
            print("M37468_REAL_IDENTITY_AND_LEGAL_CONSENT=NOT_ATTESTED")
            print("M37468_PAYMENT_LICENSE_PIX_ACTIVATION=OFF")
            print("M37468_TERMUX_ORIGINAL_DATABASE=UNTOUCHED")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
