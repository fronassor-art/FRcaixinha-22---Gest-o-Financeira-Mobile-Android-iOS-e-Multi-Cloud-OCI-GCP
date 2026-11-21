-- M39920 — PostgreSQL 18 DISPOSABLE-ONLY modelling exercise.
-- NOT a migration. Never run in Termux or either original FR Finance/2.2 DB.
-- Creates TEMP candidates, demonstrates constraints, then ROLLBACK.
\set ON_ERROR_STOP on
\if :{?CI_M39920_DISPOSABLE}
\else
\echo 'M39920_BLOCKED_NO_DISPOSABLE_FLAG'
\quit 2
\endif
SELECT CASE WHEN current_database()='frcaixinha_ci'
                 AND inet_server_port()=5432
                 AND session_user='postgres'
                 AND current_setting('frfinance.m39920_ci',true)='DISPOSABLE_ONLY'
            THEN 'true' ELSE 'false' END AS is_disposable
\gset
\if :is_disposable
\else
\echo 'M39920_BLOCKED_NOT_CI_POSTGRES'
\quit 2
\endif

BEGIN;

CREATE TEMP TABLE m39920_cashbox_candidate (
    id uuid PRIMARY KEY,
    scope text NOT NULL CHECK (scope IN
        ('PLATFORM_MASTER','TENANT_ADMIN_OWN','TENANT_COLLECTIVE')),
    cashbox_key text NOT NULL,
    event_type text NOT NULL,
    evidence_reference text NOT NULL CHECK (length(evidence_reference) BETWEEN 6 AND 120),
    state text NOT NULL DEFAULT 'STRUCTURAL_PREVIEW_NO_POSTING'
        CHECK (state='STRUCTURAL_PREVIEW_NO_POSTING'),
    posting_authorized boolean NOT NULL DEFAULT false CHECK (posting_authorized=false),
    provider_reconciled boolean NOT NULL DEFAULT false CHECK (provider_reconciled=false),
    withdraw_enabled boolean NOT NULL DEFAULT false CHECK (withdraw_enabled=false),
    available_balance_cents bigint CHECK (available_balance_cents IS NULL),
    CONSTRAINT m39920_scope_key CHECK (
       (scope='PLATFORM_MASTER' AND cashbox_key='platform')
       OR (scope<>'PLATFORM_MASTER' AND cashbox_key ~
           '^tenant:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')
    ),
    CONSTRAINT m39920_scope_event CHECK (
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

CREATE TEMP TABLE m39920_cashbox_candidate_line (
    journal_id uuid NOT NULL,
    scope text NOT NULL,
    cashbox_key text NOT NULL,
    account_code text NOT NULL CHECK (account_code ~ '^[A-Z0-9_]{4,40}$'),
    entry_side text NOT NULL CHECK (entry_side IN ('DR','CR')),
    amount_cents bigint NOT NULL CHECK (amount_cents BETWEEN 1 AND 999999999999),
    FOREIGN KEY(journal_id,scope,cashbox_key)
      REFERENCES m39920_cashbox_candidate(id,scope,cashbox_key),
    CONSTRAINT m39920_account_prefix CHECK (
       (scope='PLATFORM_MASTER' AND left(account_code,3)='PM_')
       OR (scope='TENANT_ADMIN_OWN' AND left(account_code,3)='TA_')
       OR (scope='TENANT_COLLECTIVE' AND left(account_code,3)='TC_')
    ),
    UNIQUE(journal_id,account_code,entry_side)
);

INSERT INTO m39920_cashbox_candidate
    (id,scope,cashbox_key,event_type,evidence_reference)
VALUES
    ('11111111-1111-4111-8111-111111111111','PLATFORM_MASTER','platform',
      'SAAS_SETTLEMENT','ci-saas-evidence-001'),
    ('22222222-2222-4222-8222-222222222222','TENANT_ADMIN_OWN',
      'tenant:aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
      'ADMIN_CLOSING_REMUNERATION','ci-admin-close-001'),
    ('33333333-3333-4333-8333-333333333333','TENANT_COLLECTIVE',
      'tenant:bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',
      'MEMBER_CONTRIBUTION','ci-member-contribution-001');

INSERT INTO m39920_cashbox_candidate_line
  (journal_id,scope,cashbox_key,account_code,entry_side,amount_cents)
VALUES
 ('11111111-1111-4111-8111-111111111111','PLATFORM_MASTER','platform',
   'PM_RECEIVABLE','DR',1200),
 ('11111111-1111-4111-8111-111111111111','PLATFORM_MASTER','platform',
   'PM_REVENUE','CR',1200),
 ('22222222-2222-4222-8222-222222222222','TENANT_ADMIN_OWN',
   'tenant:aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa','TA_RECEIVABLE','DR',150),
 ('22222222-2222-4222-8222-222222222222','TENANT_ADMIN_OWN',
   'tenant:aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa','TA_OFFSET','CR',150),
 ('33333333-3333-4333-8333-333333333333','TENANT_COLLECTIVE',
   'tenant:bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb','TC_RECEIVABLE','DR',100),
 ('33333333-3333-4333-8333-333333333333','TENANT_COLLECTIVE',
   'tenant:bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb','TC_MEMBER_CAPITAL','CR',100);

-- SQL invariant proof on disposable data only. This is NOT a production
-- deferred trigger and cannot prevent writes in another application.
DO $$
DECLARE n integer;
BEGIN
 SELECT count(*) INTO n FROM m39920_cashbox_candidate;
 IF n<>3 THEN RAISE EXCEPTION 'M39920 missing independent scopes'; END IF;
 IF EXISTS (
   SELECT journal_id
   FROM m39920_cashbox_candidate_line
   GROUP BY journal_id
   HAVING count(*)<2 OR
    COALESCE(sum(amount_cents) FILTER(WHERE entry_side='DR'),0)
    <> COALESCE(sum(amount_cents) FILTER(WHERE entry_side='CR'),0)
 ) THEN RAISE EXCEPTION 'M39920 unbalanced synthetic candidate'; END IF;
 IF EXISTS (SELECT 1 FROM m39920_cashbox_candidate
           WHERE posting_authorized OR provider_reconciled
           OR withdraw_enabled OR available_balance_cents IS NOT NULL)
 THEN RAISE EXCEPTION 'M39920 unauthorized cash state'; END IF;
END $$;

-- Expected violations are explicitly caught by PL/pgSQL subtransactions.
DO $$
BEGIN
  BEGIN
    INSERT INTO m39920_cashbox_candidate_line
      (journal_id,scope,cashbox_key,account_code,entry_side,amount_cents)
    VALUES
      ('11111111-1111-4111-8111-111111111111','PLATFORM_MASTER',
       'tenant:aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
       'PM_WRONG_TENANT','DR',500);
    RAISE EXCEPTION 'M39920 cross-cashbox FK unexpectedly accepted';
  EXCEPTION WHEN foreign_key_violation THEN NULL;
  END;
  BEGIN
    INSERT INTO m39920_cashbox_candidate_line
      (journal_id,scope,cashbox_key,account_code,entry_side,amount_cents)
    VALUES ('11111111-1111-4111-8111-111111111111','PLATFORM_MASTER',
       'platform','TA_NOT_MASTER','DR',500);
    RAISE EXCEPTION 'M39920 mixed account prefix unexpectedly accepted';
  EXCEPTION WHEN check_violation THEN NULL;
  END;
  BEGIN
    INSERT INTO m39920_cashbox_candidate_line
      (journal_id,scope,cashbox_key,account_code,entry_side,amount_cents)
    VALUES ('11111111-1111-4111-8111-111111111111','PLATFORM_MASTER',
       'platform','PM_ZERO_AMOUNT','DR',0);
    RAISE EXCEPTION 'M39920 zero-amount posting unexpectedly accepted';
  EXCEPTION WHEN check_violation THEN NULL;
  END;
  BEGIN
    INSERT INTO m39920_cashbox_candidate
      (id,scope,cashbox_key,event_type,evidence_reference)
    VALUES ('44444444-4444-4444-8444-444444444444',
        'PLATFORM_MASTER','platform','SAAS_SETTLEMENT','ci-saas-evidence-001');
    RAISE EXCEPTION 'M39920 replay reference unexpectedly accepted';
  EXCEPTION WHEN unique_violation THEN NULL;
  END;
  BEGIN
    INSERT INTO m39920_cashbox_candidate
      (id,scope,cashbox_key,event_type,evidence_reference,posting_authorized)
    VALUES ('55555555-5555-4555-8555-555555555555',
        'TENANT_ADMIN_OWN','tenant:aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
        'ADMIN_CLOSING_REMUNERATION','ci-admin-close-002',true);
    RAISE EXCEPTION 'M39920 unauthorized posting unexpectedly accepted';
  EXCEPTION WHEN check_violation THEN NULL;
  END;
  BEGIN
    INSERT INTO m39920_cashbox_candidate
      (id,scope,cashbox_key,event_type,evidence_reference)
    VALUES ('66666666-6666-4666-8666-666666666666',
        'PLATFORM_MASTER','platform','MEMBER_CONTRIBUTION','ci-wrong-event-001');
    RAISE EXCEPTION 'M39920 wrong event scope unexpectedly accepted';
  EXCEPTION WHEN check_violation THEN NULL;
  END;
END $$;

ROLLBACK;
\echo 'M39920_DISPOSABLE_CASHBOX_SCHEMA=PASS'
\echo 'M39920_CROSS_TENANT_AND_REPLAY_BLOCKED=PASS'
\echo 'M39920_SYNTHETIC_PERSISTENCE=NONE'
\echo 'M39920_PRODUCTION=BLOCKED'
