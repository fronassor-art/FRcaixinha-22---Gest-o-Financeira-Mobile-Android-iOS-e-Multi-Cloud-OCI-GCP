-- M40030: add second packet as same synthetic tenant solely for nonce/idempotency.
-- Schema M40010+M40020 must have been initialized in CI disposable database.
\ir m40030_disposable_guard.psql
BEGIN;
INSERT INTO m40020_ci.proposed_grant_state(
 packet_id,actor_db_role,reviewer_id,slot)
VALUES
 ('22222222-2222-4222-8222-222222222222','m40010_a_a',
  '43333333-3333-4333-8333-333333333333',1),
 ('22222222-2222-4222-8222-222222222222','m40010_a_b',
  '44444444-4444-4444-8444-444444444444',2);
COMMIT;
\echo M40030_ADDITIONAL_CI_PACKET_GRANTS=PASS
