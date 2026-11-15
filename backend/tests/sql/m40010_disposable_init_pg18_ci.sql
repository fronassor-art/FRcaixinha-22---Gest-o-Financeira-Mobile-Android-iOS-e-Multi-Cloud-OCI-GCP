-- M40010 synthetic schema in GitHub Actions PostgreSQL18 ONLY.
-- Durable solely within disposable service. NOT A REPO MIGRATION.
\ir m40010_disposable_guard.psql
BEGIN;

CREATE SCHEMA m40010_ci;
CREATE ROLE m40010_m_a NOLOGIN NOBYPASSRLS;
CREATE ROLE m40010_m_b NOLOGIN NOBYPASSRLS;
CREATE ROLE m40010_a_a NOLOGIN NOBYPASSRLS;
CREATE ROLE m40010_a_b NOLOGIN NOBYPASSRLS;
CREATE ROLE m40010_b_a NOLOGIN NOBYPASSRLS;
CREATE ROLE m40010_b_b NOLOGIN NOBYPASSRLS;

CREATE TABLE m40010_ci.review_packets(
 id uuid PRIMARY KEY,
 scope text NOT NULL CHECK(scope IN ('PLATFORM_MASTER','TENANT_ADMIN_OWN')),
 cashbox_key text NOT NULL,
 policy_fingerprint char(64) NOT NULL CHECK(policy_fingerprint ~ '^[0-9a-f]{64}$'),
 evidence_digest char(64) NOT NULL CHECK(evidence_digest ~ '^[0-9a-f]{64}$'),
 preparer_id uuid NOT NULL,
 state text NOT NULL DEFAULT 'UNAUTHENTICATED_DOCUMENT_CANDIDATE'
    CHECK(state='UNAUTHENTICATED_DOCUMENT_CANDIDATE'),
 policy_ratified boolean NOT NULL DEFAULT false CHECK(policy_ratified=false),
 journal_posted boolean NOT NULL DEFAULT false CHECK(journal_posted=false),
 payout_enabled boolean NOT NULL DEFAULT false CHECK(payout_enabled=false),
 available_balance_cents bigint CHECK(available_balance_cents IS NULL),
 CHECK(
  (scope='PLATFORM_MASTER' AND cashbox_key='platform')
  OR (scope='TENANT_ADMIN_OWN' AND cashbox_key ~
   '^tenant:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')
 ),
 UNIQUE(id,scope,cashbox_key,policy_fingerprint)
);

CREATE TABLE m40010_ci.synthetic_role_bindings(
 packet_id uuid NOT NULL REFERENCES m40010_ci.review_packets(id),
 db_role name NOT NULL,
 reviewer_id uuid NOT NULL,
 slot integer NOT NULL CHECK(slot IN (1,2)),
 PRIMARY KEY(packet_id,db_role),
 UNIQUE(packet_id,reviewer_id),
 UNIQUE(packet_id,slot),
 UNIQUE(packet_id,db_role,reviewer_id,slot)
);

CREATE TABLE m40010_ci.review_receipts(
 receipt_id uuid PRIMARY KEY,
 packet_id uuid NOT NULL,
 scope text NOT NULL,
 cashbox_key text NOT NULL,
 policy_fingerprint char(64) NOT NULL,
 slot integer NOT NULL CHECK(slot IN (1,2)),
 actor_db_role name NOT NULL,
 reviewer_id uuid NOT NULL,
 claimed_session_id uuid NOT NULL,
 nonce uuid NOT NULL,
 idempotency_key uuid NOT NULL,
 action text NOT NULL CHECK(action IN (
  'DOCUMENTARY_CHECK_PROPOSED','REQUEST_MORE_EVIDENCE')),
 recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 state text NOT NULL DEFAULT 'DB_ROLE_SIMULATED_NOT_AUTHENTICATED'
    CHECK(state='DB_ROLE_SIMULATED_NOT_AUTHENTICATED'),
 human_identity_verified boolean NOT NULL DEFAULT false CHECK(human_identity_verified=false),
 reviewer_mandate_ratified boolean NOT NULL DEFAULT false CHECK(reviewer_mandate_ratified=false),
 document_authenticated boolean NOT NULL DEFAULT false CHECK(document_authenticated=false),
 approved boolean NOT NULL DEFAULT false CHECK(approved=false),
 provider_reconciled boolean NOT NULL DEFAULT false CHECK(provider_reconciled=false),
 journal_posted boolean NOT NULL DEFAULT false CHECK(journal_posted=false),
 payout_enabled boolean NOT NULL DEFAULT false CHECK(payout_enabled=false),
 available_balance_cents bigint CHECK(available_balance_cents IS NULL),
 CONSTRAINT m40010_packet_fk FOREIGN KEY(packet_id,scope,cashbox_key,policy_fingerprint)
  REFERENCES m40010_ci.review_packets(id,scope,cashbox_key,policy_fingerprint),
 CONSTRAINT m40010_bound_actor_fk FOREIGN KEY(packet_id,actor_db_role,reviewer_id,slot)
  REFERENCES m40010_ci.synthetic_role_bindings(packet_id,db_role,reviewer_id,slot),
 CONSTRAINT m40010_unique_slot UNIQUE(packet_id,slot),
 CONSTRAINT m40010_unique_reviewer UNIQUE(packet_id,reviewer_id),
 CONSTRAINT m40010_unique_session UNIQUE(packet_id,claimed_session_id),
 CONSTRAINT m40010_unique_nonce UNIQUE(scope,cashbox_key,nonce),
 CONSTRAINT m40010_unique_idem UNIQUE(scope,cashbox_key,idempotency_key)
);

CREATE FUNCTION m40010_ci.reject_changes() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog,pg_temp AS $$
BEGIN
 RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='M40010_APPEND_ONLY';
END;
$$;
CREATE TRIGGER m40010_packets_immutable BEFORE UPDATE OR DELETE
 ON m40010_ci.review_packets FOR EACH ROW
 EXECUTE FUNCTION m40010_ci.reject_changes();
CREATE TRIGGER m40010_bindings_immutable BEFORE UPDATE OR DELETE
 ON m40010_ci.synthetic_role_bindings FOR EACH ROW
 EXECUTE FUNCTION m40010_ci.reject_changes();
CREATE TRIGGER m40010_receipts_immutable BEFORE UPDATE OR DELETE
 ON m40010_ci.review_receipts FOR EACH ROW
 EXECUTE FUNCTION m40010_ci.reject_changes();

ALTER TABLE m40010_ci.review_packets ENABLE ROW LEVEL SECURITY;
ALTER TABLE m40010_ci.review_packets FORCE ROW LEVEL SECURITY;
ALTER TABLE m40010_ci.synthetic_role_bindings ENABLE ROW LEVEL SECURITY;
ALTER TABLE m40010_ci.synthetic_role_bindings FORCE ROW LEVEL SECURITY;
ALTER TABLE m40010_ci.review_receipts ENABLE ROW LEVEL SECURITY;
ALTER TABLE m40010_ci.review_receipts FORCE ROW LEVEL SECURITY;

-- Unlike client-provided role GUCs, the test binds a synthetic actor to
-- CURRENT_USER derived from SET ROLE. This is NOT real end-user login.
CREATE POLICY m40010_bindings_read ON m40010_ci.synthetic_role_bindings
 FOR SELECT USING(db_role=current_user);
CREATE POLICY m40010_packets_read ON m40010_ci.review_packets
 FOR SELECT USING(EXISTS(
   SELECT 1 FROM m40010_ci.synthetic_role_bindings b
   WHERE b.packet_id=id AND b.db_role=current_user));
CREATE POLICY m40010_receipts_read ON m40010_ci.review_receipts
 FOR SELECT USING(actor_db_role=current_user);
CREATE POLICY m40010_receipts_insert ON m40010_ci.review_receipts
 FOR INSERT WITH CHECK (
  actor_db_role=current_user AND EXISTS(
    SELECT 1 FROM m40010_ci.synthetic_role_bindings b
    WHERE b.packet_id=review_receipts.packet_id
      AND b.db_role=current_user
      AND b.reviewer_id=review_receipts.reviewer_id
      AND b.slot=review_receipts.slot)
 );

GRANT USAGE ON SCHEMA m40010_ci TO
 m40010_m_a,m40010_m_b,m40010_a_a,m40010_a_b,m40010_b_a,m40010_b_b;
GRANT SELECT ON m40010_ci.review_packets,m40010_ci.synthetic_role_bindings,
 m40010_ci.review_receipts TO
 m40010_m_a,m40010_m_b,m40010_a_a,m40010_a_b,m40010_b_a,m40010_b_b;
GRANT INSERT(receipt_id,packet_id,scope,cashbox_key,policy_fingerprint,
 slot,actor_db_role,reviewer_id,claimed_session_id,nonce,idempotency_key,action)
 ON m40010_ci.review_receipts TO
 m40010_m_a,m40010_m_b,m40010_a_a,m40010_a_b,m40010_b_a,m40010_b_b;

INSERT INTO m40010_ci.review_packets(id,scope,cashbox_key,policy_fingerprint,
 evidence_digest,preparer_id) VALUES
 ('11111111-1111-4111-8111-111111111111','PLATFORM_MASTER','platform',
  repeat('a',64),repeat('b',64),'88888888-8888-4888-8888-888888888888'),
 ('22222222-2222-4222-8222-222222222222','TENANT_ADMIN_OWN',
  'tenant:aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',repeat('c',64),repeat('d',64),
  '88888888-8888-4888-8888-888888888888'),
 ('33333333-3333-4333-8333-333333333333','TENANT_ADMIN_OWN',
  'tenant:bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',repeat('e',64),repeat('f',64),
  '88888888-8888-4888-8888-888888888888'),
 ('44444444-4444-4444-8444-444444444444','TENANT_ADMIN_OWN',
  'tenant:aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',repeat('1',64),repeat('2',64),
  '88888888-8888-4888-8888-888888888888');

INSERT INTO m40010_ci.synthetic_role_bindings(packet_id,db_role,reviewer_id,slot)
VALUES
 ('11111111-1111-4111-8111-111111111111','m40010_m_a',
  '41111111-1111-4111-8111-111111111111',1),
 ('11111111-1111-4111-8111-111111111111','m40010_m_b',
  '42222222-2222-4222-8222-222222222222',2),
 ('22222222-2222-4222-8222-222222222222','m40010_a_a',
  '43333333-3333-4333-8333-333333333333',1),
 ('22222222-2222-4222-8222-222222222222','m40010_a_b',
  '44444444-4444-4444-8444-444444444444',2),
 ('33333333-3333-4333-8333-333333333333','m40010_b_a',
  '45555555-5555-4555-8555-555555555555',1),
 ('33333333-3333-4333-8333-333333333333','m40010_b_b',
  '46666666-6666-4666-8666-666666666666',2),
 ('44444444-4444-4444-8444-444444444444','m40010_a_a',
  '43333333-3333-4333-8333-333333333333',1),
 ('44444444-4444-4444-8444-444444444444','m40010_a_b',
  '44444444-4444-4444-8444-444444444444',2);

COMMIT;
\echo M40010_DISPOSABLE_SCHEMA_COMMITTED=PASS
