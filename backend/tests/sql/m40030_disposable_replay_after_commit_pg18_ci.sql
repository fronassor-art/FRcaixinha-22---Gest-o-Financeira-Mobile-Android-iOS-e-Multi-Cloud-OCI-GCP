-- A commit survived a separate psql process. Replays from ANOTHER
-- packet of the SAME tenant must hit the intended unique constraint.
\ir m40030_disposable_guard.psql
BEGIN;
SET LOCAL ROLE m40010_a_a;
DO $$
DECLARE caught boolean; name text;
BEGIN
 caught:=false; name:=NULL;
 BEGIN
  INSERT INTO m40010_ci.review_receipts(
   receipt_id,packet_id,scope,cashbox_key,policy_fingerprint,slot,
   actor_db_role,reviewer_id,claimed_session_id,nonce,idempotency_key,action)
  VALUES(
   'd3333333-3333-4333-8333-333333333333',
   '22222222-2222-4222-8222-222222222222',
   'TENANT_ADMIN_OWN','tenant:aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
   repeat('c',64),1,current_user,
   '43333333-3333-4333-8333-333333333333',
   'd7333333-3333-4333-8333-333333333333',
   'd8111111-1111-4111-8111-111111111111',
   'd9333333-3333-4333-8333-333333333333',
   'DOCUMENTARY_CHECK_PROPOSED');
 EXCEPTION WHEN unique_violation THEN
  GET STACKED DIAGNOSTICS name=CONSTRAINT_NAME;
  caught:=(name='m40010_unique_nonce');
 END;
 IF NOT caught THEN
  RAISE EXCEPTION 'M40030_NONCE_REPLAY_UNEXPECTED_CONSTRAINT_%',name;
 END IF;

 caught:=false; name:=NULL;
 BEGIN
  INSERT INTO m40010_ci.review_receipts(
   receipt_id,packet_id,scope,cashbox_key,policy_fingerprint,slot,
   actor_db_role,reviewer_id,claimed_session_id,nonce,idempotency_key,action)
  VALUES(
   'd4444444-4444-4444-8444-444444444444',
   '22222222-2222-4222-8222-222222222222',
   'TENANT_ADMIN_OWN','tenant:aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
   repeat('c',64),1,current_user,
   '43333333-3333-4333-8333-333333333333',
   'd7444444-4444-4444-8444-444444444444',
   'd8444444-4444-4444-8444-444444444444',
   'd9111111-1111-4111-8111-111111111111',
   'DOCUMENTARY_CHECK_PROPOSED');
 EXCEPTION WHEN unique_violation THEN
  GET STACKED DIAGNOSTICS name=CONSTRAINT_NAME;
  caught:=(name='m40010_unique_idem');
 END;
 IF NOT caught THEN
  RAISE EXCEPTION 'M40030_IDEMPOTENCY_REPLAY_UNEXPECTED_CONSTRAINT_%',name;
 END IF;
END;
$$;
COMMIT;
\echo M40030_COMMITTED_NONCE_AND_IDEMPOTENCY_REPLAY=DENIED
