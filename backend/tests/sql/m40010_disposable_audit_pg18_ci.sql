-- Third independent psql process: attest database persistence and deny replay.
\ir m40010_disposable_guard.psql
BEGIN;

DO $$
BEGIN
 IF (SELECT count(*) FROM m40010_ci.review_packets) <> 4 OR
    (SELECT count(*) FROM m40010_ci.synthetic_role_bindings) <> 8 OR
    (SELECT count(*) FROM m40010_ci.review_receipts) <> 6 THEN
  RAISE EXCEPTION 'M40010 separate-session data not durable in CI';
 END IF;
 IF (SELECT count(*) FROM m40010_ci.review_receipts
     WHERE scope='PLATFORM_MASTER') <> 2 OR
    (SELECT count(*) FROM m40010_ci.review_receipts
     WHERE scope='TENANT_ADMIN_OWN' AND
           cashbox_key='tenant:aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa') <> 2 OR
    (SELECT count(*) FROM m40010_ci.review_receipts
     WHERE scope='TENANT_ADMIN_OWN' AND
           cashbox_key='tenant:bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb') <> 2 THEN
  RAISE EXCEPTION 'M40010 tenant pair segregation not persisted';
 END IF;
 IF EXISTS(
  SELECT 1 FROM m40010_ci.review_packets
  WHERE policy_ratified OR journal_posted OR payout_enabled
    OR available_balance_cents IS NOT NULL) OR EXISTS(
  SELECT 1 FROM m40010_ci.review_receipts
  WHERE human_identity_verified OR reviewer_mandate_ratified OR
        document_authenticated OR approved OR provider_reconciled OR
        journal_posted OR payout_enabled OR
        available_balance_cents IS NOT NULL) THEN
  RAISE EXCEPTION 'M40010 fabricated real approval';
 END IF;
 IF EXISTS(SELECT 1 FROM m40010_ci.review_receipts
  WHERE recorded_at IS NULL OR
        state <> 'DB_ROLE_SIMULATED_NOT_AUTHENTICATED') THEN
  RAISE EXCEPTION 'M40010 client altered recorded date or state';
 END IF;
 IF EXISTS(SELECT 1 FROM m40010_ci.review_receipts r
   LEFT JOIN m40010_ci.synthetic_role_bindings b
      ON b.packet_id=r.packet_id AND b.db_role=r.actor_db_role
         AND b.reviewer_id=r.reviewer_id AND b.slot=r.slot
   WHERE b.packet_id IS NULL) THEN
  RAISE EXCEPTION 'M40010 receipt identity lacks synthetic DB role binding';
 END IF;
 IF EXISTS(SELECT 1 FROM m40010_ci.review_receipts
    GROUP BY packet_id HAVING count(*) > 2) THEN
  RAISE EXCEPTION 'M40010 packet has more than two unique role slots';
 END IF;
 IF has_table_privilege('m40010_m_a','m40010_ci.review_receipts','UPDATE')
 OR has_table_privilege('m40010_a_a','m40010_ci.review_receipts','DELETE')
 OR has_table_privilege('m40010_a_b','m40010_ci.review_packets','INSERT')
 OR has_table_privilege('m40010_b_b','m40010_ci.synthetic_role_bindings','UPDATE') THEN
   RAISE EXCEPTION 'M40010 writer gained unauthorized mutation rights';
 END IF;
 IF pg_has_role('m40010_a_a','m40010_a_b','MEMBER') OR
    pg_has_role('m40010_m_a','m40010_b_a','MEMBER') THEN
   RAISE EXCEPTION 'M40010 test actor roles share membership';
 END IF;
END;
$$;

-- Role A is mapped to both tenant A packets but only one receipt.
SET LOCAL ROLE m40010_a_a;
DO $$
DECLARE blocked boolean;
DECLARE violated text;
BEGIN
 IF (SELECT count(*) FROM m40010_ci.review_packets) <> 2 OR
    (SELECT count(*) FROM m40010_ci.synthetic_role_bindings) <> 2 OR
    (SELECT count(*) FROM m40010_ci.review_receipts) <> 1 THEN
    RAISE EXCEPTION 'M40010 tenant A reviewer RLS view leak';
 END IF;

 -- Replaying an idempotency key on a different packet in the SAME tenant
 -- must be rejected by its named unique constraint.
 blocked := false; violated := NULL;
 BEGIN
  INSERT INTO m40010_ci.review_receipts(
   receipt_id,packet_id,scope,cashbox_key,policy_fingerprint,slot,
   actor_db_role,reviewer_id,claimed_session_id,nonce,idempotency_key,action)
  VALUES(
   'f1111111-1111-4111-8111-111111111111',
   '44444444-4444-4444-8444-444444444444',
   'TENANT_ADMIN_OWN','tenant:aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
   repeat('1',64),1,current_user,
   '43333333-3333-4333-8333-333333333333',
   'f7111111-1111-4111-8111-111111111111',
   'f8111111-1111-4111-8111-111111111111',
   '93333333-3333-4333-8333-333333333333',
   'DOCUMENTARY_CHECK_PROPOSED');
 EXCEPTION WHEN unique_violation THEN
   GET STACKED DIAGNOSTICS violated = CONSTRAINT_NAME;
   blocked := violated='m40010_unique_idem';
 END;
 IF NOT blocked THEN
  RAISE EXCEPTION 'M40010 idempotency key replay not rejected by named constraint';
 END IF;

 -- Repeating a nonce on the other packet is independently blocked.
 blocked := false; violated := NULL;
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
   '83333333-3333-4333-8333-333333333333',
   'f9222222-2222-4222-8222-222222222222',
   'DOCUMENTARY_CHECK_PROPOSED');
 EXCEPTION WHEN unique_violation THEN
   GET STACKED DIAGNOSTICS violated = CONSTRAINT_NAME;
   blocked := violated='m40010_unique_nonce';
 END;
 IF NOT blocked THEN RAISE EXCEPTION 'M40010 nonce replay not rejected'; END IF;

 -- A role from tenant A may not write a tenant B receipt, even if it
 -- knows all synthetic identifiers.
 blocked := false;
 BEGIN
  INSERT INTO m40010_ci.review_receipts(
   receipt_id,packet_id,scope,cashbox_key,policy_fingerprint,slot,
   actor_db_role,reviewer_id,claimed_session_id,nonce,idempotency_key,action)
  VALUES(
   'f3333333-3333-4333-8333-333333333333',
   '33333333-3333-4333-8333-333333333333',
   'TENANT_ADMIN_OWN','tenant:bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',
   repeat('e',64),1,current_user,
   '43333333-3333-4333-8333-333333333333',
   'f7333333-3333-4333-8333-333333333333',
   'f8333333-3333-4333-8333-333333333333',
   'f9333333-3333-4333-8333-333333333333',
   'DOCUMENTARY_CHECK_PROPOSED');
 EXCEPTION WHEN insufficient_privilege THEN blocked := true;
 END;
 IF NOT blocked THEN RAISE EXCEPTION 'M40010 cross tenant writer accepted'; END IF;

 -- User cannot masquerade as another DB role, even with a matching FK.
 blocked := false;
 BEGIN
  INSERT INTO m40010_ci.review_receipts(
   receipt_id,packet_id,scope,cashbox_key,policy_fingerprint,slot,
   actor_db_role,reviewer_id,claimed_session_id,nonce,idempotency_key,action)
  VALUES(
   'f4444444-4444-4444-8444-444444444444',
   '44444444-4444-4444-8444-444444444444',
   'TENANT_ADMIN_OWN','tenant:aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
   repeat('1',64),2,'m40010_a_b',
   '44444444-4444-4444-8444-444444444444',
   'f7444444-4444-4444-8444-444444444444',
   'f8444444-4444-4444-8444-444444444444',
   'f9444444-4444-4444-8444-444444444444',
   'REQUEST_MORE_EVIDENCE');
 EXCEPTION WHEN insufficient_privilege THEN blocked := true;
 END;
 IF NOT blocked THEN RAISE EXCEPTION 'M40010 actor DB role spoof accepted'; END IF;

 -- The limited writer role is not allowed to supply an approved flag
 -- and is not allowed to mutate prior receipts.
 blocked := false;
 BEGIN
  UPDATE m40010_ci.review_receipts SET approved=true
  WHERE receipt_id='53333333-3333-4333-8333-333333333333';
 EXCEPTION WHEN insufficient_privilege THEN blocked := true;
 END;
 IF NOT blocked THEN RAISE EXCEPTION 'M40010 writer may update approval'; END IF;
END;
$$;

ROLLBACK;

-- A fresh connection (the auditing process) saw all six committed rows.
-- Every failed attempt above rolled back in its PL/pgSQL subtransaction.
\echo M40010_SEPARATE_CONNECTION_DURABILITY=PASS
\echo M40010_ROLES_AND_CROSS_TENANT_RLS=PASS
\echo M40010_NONCE_AND_IDEMPOTENCY=PASS
\echo M40010_SYNTHETIC_ROLES_NOT_HUMAN_IDENTITY=TRUE
\echo M40010_REAL_APPROVAL=FALSE
\echo M40010_ORIGINAL_DB_ACCESS=NONE
\echo M40010_LOCAL_MIGRATIONS=NONE
\echo M40010_PRODUCTION=BLOCKED
