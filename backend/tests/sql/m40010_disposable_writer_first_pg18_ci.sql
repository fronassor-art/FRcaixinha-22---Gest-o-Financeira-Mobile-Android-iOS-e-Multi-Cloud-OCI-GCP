-- First independent psql process: simulated reviewer-A role grants.
\ir m40010_disposable_guard.psql
BEGIN;
SET LOCAL ROLE m40010_m_a;
INSERT INTO m40010_ci.review_receipts(
 receipt_id,packet_id,scope,cashbox_key,policy_fingerprint,slot,
 actor_db_role,reviewer_id,claimed_session_id,nonce,idempotency_key,action)
VALUES(
 '51111111-1111-4111-8111-111111111111','11111111-1111-4111-8111-111111111111','PLATFORM_MASTER','platform',repeat('a',64),1,
 current_user,'41111111-1111-4111-8111-111111111111','71111111-1111-4111-8111-111111111111','81111111-1111-4111-8111-111111111111','91111111-1111-4111-8111-111111111111',
 'DOCUMENTARY_CHECK_PROPOSED');
COMMIT;
BEGIN;
SET LOCAL ROLE m40010_a_a;
INSERT INTO m40010_ci.review_receipts(
 receipt_id,packet_id,scope,cashbox_key,policy_fingerprint,slot,
 actor_db_role,reviewer_id,claimed_session_id,nonce,idempotency_key,action)
VALUES(
 '53333333-3333-4333-8333-333333333333','22222222-2222-4222-8222-222222222222','TENANT_ADMIN_OWN','tenant:aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',repeat('c',64),1,
 current_user,'43333333-3333-4333-8333-333333333333','73333333-3333-4333-8333-333333333333','83333333-3333-4333-8333-333333333333','93333333-3333-4333-8333-333333333333',
 'DOCUMENTARY_CHECK_PROPOSED');
COMMIT;
BEGIN;
SET LOCAL ROLE m40010_b_a;
INSERT INTO m40010_ci.review_receipts(
 receipt_id,packet_id,scope,cashbox_key,policy_fingerprint,slot,
 actor_db_role,reviewer_id,claimed_session_id,nonce,idempotency_key,action)
VALUES(
 '55555555-5555-4555-8555-555555555555','33333333-3333-4333-8333-333333333333','TENANT_ADMIN_OWN','tenant:bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',repeat('e',64),1,
 current_user,'45555555-5555-4555-8555-555555555555','75555555-5555-4555-8555-555555555555','85555555-5555-4555-8555-555555555555','95555555-5555-4555-8555-555555555555',
 'DOCUMENTARY_CHECK_PROPOSED');
COMMIT;

\echo M40010_FIRST_INDEPENDENT_SESSION=COMMITTED
