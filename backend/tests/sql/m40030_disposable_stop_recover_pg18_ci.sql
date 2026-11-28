-- A killed connection may not leave a half-written stop proposal.
-- Retry exact same synthetic stop event id, then COMMIT atomically.
\ir m40030_disposable_guard.psql
DO $$
BEGIN
 IF (SELECT count(*) FROM m40020_ci.proposed_stop_events)<>0 OR
    (SELECT count(*) FROM m40020_ci.proposed_grant_state
     WHERE packet_id='44444444-4444-4444-8444-444444444444'
       AND actor_db_role='m40010_a_b' AND stopped_for_ci)<>0 THEN
  RAISE EXCEPTION 'M40030_CRASHED_STOP_PARTIALLY_COMMITTED';
 END IF;
END;
$$;
BEGIN;
UPDATE m40020_ci.proposed_grant_state
SET stopped_for_ci=true,
    stop_event_id='d2222222-2222-4222-8222-222222222222'::uuid,
    stop_proposed_at=clock_timestamp()
WHERE packet_id='44444444-4444-4444-8444-444444444444'
  AND actor_db_role='m40010_a_b'
  AND stopped_for_ci=false;
INSERT INTO m40020_ci.proposed_stop_events(
 event_id,packet_id,actor_db_role,action)
VALUES('d2222222-2222-4222-8222-222222222222',
       '44444444-4444-4444-8444-444444444444',
       'm40010_a_b','REVOCATION_PROPOSED');
COMMIT;
DO $$
BEGIN
 IF (SELECT count(*) FROM m40020_ci.proposed_stop_events
     WHERE event_id='d2222222-2222-4222-8222-222222222222')<>1 OR
    (SELECT count(*) FROM m40020_ci.proposed_grant_state
     WHERE actor_db_role='m40010_a_b' AND stopped_for_ci)<>1 THEN
  RAISE EXCEPTION 'M40030_STOP_RECOVERY_NOT_ATOMIC';
 END IF;
END;
$$;
\echo M40030_CRASHED_STOP_ROLLBACK_AND_IDENTICAL_RETRY=PASS
