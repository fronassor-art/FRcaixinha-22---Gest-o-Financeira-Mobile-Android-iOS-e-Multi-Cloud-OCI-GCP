-- CI session 2: colliding receipt cannot bypass the unique slot and nonce.
\ir m40020_disposable_guard.psql
BEGIN;
SET LOCAL ROLE m40010_a_a;
DO $$
DECLARE constraint_hit text;
DECLARE accepted boolean := false;
BEGIN
 BEGIN
  INSERT INTO m40010_ci.review_receipts(
   receipt_id,packet_id,scope,cashbox_key,policy_fingerprint,slot,
   actor_db_role,reviewer_id,claimed_session_id,nonce,idempotency_key,action)
  VALUES(
   'b2222222-2222-4222-8222-222222222222',
   '44444444-4444-4444-8444-444444444444',
   'TENANT_ADMIN_OWN','tenant:aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
   repeat('1',64),1,current_user,
   '43333333-3333-4333-8333-333333333333',
   'b7222222-2222-4222-8222-222222222222',
   'b8111111-1111-4111-8111-111111111111',
   'b9111111-1111-4111-8111-111111111111',
   'REQUEST_MORE_EVIDENCE');
  accepted := true;
 EXCEPTION WHEN unique_violation THEN
  GET STACKED DIAGNOSTICS constraint_hit = CONSTRAINT_NAME;
  IF constraint_hit NOT IN (
    'm40010_unique_slot','m40010_unique_reviewer',
    'm40010_unique_nonce','m40010_unique_idem'
  ) THEN
    RAISE EXCEPTION 'M40020 unexpected constraint: %',constraint_hit;
  END IF;
  RAISE NOTICE 'M40020_CONCURRENT_DUPLICATE_REJECTED=%',constraint_hit;
 END;
 IF accepted THEN RAISE EXCEPTION 'M40020_CONCURRENT_DUPLICATE_ACCEPTED'; END IF;
END;
$$;
COMMIT;
\echo M40020_SECOND_WRITER_DENIED
