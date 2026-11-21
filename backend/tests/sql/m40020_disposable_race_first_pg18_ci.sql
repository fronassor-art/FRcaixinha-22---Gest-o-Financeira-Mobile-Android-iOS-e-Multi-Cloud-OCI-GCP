-- CI session 1: lock slot 1 by inserting and holding transaction.
\ir m40020_disposable_guard.psql
BEGIN;
SET LOCAL ROLE m40010_a_a;
INSERT INTO m40010_ci.review_receipts(
 receipt_id,packet_id,scope,cashbox_key,policy_fingerprint,slot,
 actor_db_role,reviewer_id,claimed_session_id,nonce,idempotency_key,action)
VALUES(
 'b1111111-1111-4111-8111-111111111111',
 '44444444-4444-4444-8444-444444444444',
 'TENANT_ADMIN_OWN','tenant:aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
 repeat('1',64),1,current_user,
 '43333333-3333-4333-8333-333333333333',
 'b7111111-1111-4111-8111-111111111111',
 'b8111111-1111-4111-8111-111111111111',
 'b9111111-1111-4111-8111-111111111111',
 'DOCUMENTARY_CHECK_PROPOSED');
\echo M40020_FIRST_WRITER_LOCK_HELD
SELECT pg_sleep(3);
COMMIT;
\echo M40020_FIRST_WRITER_COMMITTED
