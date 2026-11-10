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
CREATE ROLE frcaixinha_mp_oauth_worker LOGIN PASSWORD 'ci-test-only'
  NOSUPERUSER NOBYPASSRLS NOINHERIT NOCREATEDB NOCREATEROLE;
CREATE ROLE frcaixinha_mp_financial_worker LOGIN PASSWORD 'ci-test-only'
  NOSUPERUSER NOBYPASSRLS NOINHERIT NOCREATEDB NOCREATEROLE;
CREATE ROLE frcaixinha_notify_producer_ci LOGIN PASSWORD 'ci-test-only'
  NOSUPERUSER NOBYPASSRLS NOINHERIT NOCREATEDB NOCREATEROLE;
CREATE ROLE frcaixinha_invite_queue_ci LOGIN PASSWORD 'ci-test-only'
  NOSUPERUSER NOBYPASSRLS NOINHERIT NOCREATEDB NOCREATEROLE;
CREATE ROLE frcaixinha_account_recovery_ci LOGIN PASSWORD 'ci-test-only'
  NOSUPERUSER NOBYPASSRLS NOINHERIT NOCREATEDB NOCREATEROLE;
CREATE ROLE frcaixinha_invite_dispatch_ci LOGIN PASSWORD 'ci-test-only'
  NOSUPERUSER NOBYPASSRLS NOINHERIT NOCREATEDB NOCREATEROLE;
CREATE ROLE frcaixinha_mail_receipt_ci LOGIN PASSWORD 'ci-test-only'
  NOSUPERUSER NOBYPASSRLS NOINHERIT NOCREATEDB NOCREATEROLE;
CREATE ROLE frcaixinha_envelope_producer_ci LOGIN PASSWORD 'ci-test-only'
  NOSUPERUSER NOBYPASSRLS NOINHERIT NOCREATEDB NOCREATEROLE;
CREATE ROLE frcaixinha_email_proof_ci LOGIN PASSWORD 'ci-test-only'
  NOSUPERUSER NOBYPASSRLS NOINHERIT NOCREATEDB NOCREATEROLE;
CREATE ROLE frcaixinha_email_attestor_ci LOGIN PASSWORD 'ci-test-only'
  NOSUPERUSER NOBYPASSRLS NOINHERIT NOCREATEDB NOCREATEROLE;
CREATE ROLE frcaixinha_annual_ci LOGIN PASSWORD 'ci-test-only'
  NOSUPERUSER NOBYPASSRLS NOINHERIT NOCREATEDB NOCREATEROLE;
CREATE ROLE frcaixinha_saas_enroll_ci LOGIN PASSWORD 'ci-test-only'
  NOSUPERUSER NOBYPASSRLS NOINHERIT NOCREATEDB NOCREATEROLE;
CREATE ROLE frcaixinha_saas_consent_ci LOGIN PASSWORD 'ci-test-only'
  NOSUPERUSER NOBYPASSRLS NOINHERIT NOCREATEDB NOCREATEROLE;
CREATE ROLE frcaixinha_saas_capacity_ci LOGIN PASSWORD 'ci-test-only'
  NOSUPERUSER NOBYPASSRLS NOINHERIT NOCREATEDB NOCREATEROLE;
CREATE ROLE frcaixinha_saas_renewal_ci LOGIN PASSWORD 'ci-test-only'
  NOSUPERUSER NOBYPASSRLS NOINHERIT NOCREATEDB NOCREATEROLE;
CREATE ROLE frcaixinha_saas_claim_ci LOGIN PASSWORD 'ci-test-only'
  NOSUPERUSER NOBYPASSRLS NOINHERIT NOCREATEDB NOCREATEROLE;
CREATE ROLE frcaixinha_saas_admission_ci LOGIN PASSWORD 'ci-test-only'
  NOSUPERUSER NOBYPASSRLS INHERIT NOCREATEDB NOCREATEROLE;
CREATE ROLE frcaixinha_saas_admission_intent_ci LOGIN PASSWORD 'ci-test-only'
  NOSUPERUSER NOBYPASSRLS NOINHERIT NOCREATEDB NOCREATEROLE;
CREATE ROLE frcaixinha_saas_review_ci LOGIN PASSWORD 'ci-test-only'
  NOSUPERUSER NOBYPASSRLS NOINHERIT NOCREATEDB NOCREATEROLE;
GRANT frcaixinha_app_role TO frcaixinha_saas_admission_ci;
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
if PGOPTIONS="-c frcaixinha.invite_queue_staging_ci=1" \
    psql -X -v ON_ERROR_STOP=1 \
    -f backend/staging_migrations/050_invitation_outbox_staging_only.sql \
    >/dev/null 2>&1; then
  echo "BLOCKED: invitation outbox migration accepted wrong database"
  exit 1
fi
test "$(psql -XAt -v ON_ERROR_STOP=1 -c \
  "SELECT to_regclass('public.invite_delivery_outbox_staging') IS NULL")" = "t"
echo "M25900_WRONG_DATABASE_ROLLBACK=PASS"
if PGOPTIONS="-c frcaixinha.recovery_staging_ci=1" \
    psql -X -v ON_ERROR_STOP=1 \
    -f backend/staging_migrations/051_password_reset_staging_only.sql \
    >/dev/null 2>&1; then
  echo "BLOCKED: password recovery migration accepted wrong database"
  exit 1
fi
test "$(psql -XAt -v ON_ERROR_STOP=1 -c \
  "SELECT to_regclass('public.password_recovery_audit_staging') IS NULL")" = "t"
echo "M26000_WRONG_DATABASE_ROLLBACK=PASS"
if PGOPTIONS="-c frcaixinha.invite_dispatch_staging_ci=1" \
    psql -X -v ON_ERROR_STOP=1 \
    -f backend/staging_migrations/052_invite_dispatch_lease_staging_only.sql \
    >/dev/null 2>&1; then
  echo "BLOCKED: dispatch lease migration accepted wrong database"
  exit 1
fi
test "$(psql -XAt -v ON_ERROR_STOP=1 -c \
  "SELECT to_regclass('public.invite_dispatch_leases_staging') IS NULL")" = "t"
echo "M26100_WRONG_DATABASE_ROLLBACK=PASS"
if PGOPTIONS="-c frcaixinha.mail_receipt_staging_ci=1" \
    psql -X -v ON_ERROR_STOP=1 \
    -f backend/staging_migrations/053_mail_receipt_audit_staging_only.sql \
    >/dev/null 2>&1; then
  echo "BLOCKED: mail receipt migration accepted wrong database"
  exit 1
fi
test "$(psql -XAt -v ON_ERROR_STOP=1 -c \
  "SELECT to_regclass('public.invite_provider_receipts_staging') IS NULL")" = "t"
echo "M26300_WRONG_DATABASE_ROLLBACK=PASS"
if PGOPTIONS="-c frcaixinha.delivery_gate_staging_ci=1" \
    psql -X -v ON_ERROR_STOP=1 \
    -f backend/staging_migrations/054_invite_delivery_terminal_gate_staging_only.sql \
    >/dev/null 2>&1; then
  echo "BLOCKED: terminal gate migration accepted wrong database"
  exit 1
fi
test "$(psql -XAt -v ON_ERROR_STOP=1 -c \
  "SELECT to_regclass('public.invite_delivery_terminal_gate_staging') IS NULL")" = "t"
echo "M26600_WRONG_DATABASE_ROLLBACK=PASS"
if PGOPTIONS="-c frcaixinha.envelope_staging_ci=1" \
  psql -X -v ON_ERROR_STOP=1 \
  -f backend/staging_migrations/055_invite_encrypted_envelope_staging_only.sql \
  >/dev/null 2>&1; then
  echo "BLOCKED: sealed envelope migration accepted wrong database"
  exit 1
fi
test "$(psql -XAt -v ON_ERROR_STOP=1 -c \
  "SELECT to_regclass('public.invite_encrypted_envelopes_staging') IS NULL")" = "t"
echo "M26700_WRONG_DATABASE_ROLLBACK=PASS"
if PGOPTIONS="-c frcaixinha.email_proof_staging_ci=1" \
  psql -X -v ON_ERROR_STOP=1 \
  -f backend/staging_migrations/056_email_ownership_challenge_staging_only.sql \
  >/dev/null 2>&1; then
  echo "BLOCKED: email challenge staging SQL accepted wrong database"
  exit 1
fi
test "$(psql -XAt -v ON_ERROR_STOP=1 -c \
  "SELECT to_regclass('public.invite_email_challenges_staging') IS NULL")" = "t"
echo "M27100_WRONG_DATABASE_ROLLBACK=PASS"
if PGOPTIONS="-c frcaixinha.email_attestation_staging_ci=1" \
  psql -X -v ON_ERROR_STOP=1 \
  -f backend/staging_migrations/057_email_challenge_readback_staging_only.sql \
  >/dev/null 2>&1; then
  echo "BLOCKED: email readback migration accepted wrong database"
  exit 1
fi
test "$(psql -XAt -v ON_ERROR_STOP=1 -c \
  "SELECT to_regprocedure('public.invite_challenge_readback_staging_ci(uuid,uuid)') IS NULL")" = "t"
echo "M27500_WRONG_DATABASE_ROLLBACK=PASS"

echo "=== STAGING CI: CLONE SYNTHETIC DISPOSABLE DATABASE ==="
createdb -T frcaixinha_ci frcaixinha_staging
export PGDATABASE=frcaixinha_staging
psql -X -v ON_ERROR_STOP=1 <<'SQL'
GRANT CONNECT ON DATABASE frcaixinha_staging
  TO frcaixinha_mp_webhook_ingest,frcaixinha_mp_oauth_worker,frcaixinha_mp_financial_worker,frcaixinha_notify_producer_ci,frcaixinha_invite_queue_ci,frcaixinha_account_recovery_ci,frcaixinha_invite_dispatch_ci,frcaixinha_mail_receipt_ci,frcaixinha_envelope_producer_ci,frcaixinha_email_proof_ci,frcaixinha_email_attestor_ci,frcaixinha_annual_ci,frcaixinha_saas_enroll_ci,frcaixinha_saas_consent_ci,frcaixinha_saas_capacity_ci,frcaixinha_saas_renewal_ci,frcaixinha_saas_claim_ci,frcaixinha_saas_admission_intent_ci,frcaixinha_saas_review_ci;
GRANT USAGE ON SCHEMA public
  TO frcaixinha_mp_webhook_ingest,frcaixinha_mp_oauth_worker,frcaixinha_mp_financial_worker,frcaixinha_notify_producer_ci,frcaixinha_invite_queue_ci,frcaixinha_account_recovery_ci,frcaixinha_invite_dispatch_ci,frcaixinha_mail_receipt_ci,frcaixinha_envelope_producer_ci,frcaixinha_email_proof_ci,frcaixinha_email_attestor_ci,frcaixinha_annual_ci,frcaixinha_saas_enroll_ci,frcaixinha_saas_consent_ci,frcaixinha_saas_capacity_ci,frcaixinha_saas_renewal_ci,frcaixinha_saas_claim_ci,frcaixinha_saas_admission_intent_ci,frcaixinha_saas_review_ci;
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
  backend/staging_migrations/041_notifications_inbox_outbox_staging_ci_only.sql \
  backend/staging_migrations/045_mp_oauth_attempts_staging_only.sql \
  backend/staging_migrations/046_mp_oauth_seller_consent_cas_staging_only.sql \
  backend/staging_migrations/047_mp_oauth_generation_staging_only.sql \
  backend/staging_migrations/048_mp_oauth_failed_reference_staging_only.sql \
  backend/staging_migrations/049_mp_oauth_revision_state_staging_only.sql \
  backend/staging_migrations/050_invitation_outbox_staging_only.sql \
  backend/staging_migrations/051_password_reset_staging_only.sql \
  backend/staging_migrations/052_invite_dispatch_lease_staging_only.sql \
  backend/staging_migrations/053_mail_receipt_audit_staging_only.sql
do
  PGOPTIONS="-c frcaixinha.mp_staging_authorized=1 -c frcaixinha.mp_pix_automation_staging_authorized=1 -c frcaixinha.orders_staging_authorized=1 -c frcaixinha.notifications_staging_ci=1 -c frcaixinha.mp_oauth_staging_authorized=1 -c frcaixinha.invite_queue_staging_ci=1 -c frcaixinha.recovery_staging_ci=1 -c frcaixinha.invite_dispatch_staging_ci=1 -c frcaixinha.mail_receipt_staging_ci=1" \
    psql -X -v ON_ERROR_STOP=1 -f "$file" >/dev/null
  echo "STAGING_CI_APPLIED_$(basename "$file" | cut -c1-3)=PASS"
done

echo "=== STAGING CI: SYNTHETIC TENANTS/OBLIGATIONS ==="
psql -X -v ON_ERROR_STOP=1 -f backend/ci_migrations/033_staging_orders_fixture_ci_only.sql >/dev/null
echo "=== M25900: durable invitation outbox, disposable CI only ==="
PGOPTIONS='-c frcaixinha.invite_queue_staging_ci=1' \
  psql -X -v ON_ERROR_STOP=1 -f backend/ci_migrations/046_invitation_outbox_fixture_ci_only.sql >/dev/null
PGOPTIONS='-c frcaixinha.invite_queue_staging_ci=1' \
  PGUSER=frcaixinha_invite_queue_ci psql -X -v ON_ERROR_STOP=1 \
  -f backend/ci_migrations/047_invitation_outbox_worker_probe_ci_only.sql >/dev/null
test "$(psql -XAt -v ON_ERROR_STOP=1 -c \
  "SELECT count(*) FROM public.invite_delivery_outbox_staging")" = "1"
test "$(psql -XAt -v ON_ERROR_STOP=1 -c \
  "SELECT count(*) FROM public.invite_delivery_audit_staging")" = "1"
test "$(psql -XAt -v ON_ERROR_STOP=1 -c \
  "SELECT (status='HELD_CI_NOT_SENT') AND NOT provider_delivery_confirmed AND NOT recipient_verified FROM public.invite_delivery_outbox_staging")" = "t"
if PGUSER=frcaixinha_invite_queue_ci psql -XAt -v ON_ERROR_STOP=1 \
  -c "SELECT count(*) FROM public.invite_delivery_outbox_staging" >/dev/null 2>&1; then
  echo "BLOCKED: invitation worker has raw outbox SELECT"
  exit 1
fi
echo "M25900_STAGING_OUTBOX_IDEMPOTENT_AUDIT=PASS"
echo "=== M26100: dispatch lease and retry without network ==="
PGOPTIONS='-c frcaixinha.invite_dispatch_staging_ci=1' \
  PGUSER=frcaixinha_invite_dispatch_ci psql -X -v ON_ERROR_STOP=1 \
  -f backend/ci_migrations/050_invite_dispatch_first_probe_ci_only.sql >/dev/null
test "$(psql -XAt -v ON_ERROR_STOP=1 -c \
  "SELECT count(*) FROM public.invite_dispatch_attempt_audit_staging")" = "1"
test "$(psql -XAt -v ON_ERROR_STOP=1 -c \
  "SELECT attempts=1 AND status='HELD_CI_NO_NETWORK' FROM public.invite_dispatch_leases_staging")" = "t"
psql -X -v ON_ERROR_STOP=1 -c \
  "UPDATE public.invite_dispatch_leases_staging SET lease_expires_at=clock_timestamp()-interval '1 second'" >/dev/null
PGOPTIONS='-c frcaixinha.invite_dispatch_staging_ci=1' \
  PGUSER=frcaixinha_invite_dispatch_ci psql -X -v ON_ERROR_STOP=1 \
  -f backend/ci_migrations/051_invite_dispatch_retry_probe_ci_only.sql >/dev/null
test "$(psql -XAt -v ON_ERROR_STOP=1 -c \
  "SELECT count(*) FROM public.invite_dispatch_attempt_audit_staging")" = "2"
psql -X -v ON_ERROR_STOP=1 -c \
  "UPDATE public.invite_dispatch_leases_staging SET lease_expires_at=clock_timestamp()-interval '1 second'" >/dev/null
test "$(PGOPTIONS='-c frcaixinha.invite_dispatch_staging_ci=1' \
 PGUSER=frcaixinha_invite_dispatch_ci psql -XAt -v ON_ERROR_STOP=1 -c \
 "SELECT public.invite_dispatch_lease_staging_ci('eeeeeeee-0000-4000-8000-000000000015','eeeeeeee-0000-4000-8000-000000000033')")" = "HELD:3"
test "$(psql -XAt -v ON_ERROR_STOP=1 -c \
  "SELECT count(*) FROM public.invite_dispatch_attempt_audit_staging")" = "3"
psql -X -v ON_ERROR_STOP=1 -c \
  "UPDATE public.invite_dispatch_leases_staging SET lease_expires_at=clock_timestamp()-interval '1 second'" >/dev/null
test "$(PGOPTIONS='-c frcaixinha.invite_dispatch_staging_ci=1' \
 PGUSER=frcaixinha_invite_dispatch_ci psql -XAt -v ON_ERROR_STOP=1 -c \
 "SELECT public.invite_dispatch_lease_staging_ci('eeeeeeee-0000-4000-8000-000000000015','eeeeeeee-0000-4000-8000-000000000034')")" = "EXHAUSTED"
test "$(psql -XAt -v ON_ERROR_STOP=1 -c \
  "SELECT count(*) FROM public.invite_dispatch_attempt_audit_staging")" = "3"
test "$(psql -XAt -v ON_ERROR_STOP=1 -c \
  "SELECT count(*) FROM public.invite_delivery_outbox_staging WHERE status='HELD_CI_NOT_SENT' AND NOT provider_delivery_confirmed AND NOT recipient_verified")" = "1"
if PGUSER=frcaixinha_invite_dispatch_ci psql -XAt -v ON_ERROR_STOP=1 \
  -c "SELECT count(*) FROM public.invite_dispatch_leases_staging" >/dev/null 2>&1; then
  echo "BLOCKED: dispatch worker has raw lease SELECT"
  exit 1
fi
echo "M26100_CI_DISPATCH_LEASE_BOUNDED_RETRIES=PASS"
echo "=== M26300: signed CI mail receipt never confirms delivery ==="
PGOPTIONS='-c frcaixinha.mail_receipt_staging_ci=1' \
  PGUSER=frcaixinha_mail_receipt_ci psql -X -v ON_ERROR_STOP=1 \
  -f backend/ci_migrations/052_mail_receipt_idempotency_probe_ci_only.sql >/dev/null
GITHUB_ACTIONS=true FRCAIXINHA_CI_ISOLATED=1 \
CI_MAIL_RECEIPT_WORKER_URL='postgresql://frcaixinha_mail_receipt_ci:ci-test-only@127.0.0.1:5432/frcaixinha_staging' \
PYTHONPATH=backend python -m pytest -q --asyncio-mode=auto \
  backend/tests/test_m26300_signed_receipt_pg_ci.py
test "$(psql -XAt -v ON_ERROR_STOP=1 -c \
  "SELECT count(*) FROM public.invite_provider_receipts_staging")" = "2"
test "$(psql -XAt -v ON_ERROR_STOP=1 -c \
  "SELECT bool_and(NOT provider_delivery_confirmed AND NOT recipient_verified AND NOT acceptance_recorded AND NOT account_activated AND state='CI_RECEIPT_ONLY_NO_DELIVERY') FROM public.invite_provider_receipts_staging")" = "t"
if PGUSER=frcaixinha_mail_receipt_ci psql -XAt -v ON_ERROR_STOP=1 \
  -c "SELECT count(*) FROM public.invite_provider_receipts_staging" >/dev/null 2>&1; then
  echo "BLOCKED: receipt worker can read audit table directly"
  exit 1
fi
echo "M26300_CI_SIGNED_RECEIPT_POSTGRES_NO_DELIVERY=PASS"
echo "=== M26600: install terminal gate before encrypted outbox ==="
PGOPTIONS="-c frcaixinha.delivery_gate_staging_ci=1" \
  psql -X -v ON_ERROR_STOP=1 \
  -f backend/staging_migrations/054_invite_delivery_terminal_gate_staging_only.sql >/dev/null
echo "=== M26700: encrypted payload only, restricted storage and reading ==="
# Migration 055 is built on the new terminal gate (054), not the legacy claim.
PGOPTIONS="-c frcaixinha.envelope_staging_ci=1" \
  psql -X -v ON_ERROR_STOP=1 \
  -f backend/staging_migrations/055_invite_encrypted_envelope_staging_only.sql >/dev/null
# Earlier M26100 test exhausted 3 synthetic leases; restore only synthetic
# lease #3 momentarily so the read function can prove its permission boundary.
psql -X -v ON_ERROR_STOP=1 -c \
  "UPDATE public.invite_dispatch_leases_staging SET lease_expires_at=clock_timestamp()+interval '5 minutes' WHERE lease_id='eeeeeeee-0000-4000-8000-000000000033'" >/dev/null
GITHUB_ACTIONS=true FRCAIXINHA_CI_ISOLATED=1 \
CI_SEALED_ENVELOPE_PRODUCER_URL='postgresql://frcaixinha_envelope_producer_ci:ci-test-only@127.0.0.1:5432/frcaixinha_staging' \
CI_SEALED_ENVELOPE_DISPATCH_URL='postgresql://frcaixinha_invite_dispatch_ci:ci-test-only@127.0.0.1:5432/frcaixinha_staging' \
PYTHONPATH=backend python -m pytest -q --asyncio-mode=auto \
  backend/tests/test_m26700_sealed_outbox_postgres_ci.py
psql -X -v ON_ERROR_STOP=1 -c \
  "UPDATE public.invite_dispatch_leases_staging SET lease_expires_at=clock_timestamp()-interval '1 second' WHERE lease_id='eeeeeeee-0000-4000-8000-000000000033'" >/dev/null
test "$(psql -XAt -v ON_ERROR_STOP=1 -c \
  "SELECT count(*) FROM public.invite_encrypted_envelopes_staging")" = "1"
test "$(psql -XAt -v ON_ERROR_STOP=1 -c \
  "SELECT bool_and(status='SEALED_CI_NOT_SENT' AND event_id='eeeeeeee-0000-4000-8000-000000000015'::uuid) FROM public.invite_encrypted_envelopes_staging")" = "t"
echo "M26700_POSTGRES_AES_GCM_PERSISTENCE=PASS"
echo "=== M27100: one-use synthetic email challenge, NO actual delivery ==="
PGOPTIONS='-c frcaixinha.email_proof_staging_ci=1' \
  psql -X -v ON_ERROR_STOP=1 \
  -f backend/staging_migrations/056_email_ownership_challenge_staging_only.sql >/dev/null
PGOPTIONS='-c frcaixinha.email_attestation_staging_ci=1' \
  psql -X -v ON_ERROR_STOP=1 \
  -f backend/staging_migrations/057_email_challenge_readback_staging_only.sql >/dev/null
PGOPTIONS='-c frcaixinha.email_proof_staging_ci=1' \
  PGUSER=frcaixinha_invite_queue_ci psql -X -v ON_ERROR_STOP=1 \
  -f backend/ci_migrations/054_email_challenge_issue_probe_ci_only.sql >/dev/null
# Re-activate only the synthetic disposable lease for the postcommit
# readback; its prior expiration is intentionally restored afterwards.
psql -X -v ON_ERROR_STOP=1 -c \
  "UPDATE public.invite_dispatch_leases_staging SET lease_expires_at=clock_timestamp()+interval '5 minutes' WHERE lease_id='eeeeeeee-0000-4000-8000-000000000033'" >/dev/null
GITHUB_ACTIONS=true FRCAIXINHA_CI_ISOLATED=1 \
CI_EMAIL_ATTESTOR_URL='postgresql://frcaixinha_email_attestor_ci:ci-test-only@127.0.0.1:5432/frcaixinha_staging' \
PYTHONPATH=backend python -m pytest -q --asyncio-mode=auto \
  backend/tests/test_m27600_committed_challenge_postgres_ci.py
psql -X -v ON_ERROR_STOP=1 -c \
  "UPDATE public.invite_dispatch_leases_staging SET lease_expires_at=clock_timestamp()-interval '1 second' WHERE lease_id='eeeeeeee-0000-4000-8000-000000000033'" >/dev/null
echo "M27600_POSTCOMMIT_NO_DELIVERY=PASS"
PGOPTIONS='-c frcaixinha.email_proof_staging_ci=1' \
  PGUSER=frcaixinha_email_proof_ci psql -X -v ON_ERROR_STOP=1 \
  -f backend/ci_migrations/055_email_challenge_consume_probe_ci_only.sql >/dev/null
# Even if the lease is restored, an already-consumed token cannot be
# retrieved by the independent readback role.
psql -X -v ON_ERROR_STOP=1 -c \
  "UPDATE public.invite_dispatch_leases_staging SET lease_expires_at=clock_timestamp()+interval '2 minutes' WHERE lease_id='eeeeeeee-0000-4000-8000-000000000033'" >/dev/null
test "$(PGOPTIONS='-c frcaixinha.email_attestation_staging_ci=1' \
  PGUSER=frcaixinha_email_attestor_ci psql -XAt -v ON_ERROR_STOP=1 -c \
  "SELECT public.invite_challenge_readback_staging_ci('eeeeeeee-0000-4000-8000-000000000015','eeeeeeee-0000-4000-8000-000000000033')")" = ""
psql -X -v ON_ERROR_STOP=1 -c \
  "UPDATE public.invite_dispatch_leases_staging SET lease_expires_at=clock_timestamp()-interval '1 second' WHERE lease_id='eeeeeeee-0000-4000-8000-000000000033'" >/dev/null
echo "M27600_POSTCONSUME_READBACK_DENIED=PASS"
test "$(psql -XAt -v ON_ERROR_STOP=1 -c \
  "SELECT count(*) FROM public.invite_email_challenges_staging WHERE consumed_at IS NOT NULL AND failed_attempts=1 AND state='CI_TOKEN_CONSUMED_NOT_PROOF' AND NOT recipient_verified AND NOT user_activated AND NOT contract_accepted")" = "1"
if PGUSER=frcaixinha_email_proof_ci psql -XAt -v ON_ERROR_STOP=1 \
  -c "SELECT count(*) FROM public.invite_email_challenges_staging" >/dev/null 2>&1; then
  echo "BLOCKED: proof worker can SELECT challenge table"
  exit 1
fi
if PGUSER=frcaixinha_invite_queue_ci psql -XAt -v ON_ERROR_STOP=1 \
  -c "SELECT count(*) FROM public.invite_email_challenges_staging" >/dev/null 2>&1; then
  echo "BLOCKED: challenge producer can SELECT token digests"
  exit 1
fi
echo "M27100_CI_EMAIL_TOKEN_CONSUMED_NO_IDENTITY_GRANT=PASS"
echo "=== M27101: 3 invalid token guesses permanently exhaust CI challenge ==="
# All rows in this DB are synthetic; no production data or external link exists.
psql -X -v ON_ERROR_STOP=1 -c \
  "UPDATE public.invite_email_challenges_staging SET consumed_at=NULL,failed_attempts=0,state='CI_CHALLENGE_NOT_DELIVERED' WHERE outbox_id=(SELECT id FROM public.invite_delivery_outbox_staging WHERE event_id='eeeeeeee-0000-4000-8000-000000000015')" >/dev/null
PGOPTIONS='-c frcaixinha.email_proof_staging_ci=1' \
  PGUSER=frcaixinha_email_proof_ci psql -X -v ON_ERROR_STOP=1 \
  -f backend/ci_migrations/056_email_challenge_lockout_probe_ci_only.sql >/dev/null
test "$(psql -XAt -v ON_ERROR_STOP=1 -c \
  "SELECT count(*) FROM public.invite_email_challenges_staging WHERE consumed_at IS NULL AND failed_attempts=3 AND NOT recipient_verified AND NOT user_activated AND NOT contract_accepted")" = "1"
psql -X -v ON_ERROR_STOP=1 -c \
  "UPDATE public.invite_email_challenges_staging SET failed_attempts=0,expires_at=clock_timestamp()-interval '1 second'" >/dev/null
test "$(PGOPTIONS='-c frcaixinha.email_proof_staging_ci=1' \
  PGUSER=frcaixinha_email_proof_ci psql -XAt -v ON_ERROR_STOP=1 -c \
  "SELECT public.invite_consume_ci_email_challenge('eeeeeeee-0000-4000-8000-000000000015',repeat('T',48))")" = "DENIED"
echo "M27101_CI_LOCKOUT_EXPIRY_NO_ACTIVATION=PASS"
echo "=== M26600: quarantine unknown SMTP ACK durably, disable old claim ==="
PGOPTIONS="-c frcaixinha.delivery_gate_staging_ci=1" \
  PGUSER=frcaixinha_invite_dispatch_ci psql -X -v ON_ERROR_STOP=1 \
  -f backend/ci_migrations/053_delivery_terminal_gate_probe_ci_only.sql >/dev/null
test "$(psql -XAt -v ON_ERROR_STOP=1 -c \
  "SELECT count(*) FROM public.invite_delivery_terminal_gate_staging")" = "1"
test "$(psql -XAt -v ON_ERROR_STOP=1 -c \
  "SELECT state='CI_UNKNOWN_TIMEOUT_QUARANTINE' AND NOT provider_delivery_confirmed AND NOT recipient_verified AND NOT consent_recorded AND NOT user_activated FROM public.invite_delivery_terminal_gate_staging")" = "t"
test "$(psql -XAt -v ON_ERROR_STOP=1 -c \
  "SELECT count(*) FROM public.invite_dispatch_attempt_audit_staging")" = "3"
if PGUSER=frcaixinha_invite_dispatch_ci psql -XAt -v ON_ERROR_STOP=1 \
  -c "SELECT count(*) FROM public.invite_delivery_terminal_gate_staging" >/dev/null 2>&1; then
  echo "BLOCKED: dispatch worker can read terminal gate table"
  exit 1
fi
echo "M26600_CI_TERMINAL_DELIVERY_QUARANTINE=PASS"
# Prove terminal quarantine rather than just lease expiry: synthetic DBA
# temporarily restores the CI lease and the worker STILL cannot read.
psql -X -v ON_ERROR_STOP=1 -c \
  "UPDATE public.invite_dispatch_leases_staging SET lease_expires_at=clock_timestamp()+interval '2 minutes' WHERE lease_id='eeeeeeee-0000-4000-8000-000000000033'" >/dev/null
test "$(PGOPTIONS='-c frcaixinha.envelope_staging_ci=1' \
  PGUSER=frcaixinha_invite_dispatch_ci psql -XAt -v ON_ERROR_STOP=1 -c \
  "SELECT public.invite_read_encrypted_envelope_staging_ci('eeeeeeee-0000-4000-8000-000000000015','eeeeeeee-0000-4000-8000-000000000033')")" = ""
psql -X -v ON_ERROR_STOP=1 -c \
  "UPDATE public.invite_dispatch_leases_staging SET lease_expires_at=clock_timestamp()-interval '1 second' WHERE lease_id='eeeeeeee-0000-4000-8000-000000000033'" >/dev/null
echo "M26700_QUARANTINED_ENVELOPE_NOT_RETRIEVABLE=PASS"
echo "=== M26000: single-use recovery rotation in disposable staging ==="
PGOPTIONS='-c frcaixinha.recovery_staging_ci=1' \
  psql -X -v ON_ERROR_STOP=1 -f backend/ci_migrations/048_password_reset_fixture_ci_only.sql >/dev/null
PGOPTIONS='-c frcaixinha.recovery_staging_ci=1' \
  PGUSER=frcaixinha_account_recovery_ci psql -X -v ON_ERROR_STOP=1 \
  -f backend/ci_migrations/049_password_reset_worker_probe_ci_only.sql >/dev/null
test "$(psql -XAt -v ON_ERROR_STOP=1 -c \
  "SELECT count(*) FROM public.password_recovery_audit_staging")" = "1"
test "$(psql -XAt -v ON_ERROR_STOP=1 -c \
  "SELECT consumed_at IS NOT NULL FROM public.password_reset_tokens WHERE id='eeeeeeee-0000-4000-8000-000000000024'")" = "t"
test "$(psql -XAt -v ON_ERROR_STOP=1 -c \
  "SELECT revoked_at IS NOT NULL FROM public.password_reset_tokens WHERE id='eeeeeeee-0000-4000-8000-000000000025'")" = "t"
test "$(psql -XAt -v ON_ERROR_STOP=1 -c \
  "SELECT revoked_at IS NOT NULL FROM public.sessions WHERE id='eeeeeeee-0000-4000-8000-000000000023'")" = "t"
test "$(psql -XAt -v ON_ERROR_STOP=1 -c \
  "SELECT position(repeat('Z',72) in password_hash)>0 FROM public.credentials WHERE user_id='eeeeeeee-0000-4000-8000-000000000021'")" = "t"
if PGUSER=frcaixinha_account_recovery_ci psql -XAt -v ON_ERROR_STOP=1 \
  -c "SELECT count(*) FROM public.password_reset_tokens" >/dev/null 2>&1; then
  echo "BLOCKED: reset worker has raw reset-token SELECT"
  exit 1
fi
echo "M26000_STAGING_PASSWORD_ROTATION_SESSIONS_REVOKED=PASS"
echo "=== M23200: synthetic OAuth admins + atomic consume ==="
psql -X -v ON_ERROR_STOP=1 -f backend/ci_migrations/038_oauth_admins_fixture_ci_only.sql >/dev/null
PGUSER=frcaixinha_mp_oauth_worker psql -X -v ON_ERROR_STOP=1 \
  -f backend/ci_migrations/039_oauth_state_atomic_probe_ci_only.sql
echo "M23200_DISPOSABLE_PG=PASS"
echo "=== M23600: tenant consent metadata, CAS and revocation in disposable CI ==="
psql -X -v ON_ERROR_STOP=1 \
  -f backend/ci_migrations/040_oauth_consents_fixture_ci_only.sql >/dev/null
PGUSER=frcaixinha_mp_oauth_worker psql -X -v ON_ERROR_STOP=1 \
  -f backend/ci_migrations/041_oauth_seller_cas_probe_ci_only.sql
PGUSER=frcaixinha_mp_oauth_worker psql -X -v ON_ERROR_STOP=1 \
  -f backend/ci_migrations/043_oauth_generation_worker_probe_ci_only.sql
PGUSER=frcaixinha_mp_oauth_worker psql -X -v ON_ERROR_STOP=1 \
  -f backend/ci_migrations/044_oauth_failed_reference_worker_probe_ci_only.sql
PGUSER=frcaixinha_mp_oauth_worker psql -X -v ON_ERROR_STOP=1 \
  -f backend/ci_migrations/045_oauth_revision_state_worker_probe_ci_only.sql
echo "M24300_OAUTH_REVISION_RECOVERY_SCOPE=PASS"
echo "M24200_FAILED_REFERENCE_SCOPE=PASS"
echo "M23900_CONSENT_GENERATION_SCOPE=PASS"
psql -X -v ON_ERROR_STOP=1 -c \
  "UPDATE public.mp_oauth_seller_consents_staging SET revoked_at=clock_timestamp() WHERE tenant_id='ffffffff-0000-4000-8000-000000000091' AND seller_id='2002'" >/dev/null
test "$(psql -XAt -v ON_ERROR_STOP=1 -c \
  "SELECT revoked_at IS NOT NULL FROM public.mp_oauth_seller_consents_staging WHERE seller_id='2002'")" = "t"
PGUSER=frcaixinha_mp_oauth_worker psql -X -v ON_ERROR_STOP=1 \
  -f backend/ci_migrations/042_oauth_revocation_probe_ci_only.sql
echo "M23600_DISPOSABLE_CAS_REVOKE=PASS"


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
if [ "$NOTIFY_APP_ROLE" = "frcaixinha_ci" ]; then
  NOTIFY_AUTH_ROLE="frcaixinha_auth_ci"
else
  NOTIFY_AUTH_ROLE="frcaixinha_pg18_auth"
fi
echo "=== M19000 notification schema inherited from disposable frcaixinha_ci ==="
test "$(psql -XAt -v ON_ERROR_STOP=1 -c "SELECT to_regclass('public.notification_inbox') IS NOT NULL")" = "t"
echo "M19000_M031_DISPOSABLE=PASS"
GITHUB_ACTIONS=true FRCAIXINHA_CI_ISOLATED=1 \
CI_MP_DISPOSABLE_DATABASE_URL='postgresql://postgres:ci-test-only@127.0.0.1:5432/frcaixinha_staging' \
CI_MP_NOTIFICATION_APP_URL="postgresql://${NOTIFY_APP_ROLE}:ci-test-only@127.0.0.1:5432/frcaixinha_staging" \
CI_MP_NOTIFICATION_AUTH_URL="postgresql://${NOTIFY_AUTH_ROLE}:ci-test-only@127.0.0.1:5432/frcaixinha_staging" \
PYTHONPATH=backend python -m pytest -q --asyncio-mode=auto \
 backend/tests/test_m19000_notifications_local_db_ci.py
echo "M19000_DISPOSABLE_INBOX=PASS"
echo "=== M6700 — SERIALIZABLE ledger synthetic commits and rollback ==="
CI_MP_DISPOSABLE_DATABASE_URL='postgresql://postgres:ci-test-only@127.0.0.1:5432/frcaixinha_staging' \
PYTHONPATH=backend python -m pytest -q --asyncio-mode=auto \
 backend/tests/test_m6700_disposable_ledger_atomicity_ci.py
echo "M6700_LEDGER_DISPOSABLE=PASS"


echo "=== M30400-M30800: PostgreSQL annual consent disposable ==="
if PGDATABASE=frcaixinha_ci PGOPTIONS='-c frcaixinha.annual_ci=1' \
psql -X -v ON_ERROR_STOP=1 \
-f backend/staging_migrations/058_annual_self_loan_consent_staging_only.sql >/dev/null 2>&1; then
 echo "BLOCKED=STAGING_SQL_ACCEPTED_WRONG_DB"; exit 1
fi
PGOPTIONS='-c frcaixinha.annual_ci=1' \
psql -X -v ON_ERROR_STOP=1 \
-f backend/staging_migrations/058_annual_self_loan_consent_staging_only.sql >/dev/null
PGOPTIONS='-c frcaixinha.annual_ci=1' \
psql -X -v ON_ERROR_STOP=1 \
-f backend/ci_migrations/057_annual_self_loan_fixture_ci_only.sql >/dev/null
T='dada0000-0000-4000-8000-000000000010'
A='dada0000-0000-4000-8000-000000000001'
M1='dada0000-0000-4000-8000-000000000012'
M2='dada0000-0000-4000-8000-000000000013'
U1='dada0000-0000-4000-8000-000000000002'
U2='dada0000-0000-4000-8000-000000000003'
TERMS="$(printf 'a%.0s' {1..64})"
DIGEST="$(printf 'b%.0s' {1..64})"
DATE='2027-06-01 12:00:00+00'
write_annual() {
 PGUSER=frcaixinha_annual_ci PGOPTIONS='-c frcaixinha.annual_ci=1' \
 psql -XAt -v ON_ERROR_STOP=1 -c \
 "SELECT public.annual_event_record_ci('$1','$T',2027,'$A','$2','$3','$TERMS','$4','$DIGEST','$DATE')"
}
read_annual() {
 PGUSER=frcaixinha_annual_ci PGOPTIONS='-c frcaixinha.annual_ci=1' \
 psql -XAt -v ON_ERROR_STOP=1 -c \
 "SELECT public.annual_event_review_ci('$T',2027,'$A','$TERMS','$DATE')->>'$1'"
}
test "$(read_annual unanimous_synthetic)" = "false"
test "$(write_annual 'dada0000-0000-4000-8000-000000000021' "$M1" "$U1" SIGNED)" = "RECORDED_CI_NOT_AUTHORIZED"
test "$(write_annual 'dada0000-0000-4000-8000-000000000021' "$M1" "$U1" SIGNED)" = "REPLAY_CI"
test "$(read_annual missing)" = "1"
test "$(write_annual 'dada0000-0000-4000-8000-000000000022' "$M2" "$U2" SIGNED)" = "RECORDED_CI_NOT_AUTHORIZED"
test "$(read_annual unanimous_synthetic)" = "true"
test "$(read_annual real_authorized)" = "false"
test "$(write_annual 'dada0000-0000-4000-8000-000000000023' "$M1" "$U1" REVOKED)" = "RECORDED_CI_NOT_AUTHORIZED"
test "$(read_annual unanimous_synthetic)" = "false"
test "$(write_annual 'dada0000-0000-4000-8000-000000000024' "$M1" "$U1" SIGNED)" = "RECORDED_CI_NOT_AUTHORIZED"
test "$(read_annual unanimous_synthetic)" = "true"
test "$(write_annual 'dada0000-0000-4000-8000-000000000024' "$M2" "$U2" SIGNED)" = "DENIED"
test "$(write_annual 'dada0000-0000-4000-8000-000000000025' "$M1" "$A" SIGNED)" = "DENIED"
test "$(psql -XAt -v ON_ERROR_STOP=1 -c "SELECT count(*) FROM public.annual_self_loan_events_staging")" = "4"
if PGUSER=frcaixinha_annual_ci psql -XAt -v ON_ERROR_STOP=1 \
-c 'SELECT count(*) FROM public.annual_self_loan_events_staging' >/dev/null 2>&1; then
 echo "BLOCKED=UNPRIVILEGED_RAW_READ"; exit 1
fi
if psql -XAt -v ON_ERROR_STOP=1 -c \
'DELETE FROM public.annual_self_loan_events_staging' >/dev/null 2>&1; then
 echo "BLOCKED=APPEND_ONLY_MUTATION"; exit 1
fi
echo "M30800_CI_ANNUAL_CONSENT_POSTGRES=PASS"

echo "=== M30900-M31300: SaaS contract/preparation in disposable PG ==="
# The same schema MUST refuse to run in the base database.
if PGDATABASE=frcaixinha_ci PGOPTIONS='-c frcaixinha.saas_enroll_staging_ci=1' \
  psql -X -v ON_ERROR_STOP=1 \
  -f backend/staging_migrations/059_saas_enrollment_staging_only.sql >/dev/null 2>&1; then
 echo "BLOCKED=SAAS_CI_MIGRATION_WRONG_DATABASE"; exit 1
fi
PGOPTIONS='-c frcaixinha.saas_enroll_staging_ci=1' \
  psql -X -v ON_ERROR_STOP=1 \
  -f backend/staging_migrations/059_saas_enrollment_staging_only.sql >/dev/null
PGOPTIONS='-c frcaixinha.saas_enroll_staging_ci=1' \
  psql -X -v ON_ERROR_STOP=1 \
  -f backend/ci_migrations/058_saas_enrollment_fixture_ci_only.sql >/dev/null

SAAS_TENANT='daba0000-0000-4000-8000-000000000010'
SAAS_OTHER_TENANT='daba0000-0000-4000-8000-000000000020'
SAAS_ADMIN='daba0000-0000-4000-8000-000000000001'
SAAS_OTHER_ADMIN='daba0000-0000-4000-8000-000000000002'
SAAS_ACCEPT='daba0000-0000-4000-8000-000000000040'
SAAS_OTHER_ACCEPT='daba0000-0000-4000-8000-000000000041'
SAAS_DRAFT_ACCEPT='daba0000-0000-4000-8000-000000000042'
SAAS_PRICE="$(psql -XAt -v ON_ERROR_STOP=1 -c \
 "SELECT id FROM public.platform_license_price_versions WHERE plan_tier='ESSENCIAL' ORDER BY created_at,id LIMIT 1")"
test -n "$SAAS_PRICE"
saas_prepare() {
  PGOPTIONS='-c frcaixinha.saas_enroll_staging_ci=1' \
  PGUSER=frcaixinha_saas_enroll_ci \
  psql -XAt -v ON_ERROR_STOP=1 -c \
  "SELECT public.saas_prepare_enrollment_staging_ci('$1','$2','$3','$SAAS_PRICE','$4','$5')->>'state'"
}
SAAS_REQUEST='daba0000-0000-4000-8000-000000000050'
test "$(saas_prepare "$SAAS_REQUEST" "$SAAS_TENANT" "$SAAS_ADMIN" "$SAAS_ACCEPT" MONTHLY)" = "PREPARED_CI_NO_PAYMENT"
test "$(saas_prepare "$SAAS_REQUEST" "$SAAS_TENANT" "$SAAS_ADMIN" "$SAAS_ACCEPT" MONTHLY)" = "REPLAY_CI_NO_PAYMENT"
test "$(saas_prepare "$SAAS_REQUEST" "$SAAS_TENANT" "$SAAS_ADMIN" "$SAAS_ACCEPT" ANNUAL)" = "DENIED"
test "$(saas_prepare 'daba0000-0000-4000-8000-000000000051' "$SAAS_TENANT" "$SAAS_ADMIN" "$SAAS_ACCEPT" MONTHLY)" = "EXISTING_PREPARATION_REQUIRES_REVIEW"
test "$(saas_prepare 'daba0000-0000-4000-8000-000000000052' "$SAAS_TENANT" "$SAAS_ADMIN" "$SAAS_OTHER_ACCEPT" MONTHLY)" = "DENIED"
test "$(saas_prepare 'daba0000-0000-4000-8000-000000000053' "$SAAS_TENANT" "$SAAS_ADMIN" "$SAAS_DRAFT_ACCEPT" MONTHLY)" = "DENIED"
test "$(saas_prepare 'daba0000-0000-4000-8000-000000000054' "$SAAS_OTHER_TENANT" "$SAAS_ADMIN" "$SAAS_ACCEPT" MONTHLY)" = "DENIED"
test "$(saas_prepare 'daba0000-0000-4000-8000-000000000055' "$SAAS_TENANT" "$SAAS_OTHER_ADMIN" "$SAAS_OTHER_ACCEPT" MONTHLY)" = "DENIED"
test "$(psql -XAt -v ON_ERROR_STOP=1 -c \
 "SELECT count(*) FROM public.saas_subscription_preparations WHERE tenant_id='$SAAS_TENANT'")" = "1"
test "$(psql -XAt -v ON_ERROR_STOP=1 -c \
 "SELECT count(*) FROM public.saas_enrollment_requests_staging WHERE tenant_id='$SAAS_TENANT' AND NOT payment_created AND NOT entitlement_created")" = "1"
test "$(psql -XAt -v ON_ERROR_STOP=1 -c \
 "SELECT count(*) FROM public.saas_payment_intents WHERE tenant_id='$SAAS_TENANT'")" = "0"
test "$(psql -XAt -v ON_ERROR_STOP=1 -c \
 "SELECT count(*) FROM public.saas_license_entitlements WHERE tenant_id='$SAAS_TENANT'")" = "0"
test "$(psql -XAt -v ON_ERROR_STOP=1 -c \
 "SELECT count(*) FROM public.ledger_entries WHERE tenant_id='$SAAS_TENANT'")" = "0"
if PGUSER=frcaixinha_saas_enroll_ci psql -XAt -v ON_ERROR_STOP=1 \
 -c "SELECT count(*) FROM public.saas_enrollment_requests_staging" >/dev/null 2>&1; then
 echo "BLOCKED=SAAS_CI_WORKER_CAN_READ_ENROLLMENTS"; exit 1
fi
if PGUSER=frcaixinha_saas_enroll_ci psql -XAt -v ON_ERROR_STOP=1 \
 -c "INSERT INTO public.saas_subscription_preparations DEFAULT VALUES" >/dev/null 2>&1; then
 echo "BLOCKED=SAAS_CI_WORKER_CAN_INSERT_DIRECTLY"; exit 1
fi
if psql -XAt -v ON_ERROR_STOP=1 \
 -c "DELETE FROM public.saas_enrollment_requests_staging" >/dev/null 2>&1; then
 echo "BLOCKED=SAAS_CI_IDEMPOTENCY_HISTORY_MUTABLE"; exit 1
fi
echo "M31300_SAAS_ENROLLMENT_POSTGRES=PASS"
echo "M31300_REAL_SAAS_BILLING=OFF"

echo "=== M37453: readback de preparacao SaaS committed em PostgreSQL descartavel ==="
PYTHONPATH=backend PYTHONDONTWRITEBYTECODE=1 \
  python backend/scripts/aistudio_m37453_disposable_saas_readback.py


echo "=== M37455: atomic synthetic consent in disposable PostgreSQL ==="
if PGDATABASE=frcaixinha_ci PGOPTIONS='-c frcaixinha.saas_consent_ci=1' \
  psql -X -v ON_ERROR_STOP=1 \
  -f backend/tests/sql/m37455_saas_consent_disposable_ci.sql >/dev/null 2>&1; then
  echo "BLOCKED=M37455_WRONG_DATABASE_ACCEPTED"
  exit 1
fi
PGOPTIONS='-c frcaixinha.saas_consent_ci=1' \
  psql -X -v ON_ERROR_STOP=1 \
  -f backend/tests/sql/m37455_saas_consent_disposable_ci.sql >/dev/null
PGOPTIONS='-c frcaixinha.saas_consent_ci=1' PYTHONPATH=backend \
  PYTHONDONTWRITEBYTECODE=1 \
  python backend/scripts/aistudio_m37455_saas_disposable_ci.py
echo "M37455_REAL_SAAS_BILLING=OFF"

echo "=== M37456: vinculo consentimento/preparacao, somente CI descartavel ==="
if PGDATABASE=frcaixinha_ci PGOPTIONS='-c frcaixinha.saas_consent_ci=1' \
  psql -X -v ON_ERROR_STOP=1 \
  -f backend/tests/sql/m37456_saas_consent_preparation_link_ci.sql >/dev/null 2>&1; then
  echo "BLOCKED=M37456_WRONG_DATABASE_ACCEPTED"
  exit 1
fi
PGOPTIONS='-c frcaixinha.saas_consent_ci=1' \
  psql -X -v ON_ERROR_STOP=1 \
  -f backend/tests/sql/m37456_saas_consent_preparation_link_ci.sql >/dev/null
PGOPTIONS='-c frcaixinha.saas_consent_ci=1' PYTHONPATH=backend \
  PYTHONDONTWRITEBYTECODE=1 \
  python backend/scripts/aistudio_m37456_saas_preparation_link_ci.py
echo "M37456_REAL_SAAS_BILLING=OFF"

echo "=== M31400-M31800: SaaS capacity disposable CI ==="
if PGDATABASE=frcaixinha_ci PGOPTIONS='-c frcaixinha.saas_capacity_ci=1' \
  psql -X -v ON_ERROR_STOP=1 \
  -f backend/staging_migrations/060_saas_capacity_staging_only.sql >/dev/null 2>&1; then
 echo "BLOCKED=SAAS_CAPACITY_WRONG_DB"; exit 1
fi
PGOPTIONS='-c frcaixinha.saas_capacity_ci=1' \
  psql -X -v ON_ERROR_STOP=1 \
  -f backend/staging_migrations/060_saas_capacity_staging_only.sql >/dev/null
PGOPTIONS='-c frcaixinha.saas_capacity_ci=1' \
  psql -X -v ON_ERROR_STOP=1 \
  -f backend/ci_migrations/059_saas_capacity_fixture_ci_only.sql >/dev/null
CAP_TENANT='daba0000-0000-4000-8000-000000000010'
CAP_ADMIN='daba0000-0000-4000-8000-000000000001'
CAP_OTHER='daba0000-0000-4000-8000-000000000020'
capacity_hold() {
  PGOPTIONS='-c frcaixinha.saas_capacity_ci=1' \
  PGUSER=frcaixinha_saas_capacity_ci psql -XAt -v ON_ERROR_STOP=1 -c \
   "SELECT public.saas_capacity_hold_ci('$1','$2','$3','$4',$5)->>'state'"
}
CAP_ID='daba0000-0000-4000-8000-000000000060'
test "$(capacity_hold "$CAP_ID" "$CAP_TENANT" "$CAP_ADMIN" MEMBER 20)" = "HELD_CI_NO_REAL_ALLOCATION"
test "$(capacity_hold "$CAP_ID" "$CAP_TENANT" "$CAP_ADMIN" MEMBER 20)" = "REPLAY_CI"
test "$(capacity_hold "$CAP_ID" "$CAP_TENANT" "$CAP_ADMIN" MEMBER 19)" = "DENIED"
test "$(capacity_hold 'daba0000-0000-4000-8000-000000000061' "$CAP_TENANT" "$CAP_ADMIN" MEMBER 1)" = "CAPACITY_EXCEEDED"
test "$(capacity_hold 'daba0000-0000-4000-8000-000000000062' "$CAP_OTHER" "$CAP_ADMIN" MEMBER 1)" = "DENIED"
test "$(capacity_hold 'daba0000-0000-4000-8000-000000000063' "$CAP_TENANT" "$CAP_ADMIN" QUOTA 40)" = "HELD_CI_NO_REAL_ALLOCATION"
test "$(capacity_hold 'daba0000-0000-4000-8000-000000000064' "$CAP_TENANT" "$CAP_ADMIN" QUOTA 1)" = "CAPACITY_EXCEEDED"
CAP_HOLD="$(psql -XAt -v ON_ERROR_STOP=1 -c \
 "SELECT event_id FROM public.saas_capacity_events_staging WHERE request_id='$CAP_ID'")"
test -n "$CAP_HOLD"
capacity_release() {
 PGOPTIONS='-c frcaixinha.saas_capacity_ci=1' \
 PGUSER=frcaixinha_saas_capacity_ci psql -XAt -v ON_ERROR_STOP=1 -c \
 "SELECT public.saas_capacity_release_ci('$1','$2','$3','$4')->>'state'"
}
CAP_RELEASE='daba0000-0000-4000-8000-000000000065'
test "$(capacity_release "$CAP_RELEASE" "$CAP_TENANT" "$CAP_ADMIN" "$CAP_HOLD")" = "RELEASED_CI"
test "$(capacity_release "$CAP_RELEASE" "$CAP_TENANT" "$CAP_ADMIN" "$CAP_HOLD")" = "REPLAY_RELEASE_CI"
test "$(capacity_release 'daba0000-0000-4000-8000-000000000066' "$CAP_TENANT" "$CAP_ADMIN" "$CAP_HOLD")" = "DENIED"
test "$(capacity_hold 'daba0000-0000-4000-8000-000000000067' "$CAP_TENANT" "$CAP_ADMIN" MEMBER 20)" = "HELD_CI_NO_REAL_ALLOCATION"
test "$(psql -XAt -v ON_ERROR_STOP=1 -c \
 "SELECT count(*) FROM public.memberships WHERE tenant_id='$CAP_TENANT' AND role='TENANT_MEMBER'")" = "0"
test "$(psql -XAt -v ON_ERROR_STOP=1 -c \
 "SELECT count(*) FROM public.quotas WHERE tenant_id='$CAP_TENANT'")" = "0"
test "$(psql -XAt -v ON_ERROR_STOP=1 -c \
 "SELECT count(*) FROM public.saas_payment_intents WHERE tenant_id='$CAP_TENANT'")" = "0"
if PGUSER=frcaixinha_saas_capacity_ci psql -XAt -v ON_ERROR_STOP=1 \
 -c "SELECT count(*) FROM public.saas_capacity_events_staging" >/dev/null 2>&1; then
 echo "BLOCKED=CAPACITY_WORKER_RAW_SELECT"; exit 1
fi
if psql -XAt -v ON_ERROR_STOP=1 \
 -c "DELETE FROM public.saas_capacity_events_staging" >/dev/null 2>&1; then
 echo "BLOCKED=CAPACITY_HISTORY_MUTATION"; exit 1
fi
GITHUB_ACTIONS=true FRCAIXINHA_CI_ISOLATED=1 \
CI_SAAS_CAPACITY_DB_URL='postgresql://frcaixinha_saas_capacity_ci:ci-test-only@127.0.0.1:5432/frcaixinha_staging' \
CI_SAAS_CAPACITY_DB_ADMIN_URL='postgresql://postgres:ci-test-only@127.0.0.1:5432/frcaixinha_staging' \
PYTHONPATH=backend python -m pytest -q backend/tests/test_m31800_saas_capacity_pg_ci.py
echo "M31800_SAAS_CAPACITY_PG=PASS"
echo "M31800_REAL_LICENSE_OPERATIONS=OFF"

echo "=== M31900-M32300: CI-only SaaS renewal ==="
if PGDATABASE=frcaixinha_ci PGOPTIONS='-c frcaixinha.saas_renewal_ci=1' \
 psql -X -v ON_ERROR_STOP=1 \
 -f backend/staging_migrations/061_saas_renewal_review_staging_only.sql >/dev/null 2>&1; then
 echo "BLOCKED=M32300_SQL_WRONG_DATABASE"; exit 1
fi
PGOPTIONS='-c frcaixinha.saas_renewal_ci=1' psql -X -v ON_ERROR_STOP=1 \
 -f backend/staging_migrations/061_saas_renewal_review_staging_only.sql >/dev/null
PGOPTIONS='-c frcaixinha.saas_renewal_ci=1' psql -X -v ON_ERROR_STOP=1 \
 -f backend/ci_migrations/060_saas_renewal_review_fixture_ci_only.sql >/dev/null
GITHUB_ACTIONS=true FRCAIXINHA_CI_ISOLATED=1 \
 CI_SAAS_RENEWAL_DB_URL='postgresql://frcaixinha_saas_renewal_ci:ci-test-only@127.0.0.1:5432/frcaixinha_staging' \
 CI_SAAS_RENEWAL_DB_ADMIN_URL='postgresql://postgres:ci-test-only@127.0.0.1:5432/frcaixinha_staging' \
 PYTHONPATH=backend python -m pytest -q backend/tests/test_m32300_saas_renewal_pg_ci.py
echo "M32300_RENEWAL_PG=PASS"
echo "M32300_REAL_BILLING_AND_ENTITLEMENTS=OFF"

echo "=== M33400-M33800: SaaS plan RLS admission read gate ==="
GITHUB_ACTIONS=true FRCAIXINHA_CI_ISOLATED=1 \
 CI_SAAS_ADMISSION_APP_URL='postgresql://frcaixinha_saas_admission_ci:ci-test-only@127.0.0.1:5432/frcaixinha_staging' \
 CI_SAAS_ADMISSION_ADMIN_URL='postgresql://postgres:ci-test-only@127.0.0.1:5432/frcaixinha_staging' \
 PYTHONPATH=backend python -m pytest -q backend/tests/test_m33800_saas_admission_pg_ci.py
echo "M33800_SAAS_ADMISSION_RLS_PG=PASS"
echo "M33800_REAL_MEMBER_ADMISSION=OFF"
echo "=== M33900-M34300: DB-enforced membership/quota write lock ==="
GITHUB_ACTIONS=true FRCAIXINHA_CI_ISOLATED=1 \
 CI_SAAS_WRITE_GATE_APP_URL='postgresql://frcaixinha_saas_admission_ci:ci-test-only@127.0.0.1:5432/frcaixinha_staging' \
 CI_SAAS_WRITE_GATE_ADMIN_URL='postgresql://postgres:ci-test-only@127.0.0.1:5432/frcaixinha_staging' \
 PYTHONPATH=backend python -m pytest -q backend/tests/test_m34300_saas_write_lock_pg_ci.py
echo "M34300_MEMBER_QUOTA_WRITES_CLOSED=PASS"
echo "M34300_REAL_MEMBER_ADMISSION=OFF"

echo "=== M32400-M32800: CI-only synthetic claim ==="
if PGDATABASE=frcaixinha_ci PGOPTIONS='-c frcaixinha.saas_claim_ci=1' \
 psql -X -v ON_ERROR_STOP=1 \
 -f backend/staging_migrations/062_saas_capacity_claim_staging_only.sql >/dev/null 2>&1; then
 echo "BLOCKED=M32800_WRONG_DATABASE"; exit 1
fi
PGOPTIONS='-c frcaixinha.saas_claim_ci=1' psql -X -v ON_ERROR_STOP=1 \
 -f backend/staging_migrations/062_saas_capacity_claim_staging_only.sql >/dev/null
GITHUB_ACTIONS=true FRCAIXINHA_CI_ISOLATED=1 \
 CI_SAAS_CLAIM_DB_URL='postgresql://frcaixinha_saas_claim_ci:ci-test-only@127.0.0.1:5432/frcaixinha_staging' \
 CI_SAAS_CLAIM_DB_ADMIN_URL='postgresql://postgres:ci-test-only@127.0.0.1:5432/frcaixinha_staging' \
 CI_SAAS_CLAIM_CAPACITY_URL='postgresql://frcaixinha_saas_capacity_ci:ci-test-only@127.0.0.1:5432/frcaixinha_staging' \
 PYTHONPATH=backend python -m pytest -q backend/tests/test_m32800_saas_capacity_claim_pg_ci.py
echo "M32800_SAAS_CLAIM_PG=PASS"
echo "M32800_REAL_USERS_AND_PIX=OFF"


echo "=== M32900-M33300: CI-only stale hold recovery ==="
if PGDATABASE=frcaixinha_ci PGOPTIONS='-c frcaixinha.saas_expiry_ci=1' \
 psql -X -v ON_ERROR_STOP=1 \
 -f backend/staging_migrations/063_saas_capacity_expiry_staging_only.sql >/dev/null 2>&1; then
 echo "BLOCKED=M33300_WRONG_DATABASE"; exit 1
fi
PGOPTIONS='-c frcaixinha.saas_expiry_ci=1' psql -X -v ON_ERROR_STOP=1 \
 -f backend/staging_migrations/063_saas_capacity_expiry_staging_only.sql >/dev/null
GITHUB_ACTIONS=true FRCAIXINHA_CI_ISOLATED=1 \
 CI_SAAS_EXPIRY_DB_URL='postgresql://frcaixinha_saas_capacity_ci:ci-test-only@127.0.0.1:5432/frcaixinha_staging' \
 CI_SAAS_EXPIRY_CLAIM_URL='postgresql://frcaixinha_saas_claim_ci:ci-test-only@127.0.0.1:5432/frcaixinha_staging' \
 CI_SAAS_EXPIRY_DB_ADMIN_URL='postgresql://postgres:ci-test-only@127.0.0.1:5432/frcaixinha_staging' \
 PYTHONPATH=backend python -m pytest -q backend/tests/test_m33300_saas_capacity_expiry_pg_ci.py
echo "M33300_EXPIRY_PG=PASS"
echo "M33300_REAL_USERS_AND_PIX=OFF"
echo "=== M34400-M34800: synthetic verified admission intent ==="
if PGDATABASE=frcaixinha_ci PGOPTIONS='-c frcaixinha.admission_intent_ci=1' \
 psql -X -v ON_ERROR_STOP=1 \
 -f backend/staging_migrations/064_saas_member_admission_intent_staging_only.sql >/dev/null 2>&1; then
 echo "BLOCKED=M34800_WRONG_DATABASE"; exit 1
fi
PGOPTIONS='-c frcaixinha.admission_intent_ci=1' psql -X -v ON_ERROR_STOP=1 \
 -f backend/staging_migrations/064_saas_member_admission_intent_staging_only.sql >/dev/null
GITHUB_ACTIONS=true FRCAIXINHA_CI_ISOLATED=1 \
 CI_SAAS_INTENT_WORKER_URL='postgresql://frcaixinha_saas_admission_intent_ci:ci-test-only@127.0.0.1:5432/frcaixinha_staging' \
 CI_SAAS_INTENT_OWNER_URL='postgresql://postgres:ci-test-only@127.0.0.1:5432/frcaixinha_staging' \
 CI_SAAS_INTENT_APP_URL='postgresql://frcaixinha_saas_admission_ci:ci-test-only@127.0.0.1:5432/frcaixinha_staging' \
 CI_SAAS_INTENT_CAPACITY_URL='postgresql://frcaixinha_saas_capacity_ci:ci-test-only@127.0.0.1:5432/frcaixinha_staging' \
 CI_SAAS_INTENT_CLAIM_URL='postgresql://frcaixinha_saas_claim_ci:ci-test-only@127.0.0.1:5432/frcaixinha_staging' \
 PYTHONPATH=backend python -m pytest -q backend/tests/test_m34800_saas_admission_intent_pg_ci.py
echo "M34800_INTENT_PG=PASS"
echo "M34800_REAL_MEMBERS_AND_PIX=OFF"

echo "=== M35900-M36300: CI-only SaaS reconciliation review ==="
if PGDATABASE=frcaixinha_ci PGOPTIONS='-c frcaixinha.saas_review_ci=1' \
  psql -X -v ON_ERROR_STOP=1 \
  -f backend/staging_migrations/065_saas_reconciliation_review_staging_only.sql >/dev/null 2>&1; then
  echo "BLOCKED=M36300_WRONG_DATABASE"; exit 1
fi
PGOPTIONS='-c frcaixinha.saas_review_ci=1' psql -X -v ON_ERROR_STOP=1 \
  -f backend/staging_migrations/065_saas_reconciliation_review_staging_only.sql >/dev/null
GITHUB_ACTIONS=true FRCAIXINHA_CI_ISOLATED=1 \
  CI_SAAS_REVIEW_WORKER_URL='postgresql://frcaixinha_saas_review_ci:ci-test-only@127.0.0.1:5432/frcaixinha_staging' \
  CI_SAAS_REVIEW_OWNER_URL='postgresql://postgres:ci-test-only@127.0.0.1:5432/frcaixinha_staging' \
  CI_SAAS_REVIEW_APP_URL='postgresql://frcaixinha_saas_admission_ci:ci-test-only@127.0.0.1:5432/frcaixinha_staging' \
  PYTHONPATH=backend python -m pytest -q backend/tests/test_m36300_saas_reconciliation_pg_ci.py
echo "M36300_RECONCILIATION_EVIDENCE_CI=PASS"
echo "M36300_PRODUCTION_RECONCILIATION_AND_PIX=OFF"

echo "STAGING_034_039_DISPOSABLE_POSTGRES=PASS"
echo "LOCAL_MIGRATIONS=NOT_TOUCHED"
echo "OCI_APPLY=NOT_EXECUTED"
echo "REAL_MONEY=OFF"
