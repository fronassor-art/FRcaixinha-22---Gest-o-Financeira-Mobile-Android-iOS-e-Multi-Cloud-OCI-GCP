-- Independent final CI connection: assert only one receipt, one stop proposal,
-- immutability and no real authority or payout.
\ir m40020_disposable_guard.psql
BEGIN;
DO $$
DECLARE rejected boolean;
BEGIN
 IF (SELECT count(*) FROM m40010_ci.review_receipts
     WHERE packet_id='44444444-4444-4444-8444-444444444444')<>1 THEN
  RAISE EXCEPTION 'M40020_ATOMIC_ONE_RECEIPT_EXPECTED';
 END IF;
 IF (SELECT count(*) FROM m40020_ci.proposed_stop_events)<>1
 OR (SELECT count(*) FROM m40020_ci.proposed_grant_state
     WHERE stopped_for_ci=true)<>1
 OR (SELECT count(*) FROM m40020_ci.proposed_grant_state
     WHERE stopped_for_ci=false)<>1 THEN
  RAISE EXCEPTION 'M40020_STOP_EVENT_NOT_ATOMICALLY_PERSISTED';
 END IF;
 IF EXISTS (SELECT 1 FROM m40010_ci.review_receipts
    WHERE packet_id='44444444-4444-4444-8444-444444444444'
      AND actor_db_role<>'m40010_a_a') THEN
  RAISE EXCEPTION 'M40020_LATE_WRITER_BYPASSED_STOP';
 END IF;
 IF EXISTS (SELECT 1 FROM m40020_ci.proposed_grant_state
   WHERE reviewer_identity_authenticated OR mandate_ratified
      OR effective_revocation_verified)
 OR EXISTS (SELECT 1 FROM m40020_ci.proposed_stop_events
   WHERE signed_human_consent OR authentic_revocation OR approved OR payments_enabled)
 OR EXISTS (SELECT 1 FROM m40010_ci.review_receipts
   WHERE human_identity_verified OR reviewer_mandate_ratified
    OR document_authenticated OR approved OR provider_reconciled
    OR journal_posted OR payout_enabled OR available_balance_cents IS NOT NULL)
 OR EXISTS (SELECT 1 FROM m40010_ci.review_packets
   WHERE policy_ratified OR journal_posted OR payout_enabled
      OR available_balance_cents IS NOT NULL) THEN
  RAISE EXCEPTION 'M40020_ANY_REAL_FINANCIAL_OR_IDENTITY_CLAIM';
 END IF;
 IF has_table_privilege('m40010_a_b','m40020_ci.proposed_grant_state','UPDATE')
 OR has_table_privilege('m40010_a_a','m40020_ci.proposed_stop_events','INSERT')
 OR has_table_privilege('m40010_a_b','m40010_ci.review_receipts','UPDATE') THEN
  RAISE EXCEPTION 'M40020_UNEXPECTED_APPLICATION_WRITE_GRANT';
 END IF;

 rejected:=false;
 BEGIN
  UPDATE m40020_ci.proposed_grant_state
  SET stopped_for_ci=false, stop_event_id=NULL, stop_proposed_at=NULL
  WHERE actor_db_role='m40010_a_b';
 EXCEPTION WHEN SQLSTATE '55000' THEN rejected:=true;
 END;
 IF NOT rejected THEN RAISE EXCEPTION 'M40020_REACTIVATION_ACCEPTED'; END IF;

 rejected:=false;
 BEGIN
  DELETE FROM m40020_ci.proposed_stop_events;
 EXCEPTION WHEN SQLSTATE '55000' THEN rejected:=true;
 END;
 IF NOT rejected THEN RAISE EXCEPTION 'M40020_AUDIT_DELETE_ACCEPTED'; END IF;
END;
$$;
SET LOCAL ROLE m40010_a_a;
DO $$
BEGIN
 IF (SELECT count(*) FROM m40020_ci.proposed_grant_state)<>1
 OR (SELECT count(*) FROM m40020_ci.proposed_stop_events)<>0
 OR (SELECT count(*) FROM m40010_ci.review_receipts
     WHERE packet_id='44444444-4444-4444-8444-444444444444')<>1 THEN
  RAISE EXCEPTION 'M40020_FIRST_ACTOR_RLS_LEAK';
 END IF;
END;
$$;
RESET ROLE;
SET LOCAL ROLE m40010_a_b;
DO $$
BEGIN
 IF (SELECT count(*) FROM m40020_ci.proposed_grant_state)<>1
 OR (SELECT count(*) FROM m40020_ci.proposed_stop_events)<>1
 OR (SELECT count(*) FROM m40010_ci.review_receipts
     WHERE packet_id='44444444-4444-4444-8444-444444444444')<>0 THEN
  RAISE EXCEPTION 'M40020_SECOND_ACTOR_RLS_LEAK';
 END IF;
END;
$$;
ROLLBACK;
\echo M40020_DOUBLE_INSERT_COLLISION=PASS
\echo M40020_STOP_PROPOSAL_COLLISION=PASS
\echo M40020_INDEPENDENT_AUDIT_CONNECTION=PASS
\echo M40020_ACTOR_RLS_AND_IMMUTABILITY=PASS
\echo M40020_REAL_AUTHENTICATION=NOT_ATTESTED
\echo M40020_REAL_REVOCATION=NOT_ATTESTED
\echo M40020_REAL_PAYMENTS=OFF
\echo M40020_ORIGINAL_DB_WRITES=NONE
\echo M40020_PRODUCTION=BLOCKED
