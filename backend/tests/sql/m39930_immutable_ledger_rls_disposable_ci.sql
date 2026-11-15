-- FR Finance M39930 — CI ONLY, disposable PostgreSQL 18 / frcaixinha_ci.
-- EXPERIMENTAL transaction-scoped schema, NOT a migration for Termux.
-- No payment provider, network callback, or original cluster is contacted.
\set ON_ERROR_STOP on
\if :{?CI_M39930_DISPOSABLE}
\else
\echo M39930_BLOCKED_NO_CI_FLAG
\quit 2
\endif
SELECT CASE WHEN current_database()='frcaixinha_ci'
  AND inet_server_port()=5432 AND session_user='postgres'
  AND current_setting('frfinance.m39930_ci',true)='DISPOSABLE_ONLY'
  THEN 'true' ELSE 'false' END AS disposable_ok
\gset
\if :disposable_ok
\else
\echo M39930_BLOCKED_WRONG_CLUSTER_OR_DB
\quit 2
\endif

BEGIN;
CREATE SCHEMA m39930_ci;
CREATE ROLE m39930_ci_reader NOLOGIN NOBYPASSRLS;

CREATE TABLE m39930_ci.journals (
  id uuid PRIMARY KEY,
  scope text NOT NULL CHECK (scope IN
   ('PLATFORM_MASTER','TENANT_ADMIN_OWN','TENANT_COLLECTIVE')),
  cashbox_key text NOT NULL,
  event_type text NOT NULL,
  evidence_reference text NOT NULL CHECK(length(evidence_reference) BETWEEN 6 AND 120),
  state text NOT NULL DEFAULT 'STRUCTURAL_PREVIEW_NO_POSTING'
    CHECK(state='STRUCTURAL_PREVIEW_NO_POSTING'),
  posted boolean NOT NULL DEFAULT false CHECK(posted=false),
  provider_reconciled boolean NOT NULL DEFAULT false CHECK(provider_reconciled=false),
  payout_enabled boolean NOT NULL DEFAULT false CHECK(payout_enabled=false),
  available_balance_cents bigint CHECK(available_balance_cents IS NULL),
  recorded_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT m39930_scope_key CHECK(
   (scope='PLATFORM_MASTER' AND cashbox_key='platform')
   OR (scope IN ('TENANT_ADMIN_OWN','TENANT_COLLECTIVE') AND cashbox_key ~
    '^tenant:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')
  ),
  CONSTRAINT m39930_event_scope CHECK(
   (scope='PLATFORM_MASTER' AND event_type IN
    ('SAAS_SETTLEMENT','PLATFORM_OPERATING_EXPENSE'))
   OR (scope='TENANT_ADMIN_OWN' AND event_type IN
    ('ADMIN_CLOSING_REMUNERATION','ADMIN_OWN_EXPENSE'))
   OR (scope='TENANT_COLLECTIVE' AND event_type IN
    ('MEMBER_CONTRIBUTION','TENANT_LOAN_REPAYMENT','TENANT_OPERATING_EXPENSE'))
  ),
  UNIQUE(id,scope,cashbox_key),
  UNIQUE(scope,cashbox_key,evidence_reference)
);

CREATE TABLE m39930_ci.entries (
  id uuid PRIMARY KEY,
  journal_id uuid NOT NULL,
  scope text NOT NULL,
  cashbox_key text NOT NULL,
  account_code text NOT NULL CHECK(account_code ~ '^[A-Z0-9_]{4,40}$'),
  side text NOT NULL CHECK(side IN ('DR','CR')),
  amount_cents bigint NOT NULL CHECK(amount_cents BETWEEN 1 AND 999999999999),
  FOREIGN KEY(journal_id,scope,cashbox_key)
    REFERENCES m39930_ci.journals(id,scope,cashbox_key),
  CONSTRAINT m39930_account_namespace CHECK (
   (scope='PLATFORM_MASTER' AND left(account_code,3)='PM_')
   OR (scope='TENANT_ADMIN_OWN' AND left(account_code,3)='TA_')
   OR (scope='TENANT_COLLECTIVE' AND left(account_code,3)='TC_')
  ),
  UNIQUE(journal_id,account_code,side)
);

-- All table owners also subject to RLS, even for synthetic scope tests.
ALTER TABLE m39930_ci.journals ENABLE ROW LEVEL SECURITY;
ALTER TABLE m39930_ci.journals FORCE ROW LEVEL SECURITY;
ALTER TABLE m39930_ci.entries ENABLE ROW LEVEL SECURITY;
ALTER TABLE m39930_ci.entries FORCE ROW LEVEL SECURITY;

CREATE POLICY m39930_journal_reader ON m39930_ci.journals
  FOR SELECT TO m39930_ci_reader USING (
    (scope='PLATFORM_MASTER'
      AND current_setting('frfinance.actor_role',true)='MASTER'
      AND COALESCE(current_setting('frfinance.actor_tenant',true),'')='')
    OR (
      scope IN ('TENANT_ADMIN_OWN','TENANT_COLLECTIVE')
      AND current_setting('frfinance.actor_role',true)='TENANT_ADMIN'
      AND cashbox_key='tenant:' ||
        COALESCE(NULLIF(current_setting('frfinance.actor_tenant',true),''),'NONE')
    )
  );
CREATE POLICY m39930_entry_reader ON m39930_ci.entries
  FOR SELECT TO m39930_ci_reader USING (
    EXISTS (SELECT 1 FROM m39930_ci.journals j
      WHERE j.id=journal_id AND j.scope=entries.scope
      AND j.cashbox_key=entries.cashbox_key)
  );
GRANT USAGE ON SCHEMA m39930_ci TO m39930_ci_reader;
GRANT SELECT ON m39930_ci.journals,m39930_ci.entries TO m39930_ci_reader;

-- Synthetic append-only guard. A future production design must additionally
-- prevent ownership bypasses, privileged DDL and deletion of provenance.
CREATE FUNCTION m39930_ci.reject_changes() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog,pg_temp
AS $$
BEGIN
  RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='M39930_APPEND_ONLY';
END;
$$;
CREATE TRIGGER m39930_journal_immutable BEFORE UPDATE OR DELETE
 ON m39930_ci.journals FOR EACH ROW EXECUTE FUNCTION m39930_ci.reject_changes();
CREATE TRIGGER m39930_entry_immutable BEFORE UPDATE OR DELETE
 ON m39930_ci.entries FOR EACH ROW EXECUTE FUNCTION m39930_ci.reject_changes();

-- Deferred statement-coherent DR/CR check, evaluated at SET CONSTRAINTS or COMMIT.
CREATE FUNCTION m39930_ci.enforce_balance() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog,pg_temp
AS $$
DECLARE jid uuid; n integer; debit bigint; credit bigint;
BEGIN
  IF TG_TABLE_NAME='journals' THEN
    jid := NEW.id;
  ELSE
    jid := NEW.journal_id;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM m39930_ci.journals WHERE id=jid)
    THEN RETURN NULL;
  END IF;
  SELECT count(*),
    COALESCE(sum(amount_cents) FILTER(WHERE side='DR'),0),
    COALESCE(sum(amount_cents) FILTER(WHERE side='CR'),0)
    INTO n,debit,credit FROM m39930_ci.entries WHERE journal_id=jid;
  IF n<2 OR debit<>credit THEN
    RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='M39930_UNBALANCED_JOURNAL';
  END IF;
  RETURN NULL;
END;
$$;
CREATE CONSTRAINT TRIGGER m39930_journal_balance
 AFTER INSERT ON m39930_ci.journals DEFERRABLE INITIALLY DEFERRED
 FOR EACH ROW EXECUTE FUNCTION m39930_ci.enforce_balance();
CREATE CONSTRAINT TRIGGER m39930_entry_balance
 AFTER INSERT ON m39930_ci.entries DEFERRABLE INITIALLY DEFERRED
 FOR EACH ROW EXECUTE FUNCTION m39930_ci.enforce_balance();

INSERT INTO m39930_ci.journals
 (id,scope,cashbox_key,event_type,evidence_reference) VALUES
 ('11111111-1111-4111-8111-111111111111','PLATFORM_MASTER','platform',
  'SAAS_SETTLEMENT','synthetic-saas-001'),
 ('22222222-2222-4222-8222-222222222222','TENANT_ADMIN_OWN',
  'tenant:aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
  'ADMIN_CLOSING_REMUNERATION','synthetic-admin-001'),
 ('33333333-3333-4333-8333-333333333333','TENANT_COLLECTIVE',
  'tenant:aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
  'MEMBER_CONTRIBUTION','synthetic-member-001'),
 ('44444444-4444-4444-8444-444444444444','TENANT_COLLECTIVE',
  'tenant:bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',
  'TENANT_LOAN_REPAYMENT','synthetic-other-tenant-001');

INSERT INTO m39930_ci.entries
 (id,journal_id,scope,cashbox_key,account_code,side,amount_cents) VALUES
 ('11111111-aaaa-4111-8111-111111111111','11111111-1111-4111-8111-111111111111','PLATFORM_MASTER','platform','PM_RECEIVABLE','DR',500),
 ('11111111-bbbb-4111-8111-111111111111','11111111-1111-4111-8111-111111111111','PLATFORM_MASTER','platform','PM_REVENUE','CR',500),
 ('22222222-aaaa-4222-8222-222222222222','22222222-2222-4222-8222-222222222222','TENANT_ADMIN_OWN','tenant:aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa','TA_RECEIVABLE','DR',150),
 ('22222222-bbbb-4222-8222-222222222222','22222222-2222-4222-8222-222222222222','TENANT_ADMIN_OWN','tenant:aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa','TA_PROVISION','CR',150),
 ('33333333-aaaa-4333-8333-333333333333','33333333-3333-4333-8333-333333333333','TENANT_COLLECTIVE','tenant:aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa','TC_RECEIVABLE','DR',850),
 ('33333333-bbbb-4333-8333-333333333333','33333333-3333-4333-8333-333333333333','TENANT_COLLECTIVE','tenant:aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa','TC_CAPITAL','CR',850),
 ('44444444-aaaa-4444-8444-444444444444','44444444-4444-4444-8444-444444444444','TENANT_COLLECTIVE','tenant:bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb','TC_RECEIVABLE','DR',900),
 ('44444444-bbbb-4444-8444-444444444444','44444444-4444-4444-8444-444444444444','TENANT_COLLECTIVE','tenant:bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb','TC_CAPITAL','CR',900);

-- Prove all four inserted examples have valid DR/CR before reading them.
SET CONSTRAINTS ALL IMMEDIATE;

DO $$
DECLARE blocked boolean;
BEGIN
  -- Deferred trigger must reject an incomplete journal on constraint check.
  blocked := false;
  BEGIN
    EXECUTE 'SET CONSTRAINTS ALL DEFERRED';
    INSERT INTO m39930_ci.journals
      (id,scope,cashbox_key,event_type,evidence_reference)
    VALUES ('88888888-8888-4888-8888-888888888888','PLATFORM_MASTER',
      'platform','SAAS_SETTLEMENT','synthetic-incomplete-001');
    INSERT INTO m39930_ci.entries
      (id,journal_id,scope,cashbox_key,account_code,side,amount_cents)
    VALUES ('99999999-9999-4999-8999-999999999999',
      '88888888-8888-4888-8888-888888888888','PLATFORM_MASTER',
      'platform','PM_ONLY_DEBIT','DR',777);
    EXECUTE 'SET CONSTRAINTS ALL IMMEDIATE';
  EXCEPTION WHEN check_violation THEN blocked:=true;
  END;
  IF NOT blocked THEN RAISE EXCEPTION 'M39930 unbalanced journal escaped'; END IF;

  -- A second posting for the same evidence must not be accepted.
  blocked := false;
  BEGIN
    INSERT INTO m39930_ci.journals
      (id,scope,cashbox_key,event_type,evidence_reference)
    VALUES ('55555555-5555-4555-8555-555555555555','PLATFORM_MASTER',
      'platform','SAAS_SETTLEMENT','synthetic-saas-001');
  EXCEPTION WHEN unique_violation THEN blocked:=true;
  END;
  IF NOT blocked THEN RAISE EXCEPTION 'M39930 replay not blocked'; END IF;

  -- A tenant A account cannot belong to tenant B's journal.
  blocked := false;
  BEGIN
    INSERT INTO m39930_ci.entries
      (id,journal_id,scope,cashbox_key,account_code,side,amount_cents)
    VALUES ('66666666-6666-4666-8666-666666666666',
      '33333333-3333-4333-8333-333333333333','TENANT_COLLECTIVE',
      'tenant:bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb','TC_TEST','DR',1);
  EXCEPTION WHEN foreign_key_violation THEN blocked:=true;
  END;
  IF NOT blocked THEN RAISE EXCEPTION 'M39930 cross-tenant FK not blocked'; END IF;

  -- Master cannot book in the admin's namespace.
  blocked := false;
  BEGIN
    INSERT INTO m39930_ci.entries
      (id,journal_id,scope,cashbox_key,account_code,side,amount_cents)
    VALUES ('77777777-7777-4777-8777-777777777777',
      '11111111-1111-4111-8111-111111111111','PLATFORM_MASTER','platform',
      'TA_WRONG','DR',1);
  EXCEPTION WHEN check_violation THEN blocked:=true;
  END;
  IF NOT blocked THEN RAISE EXCEPTION 'M39930 mixed namespace not blocked'; END IF;

  -- Both journal and entries must reject UPDATE/DELETE.
  blocked := false;
  BEGIN
    UPDATE m39930_ci.journals SET evidence_reference='modified'
     WHERE id='11111111-1111-4111-8111-111111111111';
  EXCEPTION WHEN SQLSTATE '55000' THEN blocked:=true;
  END;
  IF NOT blocked THEN RAISE EXCEPTION 'M39930 journal mutability leak'; END IF;

  blocked := false;
  BEGIN
    DELETE FROM m39930_ci.entries
     WHERE id='11111111-aaaa-4111-8111-111111111111';
  EXCEPTION WHEN SQLSTATE '55000' THEN blocked:=true;
  END;
  IF NOT blocked THEN RAISE EXCEPTION 'M39930 entry mutability leak'; END IF;

  -- The synthetic application role has no write privileges by design.
  IF has_table_privilege('m39930_ci_reader','m39930_ci.journals','INSERT')
    OR has_table_privilege('m39930_ci_reader','m39930_ci.journals','UPDATE')
    OR has_table_privilege('m39930_ci_reader','m39930_ci.journals','DELETE')
    OR has_table_privilege('m39930_ci_reader','m39930_ci.entries','INSERT')
    OR has_table_privilege('m39930_ci_reader','m39930_ci.entries','DELETE') THEN
    RAISE EXCEPTION 'M39930 role has write privilege';
  END IF;
END;
$$;

-- Non-owner/no-BYPASSRLS viewer; simulate only server-set role and tenant GUCs.
SET LOCAL ROLE m39930_ci_reader;
SELECT set_config('frfinance.actor_role','MASTER',true);
SELECT set_config('frfinance.actor_tenant','',true);
DO $$
BEGIN
  IF (SELECT count(*) FROM m39930_ci.journals)<>1
   OR (SELECT count(*) FROM m39930_ci.entries)<>2 THEN
    RAISE EXCEPTION 'M39930 Master RLS leakage';
  END IF;
END;
$$;
SELECT set_config('frfinance.actor_role','TENANT_ADMIN',true);
SELECT set_config('frfinance.actor_tenant','aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',true);
DO $$
BEGIN
  IF (SELECT count(*) FROM m39930_ci.journals)<>2
   OR (SELECT count(*) FROM m39930_ci.entries)<>4 THEN
    RAISE EXCEPTION 'M39930 Admin A RLS leakage';
  END IF;
END;
$$;
SELECT set_config('frfinance.actor_tenant','bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',true);
DO $$
BEGIN
  IF (SELECT count(*) FROM m39930_ci.journals)<>1
   OR (SELECT count(*) FROM m39930_ci.entries)<>2 THEN
    RAISE EXCEPTION 'M39930 Admin B RLS leakage';
  END IF;
END;
$$;
SELECT set_config('frfinance.actor_role','TENANT_MEMBER',true);
DO $$
BEGIN
  IF (SELECT count(*) FROM m39930_ci.journals)<>0
   OR (SELECT count(*) FROM m39930_ci.entries)<>0 THEN
    RAISE EXCEPTION 'M39930 Member exclusive cashbox leak';
  END IF;
END;
$$;

-- The final ROLLBACK drops schema, role, fixtures, triggers, and functions.
ROLLBACK;
\echo M39930_DISPOSABLE_PG18=PASS
\echo M39930_DEFERRED_BALANCE=PASS
\echo M39930_IMMUTABLE_PREVIEW=PASS
\echo M39930_RLS_SEPARATION=PASS
\echo M39930_REAL_POSTINGS=NONE
\echo M39930_ORIGINAL_DB_ACCESS=NONE
