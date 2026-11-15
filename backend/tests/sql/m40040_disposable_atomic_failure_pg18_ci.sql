-- M40040: intentional ACK mismatch must abort the WHOLE synthetic transaction.
-- CI expects psql exit 3, the precise error, then checks rollback separately.
\ir m40040_disposable_guard.psql
BEGIN;
SET LOCAL ROLE m40010_a_a;
INSERT INTO m40010_ci.review_receipts(
 receipt_id,packet_id,scope,cashbox_key,policy_fingerprint,slot,
 actor_db_role,reviewer_id,claimed_session_id,nonce,idempotency_key,action)
VALUES(
 'e2222222-2222-4222-8222-222222222222',
 '44444444-4444-4444-8444-444444444444',
 'TENANT_ADMIN_OWN','tenant:aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
 repeat('1',64),1,current_user,
 '43333333-3333-4333-8333-333333333333',
 'e7222222-2222-4222-8222-222222222222',
 'e8222222-2222-4222-8222-222222222222',
 'e9222222-2222-4222-8222-222222222222',
 'DOCUMENTARY_CHECK_PROPOSED');
INSERT INTO m40040_ci.receipt_ack(
 receipt_id,packet_id,scope,cashbox_key,actor_db_role,
 idempotency_key,request_fingerprint)
VALUES(
 'e2222222-2222-4222-8222-222222222222',
 '44444444-4444-4444-8444-444444444444',
 'TENANT_ADMIN_OWN','tenant:aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
 current_user,'f9222222-2222-4222-8222-222222222222',repeat('b',64));
-- No COMMIT: the previous insert fails in the trigger.
\echo M40040_UNEXPECTED_MISMATCH_ACCEPTED
