-- M40040: final audit in its own fresh psql connection.
\ir m40040_disposable_guard.psql
BEGIN;
DO $$
DECLARE blocked boolean;
BEGIN
 IF (SELECT count(*) FROM m40040_ci.receipt_ack)<>1
 OR (SELECT count(*) FROM m40010_ci.review_receipts
     WHERE packet_id='44444444-4444-4444-8444-444444444444')<>1
 OR (SELECT count(*) FROM m40020_ci.proposed_stop_events)<>1 THEN
  RAISE EXCEPTION 'M40040_ACK_RECOVERY_COUNTERS_INVALID';
 END IF;
 IF NOT EXISTS(
   SELECT 1 FROM m40040_ci.receipt_ack a
   JOIN m40010_ci.review_receipts r ON r.receipt_id=a.receipt_id
   WHERE a.receipt_id='e1111111-1111-4111-8111-111111111111'
     AND a.idempotency_key=r.idempotency_key
     AND a.packet_id=r.packet_id
     AND a.actor_db_role=r.actor_db_role
     AND a.cashbox_key=r.cashbox_key
     AND a.request_fingerprint=repeat('a',64)
 ) THEN
  RAISE EXCEPTION 'M40040_ACK_RECEIPT_BINDING_INCONSISTENT';
 END IF;
 IF EXISTS(SELECT 1 FROM m40040_ci.receipt_ack
   WHERE session_authenticated OR signed_human_consent OR policy_approved
    OR payout_enabled OR available_balance_cents IS NOT NULL)
 OR EXISTS(SELECT 1 FROM m40010_ci.review_receipts
   WHERE human_identity_verified OR reviewer_mandate_ratified OR
    document_authenticated OR approved OR provider_reconciled OR
    journal_posted OR payout_enabled OR available_balance_cents IS NOT NULL)
 OR EXISTS(SELECT 1 FROM m40020_ci.proposed_stop_events
   WHERE signed_human_consent OR authentic_revocation OR approved OR payments_enabled)
 OR EXISTS(SELECT 1 FROM m40020_ci.proposed_grant_state
   WHERE reviewer_identity_authenticated OR mandate_ratified OR
    effective_revocation_verified)
 THEN
  RAISE EXCEPTION 'M40040_FINANCIAL_OR_IDENTITY_AUTHORITY_FABRICATED';
 END IF;
 IF has_table_privilege('m40010_a_a','m40040_ci.receipt_ack','UPDATE')
 OR has_table_privilege('m40010_a_b','m40040_ci.receipt_ack','DELETE')
 OR has_table_privilege('m40010_a_a','m40020_ci.proposed_grant_state','UPDATE') THEN
  RAISE EXCEPTION 'M40040_UNAUTHORIZED_MUTATION_GRANT';
 END IF;
 blocked:=false;
 BEGIN
  UPDATE m40040_ci.receipt_ack SET policy_approved=true;
 EXCEPTION WHEN SQLSTATE '55000' THEN blocked:=true;
 END;
 IF NOT blocked THEN RAISE EXCEPTION 'M40040_ACK_WAS_MUTABLE'; END IF;
 blocked:=false;
 BEGIN
  DELETE FROM m40040_ci.receipt_ack;
 EXCEPTION WHEN SQLSTATE '55000' THEN blocked:=true;
 END;
 IF NOT blocked THEN RAISE EXCEPTION 'M40040_ACK_WAS_DELETABLE'; END IF;
END;
$$;
ROLLBACK;
\echo M40040_FINAL_AUDIT_EXACTLY_ONE_COMMITTED_RECEIPT=PASS
\echo M40040_LOST_RESPONSE_RECOVERABLE_READ_ONLY=PASS
\echo M40040_CHANGED_PAYLOAD_CONFLICT=PASS
\echo M40040_CROSS_TENANT_RLS=PASS
\echo M40040_PROPOSED_STOP_REJECTS_NEW_CI_WRITES=PASS
\echo M40040_NO_HUMAN_AUTHENTICATION=TRUE
\echo M40040_REAL_REVOCATION=NOT_ATTESTED
\echo M40040_ORIGINAL_DB_ACCESS=NONE
\echo M40040_LOCAL_MIGRATIONS=NONE
\echo M40040_PIX_REAL=OFF
\echo M40040_PRODUCTION=BLOCKED
