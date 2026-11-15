-- CI root's untrusted REVOCATION_PROPOSED, not an actual mandate revocation.
-- This holds the same proposed-grant row lock used by receipt trigger.
\ir m40020_disposable_guard.psql
BEGIN;
DO $$
BEGIN
 UPDATE m40020_ci.proposed_grant_state
 SET stopped_for_ci=true,
     stop_event_id='c1111111-1111-4111-8111-111111111111'::uuid,
     stop_proposed_at=clock_timestamp()
 WHERE packet_id='44444444-4444-4444-8444-444444444444'
   AND actor_db_role='m40010_a_b' AND stopped_for_ci=false;
 IF NOT FOUND THEN RAISE EXCEPTION 'M40020_STOP_PROPOSAL_TARGET_MISSING'; END IF;
 INSERT INTO m40020_ci.proposed_stop_events(
   event_id,packet_id,actor_db_role,action)
 VALUES(
   'c1111111-1111-4111-8111-111111111111',
   '44444444-4444-4444-8444-444444444444',
   'm40010_a_b','REVOCATION_PROPOSED');
END;
$$;
\echo M40020_STOP_PROPOSAL_LOCK_HELD
SELECT pg_sleep(3);
COMMIT;
\echo M40020_STOP_PROPOSAL_COMMITTED_CI_ONLY
