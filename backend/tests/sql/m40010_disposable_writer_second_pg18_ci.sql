-- Second independent psql process: synthetic reviewer-B role grants.
\ir m40010_disposable_guard.psql
BEGIN;
SET LOCAL ROLE m40010_m_b;
INSERT INTO m40010_ci.review_receipts(
 receipt_id,packet_id,scope,cashbox_key,policy_fingerprint,slot,
 actor_db_role,reviewer_id,claimed_session_id,nonce,idempotency_key,action)
VALUES(
 '52222222-2222-4222-8222-222222222222','11111111-1111-4111-8111-111111111111','PLATFORM_MASTER','platform',repeat('a',64),2,
 current_user,'42222222-2222-4222-8222-222222222222','72222222-2222-4222-8222-222222222222','82222222-2222-4222-8222-222222222222','92222222-2222-4222-8222-222222222222',
 'REQUEST_MORE_EVIDENCE');
COMMIT;
BEGIN;
SET LOCAL ROLE m40010_a_b;
INSERT INTO m40010_ci.review_receipts(
 receipt_id,packet_id,scope,cashbox_key,policy_fingerprint,slot,
 actor_db_role,reviewer_id,claimed_session_id,nonce,idempotency_key,action)
VALUES(
 '54444444-4444-4444-8444-444444444444','22222222-2222-4222-8222-222222222222','TENANT_ADMIN_OWN','tenant:aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',repeat('c',64),2,
 current_user,'44444444-4444-4444-8444-444444444444','74444444-4444-4444-8444-444444444444','84444444-4444-4444-8444-444444444444','94444444-4444-4444-8444-444444444444',
 'REQUEST_MORE_EVIDENCE');
COMMIT;
BEGIN;
SET LOCAL ROLE m40010_b_b;
INSERT INTO m40010_ci.review_receipts(
 receipt_id,packet_id,scope,cashbox_key,policy_fingerprint,slot,
 actor_db_role,reviewer_id,claimed_session_id,nonce,idempotency_key,action)
VALUES(
 '56666666-6666-4666-8666-666666666666','33333333-3333-4333-8333-333333333333','TENANT_ADMIN_OWN','tenant:bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',repeat('e',64),2,
 current_user,'46666666-6666-4666-8666-666666666666','76666666-6666-4666-8666-666666666666','86666666-6666-4666-8666-666666666666','96666666-6666-4666-8666-666666666666',
 'REQUEST_MORE_EVIDENCE');
COMMIT;

\echo M40010_SECOND_INDEPENDENT_SESSION=COMMITTED
