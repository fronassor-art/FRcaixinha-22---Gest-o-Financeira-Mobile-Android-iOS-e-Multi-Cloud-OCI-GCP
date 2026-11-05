#!/usr/bin/env bash
# M5700: disposable GitHub Actions CI ONLY. NEVER run against local Termux,
# OCI staging, production, or any pre-existing frcaixinha_staging database.
set -euo pipefail
umask 077
: "${FRCAIXINHA_CI_ISOLATED:?CI isolation must be explicit}"
: "${GITHUB_ACTIONS:?GitHub Actions only}"
test "$FRCAIXINHA_CI_ISOLATED" = "1"
test "$GITHUB_ACTIONS" = "true"
test "${PGHOST:-}" = "127.0.0.1"
test "${PGPORT:-}" = "5432"
test "${PGUSER:-}" = "postgres"
test "${PGDATABASE:-}" = "frcaixinha_ci"
test "${PGPASSWORD:-}" = "ci-test-only"
test "$(psql -XAt -v ON_ERROR_STOP=1 -c 'SELECT current_database()')" = "frcaixinha_ci"
test "$(psql -XAt -v ON_ERROR_STOP=1 -c "SELECT to_regclass('public.ledger_entries') IS NOT NULL")" = "t"
if psql -XAt -v ON_ERROR_STOP=1 -c "SELECT 1 FROM pg_database WHERE datname='frcaixinha_staging'" | grep -q 1; then
  echo "BLOCKED: staging database unexpectedly already exists"
  exit 1
fi

echo "=== STAGING CI: CREATE DEDICATED UNPRIVILEGED ROLES ==="
psql -X -v ON_ERROR_STOP=1 <<'SQL'
CREATE ROLE frcaixinha_mp_webhook_ingest LOGIN PASSWORD 'ci-test-only'
  NOSUPERUSER NOBYPASSRLS NOINHERIT NOCREATEDB NOCREATEROLE;
CREATE ROLE frcaixinha_mp_financial_worker LOGIN PASSWORD 'ci-test-only'
  NOSUPERUSER NOBYPASSRLS NOINHERIT NOCREATEDB NOCREATEROLE;
CREATE ROLE frcaixinha_notify_producer_ci LOGIN PASSWORD 'ci-test-only'
  NOSUPERUSER NOBYPASSRLS NOINHERIT NOCREATEDB NOCREATEROLE;
SQL

echo "=== STAGING CI: VERIFY WRONG-DATABASE GUARD + ROLLBACK ==="
if PGOPTIONS="-c frcaixinha.mp_staging_authorized=1" \
    psql -X -v ON_ERROR_STOP=1 \
    -f backend/staging_migrations/034_mp_signed_webhook_staging_only.sql \
    >/dev/null 2>&1; then
  echo "BLOCKED: wrong database accepted staging migration"
  exit 1
fi
test "$(psql -XAt -v ON_ERROR_STOP=1 -c \
  "SELECT to_regclass('public.mp_seller_connections_staging') IS NULL")" = "t"
echo "M034_WRONG_DATABASE_ROLLBACK=PASS"

echo "=== STAGING CI: CLONE SYNTHETIC DISPOSABLE DATABASE ==="
createdb -T frcaixinha_ci frcaixinha_staging
export PGDATABASE=frcaixinha_staging
psql -X -v ON_ERROR_STOP=1 <<'SQL'
GRANT CONNECT ON DATABASE frcaixinha_staging
  TO frcaixinha_mp_webhook_ingest,frcaixinha_mp_financial_worker,frcaixinha_notify_producer_ci;
GRANT USAGE ON SCHEMA public
  TO frcaixinha_mp_webhook_ingest,frcaixinha_mp_financial_worker,frcaixinha_notify_producer_ci;
SQL

echo "=== MIGRATIONS 034-038 IN STAGING CI (NOT OCI) ==="
for file in \
  backend/staging_migrations/034_mp_signed_webhook_staging_only.sql \
  backend/staging_migrations/035_pix_payment_automation_staging_only.sql \
  backend/staging_migrations/036_signed_orders_inbox_staging_only.sql \
  backend/staging_migrations/037_orders_payment_link_staging_only.sql \
  backend/staging_migrations/038_orders_reservation_staging_only.sql \
  backend/staging_migrations/039_orders_reconciliation_holds_staging_only.sql \
  backend/staging_migrations/040_orders_incident_audit_staging_only.sql \
  backend/staging_migrations/041_notifications_inbox_outbox_staging_ci_only.sql
do
  PGOPTIONS="-c frcaixinha.mp_staging_authorized=1 -c frcaixinha.mp_pix_automation_staging_authorized=1 -c frcaixinha.orders_staging_authorized=1 -c frcaixinha.notifications_staging_ci=1" \
    psql -X -v ON_ERROR_STOP=1 -f "$file" >/dev/null
  echo "STAGING_CI_APPLIED_$(basename "$file" | cut -c1-3)=PASS"
done

echo "=== STAGING CI: SYNTHETIC TENANTS/OBLIGATIONS ==="
psql -X -v ON_ERROR_STOP=1 -f backend/ci_migrations/033_staging_orders_fixture_ci_only.sql >/dev/null

echo "=== STAGING CI: ROLE AND RLS NEGATIVE CHECKS ==="
PGUSER=frcaixinha_mp_financial_worker \
  psql -X -v ON_ERROR_STOP=1 \
  -f backend/ci_migrations/034_staging_orders_worker_probe_ci_only.sql
PGUSER=frcaixinha_mp_webhook_ingest \
  psql -X -v ON_ERROR_STOP=1 \
  -f backend/ci_migrations/035_staging_webhook_probe_ci_only.sql
PGUSER=frcaixinha_mp_financial_worker \
  psql -X -v ON_ERROR_STOP=1 \
  -f backend/ci_migrations/036_staging_hold_probe_ci_only.sql
echo "=== M14000 — APPEND-ONLY SYNTHETIC CI PROBE ==="
PGUSER=frcaixinha_mp_financial_worker \
  psql -X -v ON_ERROR_STOP=1 \
  -f backend/ci_migrations/037_staging_incident_audit_probe_ci_only.sql
echo "=== M14000 — PostgreSQL transactional audit regression ==="
CI_MP_DISPOSABLE_DATABASE_URL='postgresql://postgres:ci-test-only@127.0.0.1:5432/frcaixinha_staging' \
CI_MP_AUDIT_WORKER_URL='postgresql://frcaixinha_mp_financial_worker:ci-test-only@127.0.0.1:5432/frcaixinha_staging' \
PYTHONPATH=backend python -m pytest -q --asyncio-mode=auto \
 backend/tests/test_m14000_staging_audit_persistence_ci.py
echo "M14000_POSTGRES_DISPOSABLE=PASS"
echo "=== M16000 NOTIFICATIONS DISPOSABLE PG ==="
if test "$(psql -XAt -v ON_ERROR_STOP=1 -c "SELECT 1 FROM pg_roles WHERE rolname='frcaixinha_ci'")" = "1"; then
  NOTIFY_APP_ROLE="frcaixinha_ci"
else
  test "$(psql -XAt -v ON_ERROR_STOP=1 -c "SELECT 1 FROM pg_roles WHERE rolname='frcaixinha_pg18_app'")" = "1"
  NOTIFY_APP_ROLE="frcaixinha_pg18_app"
fi
GITHUB_ACTIONS=true FRCAIXINHA_CI_ISOLATED=1 \
CI_MP_DISPOSABLE_DATABASE_URL='postgresql://postgres:ci-test-only@127.0.0.1:5432/frcaixinha_staging' \
CI_MP_NOTIFICATION_PRODUCER_URL='postgresql://frcaixinha_notify_producer_ci:ci-test-only@127.0.0.1:5432/frcaixinha_staging' \
CI_MP_NOTIFICATION_APP_URL="postgresql://${NOTIFY_APP_ROLE}:ci-test-only@127.0.0.1:5432/frcaixinha_staging" \
PYTHONPATH=backend python -m pytest -q --asyncio-mode=auto \
 backend/tests/test_m16000_notifications_postgres_ci.py
echo "M16000_POSTGRES_DISPOSABLE=PASS"
echo "=== M18000: authenticated-scope CI-only inbox adapter ==="
GITHUB_ACTIONS=true FRCAIXINHA_CI_ISOLATED=1 \
CI_MP_NOTIFICATION_PRODUCER_URL='postgresql://frcaixinha_notify_producer_ci:ci-test-only@127.0.0.1:5432/frcaixinha_staging' \
CI_MP_NOTIFICATION_APP_URL="postgresql://${NOTIFY_APP_ROLE}:ci-test-only@127.0.0.1:5432/frcaixinha_staging" \
PYTHONPATH=backend python -m pytest -q --asyncio-mode=auto \
 backend/tests/test_m18000_notification_ci_adapter_postgres.py
echo "M18000_CI_INBOX_ADAPTER=PASS"
echo "=== M6700 — SERIALIZABLE ledger synthetic commits and rollback ==="
CI_MP_DISPOSABLE_DATABASE_URL='postgresql://postgres:ci-test-only@127.0.0.1:5432/frcaixinha_staging' \
PYTHONPATH=backend python -m pytest -q --asyncio-mode=auto \
 backend/tests/test_m6700_disposable_ledger_atomicity_ci.py
echo "M6700_LEDGER_DISPOSABLE=PASS"

echo "STAGING_034_039_DISPOSABLE_POSTGRES=PASS"
echo "LOCAL_MIGRATIONS=NOT_TOUCHED"
echo "OCI_APPLY=NOT_EXECUTED"
echo "REAL_MONEY=OFF"
