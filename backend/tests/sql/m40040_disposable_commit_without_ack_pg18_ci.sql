-- M40040 CI: first connection commits both receipt and evidence of the reply.
-- CI orchestration DISCARDs the result body after a successful COMMIT.
\ir m40040_disposable_guard.psql
BEGIN;
SET LOCAL ROLE m40010_a_a;
INSERT INTO m40010_ci.review_receipts(
 receipt_id,packet_id,scope,cashbox_key,policy_fingerprint,slot,
 actor_db_role,reviewer_id,claimed_session_id,nonce,idempotency_key,action)
VALUES(
 'e1111111-1111-4111-8111-111111111111',
 '44444444-4444-4444-8444-444444444444',
 'TENANT_ADMIN_OWN','tenant:aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
 repeat('1',64),1,current_user,
 '43333333-3333-4333-8333-333333333333',
 'e7111111-1111-4111-8111-111111111111',
 'e8111111-1111-4111-8111-111111111111',
 'e9111111-1111-4111-8111-111111111111',
 'DOCUMENTARY_CHECK_PROPOSED');
INSERT INTO m40040_ci.receipt_ack(
 receipt_id,packet_id,scope,cashbox_key,actor_db_role,idempotency_key,
 request_fingerprint)
VALUES(
 'e1111111-1111-4111-8111-111111111111',
 '44444444-4444-4444-8444-444444444444',
 'TENANT_ADMIN_OWN','tenant:aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
 current_user,'e9111111-1111-4111-8111-111111111111',repeat('a',64));
COMMIT;
\echo M40040_TRANSACTION_COMMITTED_RESPONSE_BODY_NOT_DELIVERED_IN_CI
