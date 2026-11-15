-- M40040: a different synthetic actor must not infer an acknowledgement.
\ir m40040_disposable_guard.psql
BEGIN;
SET LOCAL ROLE m40010_a_b;
DO $$
DECLARE result text;
BEGIN
 result:=m40040_ci.inspect_uncertain_commit(
  'e9111111-1111-4111-8111-111111111111'::uuid, repeat('a',64));
 IF result <> 'NOT_FOUND_OR_NOT_VISIBLE' THEN
  RAISE EXCEPTION 'M40040_SECOND_REVIEWER_SAW_FIRST_ACK_%',result;
 END IF;
 IF (SELECT count(*) FROM m40040_ci.receipt_ack)<>0 THEN
  RAISE EXCEPTION 'M40040_SECOND_REVIEWER_RLS_LEAK';
 END IF;
END;
$$;
ROLLBACK;

BEGIN;
SET LOCAL ROLE m40010_b_a;
DO $$
BEGIN
 IF m40040_ci.inspect_uncertain_commit(
  'e9111111-1111-4111-8111-111111111111'::uuid, repeat('b',64))
  <> 'NOT_FOUND_OR_NOT_VISIBLE' OR
    (SELECT count(*) FROM m40040_ci.receipt_ack)<>0 THEN
  RAISE EXCEPTION 'M40040_TENANT_B_RLS_LEAK';
 END IF;
END;
$$;
ROLLBACK;

BEGIN;
SET LOCAL ROLE m40010_m_a;
DO $$
BEGIN
 IF m40040_ci.inspect_uncertain_commit(
  'e9111111-1111-4111-8111-111111111111'::uuid, repeat('a',64))
  <> 'NOT_FOUND_OR_NOT_VISIBLE' OR
    (SELECT count(*) FROM m40040_ci.receipt_ack)<>0 THEN
  RAISE EXCEPTION 'M40040_PLATFORM_MASTER_RLS_LEAK';
 END IF;
END;
$$;
ROLLBACK;
\echo M40040_SECOND_REVIEWER_AND_TENANT_RLS=PASS
