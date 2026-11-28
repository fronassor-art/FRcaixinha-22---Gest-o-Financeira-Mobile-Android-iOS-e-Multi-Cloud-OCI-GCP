-- M40030 synthetic proposed stop transaction; connection will die BEFORE COMMIT.
\ir m40030_disposable_guard.psql
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
VALUES(
 'd2222222-2222-4222-8222-222222222222',
 '44444444-4444-4444-8444-444444444444',
 'm40010_a_b','REVOCATION_PROPOSED');
\echo M40030_STOP_PENDING_COMMIT_WITH_ROW_LOCK
SELECT pg_sleep(8);
COMMIT;
\echo M40030_UNEXPECTED_STOP_COMMIT
