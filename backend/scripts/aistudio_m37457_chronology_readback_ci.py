#!/usr/bin/env python3
"""M37457: fail-closed, SELECT-only historical consent order audit in CI PG.

The historical M37455/M37456 receipt is AFTER the M30900 subscription
preparation and must never be treated as a prerequisite that was satisfied.
Reads only disposable GitHub PostgreSQL. Performs no production actions.
"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID
import os

from app.saas_preparation_chronology_ci import assess_persisted_temporal_order_ci

EXPECTED_ENV = {
    "GITHUB_ACTIONS":"true",
    "FRCAIXINHA_CI_ISOLATED":"1",
    "PGHOST":"127.0.0.1",
    "PGPORT":"5432",
    "PGDATABASE":"frcaixinha_staging",
    "PGUSER":"postgres",
    "PGPASSWORD":"ci-test-only",
    "PGOPTIONS":"-c frcaixinha.saas_consent_ci=1",
}
REQUEST=UUID("daba0000-0000-4000-8000-000000000050")
TENANT=UUID("daba0000-0000-4000-8000-000000000010")
ADMIN=UUID("daba0000-0000-4000-8000-000000000001")
OTHER_TENANT=UUID("daba0000-0000-4000-8000-000000000020")
OTHER_ADMIN=UUID("daba0000-0000-4000-8000-000000000002")
ACCEPTANCE=UUID("daba0000-0000-4000-8000-000000000040")
READ_SQL = """
SELECT s.created_at AS prepared_at, c.issued_at AS challenge_issued_at,
 r.recorded_at AS receipt_recorded_at, l.evidence_state,
 l.legal_consent_verified, l.payment_authorized, l.license_authorized,
 l.real_activation_authorized,
 a.evidence_hash AS original_evidence_hash,
 (SELECT count(*) FROM public.saas_payment_intents x
  WHERE x.preparation_id=e.preparation_id) AS payment_count,
 (SELECT count(*) FROM public.saas_license_entitlements x
  WHERE x.preparation_id=e.preparation_id) AS entitlement_count,
 (SELECT count(*) FROM public.ledger_entries x
  WHERE x.tenant_id=e.tenant_id) AS tenant_ledger_count
FROM public.saas_enrollment_requests_staging e
JOIN public.saas_subscription_preparations s ON s.id=e.preparation_id
JOIN public.saas_consent_challenges_m37455_ci c ON c.request_id=e.request_id
JOIN public.saas_consent_receipts_m37455_ci r ON r.challenge_id=c.challenge_id
JOIN public.saas_consent_preparation_links_m37456_ci l
  ON l.request_id=e.request_id AND l.preparation_id=e.preparation_id
  AND l.challenge_id=c.challenge_id
JOIN public.contract_acceptances a ON a.id=e.contract_acceptance_id
WHERE e.request_id=%s AND e.tenant_id=%s AND e.admin_user_id=%s
LIMIT 2
"""


def environment_allowed(env: dict[str,str]) -> bool:
    return all(env.get(k)==v for k,v in EXPECTED_ENV.items())


def main() -> int:
    if not environment_allowed(dict(os.environ)):
        print("M37457_BLOCKED=NON_DISPOSABLE_ENVIRONMENT")
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
                "current_setting('transaction_read_only') AS read_only,"
                "current_setting('is_superuser') AS root,"
                "inet_server_port() AS port"
            )
            ident=cur.fetchone()
            if (ident is None or ident["db"]!="frcaixinha_staging"
                or ident["actor"]!="postgres"
                or ident["root"]!="on" or ident["read_only"]!="on"
                or ident["port"]!=5432):
                print("M37457_BLOCKED=DATABASE_IDENTITY_OR_WRITE_ENABLED")
                return 1

            cur.execute(READ_SQL,(REQUEST,TENANT,ADMIN))
            matches=cur.fetchall()
            if len(matches)!=1:
                print("M37457_BLOCKED=LEGACY_CONSENT_HISTORY_NOT_SINGLE")
                return 1
            row=dict(matches[0])
            result=assess_persisted_temporal_order_ci(
                prepared_at=row["prepared_at"],
                challenge_issued_at=row["challenge_issued_at"],
                receipt_recorded_at=row["receipt_recorded_at"],
                now=datetime.now(timezone.utc),
            )
            if (result.state!="PREPARATION_PRECEDED_CONSENT_DENIED"
                or result.hypothetical_preparation_eligible
                or result.real_identity_verified
                or result.legal_consent_verified
                or result.payment_authorized
                or result.license_authorized
                or result.user_activation_authorized
                or result.pix_authorized
                or result.production_authorized
                or result.writes_performed):
                print("M37457_BLOCKED=RETROACTIVE_CONSENT_NOT_DENIED")
                return 1
            if (row["evidence_state"]!="POST_PREPARATION_CI_UNATTESTED"
                or any(row[field] is not False for field in (
                    "legal_consent_verified","payment_authorized",
                    "license_authorized","real_activation_authorized"))
                or row["original_evidence_hash"]!="b"*64
                or any(type(row[field]) is not int or row[field]!=0
                       for field in ("payment_count","entitlement_count",
                                     "tenant_ledger_count"))):
                print("M37457_BLOCKED=LEGACY_FINANCIAL_OR_DOCUMENT_VIOLATION")
                return 1
            for scope in ((OTHER_TENANT,ADMIN),(TENANT,OTHER_ADMIN),
                          (OTHER_TENANT,OTHER_ADMIN)):
                cur.execute(READ_SQL,(REQUEST,*scope))
                if cur.fetchall():
                    print("M37457_BLOCKED=CROSS_TENANT_OR_ADMIN_READ")
                    return 1

    print("M37457_CI_HISTORICAL_CHRONOLOGY_READBACK=PASS")
    print("M37457_POST_PREPARATION_CONSENT=DENIED_AS_AUTHORITY")
    print("M37457_CONSENT_PREPARATION_ORDER_GUARD=PASS")
    print("M37457_REAL_CONSENT=NOT_ATTESTED")
    print("M37457_LICENSE_PAYMENT_PIX_ACTIVATION=OFF")
    print("M37457_LOCAL_ORIGINAL_DB=UNTOUCHED")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
