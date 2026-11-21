-- M40040: a PROPOSED stop blocks NEW receipts, but previous committed
-- response-status lookup remains available, without enabling any approval.
\ir m40040_disposable_guard.psql
BEGIN;
UPDATE m40020_ci.proposed_grant_state
SET stopped_for_ci=true,
 stop_event_id='f1111111-1111-4111-8111-111111111111'::uuid,
 stop_proposed_at=clock_timestamp()
WHERE packet_id='44444444-4444-4444-8444-444444444444'
  AND actor_db_role='m40010_a_a' AND stopped_for_ci=false;
INSERT INTO m40020_ci.proposed_stop_events(event_id,packet_id,actor_db_role,action)
VALUES('f1111111-1111-4111-8111-111111111111',
 '44444444-4444-4444-8444-444444444444',
 'm40010_a_a','REVOCATION_PROPOSED');
COMMIT;

BEGIN;
SET LOCAL ROLE m40010_a_a;
DO $$
DECLARE outcome text;
DECLARE rejected boolean:=false;
DECLARE reason text;
BEGIN
 outcome:=m40040_ci.inspect_uncertain_commit(
   'e9111111-1111-4111-8111-111111111111'::uuid,repeat('a',64));
 IF outcome<>'EXISTING_UNVERIFIED_RECEIPT_NO_NEW_WRITE' THEN
  RAISE EXCEPTION 'M40040_PREEXISTING_RECEIPT_LOST_AFTER_STOP_%',outcome;
 END IF;
 BEGIN
  INSERT INTO m40010_ci.review_receipts(
    receipt_id,packet_id,scope,cashbox_key,policy_fingerprint,slot,
    actor_db_role,reviewer_id,claimed_session_id,nonce,idempotency_key,action)
  VALUES(
   'f2222222-2222-4222-8222-222222222222',
   '44444444-4444-4444-8444-444444444444',
   'TENANT_ADMIN_OWN','tenant:aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
   repeat('1',64),1,current_user,
   '43333333-3333-4333-8333-333333333333',
   'f7222222-2222-4222-8222-222222222222',
   'f8222222-2222-4222-8222-222222222222',
   'f9222222-2222-4222-8222-222222222222',
   'REQUEST_MORE_EVIDENCE');
 EXCEPTION WHEN SQLSTATE 'P0001' THEN
  GET STACKED DIAGNOSTICS reason=MESSAGE_TEXT;
  rejected:=(reason='M40020_PROPOSED_STOP_BLOCKS_FUTURE_CI_RECEIPT');
 END;
 IF NOT rejected THEN RAISE EXCEPTION 'M40040_NEW_RECEIPT_AFTER_STOP_WAS_NOT_REJECTED'; END IF;
END;
$$;
ROLLBACK;
\echo M40040_PREEXISTING_RECEIPT_READABLE_AFTER_STOP=PASS
\echo M40040_NEW_RECEIPT_POST_STOP=BLOCKED
