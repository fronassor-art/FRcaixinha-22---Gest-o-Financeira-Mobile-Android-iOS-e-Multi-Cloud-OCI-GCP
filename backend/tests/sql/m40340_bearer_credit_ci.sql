-- M40340. ONLY disposable PG18 frfinance_ci_credit:5432 in GitHub Actions.
-- Never run on Termux/Debian, OCI, original FR Finance or FR 2.2.
\set ON_ERROR_STOP on
BEGIN;
DO $guard$
BEGIN
 IF current_database()<>'frfinance_ci_credit' OR inet_server_port()<>5432
    OR session_user<>'postgres'
    OR current_setting('frfinance.m40340_ci',true) IS DISTINCT FROM 'DISPOSABLE_ONLY'
    OR to_regclass('public.sessions') IS NOT NULL
 THEN RAISE EXCEPTION 'M40340_BLOCKED_NOT_DISPOSABLE'; END IF;
 IF (SELECT count(*) FROM public.tenants
     WHERE id IN ('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
                  'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb'))<>2
 THEN RAISE EXCEPTION 'M40340_TWO_TENANTS_MISSING'; END IF;
END $guard$;
CREATE EXTENSION IF NOT EXISTS pgcrypto;
ALTER ROLE frc_ai_app LOGIN PASSWORD 'm40340-app-ci-only'
 NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION;
CREATE ROLE fr_m40340_auth LOGIN PASSWORD 'm40340-auth-ci-only'
 NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION;
GRANT CONNECT ON DATABASE frfinance_ci_credit TO frc_ai_app,fr_m40340_auth;
GRANT USAGE ON SCHEMA public TO fr_m40340_auth;
ALTER TABLE public.users ADD COLUMN email text;
ALTER TABLE public.users ADD COLUMN full_name text;
ALTER TABLE public.users ADD COLUMN is_master boolean;
ALTER TABLE public.users ADD COLUMN status text;
UPDATE public.users SET email=id::text||'@ci.invalid',full_name='Synthetic',
 is_master=false,status='ACTIVE';
INSERT INTO public.users(id,email,full_name,is_master,status)
VALUES('55555555-5555-4555-8555-555555555555',
       'master@ci.invalid','Master synthetic',true,'ACTIVE');
CREATE TABLE public.sessions (
 id uuid PRIMARY KEY,token_hash text NOT NULL UNIQUE,
 user_id uuid NOT NULL REFERENCES public.users(id),
 active_role text NOT NULL,active_tenant_id uuid,
 expires_at timestamptz NOT NULL,revoked_at timestamptz
);
INSERT INTO public.sessions
 (id,token_hash,user_id,active_role,active_tenant_id,expires_at,revoked_at)
VALUES
 ('40340001-0000-4000-8000-000000000001',
  encode(public.digest('m40340-admin-a','sha256'),'hex'),
  '11111111-1111-4111-8111-111111111111','TENANT_ADMIN',
  'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',now()+interval '20 min',NULL),
 ('40340002-0000-4000-8000-000000000002',
  encode(public.digest('m40340-admin-b','sha256'),'hex'),
  '33333333-3333-4333-8333-333333333333','TENANT_ADMIN',
  'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',now()+interval '20 min',NULL),
 ('40340003-0000-4000-8000-000000000003',
  encode(public.digest('m40340-member-a','sha256'),'hex'),
  '22222222-2222-4222-8222-222222222222','TENANT_MEMBER',
  'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',now()+interval '20 min',NULL),
 ('40340004-0000-4000-8000-000000000004',
  encode(public.digest('m40340-member-b','sha256'),'hex'),
  '44444444-4444-4444-8444-444444444444','TENANT_MEMBER',
  'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',now()+interval '20 min',NULL),
 ('40340005-0000-4000-8000-000000000005',
  encode(public.digest('m40340-master','sha256'),'hex'),
  '55555555-5555-4555-8555-555555555555','MASTER',NULL,
  now()+interval '20 min',NULL),
 ('40340006-0000-4000-8000-000000000006',
  encode(public.digest('m40340-expired','sha256'),'hex'),
  '11111111-1111-4111-8111-111111111111','TENANT_ADMIN',
  'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',now()-interval '5 min',NULL),
 ('40340007-0000-4000-8000-000000000007',
  encode(public.digest('m40340-revoked','sha256'),'hex'),
  '11111111-1111-4111-8111-111111111111','TENANT_ADMIN',
  'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',now()+interval '20 min',
  now()-interval '1 min');

-- CI-only stand-ins for auth SQL interface; NOT the real production functions.
CREATE FUNCTION public.auth_active_memberships(raw text)
RETURNS TABLE(tenant_id uuid,role text)
LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog,public AS $f$
 SELECT s.active_tenant_id,s.active_role
 FROM public.sessions s JOIN public.users u ON u.id=s.user_id
 WHERE s.token_hash=encode(public.digest(raw,'sha256'),'hex')
 AND s.revoked_at IS NULL AND s.expires_at>now() AND u.status='ACTIVE'
 AND s.active_tenant_id IS NOT NULL AND (
   (s.active_role='TENANT_ADMIN' AND EXISTS
     (SELECT 1 FROM public.tenants t WHERE t.id=s.active_tenant_id
      AND t.admin_user_id=s.user_id AND t.status='ATIVO'))
   OR (s.active_role='TENANT_MEMBER' AND EXISTS
     (SELECT 1 FROM public.memberships m
      WHERE m.tenant_id=s.active_tenant_id AND m.user_id=s.user_id
      AND m.role='TENANT_MEMBER' AND m.status='ATIVA'))
 )
$f$;
CREATE FUNCTION public.auth_refresh_session(raw text)
RETURNS timestamptz LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,public AS $f$
DECLARE renewed timestamptz;
BEGIN
 UPDATE public.sessions SET expires_at=statement_timestamp()+interval '15 min'
 WHERE token_hash=encode(public.digest(raw,'sha256'),'hex')
 AND revoked_at IS NULL AND expires_at>statement_timestamp()
 RETURNING expires_at INTO renewed;
 RETURN renewed;
END $f$;
GRANT SELECT ON public.sessions,public.users TO fr_m40340_auth;
GRANT EXECUTE ON FUNCTION public.auth_active_memberships(text) TO fr_m40340_auth;
GRANT EXECUTE ON FUNCTION public.auth_refresh_session(text) TO fr_m40340_auth;

-- Build two nonempty, published campaigns: existing M39020 tenant A grant
-- is revoked and old campaign cancelled; use fresh rows for both tenants.
SET LOCAL ROLE frc_ai_app;
DO $seed$
DECLARE r record;
BEGIN
 FOR r IN SELECT * FROM (VALUES
   ('A','aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
     '11111111-1111-4111-8111-111111111111',
     '22222222-2222-4222-8222-222222222222',
     'aaaacccc-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
     'aaaaeeee-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
     '40340101-0000-4000-8000-000000000101',
     '40340102-0000-4000-8000-000000000102',
     '40340103-0000-4000-8000-000000000103'),
   ('B','bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',
     '33333333-3333-4333-8333-333333333333',
     '44444444-4444-4444-8444-444444444444',
     'bbbbcccc-bbbb-4bbb-8bbb-bbbbbbbbbbbb',
     'bbbbeeee-bbbb-4bbb-8bbb-bbbbbbbbbbbb',
     '40340201-0000-4000-8000-000000000201',
     '40340202-0000-4000-8000-000000000202',
     '40340203-0000-4000-8000-000000000203')
 ) AS v(label,tenant,admin,member,cycle,membership,grantid,campaignid,recipientid)
 LOOP
  PERFORM set_config('app.current_tenant_id',r.tenant,true);
  PERFORM set_config('app.current_user_id',r.admin,true);
  PERFORM set_config('app.current_role','TENANT_ADMIN',true);
  INSERT INTO public.special_credit_grants
   (id,tenant_id,cycle_id,member_id,created_by,ceiling_brl,reason,expires_at,request_id)
  VALUES(r.grantid::uuid,r.tenant::uuid,r.cycle::uuid,r.membership::uuid,
   r.admin::uuid,2000,
   'Synthetic M40340 grant for disposable tenant isolation test',
   now()+interval '7 days',gen_random_uuid());
  INSERT INTO public.special_credit_campaigns
   (id,tenant_id,cycle_id,created_by,title,body,expires_at,request_id)
  VALUES(r.campaignid::uuid,r.tenant::uuid,r.cycle::uuid,r.admin::uuid,
   'M40340 synthetic campaign','No real money, notification or approval.',
   now()+interval '2 days',gen_random_uuid());
  INSERT INTO public.special_credit_recipients
   (id,tenant_id,campaign_id,grant_id,member_id,user_id)
  VALUES(r.recipientid::uuid,r.tenant::uuid,r.campaignid::uuid,
   r.grantid::uuid,r.membership::uuid,r.member::uuid);
  PERFORM set_config('app.current_user_id',r.member,true);
  PERFORM set_config('app.current_role','TENANT_MEMBER',true);
  INSERT INTO public.special_credit_preferences(tenant_id,user_id,channel,opted_in)
  VALUES(r.tenant::uuid,r.member::uuid,'PUSH',true)
  ON CONFLICT(tenant_id,user_id,channel) DO UPDATE SET opted_in=true;
  PERFORM set_config('app.current_user_id',r.admin,true);
  PERFORM set_config('app.current_role','TENANT_ADMIN',true);
  UPDATE public.special_credit_campaigns
    SET status='PUBLISHED',published_at=now()
    WHERE id=r.campaignid::uuid;
  INSERT INTO public.special_credit_outbox
   (tenant_id,campaign_id,recipient_id,channel,state)
  VALUES(r.tenant::uuid,r.campaignid::uuid,r.recipientid::uuid,
         'PUSH','BLOCKED_EXTERNAL');
  INSERT INTO public.special_credit_audit
   (tenant_id,actor_id,entity_kind,entity_id,action,detail)
  VALUES(r.tenant::uuid,r.admin::uuid,'CAMPAIGN',r.campaignid::uuid,
   'M40340_CI_ONLY','Synthetic disposable fixture with no external delivery');
 END LOOP;
END $seed$;
RESET ROLE;
DO $proof$
BEGIN
 IF (SELECT count(*) FROM public.sessions)<>7 OR
 EXISTS(SELECT 1 FROM pg_roles WHERE rolname IN ('frc_ai_app','fr_m40340_auth')
 AND (rolsuper OR rolbypassrls)) OR
 has_table_privilege('frc_ai_app','public.sessions','SELECT') OR
 has_table_privilege('fr_m40340_auth','public.special_credit_grants','SELECT')
 THEN RAISE EXCEPTION 'M40340_PRIVILEGE_OR_SESSION_FIXTURE_FAILED'; END IF;
END $proof$;
COMMIT;
SELECT 'M40340_CI_FIXTURE=COMMITTED_DISPOSABLE_ONLY' AS result;
SELECT 'M40340_EXTERNAL_SEND=BLOCKED' AS result;
