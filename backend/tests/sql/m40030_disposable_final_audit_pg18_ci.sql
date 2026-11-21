-- Last independent connection: prove rollback-before-commit is recoverable,
-- committed receipts remain unique, and proposed stop never becomes real.
\ir m40030_disposable_guard.psql
BEGIN;
DO $$
BEGIN
 IF (SELECT count(*) FROM m40010_ci.review_receipts
     WHERE packet_id='44444444-4444-4444-8444-444444444444')<>1
 OR (SELECT count(*) FROM m40010_ci.review_receipts
     WHERE packet_id='22222222-2222-4222-8222-222222222222')<>0
 OR (SELECT count(*) FROM m40020_ci.proposed_stop_events)<>1
 OR (SELECT count(*) FROM m40020_ci.proposed_grant_state
     WHERE packet_id='44444444-4444-4444-8444-444444444444'
      AND stopped_for_ci)<>1 THEN
  RAISE EXCEPTION 'M40030_FAILURE_RECOVERY_COUNTS_INVALID';
 END IF;
 IF (SELECT count(*) FROM m40010_ci.review_receipts
     WHERE receipt_id='d1111111-1111-4111-8111-111111111111'
       AND nonce='d8111111-1111-4111-8111-111111111111'
       AND idempotency_key='d9111111-1111-4111-8111-111111111111')<>1
 OR (SELECT count(*) FROM m40020_ci.proposed_stop_events
     WHERE event_id='d2222222-2222-4222-8222-222222222222'
       AND action='REVOCATION_PROPOSED')<>1 THEN
  RAISE EXCEPTION 'M40030_RETRY_NOT_SAME_EVENT_ID';
 END IF;
 IF EXISTS(SELECT 1 FROM m40010_ci.review_receipts
     WHERE human_identity_verified OR reviewer_mandate_ratified
        OR document_authenticated OR approved OR provider_reconciled
        OR journal_posted OR payout_enabled OR available_balance_cents IS NOT NULL)
 OR EXISTS(SELECT 1 FROM m40020_ci.proposed_stop_events
     WHERE signed_human_consent OR authentic_revocation OR approved OR payments_enabled)
 OR EXISTS(SELECT 1 FROM m40020_ci.proposed_grant_state
     WHERE reviewer_identity_authenticated OR mandate_ratified
        OR effective_revocation_verified)
 OR EXISTS(SELECT 1 FROM m40010_ci.review_packets
     WHERE policy_ratified OR journal_posted OR payout_enabled
        OR available_balance_cents IS NOT NULL) THEN
  RAISE EXCEPTION 'M40030_REAL_APPROVAL_WAS_FABRICATED';
 END IF;
END;
$$;

SET LOCAL ROLE m40010_a_a;
DO $$
BEGIN
 IF (SELECT count(*) FROM m40010_ci.review_receipts
     WHERE packet_id='44444444-4444-4444-8444-444444444444')<>1 OR
    (SELECT count(*) FROM m40020_ci.proposed_stop_events)<>0 THEN
  RAISE EXCEPTION 'M40030_ACTOR_A_RLS_FAILED';
 END IF;
END;
$$;
RESET ROLE;
SET LOCAL ROLE m40010_a_b;
DO $$
BEGIN
 IF (SELECT count(*) FROM m40010_ci.review_receipts
     WHERE packet_id='44444444-4444-4444-8444-444444444444')<>0 OR
    (SELECT count(*) FROM m40020_ci.proposed_stop_events)<>1 THEN
  RAISE EXCEPTION 'M40030_ACTOR_B_RLS_FAILED';
 END IF;
END;
$$;
ROLLBACK;
\echo M40030_ATOMIC_CRASH_RECOVERY=PASS
\echo M40030_POST_COMMIT_REPLAY=DENIED
\echo M40030_PROPOSED_STOP_CANNOT_APPROVE=PASS
\echo M40030_CROSS_ACTOR_RLS=PASS
\echo M40030_REAL_REVOCATION=NOT_ATTESTED
\echo M40030_REAL_APPROVAL=FALSE
\echo M40030_PIX_REAL=OFF
\echo M40030_ORIGINAL_DB_WRITES=NONE
\echo M40030_PRODUCTION=BLOCKED
