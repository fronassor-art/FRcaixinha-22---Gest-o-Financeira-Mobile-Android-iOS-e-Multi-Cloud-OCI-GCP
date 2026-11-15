-- FR Finance M40000 — synthetic PostgreSQL18 reviewer receipt and replay constraints.
-- THIS IS NOT A MIGRATION. ROLLBACK erases all fixtures in disposable CI.
-- No original finance/legacy database; no real authentication or approvals.
\set ON_ERROR_STOP on
\if :{?CI_M40000_DISPOSABLE}
\else
\echo M40000_BLOCKED_MISSING_DISPOSABLE_FLAG
\quit 2
\endif

SELECT CASE WHEN current_database()='frcaixinha_ci'
 AND inet_server_port()=5432
 AND session_user='postgres'
 AND current_setting('frfinance.m40000_ci',true)='DISPOSABLE_ONLY'
 THEN 'true' ELSE 'false' END AS m40000_disposable_identity
\gset
\if :m40000_disposable_identity
\else
\echo M40000_BLOCKED_WRONG_CLUSTER
\quit 2
\endif

BEGIN;

CREATE SCHEMA m40000_ci;
CREATE ROLE m40000_ci_reader NOLOGIN NOBYPASSRLS;

CREATE TABLE m40000_ci.review_packets (
 id uuid PRIMARY KEY CHECK(id <> '00000000-0000-0000-0000-000000000000'::uuid),
 scope text NOT NULL CHECK(scope IN ('PLATFORM_MASTER','TENANT_ADMIN_OWN')),
 cashbox_key text NOT NULL,
 journal_fingerprint char(64) NOT NULL CHECK(journal_fingerprint ~ '^[0-9a-f]{64}$'),
 document_digest char(64) NOT NULL CHECK(document_digest ~ '^[0-9a-f]{64}$'),
 policy_draft_fingerprint char(64) NOT NULL CHECK(policy_draft_fingerprint ~ '^[0-9a-f]{64}$'),
 prepared_by uuid NOT NULL CHECK(prepared_by <> '00000000-0000-0000-0000-000000000000'::uuid),
 state text NOT NULL DEFAULT 'CI_UNAUTHENTICATED_PACKET'
   CHECK(state='CI_UNAUTHENTICATED_PACKET'),
 policy_approved boolean NOT NULL DEFAULT false CHECK(policy_approved=false),
 provider_reconciled boolean NOT NULL DEFAULT false CHECK(provider_reconciled=false),
 journal_posted boolean NOT NULL DEFAULT false CHECK(journal_posted=false),
 payout_authorized boolean NOT NULL DEFAULT false CHECK(payout_authorized=false),
 available_balance_cents bigint CHECK(available_balance_cents IS NULL),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 CONSTRAINT m40000_packet_scope CHECK(
   (scope='PLATFORM_MASTER' AND cashbox_key='platform')
   OR (scope='TENANT_ADMIN_OWN' AND cashbox_key ~
   '^tenant:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')
 ),
 UNIQUE(id,scope,cashbox_key,journal_fingerprint,document_digest,policy_draft_fingerprint)
);

CREATE TABLE m40000_ci.review_receipts (
 id uuid PRIMARY KEY CHECK(id <> '00000000-0000-0000-0000-000000000000'::uuid),
 packet_id uuid NOT NULL,
 scope text NOT NULL,
 cashbox_key text NOT NULL,
 journal_fingerprint char(64) NOT NULL,
 document_digest char(64) NOT NULL,
 policy_draft_fingerprint char(64) NOT NULL,
 reviewer_id uuid NOT NULL CHECK(reviewer_id <> '00000000-0000-0000-0000-000000000000'::uuid),
 session_id uuid NOT NULL CHECK(session_id <> '00000000-0000-0000-0000-000000000000'::uuid),
 nonce uuid NOT NULL CHECK(nonce <> '00000000-0000-0000-0000-000000000000'::uuid),
 idempotency_key uuid NOT NULL CHECK(idempotency_key <> '00000000-0000-0000-0000-000000000000'::uuid),
 action text NOT NULL CHECK(action IN (
   'DOCUMENTARY_CHECK_PROPOSED','REQUEST_MORE_EVIDENCE')),
 synthetic_observed_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 state text NOT NULL DEFAULT 'UNVERIFIED_REVIEW_RECEIPT'
   CHECK(state='UNVERIFIED_REVIEW_RECEIPT'),
 session_authenticated boolean NOT NULL DEFAULT false CHECK(session_authenticated=false),
 reviewer_mandate_verified boolean NOT NULL DEFAULT false CHECK(reviewer_mandate_verified=false),
 document_authenticated boolean NOT NULL DEFAULT false CHECK(document_authenticated=false),
 approval_verified boolean NOT NULL DEFAULT false CHECK(approval_verified=false),
 journal_posted boolean NOT NULL DEFAULT false CHECK(journal_posted=false),
 payout_enabled boolean NOT NULL DEFAULT false CHECK(payout_enabled=false),
 available_balance_cents bigint CHECK(available_balance_cents IS NULL),
 FOREIGN KEY(packet_id,scope,cashbox_key,journal_fingerprint,
             document_digest,policy_draft_fingerprint)
    REFERENCES m40000_ci.review_packets(
             id,scope,cashbox_key,journal_fingerprint,
             document_digest,policy_draft_fingerprint),
 UNIQUE(packet_id,reviewer_id),
 UNIQUE(packet_id,session_id),
 UNIQUE(scope,cashbox_key,nonce),
 UNIQUE(scope,cashbox_key,idempotency_key)
);

-- CI writer uses postgres exclusively: the synthetic reader has no INSERT.
-- Lock the parent packet row before counting, serializing competing inserts
-- for that packet. This proves a structural cap, NOT external auth or signatures.
CREATE FUNCTION m40000_ci.guard_two_claims() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog,pg_temp AS $$
DECLARE packet_preparer uuid;
DECLARE existing_count integer;
BEGIN
 SELECT prepared_by INTO packet_preparer
 FROM m40000_ci.review_packets
 WHERE id=NEW.packet_id
 FOR UPDATE;
 IF NOT FOUND THEN
  RAISE EXCEPTION USING ERRCODE='23503',MESSAGE='M40000_PACKET_NOT_FOUND';
 END IF;
 IF packet_preparer=NEW.reviewer_id THEN
  RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='M40000_SELF_REVIEW_FORBIDDEN';
 END IF;
 SELECT count(*) INTO existing_count FROM m40000_ci.review_receipts
 WHERE packet_id=NEW.packet_id;
 IF existing_count >= 2 THEN
  RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='M40000_MORE_THAN_TWO_REVIEW_CLAIMS';
 END IF;
 RETURN NEW;
END;
$$;
CREATE TRIGGER m40000_two_review_claims
 BEFORE INSERT ON m40000_ci.review_receipts FOR EACH ROW
 EXECUTE FUNCTION m40000_ci.guard_two_claims();

CREATE FUNCTION m40000_ci.reject_mutation() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog,pg_temp AS $$
BEGIN
 RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='M40000_APPEND_ONLY_CI';
END;
$$;
CREATE TRIGGER m40000_packet_append_only
 BEFORE UPDATE OR DELETE ON m40000_ci.review_packets
 FOR EACH ROW EXECUTE FUNCTION m40000_ci.reject_mutation();
CREATE TRIGGER m40000_receipt_append_only
 BEFORE UPDATE OR DELETE ON m40000_ci.review_receipts
 FOR EACH ROW EXECUTE FUNCTION m40000_ci.reject_mutation();

ALTER TABLE m40000_ci.review_packets ENABLE ROW LEVEL SECURITY;
ALTER TABLE m40000_ci.review_packets FORCE ROW LEVEL SECURITY;
ALTER TABLE m40000_ci.review_receipts ENABLE ROW LEVEL SECURITY;
ALTER TABLE m40000_ci.review_receipts FORCE ROW LEVEL SECURITY;

-- These GUCs are synthetic test context. In real server code they MUST
-- be derived server-side from authenticated roles, not client headers.
CREATE POLICY m40000_packet_read_only ON m40000_ci.review_packets
 FOR SELECT TO m40000_ci_reader USING (
  (scope='PLATFORM_MASTER'
    AND current_setting('frfinance.actor_role',true)='MASTER'
    AND COALESCE(current_setting('frfinance.actor_tenant',true),'')='')
   OR
  (scope='TENANT_ADMIN_OWN'
    AND current_setting('frfinance.actor_role',true)='TENANT_ADMIN'
    AND cashbox_key='tenant:' ||
       COALESCE(NULLIF(current_setting('frfinance.actor_tenant',true),''),'NONE'))
 );
CREATE POLICY m40000_receipt_read_only ON m40000_ci.review_receipts
 FOR SELECT TO m40000_ci_reader USING(
  EXISTS (SELECT 1 FROM m40000_ci.review_packets p
   WHERE p.id=packet_id AND p.scope=review_receipts.scope
    AND p.cashbox_key=review_receipts.cashbox_key
    AND p.journal_fingerprint=review_receipts.journal_fingerprint
    AND p.document_digest=review_receipts.document_digest
    AND p.policy_draft_fingerprint=review_receipts.policy_draft_fingerprint)
 );
GRANT USAGE ON SCHEMA m40000_ci TO m40000_ci_reader;
GRANT SELECT ON m40000_ci.review_packets,m40000_ci.review_receipts
 TO m40000_ci_reader;

INSERT INTO m40000_ci.review_packets(
 id,scope,cashbox_key,journal_fingerprint,document_digest,
 policy_draft_fingerprint,prepared_by)
VALUES
 ('11111111-1111-4111-8111-111111111111',
  'PLATFORM_MASTER','platform',repeat('a',64),repeat('b',64),repeat('c',64),
  '88888888-8888-4888-8888-888888888888'),
 ('22222222-2222-4222-8222-222222222222',
  'TENANT_ADMIN_OWN','tenant:aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
  repeat('d',64),repeat('e',64),repeat('f',64),
  '88888888-8888-4888-8888-888888888888'),
 ('33333333-3333-4333-8333-333333333333',
  'TENANT_ADMIN_OWN','tenant:bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',
  repeat('0',64),repeat('1',64),repeat('2',64),
  '88888888-8888-4888-8888-888888888888');

INSERT INTO m40000_ci.review_receipts(
 id,packet_id,scope,cashbox_key,journal_fingerprint,document_digest,
 policy_draft_fingerprint,reviewer_id,session_id,nonce,idempotency_key,action)
VALUES
 ('41111111-1111-4111-8111-111111111111',
  '11111111-1111-4111-8111-111111111111',
  'PLATFORM_MASTER','platform',repeat('a',64),repeat('b',64),repeat('c',64),
  '44444444-4444-4444-8444-444444444444',
  '71111111-1111-4111-8111-111111111111',
  '81111111-1111-4111-8111-111111111111',
  '91111111-1111-4111-8111-111111111111',
  'DOCUMENTARY_CHECK_PROPOSED'),
 ('42222222-2222-4222-8222-222222222222',
  '11111111-1111-4111-8111-111111111111',
  'PLATFORM_MASTER','platform',repeat('a',64),repeat('b',64),repeat('c',64),
  '55555555-5555-4555-8555-555555555555',
  '72222222-2222-4222-8222-222222222222',
  '82222222-2222-4222-8222-222222222222',
  '92222222-2222-4222-8222-222222222222',
  'REQUEST_MORE_EVIDENCE'),
 ('43333333-3333-4333-8333-333333333333',
  '22222222-2222-4222-8222-222222222222',
  'TENANT_ADMIN_OWN','tenant:aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
  repeat('d',64),repeat('e',64),repeat('f',64),
  '44444444-4444-4444-8444-444444444444',
  '73333333-3333-4333-8333-333333333333',
  '83333333-3333-4333-8333-333333333333',
  '93333333-3333-4333-8333-333333333333',
  'DOCUMENTARY_CHECK_PROPOSED'),
 ('44444444-4444-4444-8444-444444444444',
  '22222222-2222-4222-8222-222222222222',
  'TENANT_ADMIN_OWN','tenant:aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
  repeat('d',64),repeat('e',64),repeat('f',64),
  '55555555-5555-4555-8555-555555555555',
  '74444444-4444-4444-8444-444444444444',
  '84444444-4444-4444-8444-444444444444',
  '94444444-4444-4444-8444-444444444444',
  'REQUEST_MORE_EVIDENCE'),
 ('45555555-5555-4555-8555-555555555555',
  '33333333-3333-4333-8333-333333333333',
  'TENANT_ADMIN_OWN','tenant:bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',
  repeat('0',64),repeat('1',64),repeat('2',64),
  '44444444-4444-4444-8444-444444444444',
  '75555555-5555-4555-8555-555555555555',
  '85555555-5555-4555-8555-555555555555',
  '95555555-5555-4555-8555-555555555555',
  'DOCUMENTARY_CHECK_PROPOSED');

-- Transactional assertions: exception savepoints keep fixture data intact.
DO $$
DECLARE blocked boolean;
BEGIN
 IF (SELECT count(*) FROM m40000_ci.review_packets)<>3 OR
    (SELECT count(*) FROM m40000_ci.review_receipts)<>5 THEN
   RAISE EXCEPTION 'M40000 fixture count mismatch';
 END IF;
 IF EXISTS(SELECT 1 FROM m40000_ci.review_packets
    WHERE policy_approved OR provider_reconciled OR journal_posted
      OR payout_authorized OR available_balance_cents IS NOT NULL) OR
    EXISTS(SELECT 1 FROM m40000_ci.review_receipts
    WHERE session_authenticated OR reviewer_mandate_verified
      OR document_authenticated OR approval_verified OR journal_posted
      OR payout_enabled OR available_balance_cents IS NOT NULL) THEN
   RAISE EXCEPTION 'M40000 false money state or authenticated receipt';
 END IF;
 IF has_table_privilege('m40000_ci_reader','m40000_ci.review_packets','INSERT') OR
    has_table_privilege('m40000_ci_reader','m40000_ci.review_packets','UPDATE') OR
    has_table_privilege('m40000_ci_reader','m40000_ci.review_receipts','INSERT') OR
    has_table_privilege('m40000_ci_reader','m40000_ci.review_receipts','UPDATE') OR
    has_table_privilege('m40000_ci_reader','m40000_ci.review_receipts','DELETE') THEN
    RAISE EXCEPTION 'M40000 unexpected reader write grant';
 END IF;

 -- Another receipt on a 2-receipt packet must fail even with fresh ids.
 blocked:=false;
 BEGIN
  INSERT INTO m40000_ci.review_receipts(
   id,packet_id,scope,cashbox_key,journal_fingerprint,document_digest,
   policy_draft_fingerprint,reviewer_id,session_id,nonce,idempotency_key,action)
  VALUES(
   'f1111111-1111-4111-8111-111111111111',
   '11111111-1111-4111-8111-111111111111',
   'PLATFORM_MASTER','platform',repeat('a',64),repeat('b',64),repeat('c',64),
   '66666666-6666-4666-8666-666666666666',
   'f7111111-1111-4111-8111-111111111111',
   'f8111111-1111-4111-8111-111111111111',
   'f9111111-1111-4111-8111-111111111111','DOCUMENTARY_CHECK_PROPOSED');
 EXCEPTION WHEN check_violation THEN blocked:=true;
 END;
 IF NOT blocked THEN RAISE EXCEPTION 'M40000 third reviewer accepted'; END IF;

 -- Self-review rejected on the packet that has only one receipt.
 blocked:=false;
 BEGIN
  INSERT INTO m40000_ci.review_receipts(
   id,packet_id,scope,cashbox_key,journal_fingerprint,document_digest,
   policy_draft_fingerprint,reviewer_id,session_id,nonce,idempotency_key,action)
  VALUES(
   'f2222222-2222-4222-8222-222222222222',
   '33333333-3333-4333-8333-333333333333',
   'TENANT_ADMIN_OWN','tenant:bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',
   repeat('0',64),repeat('1',64),repeat('2',64),
   '88888888-8888-4888-8888-888888888888',
   'f7222222-2222-4222-8222-222222222222',
   'f8222222-2222-4222-8222-222222222222',
   'f9222222-2222-4222-8222-222222222222','DOCUMENTARY_CHECK_PROPOSED');
 EXCEPTION WHEN check_violation THEN blocked:=true;
 END;
 IF NOT blocked THEN RAISE EXCEPTION 'M40000 self-review accepted'; END IF;

 -- Failed idempotency key cannot be reused on another packet in same cashbox.
 blocked:=false;
 BEGIN
  INSERT INTO m40000_ci.review_receipts(
   id,packet_id,scope,cashbox_key,journal_fingerprint,document_digest,
   policy_draft_fingerprint,reviewer_id,session_id,nonce,idempotency_key,action)
  VALUES(
   'f3333333-3333-4333-8333-333333333333',
   '33333333-3333-4333-8333-333333333333',
   'TENANT_ADMIN_OWN','tenant:bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',
   repeat('0',64),repeat('1',64),repeat('2',64),
   '66666666-6666-4666-8666-666666666666',
   'f7333333-3333-4333-8333-333333333333',
   'f8333333-3333-4333-8333-333333333333',
   '95555555-5555-4555-8555-555555555555','DOCUMENTARY_CHECK_PROPOSED');
 EXCEPTION WHEN unique_violation THEN blocked:=true;
 END;
 IF NOT blocked THEN RAISE EXCEPTION 'M40000 idempotency replay accepted'; END IF;

 -- Reusing a session for a different reviewer in the same packet is prohibited.
 blocked:=false;
 BEGIN
  INSERT INTO m40000_ci.review_receipts(
   id,packet_id,scope,cashbox_key,journal_fingerprint,document_digest,
   policy_draft_fingerprint,reviewer_id,session_id,nonce,idempotency_key,action)
  VALUES(
   'f4444444-4444-4444-8444-444444444444',
   '33333333-3333-4333-8333-333333333333',
   'TENANT_ADMIN_OWN','tenant:bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',
   repeat('0',64),repeat('1',64),repeat('2',64),
   '66666666-6666-4666-8666-666666666666',
   '75555555-5555-4555-8555-555555555555',
   'f8444444-4444-4444-8444-444444444444',
   'f9444444-4444-4444-8444-444444444444','REQUEST_MORE_EVIDENCE');
 EXCEPTION WHEN unique_violation THEN blocked:=true;
 END;
 IF NOT blocked THEN RAISE EXCEPTION 'M40000 session replay accepted'; END IF;

 -- Cross-tenant or altered document digest cannot match the packet FK.
 blocked:=false;
 BEGIN
  INSERT INTO m40000_ci.review_receipts(
   id,packet_id,scope,cashbox_key,journal_fingerprint,document_digest,
   policy_draft_fingerprint,reviewer_id,session_id,nonce,idempotency_key,action)
  VALUES(
   'f5555555-5555-4555-8555-555555555555',
   '33333333-3333-4333-8333-333333333333',
   'TENANT_ADMIN_OWN','tenant:aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
   repeat('0',64),repeat('1',64),repeat('2',64),
   'f5555555-5555-4555-8555-555555555555',
   'f7555555-5555-4555-8555-555555555555',
   'f8555555-5555-4555-8555-555555555555',
   'f9555555-5555-4555-8555-555555555555','REQUEST_MORE_EVIDENCE');
 EXCEPTION WHEN foreign_key_violation THEN blocked:=true;
 END;
 IF NOT blocked THEN RAISE EXCEPTION 'M40000 cross-tenant document accepted'; END IF;

 -- An "approved" decision must fail even in a synthetic writer.
 blocked:=false;
 BEGIN
  INSERT INTO m40000_ci.review_receipts(
   id,packet_id,scope,cashbox_key,journal_fingerprint,document_digest,
   policy_draft_fingerprint,reviewer_id,session_id,nonce,idempotency_key,action)
  VALUES(
   'f6666666-6666-4666-8666-666666666666',
   '33333333-3333-4333-8333-333333333333',
   'TENANT_ADMIN_OWN','tenant:bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',
   repeat('0',64),repeat('1',64),repeat('2',64),
   'f6666666-6666-4666-8666-666666666666',
   'f7666666-6666-4666-8666-666666666666',
   'f8666666-6666-4666-8666-666666666666',
   'f9666666-6666-4666-8666-666666666666','APPROVED');
 EXCEPTION WHEN check_violation THEN blocked:=true;
 END;
 IF NOT blocked THEN RAISE EXCEPTION 'M40000 false approval accepted'; END IF;

 -- Even database-superuser modifications are rejected by table triggers
 -- under normal trigger execution (not a defense against superuser DDL).
 blocked:=false;
 BEGIN
  UPDATE m40000_ci.review_packets SET policy_approved=true
  WHERE id='11111111-1111-4111-8111-111111111111';
 EXCEPTION WHEN SQLSTATE '55000' THEN blocked:=true;
 END;
 IF NOT blocked THEN RAISE EXCEPTION 'M40000 mutable packet'; END IF;

 blocked:=false;
 BEGIN
  DELETE FROM m40000_ci.review_receipts
   WHERE id='41111111-1111-4111-8111-111111111111';
 EXCEPTION WHEN SQLSTATE '55000' THEN blocked:=true;
 END;
 IF NOT blocked THEN RAISE EXCEPTION 'M40000 mutable receipt'; END IF;
 IF (SELECT count(*) FROM m40000_ci.review_receipts)<>5 THEN
  RAISE EXCEPTION 'M40000 failed inserts changed receipt set';
 END IF;
END;
$$;

-- A synthetic reader can only see its own scoped receipts, never post.
SET LOCAL ROLE m40000_ci_reader;
SELECT set_config('frfinance.actor_role','MASTER',true);
SELECT set_config('frfinance.actor_tenant','',true);
DO $$
BEGIN
 IF (SELECT count(*) FROM m40000_ci.review_packets)<>1 OR
    (SELECT count(*) FROM m40000_ci.review_receipts)<>2 THEN
  RAISE EXCEPTION 'M40000 master RLS leak';
 END IF;
END;
$$;

SELECT set_config('frfinance.actor_role','TENANT_ADMIN',true);
SELECT set_config('frfinance.actor_tenant','aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',true);
DO $$
BEGIN
 IF (SELECT count(*) FROM m40000_ci.review_packets)<>1 OR
    (SELECT count(*) FROM m40000_ci.review_receipts)<>2 THEN
  RAISE EXCEPTION 'M40000 tenant A RLS leak';
 END IF;
END;
$$;

SELECT set_config('frfinance.actor_tenant','bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',true);
DO $$
BEGIN
 IF (SELECT count(*) FROM m40000_ci.review_packets)<>1 OR
    (SELECT count(*) FROM m40000_ci.review_receipts)<>1 THEN
  RAISE EXCEPTION 'M40000 tenant B RLS leak';
 END IF;
END;
$$;

SELECT set_config('frfinance.actor_role','TENANT_MEMBER',true);
DO $$
BEGIN
 IF (SELECT count(*) FROM m40000_ci.review_packets)<>0 OR
    (SELECT count(*) FROM m40000_ci.review_receipts)<>0 THEN
  RAISE EXCEPTION 'M40000 member RLS leak';
 END IF;
END;
$$;

ROLLBACK;
\echo M40000_POSTGRES18_SYNTHETIC_RECEIPTS=PASS
\echo M40000_IDEMPOTENCY_AND_MAX_TWO=PASS
\echo M40000_CROSS_TENANT_RLS=PASS
\echo M40000_REAL_AUTHENTICATION=NOT_ATTESTED
\echo M40000_REAL_APPROVAL=FALSE
\echo M40000_ORIGINAL_DATABASE_ACCESS=NONE
\echo M40000_LOCAL_MIGRATIONS=NONE
\echo M40000_PRODUCTION=BLOCKED
