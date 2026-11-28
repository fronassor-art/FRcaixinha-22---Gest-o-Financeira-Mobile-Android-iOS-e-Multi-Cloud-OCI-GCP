-- CI simulated reviewer B collides with pending stop proposal.
-- It must block on grant row and then see stopped_for_ci=true after commit.
\ir m40020_disposable_guard.psql
BEGIN;
SET LOCAL ROLE m40010_a_b;
DO $$
DECLARE rejected boolean := false;
DECLARE msg text;
BEGIN
 BEGIN
  INSERT INTO m40010_ci.review_receipts(
   receipt_id,packet_id,scope,cashbox_key,policy_fingerprint,slot,
   actor_db_role,reviewer_id,claimed_session_id,nonce,idempotency_key,action)
  VALUES(
   'b3333333-3333-4333-8333-333333333333',
   '44444444-4444-4444-8444-444444444444',
   'TENANT_ADMIN_OWN','tenant:aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
   repeat('1',64),2,current_user,
   '44444444-4444-4444-8444-444444444444',
   'b7333333-3333-4333-8333-333333333333',
   'b8333333-3333-4333-8333-333333333333',
   'b9333333-3333-4333-8333-333333333333',
   'DOCUMENTARY_CHECK_PROPOSED');
 EXCEPTION WHEN SQLSTATE 'P0001' THEN
  GET STACKED DIAGNOSTICS msg = MESSAGE_TEXT;
  IF msg = 'M40020_PROPOSED_STOP_BLOCKS_FUTURE_CI_RECEIPT' THEN
   rejected := true;
   RAISE NOTICE 'M40020_CONCURRENT_RECEIPT_AFTER_STOP=DENIED';
  ELSE
   RAISE EXCEPTION 'M40020 unexpected stop error: %',msg;
  END IF;
 END;
 IF NOT rejected THEN
  RAISE EXCEPTION 'M40020_CONCURRENT_RECEIPT_AFTER_STOP_ACCEPTED';
 END IF;
END;
$$;
COMMIT;
\echo M40020_STOP_COLLISION_DENIED_CI_ONLY
