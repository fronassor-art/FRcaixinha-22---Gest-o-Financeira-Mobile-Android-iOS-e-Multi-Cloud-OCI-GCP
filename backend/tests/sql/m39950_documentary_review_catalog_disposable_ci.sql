-- FR Finance M39950: CI-only documentary linkage experiment.
-- NOT A MIGRATION. No original FR Finance/FR Caixinha 2.2 database access.
-- No balances, real authentication, posting, provider, payout or webhooks.
\set ON_ERROR_STOP on
\if :{?CI_M39950_DISPOSABLE}
\else
\echo M39950_BLOCKED_MISSING_CI_DISPOSABLE_FLAG
\quit 2
\endif
SELECT CASE WHEN current_database()='frcaixinha_ci'
 AND inet_server_port()=5432
 AND session_user='postgres'
 AND current_setting('frfinance.m39950_ci',true)='DISPOSABLE_ONLY'
 THEN 'true' ELSE 'false' END AS m39950_disposable_identity
\gset
\if :m39950_disposable_identity
\else
\echo M39950_BLOCKED_WRONG_CLUSTER
\quit 2
\endif

BEGIN;

CREATE SCHEMA m39950_ci;
CREATE ROLE m39950_ci_reader NOLOGIN NOBYPASSRLS;

CREATE TABLE m39950_ci.documents (
 id uuid PRIMARY KEY,
 scope text NOT NULL CHECK(scope IN
   ('PLATFORM_MASTER','TENANT_ADMIN_OWN','TENANT_COLLECTIVE')),
 cashbox_key text NOT NULL,
 event_type text NOT NULL,
 evidence_reference text NOT NULL CHECK(length(evidence_reference) BETWEEN 6 AND 120),
 journal_fingerprint char(64) NOT NULL CHECK(journal_fingerprint ~ '^[0-9a-f]{64}$'),
 document_digest char(64) NOT NULL CHECK(document_digest ~ '^[0-9a-f]{64}$'),
 preparer_id uuid NOT NULL,
 proposed_reviewer_id uuid NOT NULL,
 state text NOT NULL DEFAULT 'DOCUMENTARY_CANDIDATE_NOT_AUTHENTICATED'
     CHECK(state='DOCUMENTARY_CANDIDATE_NOT_AUTHENTICATED'),
 document_authenticated boolean NOT NULL DEFAULT false CHECK(document_authenticated=false),
 reviewer_authenticated boolean NOT NULL DEFAULT false CHECK(reviewer_authenticated=false),
 provider_reconciled boolean NOT NULL DEFAULT false CHECK(provider_reconciled=false),
 payout_enabled boolean NOT NULL DEFAULT false CHECK(payout_enabled=false),
 journal_posted boolean NOT NULL DEFAULT false CHECK(journal_posted=false),
 available_balance_cents bigint CHECK(available_balance_cents IS NULL),
 created_at timestamptz NOT NULL DEFAULT now(),
 CONSTRAINT m39950_preparer_diff_reviewer CHECK(preparer_id <> proposed_reviewer_id),
 CONSTRAINT m39950_scope_key CHECK (
   (scope='PLATFORM_MASTER' AND cashbox_key='platform')
   OR (scope <> 'PLATFORM_MASTER' AND cashbox_key ~
    '^tenant:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')
 ),
 CONSTRAINT m39950_event_scope CHECK (
  (scope='PLATFORM_MASTER' AND event_type IN
    ('SAAS_SETTLEMENT','PLATFORM_OPERATING_EXPENSE'))
  OR (scope='TENANT_ADMIN_OWN' AND event_type IN
    ('ADMIN_CLOSING_REMUNERATION','ADMIN_OWN_EXPENSE'))
  OR (scope='TENANT_COLLECTIVE' AND event_type IN
    ('MEMBER_CONTRIBUTION','TENANT_LOAN_REPAYMENT','TENANT_OPERATING_EXPENSE'))
 ),
 UNIQUE(scope,cashbox_key,evidence_reference),
 UNIQUE(id,scope,cashbox_key,journal_fingerprint,document_digest)
);

CREATE TABLE m39950_ci.review_claims (
 id uuid PRIMARY KEY,
 document_id uuid NOT NULL,
 scope text NOT NULL,
 cashbox_key text NOT NULL,
 journal_fingerprint char(64) NOT NULL,
 document_digest char(64) NOT NULL,
 reviewer_id uuid NOT NULL,
 claimed_at timestamptz NOT NULL,
 decision text NOT NULL CHECK(decision IN (
    'DOCUMENTARY_CHECK_PROPOSED','REQUEST_MORE_EVIDENCE')),
 note_code text NOT NULL CHECK(note_code IN (
    'SHAPE_REVIEW_PENDING','PROVIDER_AUTHENTICITY_PENDING',
    'POLICY_AND_CYCLE_PENDING','EXPENSE_AUTHENTICITY_PENDING')),
 state text NOT NULL DEFAULT 'REVIEW_CLAIM_UNVERIFIED'
     CHECK(state='REVIEW_CLAIM_UNVERIFIED'),
 identity_authenticated boolean NOT NULL DEFAULT false
     CHECK(identity_authenticated=false),
 approval_verified boolean NOT NULL DEFAULT false
     CHECK(approval_verified=false),
 payout_authorized boolean NOT NULL DEFAULT false
     CHECK(payout_authorized=false),
 FOREIGN KEY(document_id,scope,cashbox_key,journal_fingerprint,document_digest)
   REFERENCES m39950_ci.documents(
     id,scope,cashbox_key,journal_fingerprint,document_digest),
 UNIQUE(document_id,reviewer_id)
);

CREATE FUNCTION m39950_ci.claim_no_preparer() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog,pg_temp
AS $$
DECLARE person uuid;
BEGIN
 SELECT preparer_id INTO person FROM m39950_ci.documents WHERE id=NEW.document_id;
 IF NEW.reviewer_id=person THEN
   RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='M39950_SELF_REVIEW_FORBIDDEN';
 END IF;
 RETURN NEW;
END;
$$;
CREATE TRIGGER m39950_claim_no_preparer
 BEFORE INSERT ON m39950_ci.review_claims FOR EACH ROW
 EXECUTE FUNCTION m39950_ci.claim_no_preparer();

CREATE FUNCTION m39950_ci.deny_mutation() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog,pg_temp
AS $$
BEGIN
 RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='M39950_APPEND_ONLY';
END;
$$;
CREATE TRIGGER m39950_documents_immutable
 BEFORE UPDATE OR DELETE ON m39950_ci.documents
 FOR EACH ROW EXECUTE FUNCTION m39950_ci.deny_mutation();
CREATE TRIGGER m39950_claims_immutable
 BEFORE UPDATE OR DELETE ON m39950_ci.review_claims
 FOR EACH ROW EXECUTE FUNCTION m39950_ci.deny_mutation();

ALTER TABLE m39950_ci.documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE m39950_ci.documents FORCE ROW LEVEL SECURITY;
ALTER TABLE m39950_ci.review_claims ENABLE ROW LEVEL SECURITY;
ALTER TABLE m39950_ci.review_claims FORCE ROW LEVEL SECURITY;

CREATE POLICY m39950_document_reader ON m39950_ci.documents
 FOR SELECT TO m39950_ci_reader USING (
  (scope='PLATFORM_MASTER'
   AND current_setting('frfinance.actor_role',true)='MASTER'
   AND COALESCE(current_setting('frfinance.actor_tenant',true),'')='')
  OR (scope IN ('TENANT_ADMIN_OWN','TENANT_COLLECTIVE')
   AND current_setting('frfinance.actor_role',true)='TENANT_ADMIN'
   AND cashbox_key='tenant:' ||
       COALESCE(NULLIF(current_setting('frfinance.actor_tenant',true),''),'NONE'))
 );
CREATE POLICY m39950_claim_reader ON m39950_ci.review_claims
 FOR SELECT TO m39950_ci_reader USING (
   EXISTS (SELECT 1 FROM m39950_ci.documents d
    WHERE d.id=document_id AND d.scope=review_claims.scope
    AND d.cashbox_key=review_claims.cashbox_key
    AND d.journal_fingerprint=review_claims.journal_fingerprint
    AND d.document_digest=review_claims.document_digest)
 );
GRANT USAGE ON SCHEMA m39950_ci TO m39950_ci_reader;
GRANT SELECT ON m39950_ci.documents,m39950_ci.review_claims TO m39950_ci_reader;

INSERT INTO m39950_ci.documents (
 id,scope,cashbox_key,event_type,evidence_reference,
 journal_fingerprint,document_digest,preparer_id,proposed_reviewer_id)
VALUES
 ('11111111-1111-4111-8111-111111111111','PLATFORM_MASTER','platform',
  'SAAS_SETTLEMENT','synthetic-platform-proof-001',
  repeat('a',64),repeat('b',64),
  '88888888-8888-4888-8888-888888888888','22222222-2222-4222-8222-222222222222'),
 ('33333333-3333-4333-8333-333333333333','TENANT_ADMIN_OWN',
  'tenant:aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
  'ADMIN_CLOSING_REMUNERATION','synthetic-admin-own-proof-001',
  repeat('c',64),repeat('d',64),
  '88888888-8888-4888-8888-888888888888','22222222-2222-4222-8222-222222222222'),
 ('44444444-4444-4444-8444-444444444444','TENANT_COLLECTIVE',
  'tenant:aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
  'MEMBER_CONTRIBUTION','synthetic-tenant-a-proof-001',
  repeat('e',64),repeat('f',64),
  '88888888-8888-4888-8888-888888888888','22222222-2222-4222-8222-222222222222'),
 ('55555555-5555-4555-8555-555555555555','TENANT_COLLECTIVE',
  'tenant:bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',
  'MEMBER_CONTRIBUTION','synthetic-tenant-b-proof-001',
  repeat('0',64),repeat('1',64),
  '88888888-8888-4888-8888-888888888888','22222222-2222-4222-8222-222222222222');

INSERT INTO m39950_ci.review_claims (
 id,document_id,scope,cashbox_key,journal_fingerprint,document_digest,
 reviewer_id,claimed_at,decision,note_code
)
SELECT gen_random_uuid(),d.id,d.scope,d.cashbox_key,
 d.journal_fingerprint,d.document_digest,v.reviewer_id,
 '2026-11-15T12:00:00+00:00'::timestamptz +
    v.delay_seconds*interval '1 second',
 v.decision,v.note_code
FROM m39950_ci.documents d CROSS JOIN (
 VALUES
  ('22222222-2222-4222-8222-222222222222'::uuid,0,
   'DOCUMENTARY_CHECK_PROPOSED','SHAPE_REVIEW_PENDING'),
  ('66666666-6666-4666-8666-666666666666'::uuid,60,
   'REQUEST_MORE_EVIDENCE','PROVIDER_AUTHENTICITY_PENDING')
) AS v(reviewer_id,delay_seconds,decision,note_code);

DO $$
DECLARE is_blocked boolean;
BEGIN
 IF (SELECT count(*) FROM m39950_ci.documents)<>4 OR
    (SELECT count(*) FROM m39950_ci.review_claims)<>8 THEN
   RAISE EXCEPTION 'M39950 missing synthetic fixtures';
 END IF;
 IF EXISTS(SELECT 1 FROM m39950_ci.documents
    WHERE document_authenticated OR reviewer_authenticated OR
          provider_reconciled OR payout_enabled OR journal_posted OR
          available_balance_cents IS NOT NULL) THEN
    RAISE EXCEPTION 'M39950 false provider money state';
 END IF;
 IF has_table_privilege('m39950_ci_reader','m39950_ci.documents','INSERT')
 OR has_table_privilege('m39950_ci_reader','m39950_ci.documents','DELETE')
 OR has_table_privilege('m39950_ci_reader','m39950_ci.review_claims','UPDATE')
 OR has_table_privilege('m39950_ci_reader','m39950_ci.review_claims','INSERT') THEN
  RAISE EXCEPTION 'M39950 unexpected app write grant';
 END IF;

 is_blocked:=false;
 BEGIN
  INSERT INTO m39950_ci.documents(
    id,scope,cashbox_key,event_type,evidence_reference,
    journal_fingerprint,document_digest,preparer_id,proposed_reviewer_id)
  VALUES(
    '99999999-9999-4999-8999-999999999999','PLATFORM_MASTER','platform',
    'SAAS_SETTLEMENT','synthetic-platform-proof-001',
    repeat('a',64),repeat('b',64),
    '88888888-8888-4888-8888-888888888888','22222222-2222-4222-8222-222222222222');
 EXCEPTION WHEN unique_violation THEN is_blocked:=true;
 END;
 IF NOT is_blocked THEN RAISE EXCEPTION 'M39950 replay accepted'; END IF;

 is_blocked:=false;
 BEGIN
  INSERT INTO m39950_ci.review_claims (
   id,document_id,scope,cashbox_key,journal_fingerprint,document_digest,
   reviewer_id,claimed_at,decision,note_code)
  VALUES (
   gen_random_uuid(),'44444444-4444-4444-8444-444444444444',
   'TENANT_COLLECTIVE','tenant:bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',
   repeat('e',64),repeat('f',64),
   '77777777-7777-4777-8777-777777777777',now(),
   'DOCUMENTARY_CHECK_PROPOSED','SHAPE_REVIEW_PENDING');
 EXCEPTION WHEN foreign_key_violation THEN is_blocked:=true;
 END;
 IF NOT is_blocked THEN RAISE EXCEPTION 'M39950 cross-tenant FK accepted'; END IF;

 is_blocked:=false;
 BEGIN
  INSERT INTO m39950_ci.review_claims (
   id,document_id,scope,cashbox_key,journal_fingerprint,document_digest,
   reviewer_id,claimed_at,decision,note_code)
  VALUES (
   gen_random_uuid(),'11111111-1111-4111-8111-111111111111',
   'PLATFORM_MASTER','platform',
   repeat('a',64),repeat('b',64),
   '88888888-8888-4888-8888-888888888888',now(),
   'DOCUMENTARY_CHECK_PROPOSED','SHAPE_REVIEW_PENDING');
 EXCEPTION WHEN check_violation THEN is_blocked:=true;
 END;
 IF NOT is_blocked THEN RAISE EXCEPTION 'M39950 self-review accepted'; END IF;

 is_blocked:=false;
 BEGIN
  INSERT INTO m39950_ci.review_claims (
   id,document_id,scope,cashbox_key,journal_fingerprint,document_digest,
   reviewer_id,claimed_at,decision,note_code)
  VALUES (
   gen_random_uuid(),'11111111-1111-4111-8111-111111111111',
   'PLATFORM_MASTER','platform',
   repeat('a',64),repeat('b',64),
   '22222222-2222-4222-8222-222222222222',now(),
   'DOCUMENTARY_CHECK_PROPOSED','SHAPE_REVIEW_PENDING');
 EXCEPTION WHEN unique_violation THEN is_blocked:=true;
 END;
 IF NOT is_blocked THEN RAISE EXCEPTION 'M39950 duplicate reviewer accepted'; END IF;

 is_blocked:=false;
 BEGIN
  INSERT INTO m39950_ci.review_claims (
   id,document_id,scope,cashbox_key,journal_fingerprint,document_digest,
   reviewer_id,claimed_at,decision,note_code)
  VALUES (
   gen_random_uuid(),'11111111-1111-4111-8111-111111111111',
   'PLATFORM_MASTER','platform',
   repeat('a',64),repeat('b',64),
   '77777777-7777-4777-8777-777777777777',now(),
   'APPROVED','SHAPE_REVIEW_PENDING');
 EXCEPTION WHEN check_violation THEN is_blocked:=true;
 END;
 IF NOT is_blocked THEN RAISE EXCEPTION 'M39950 false approval accepted'; END IF;

 is_blocked:=false;
 BEGIN
  UPDATE m39950_ci.documents SET evidence_reference='modified'
    WHERE id='11111111-1111-4111-8111-111111111111';
 EXCEPTION WHEN SQLSTATE '55000' THEN is_blocked:=true;
 END;
 IF NOT is_blocked THEN RAISE EXCEPTION 'M39950 mutable document'; END IF;

 is_blocked:=false;
 BEGIN
  DELETE FROM m39950_ci.review_claims
    WHERE document_id='11111111-1111-4111-8111-111111111111';
 EXCEPTION WHEN SQLSTATE '55000' THEN is_blocked:=true;
 END;
 IF NOT is_blocked THEN RAISE EXCEPTION 'M39950 mutable review'; END IF;
END;
$$;

SET LOCAL ROLE m39950_ci_reader;
SELECT set_config('frfinance.actor_role','MASTER',true);
SELECT set_config('frfinance.actor_tenant','',true);
DO $$
BEGIN
 IF (SELECT count(*) FROM m39950_ci.documents)<>1 OR
    (SELECT count(*) FROM m39950_ci.review_claims)<>2 THEN
  RAISE EXCEPTION 'M39950 master RLS leak';
 END IF;
END;
$$;
SELECT set_config('frfinance.actor_role','TENANT_ADMIN',true);
SELECT set_config('frfinance.actor_tenant','aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',true);
DO $$
BEGIN
 IF (SELECT count(*) FROM m39950_ci.documents)<>2 OR
    (SELECT count(*) FROM m39950_ci.review_claims)<>4 THEN
  RAISE EXCEPTION 'M39950 admin tenant A RLS leak';
 END IF;
END;
$$;
SELECT set_config('frfinance.actor_tenant','bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',true);
DO $$
BEGIN
 IF (SELECT count(*) FROM m39950_ci.documents)<>1 OR
    (SELECT count(*) FROM m39950_ci.review_claims)<>2 THEN
  RAISE EXCEPTION 'M39950 admin tenant B RLS leak';
 END IF;
END;
$$;
SELECT set_config('frfinance.actor_role','TENANT_MEMBER',true);
DO $$
BEGIN
 IF (SELECT count(*) FROM m39950_ci.documents)<>0 OR
    (SELECT count(*) FROM m39950_ci.review_claims)<>0 THEN
  RAISE EXCEPTION 'M39950 member exclusive RLS leak';
 END IF;
END;
$$;

ROLLBACK;
\echo M39950_DISPOSABLE_EVIDENCE_CATALOG=PASS
\echo M39950_APPEND_ONLY_AND_REPLAY=PASS
\echo M39950_CROSS_TENANT_REVIEW_FK=PASS
\echo M39950_RLS_PROOF_ONLY=PASS
\echo M39950_ORIGINAL_DB_ACCESS=NONE
\echo M39950_PRODUCTION=BLOCKED
