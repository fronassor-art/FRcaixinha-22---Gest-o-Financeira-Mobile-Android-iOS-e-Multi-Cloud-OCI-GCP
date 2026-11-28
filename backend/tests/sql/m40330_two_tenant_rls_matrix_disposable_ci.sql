-- FR Finance M40330 — six-table positive/negative RLS data-plane matrix.
-- Only GitHub Actions PostgreSQL 18 disposable frfinance_ci_credit :5432.
-- A and B are fictitious, seeded by m39020_special_credit_integrity_ci.sql.
-- No real tokens, no member records, no local Termux DB, no external sender.
\set ON_ERROR_STOP on

DO $guard$
BEGIN
 IF current_database()<>'frfinance_ci_credit'
    OR inet_server_port()<>5432 OR session_user<>'postgres'
    OR current_setting('frfinance.m40330_test_mode',true)
       IS DISTINCT FROM 'CI_DISPOSABLE'
 THEN RAISE EXCEPTION 'M40330 CI_DISPOSABLE_ONLY'; END IF;
 IF (SELECT count(*) FROM public.tenants
     WHERE id IN ('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
                  'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb'))<>2
 THEN RAISE EXCEPTION 'M40330 TWO_TENANT_FIXTURE_MISSING'; END IF;
 IF (SELECT count(*) FROM pg_class
     WHERE oid IN ('public.special_credit_grants'::regclass,
                   'public.special_credit_campaigns'::regclass,
                   'public.special_credit_recipients'::regclass,
                   'public.special_credit_preferences'::regclass,
                   'public.special_credit_outbox'::regclass,
                   'public.special_credit_audit'::regclass)
       AND relrowsecurity AND relforcerowsecurity)<>6
 THEN RAISE EXCEPTION 'M40330 FORCE_RLS_REQUIRED'; END IF;
END $guard$;

-- All new test data and GUC changes are transaction-local and rolled back.
BEGIN;
SET TRANSACTION ISOLATION LEVEL READ COMMITTED;
SET LOCAL ROLE frc_ai_app;
SELECT set_config('app.current_tenant_id','aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',true);
SELECT set_config('app.current_user_id','11111111-1111-4111-8111-111111111111',true);
SELECT set_config('app.current_role','TENANT_ADMIN',true);

INSERT INTO public.special_credit_grants
 (id,tenant_id,cycle_id,member_id,created_by,ceiling_brl,reason,expires_at,request_id)
VALUES
 ('40330001-0000-4000-8000-000000000001',
  'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
  'aaaacccc-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
  'aaaaeeee-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
  '11111111-1111-4111-8111-111111111111',
  5000,'M40330 synthetic test grant for tenant A positive isolation',
  now()+interval '7 days','40330f01-0000-4000-8000-000000000001');
INSERT INTO public.special_credit_campaigns
 (id,tenant_id,cycle_id,created_by,title,body,expires_at,request_id)
VALUES
 ('40330002-0000-4000-8000-000000000002',
  'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
  'aaaacccc-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
  '11111111-1111-4111-8111-111111111111',
  'M40330 fixture A','Synthetic campaign only; no money or delivery.',
  now()+interval '2 days','40330f02-0000-4000-8000-000000000002');
INSERT INTO public.special_credit_recipients
 (id,tenant_id,campaign_id,grant_id,member_id,user_id)
VALUES
 ('40330003-0000-4000-8000-000000000003',
  'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
  '40330002-0000-4000-8000-000000000002',
  '40330001-0000-4000-8000-000000000001',
  'aaaaeeee-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
  '22222222-2222-4222-8222-222222222222');
UPDATE public.special_credit_campaigns
 SET status='PUBLISHED',published_at=now()
 WHERE id='40330002-0000-4000-8000-000000000002';
INSERT INTO public.special_credit_outbox
 (id,tenant_id,campaign_id,recipient_id,channel,state)
VALUES
 ('40330004-0000-4000-8000-000000000004',
  'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
  '40330002-0000-4000-8000-000000000002',
  '40330003-0000-4000-8000-000000000003',
  'PUSH','BLOCKED_EXTERNAL');
INSERT INTO public.special_credit_audit
 (id,tenant_id,actor_id,entity_kind,entity_id,action,detail)
VALUES
 ('40330005-0000-4000-8000-000000000005',
  'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
  '11111111-1111-4111-8111-111111111111',
  'CAMPAIGN','40330002-0000-4000-8000-000000000002',
  'M40330_CI_ONLY','Synthetic RLS fixture; transaction rollback required');

-- Tenant B administrator and member are real rows only in disposable CI.
SELECT set_config('app.current_tenant_id','bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',true);
SELECT set_config('app.current_user_id','33333333-3333-4333-8333-333333333333',true);
SELECT set_config('app.current_role','TENANT_ADMIN',true);
INSERT INTO public.special_credit_grants
 (id,tenant_id,cycle_id,member_id,created_by,ceiling_brl,reason,expires_at,request_id)
VALUES
 ('40330011-0000-4000-8000-000000000011',
  'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',
  'bbbbcccc-bbbb-4bbb-8bbb-bbbbbbbbbbbb',
  'bbbbeeee-bbbb-4bbb-8bbb-bbbbbbbbbbbb',
  '33333333-3333-4333-8333-333333333333',
  4000,'M40330 synthetic test grant for tenant B positive isolation',
  now()+interval '7 days','40330f11-0000-4000-8000-000000000011');
INSERT INTO public.special_credit_campaigns
 (id,tenant_id,cycle_id,created_by,title,body,expires_at,request_id)
VALUES
 ('40330012-0000-4000-8000-000000000012',
  'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',
  'bbbbcccc-bbbb-4bbb-8bbb-bbbbbbbbbbbb',
  '33333333-3333-4333-8333-333333333333',
  'M40330 fixture B','Synthetic campaign only; no money or delivery.',
  now()+interval '2 days','40330f12-0000-4000-8000-000000000012');
INSERT INTO public.special_credit_recipients
 (id,tenant_id,campaign_id,grant_id,member_id,user_id)
VALUES
 ('40330013-0000-4000-8000-000000000013',
  'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',
  '40330012-0000-4000-8000-000000000012',
  '40330011-0000-4000-8000-000000000011',
  'bbbbeeee-bbbb-4bbb-8bbb-bbbbbbbbbbbb',
  '44444444-4444-4444-8444-444444444444');

-- Only the tenant B member may opt in; still no external delivery.
SELECT set_config('app.current_user_id','44444444-4444-4444-8444-444444444444',true);
SELECT set_config('app.current_role','TENANT_MEMBER',true);
INSERT INTO public.special_credit_preferences
 (tenant_id,user_id,channel,opted_in)
VALUES
 ('bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',
  '44444444-4444-4444-8444-444444444444','PUSH',true);

SELECT set_config('app.current_user_id','33333333-3333-4333-8333-333333333333',true);
SELECT set_config('app.current_role','TENANT_ADMIN',true);
UPDATE public.special_credit_campaigns
 SET status='PUBLISHED',published_at=now()
 WHERE id='40330012-0000-4000-8000-000000000012';
INSERT INTO public.special_credit_outbox
 (id,tenant_id,campaign_id,recipient_id,channel,state)
VALUES
 ('40330014-0000-4000-8000-000000000014',
  'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',
  '40330012-0000-4000-8000-000000000012',
  '40330013-0000-4000-8000-000000000013',
  'PUSH','BLOCKED_EXTERNAL');
INSERT INTO public.special_credit_audit
 (id,tenant_id,actor_id,entity_kind,entity_id,action,detail)
VALUES
 ('40330015-0000-4000-8000-000000000015',
  'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',
  '33333333-3333-4333-8333-333333333333',
  'CAMPAIGN','40330012-0000-4000-8000-000000000012',
  'M40330_CI_ONLY','Synthetic RLS fixture; transaction rollback required');

-- Ten contexts across all six tables: positive, cross-tenant, spoof and master.
-- All queries run under the genuine restricted frc_ai_app role.
DO $matrix$
DECLARE
 c record;
 t text;
 self_count bigint;
 other_count bigint;
 required boolean;
 opposite uuid;
 tests int := 0;
BEGIN
 IF current_user <> 'frc_ai_app'
    OR NOT row_security_active('public.special_credit_grants'::regclass)
 THEN RAISE EXCEPTION 'M40330 APP_ROLE_OR_RLS_INACTIVE'; END IF;
 FOR c IN
  SELECT * FROM (VALUES
   ('A_ADMIN','11111111-1111-4111-8111-111111111111','aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa','TENANT_ADMIN','ADMIN'),
   ('B_ADMIN','33333333-3333-4333-8333-333333333333','bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb','TENANT_ADMIN','ADMIN'),
   ('A_MEMBER','22222222-2222-4222-8222-222222222222','aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa','TENANT_MEMBER','MEMBER'),
   ('B_MEMBER','44444444-4444-4444-8444-444444444444','bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb','TENANT_MEMBER','MEMBER'),
   ('A_ADMIN_CLAIM_B','11111111-1111-4111-8111-111111111111','bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb','TENANT_ADMIN','NONE'),
   ('B_ADMIN_CLAIM_A','33333333-3333-4333-8333-333333333333','aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa','TENANT_ADMIN','NONE'),
   ('A_MEMBER_CLAIM_B','22222222-2222-4222-8222-222222222222','bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb','TENANT_MEMBER','NONE'),
   ('B_MEMBER_CLAIM_A','44444444-4444-4444-8444-444444444444','aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa','TENANT_MEMBER','NONE'),
   ('MASTER_NO_TENANT','33333333-3333-4333-8333-333333333333','','MASTER','NONE'),
   ('MASTER_CLAIM_A','11111111-1111-4111-8111-111111111111','aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa','MASTER','NONE')
  ) AS v(label,user_id,tenant_id,role_name,expected_group)
 LOOP
  PERFORM set_config('app.current_user_id',c.user_id,true);
  PERFORM set_config('app.current_tenant_id',c.tenant_id,true);
  PERFORM set_config('app.current_role',c.role_name,true);
  opposite := CASE WHEN c.tenant_id='aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'
     THEN 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb'::uuid
     ELSE 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'::uuid END;
  FOREACH t IN ARRAY ARRAY[
    'special_credit_grants','special_credit_campaigns',
    'special_credit_recipients','special_credit_preferences',
    'special_credit_outbox','special_credit_audit']
  LOOP
   EXECUTE format('SELECT count(*) FROM public.%I WHERE tenant_id=$1',t)
       INTO self_count USING NULLIF(c.tenant_id,'')::uuid;
   EXECUTE format('SELECT count(*) FROM public.%I WHERE tenant_id=$1',t)
       INTO other_count USING opposite;
   required := c.expected_group='ADMIN' OR
      (c.expected_group='MEMBER' AND t NOT IN
        ('special_credit_outbox','special_credit_audit'));
   IF (required AND self_count<1) OR
      (NOT required AND self_count<>0) OR other_count<>0 THEN
     RAISE EXCEPTION
       'M40330_RLS_MATRIX_DENIED: context %, table %, self %, other %, required %',
        c.label,t,self_count,other_count,required;
   END IF;
   tests := tests+1;
  END LOOP;
 END LOOP;
 IF tests<>60 THEN RAISE EXCEPTION 'M40330_MATRIX_INCOMPLETE_%',tests; END IF;
 RAISE NOTICE 'M40330_DATA_PLANE_MATRIX=PASS_60_OF_60';
 RAISE NOTICE 'M40330_CONTEXTS=PASS_10_OF_10_SYNTHETIC_EXISTING_ROWS';
END $matrix$;

-- The role and user/tenant context must not carry across transactions.
ROLLBACK;

DO $rollback$
BEGIN
 IF current_user<>'postgres'
    OR coalesce(current_setting('app.current_tenant_id',true),'')<>''
    OR coalesce(current_setting('app.current_user_id',true),'')<>''
    OR coalesce(current_setting('app.current_role',true),'')<>''
 THEN RAISE EXCEPTION 'M40330_TRANSACTION_CONTEXT_LEAK'; END IF;
 IF EXISTS(SELECT 1 FROM public.special_credit_grants
      WHERE id IN ('40330001-0000-4000-8000-000000000001',
                   '40330011-0000-4000-8000-000000000011'))
    OR EXISTS(SELECT 1 FROM public.special_credit_campaigns
      WHERE id IN ('40330002-0000-4000-8000-000000000002',
                   '40330012-0000-4000-8000-000000000012'))
    OR EXISTS(SELECT 1 FROM public.special_credit_recipients
      WHERE id IN ('40330003-0000-4000-8000-000000000003',
                   '40330013-0000-4000-8000-000000000013'))
    OR EXISTS(SELECT 1 FROM public.special_credit_outbox
      WHERE id IN ('40330004-0000-4000-8000-000000000004',
                   '40330014-0000-4000-8000-000000000014'))
    OR EXISTS(SELECT 1 FROM public.special_credit_audit
      WHERE id IN ('40330005-0000-4000-8000-000000000005',
                   '40330015-0000-4000-8000-000000000015'))
    OR EXISTS(SELECT 1 FROM public.special_credit_preferences
      WHERE tenant_id='bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb'
        AND user_id='44444444-4444-4444-8444-444444444444')
 THEN RAISE EXCEPTION 'M40330_SYNTHETIC_ROWS_SURVIVED_ROLLBACK'; END IF;
END $rollback$;
SELECT 'M40330_TRANSACTION_ROLLBACK=PASS' AS result;
SELECT 'M40330_AUTHENTICATED_BEARER_ISOLATION=NOT_TESTED' AS result;
SELECT 'M40330_ORIGINAL_TERMUX_DB=NOT_TOUCHED' AS result;
SELECT 'M40330_PIX_REAL=OFF' AS result;
SELECT 'M40330_PRODUCTION=BLOCKED' AS result;
