-- Verify uncommitted row was rolled back after killing psql, then retry exact
-- same id, nonce and idempotency key in a NEW connection.
\ir m40030_disposable_guard.psql
DO $$
BEGIN
 IF (SELECT count(*) FROM m40010_ci.review_receipts
     WHERE packet_id='44444444-4444-4444-8444-444444444444')<>0 THEN
  RAISE EXCEPTION 'M40030_CRASHED_RECEIPT_WAS_NOT_ROLLED_BACK';
 END IF;
END;
$$;
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
COMMIT;
DO $$
BEGIN
 IF (SELECT count(*) FROM m40010_ci.review_receipts
     WHERE receipt_id='d1111111-1111-4111-8111-111111111111')<>1 THEN
  RAISE EXCEPTION 'M40030_RECOVERED_RECEIPT_NOT_COMMITTED';
 END IF;
END;
$$;
\echo M40030_CRASHED_RECEIPT_ROLLBACK_AND_IDENTICAL_RETRY=PASS
