#!/usr/bin/env python3
"""M37453: verify disposable PostgreSQL-only SaaS readback in GitHub CI.

Never run against the Termux original database or OCI. Executes SELECT only,
with the PostgreSQL connection forced into default_transaction_read_only=on.
"""
from __future__ import annotations

from datetime import datetime, timezone
import os
from uuid import UUID

from app.saas_disposable_checkout_readback_ci import (
    READBACK_SQL, evaluate_disposable_readback,
)

CI_REQUEST = UUID("daba0000-0000-4000-8000-000000000050")
CI_TENANT = UUID("daba0000-0000-4000-8000-000000000010")
CI_ADMIN = UUID("daba0000-0000-4000-8000-000000000001")
CI_OTHER_TENANT = UUID("daba0000-0000-4000-8000-000000000020")
CI_OTHER_ADMIN = UUID("daba0000-0000-4000-8000-000000000002")

EXPECTED_ENV = {
    "GITHUB_ACTIONS": "true",
    "FRCAIXINHA_CI_ISOLATED": "1",
    "PGHOST": "127.0.0.1",
    "PGPORT": "5432",
    "PGDATABASE": "frcaixinha_staging",
    "PGUSER": "postgres",
    "PGPASSWORD": "ci-test-only",
}


def environment_allowed(environ: dict[str, str]) -> bool:
    return all(environ.get(k) == v for k, v in EXPECTED_ENV.items())


def main() -> int:
    if not environment_allowed(dict(os.environ)):
        print("M37453_BLOCKED=NON_DISPOSABLE_ENVIRONMENT")
        return 1

    # Import only after checking hard-coded CI isolation. Password stays
    # in environment; no connection string or SQL data printed to logs.
    import psycopg
    from psycopg.rows import dict_row

    with psycopg.connect(
        connect_timeout=5,
        options="-c default_transaction_read_only=on",
        row_factory=dict_row,
    ) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT current_database() AS db, session_user AS actor,"
                " current_setting('is_superuser') AS superuser,"
                " current_setting('transaction_read_only') AS ro,"
                " inet_server_port() AS port"
            )
            identity = cur.fetchone()
            if (identity is None or identity["db"] != "frcaixinha_staging"
                    or identity["actor"] != "postgres"
                    or identity["superuser"] != "on"
                    or identity["ro"] != "on"
                    or identity["port"] != 5432):
                print("M37453_BLOCKED=DATABASE_IDENTITY_OR_READ_ONLY")
                return 1

            cur.execute(READBACK_SQL, (CI_REQUEST, CI_TENANT, CI_ADMIN))
            rows = cur.fetchall()
            if len(rows) != 1:
                print("M37453_BLOCKED=PREPARATION_ABSENT_OR_DUPLICATE")
                return 1
            result = evaluate_disposable_readback(
                dict(rows[0]), request_id=CI_REQUEST, tenant_id=CI_TENANT,
                admin_id=CI_ADMIN, now=datetime.now(timezone.utc),
            )
            if (result.state != "CI_PERSISTED_PREPARATION_REVIEW_ONLY"
                    or result.structure_consistent_in_ci is not True
                    or any((
                        result.published_contract_operationally_verified,
                        result.explicit_consent_operationally_verified,
                        result.payment_verified, result.license_activated,
                        result.member_activated, result.pix_authorized,
                        result.production_authorized, result.writes_performed,
                    ))):
                print("M37453_BLOCKED=" + result.state)
                return 1
            for tenant, admin in (
                (CI_OTHER_TENANT, CI_ADMIN),
                (CI_TENANT, CI_OTHER_ADMIN),
                (CI_OTHER_TENANT, CI_OTHER_ADMIN),
            ):
                cur.execute(READBACK_SQL, (CI_REQUEST, tenant, admin))
                if cur.fetchall():
                    print("M37453_BLOCKED=CROSS_TENANT_OR_ADMIN_READ")
                    return 1

    print("M37453_CI_STAGING_READBACK=PASS")
    print("M37453_ACCEPTANCE=CI_FIXTURE_NOT_LEGAL_ATTESTATION")
    print("M37453_PREPARATION=RECORDED_CI_ONLY")
    print("M37453_PAYMENT_OR_LICENSE=NONE")
    print("M37453_REAL_SAAS=OFF")
    print("M37453_PIX_REAL=OFF")
    print("M37453_LOCAL_DB=UNTOUCHED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
