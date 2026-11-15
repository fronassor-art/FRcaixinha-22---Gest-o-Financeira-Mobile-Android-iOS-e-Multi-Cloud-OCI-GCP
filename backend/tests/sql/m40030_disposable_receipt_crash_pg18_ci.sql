-- M40030: only a GitHub disposable DB. Process is deliberately killed
-- AFTER a successful INSERT and BEFORE COMMIT; all data must roll back.
\ir m40030_disposable_guard.psql
BEGIN;
SET LOCAL ROLE m40010_a_a;
INSERT INTO m40010_ci.review_receipts(
 receipt_id,packet_id,scope,cashbox_key,policy_fingerprint,slot,
 actor_db_role,reviewer_id,claimed_session_id,nonce,idempotency_key,action)
VALUES(
 'd1111111-1111-4111-8111-111111111111',
 '44444444-4444-4444-8444-444444444444',
 'TENANT_ADMIN_OWN','tenant:aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
 repeat('1',64),1,current_user,
 '43333333-3333-4333-8333-333333333333',
 'd7111111-1111-4111-8111-111111111111',
 'd8111111-1111-4111-8111-111111111111',
 'd9111111-1111-4111-8111-111111111111',
 'DOCUMENTARY_CHECK_PROPOSED');
\echo M40030_RECEIPT_PENDING_COMMIT_WITH_ROW_LOCK
SELECT pg_sleep(8);
COMMIT;
\echo M40030_UNEXPECTED_RECEIPT_COMMIT
