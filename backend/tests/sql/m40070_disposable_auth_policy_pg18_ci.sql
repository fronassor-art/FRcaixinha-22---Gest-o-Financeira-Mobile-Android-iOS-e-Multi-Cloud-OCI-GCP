-- FR Finance M40070: ONLY the disposable PG18 GitHub Actions database.
-- This is a small synthetic contract fixture, NOT an application migration.
\set ON_ERROR_STOP on
BEGIN;
DO $guard$
BEGIN
  IF current_database() <> 'frcaixinha_ci'
     OR session_user <> 'postgres'
     OR current_setting('is_superuser') <> 'on'
     OR current_setting('frfinance.m40070_ci', true)
        IS DISTINCT FROM 'DISPOSABLE_ONLY'
     OR to_regclass('public.sessions') IS NOT NULL
     OR EXISTS (SELECT 1 FROM pg_roles WHERE rolname IN
                ('fr_m40070_auth', 'fr_m40070_app'))
  THEN
    RAISE EXCEPTION 'M40070_BLOCKED_NOT_DISPOSABLE_PG18';
  END IF;
END $guard$;

CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE ROLE fr_m40070_auth LOGIN PASSWORD 'm40070-auth-ci-only'
  NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION;
CREATE ROLE fr_m40070_app LOGIN PASSWORD 'm40070-app-ci-only'
  NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION;
GRANT CONNECT ON DATABASE frcaixinha_ci TO fr_m40070_auth, fr_m40070_app;
GRANT USAGE ON SCHEMA public TO fr_m40070_auth, fr_m40070_app;

CREATE TABLE public.users (
 id uuid PRIMARY KEY, email text NOT NULL, full_name text NOT NULL,
 is_master boolean NOT NULL, status text NOT NULL
);
CREATE TABLE public.tenants (
 id uuid PRIMARY KEY, admin_user_id uuid NOT NULL, status text NOT NULL
);
CREATE TABLE public.sessions (
 id uuid PRIMARY KEY, token_hash text NOT NULL UNIQUE,
 user_id uuid NOT NULL REFERENCES public.users(id),
 active_role text NOT NULL, active_tenant_id uuid,
 expires_at timestamptz NOT NULL, revoked_at timestamptz
);
REVOKE ALL ON public.users, public.sessions, public.tenants FROM PUBLIC;

INSERT INTO public.users (id, email, full_name, is_master, status) VALUES
 ('11111111-1111-4111-8111-111111111111','master@ci.invalid','Master CI',true,'ACTIVE'),
 ('22222222-2222-4222-8222-222222222222','owner-a@ci.invalid','Owner A CI',false,'ACTIVE'),
 ('33333333-3333-4333-8333-333333333333','owner-b@ci.invalid','Owner B CI',false,'ACTIVE'),
 ('44444444-4444-4444-8444-444444444444','member-a@ci.invalid','Member A CI',false,'ACTIVE'),
 ('55555555-5555-4555-8555-555555555555','not-owner@ci.invalid','Not owner CI',false,'ACTIVE');

INSERT INTO public.tenants (id,admin_user_id,status) VALUES
 ('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
  '22222222-2222-4222-8222-222222222222','ATIVO'),
 ('bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',
  '33333333-3333-4333-8333-333333333333','ATIVO');

-- All tokens are synthetic and fixed solely for CI. Never put them in .env.
INSERT INTO public.sessions
(id, token_hash, user_id, active_role, active_tenant_id, expires_at, revoked_at)
VALUES
 ('10000000-0000-4000-8000-000000000001',
  encode(public.digest('m40070-ci-master-never-real','sha256'),'hex'),
  '11111111-1111-4111-8111-111111111111','MASTER',NULL,
  clock_timestamp()+interval '20 minutes',NULL),
 ('10000000-0000-4000-8000-000000000002',
  encode(public.digest('m40070-ci-admin-a-never-real','sha256'),'hex'),
  '22222222-2222-4222-8222-222222222222','TENANT_ADMIN',
  'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
  clock_timestamp()+interval '20 minutes',NULL),
 ('10000000-0000-4000-8000-000000000003',
  encode(public.digest('m40070-ci-admin-b-never-real','sha256'),'hex'),
  '33333333-3333-4333-8333-333333333333','TENANT_ADMIN',
  'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',
  clock_timestamp()+interval '20 minutes',NULL),
 ('10000000-0000-4000-8000-000000000004',
  encode(public.digest('m40070-ci-member-a-never-real','sha256'),'hex'),
  '44444444-4444-4444-8444-444444444444','TENANT_MEMBER',
  'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
  clock_timestamp()+interval '20 minutes',NULL),
 ('10000000-0000-4000-8000-000000000005',
  encode(public.digest('m40070-ci-notowner-a-never-real','sha256'),'hex'),
  '55555555-5555-4555-8555-555555555555','TENANT_ADMIN',
  'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
  clock_timestamp()+interval '20 minutes',NULL),
 ('10000000-0000-4000-8000-000000000006',
  encode(public.digest('m40070-ci-expired-a-never-real','sha256'),'hex'),
  '22222222-2222-4222-8222-222222222222','TENANT_ADMIN',
  'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
  clock_timestamp()-interval '10 minutes',NULL),
 ('10000000-0000-4000-8000-000000000007',
  encode(public.digest('m40070-ci-revoked-a-never-real','sha256'),'hex'),
  '22222222-2222-4222-8222-222222222222','TENANT_ADMIN',
  'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
  clock_timestamp()+interval '20 minutes',clock_timestamp()-interval '1 minute');

-- Functions intentionally mimic the *interface* of existing auth functions.
-- They do NOT attest the production function body, membership lifecycle,
-- real policy, or legal authorization.
CREATE FUNCTION public.auth_active_memberships(raw text)
RETURNS TABLE(tenant_id uuid, role text)
LANGUAGE sql SECURITY DEFINER
SET search_path = pg_catalog, public
AS $fn$
 SELECT s.active_tenant_id, s.active_role
 FROM public.sessions s JOIN public.users u ON u.id=s.user_id
 WHERE s.token_hash=encode(public.digest(raw,'sha256'),'hex')
   AND s.revoked_at IS NULL AND s.expires_at>statement_timestamp()
   AND s.active_tenant_id IS NOT NULL AND u.status='ACTIVE'
$fn$;

CREATE FUNCTION public.auth_refresh_session(raw text)
RETURNS timestamptz
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, public
AS $fn$
DECLARE renewed timestamptz;
BEGIN
 UPDATE public.sessions s
 SET expires_at = statement_timestamp() + interval '15 minutes'
 WHERE s.token_hash=encode(public.digest(raw,'sha256'),'hex')
   AND s.revoked_at IS NULL AND s.expires_at>statement_timestamp()
 RETURNING s.expires_at INTO renewed;
 RETURN renewed;
END
$fn$;

GRANT SELECT ON public.sessions, public.users TO fr_m40070_auth;
GRANT EXECUTE ON FUNCTION public.auth_active_memberships(text)
 TO fr_m40070_auth;
GRANT EXECUTE ON FUNCTION public.auth_refresh_session(text)
 TO fr_m40070_auth;
GRANT SELECT (id,admin_user_id,status) ON public.tenants TO fr_m40070_app;

ALTER TABLE public.tenants ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.tenants FORCE ROW LEVEL SECURITY;
CREATE POLICY m40070_tenant_owner_view ON public.tenants
FOR SELECT TO fr_m40070_app
USING (
 id::text=current_setting('app.current_tenant_id',true)
 AND admin_user_id::text=current_setting('app.current_user_id',true)
 AND current_setting('app.current_role',true)='TENANT_ADMIN'
 AND status='ATIVO'
);

-- A service role must NEVER read raw tokens or create financial data.
DO $rights$
BEGIN
 IF NOT has_table_privilege('fr_m40070_auth','public.sessions','SELECT')
    OR has_table_privilege('fr_m40070_app','public.sessions','SELECT')
    OR has_table_privilege('fr_m40070_app','public.users','SELECT')
    OR has_table_privilege('fr_m40070_auth','public.tenants','SELECT')
    OR has_table_privilege('fr_m40070_app','public.tenants','INSERT')
    OR has_table_privilege('fr_m40070_app','public.tenants','UPDATE')
    OR has_table_privilege('fr_m40070_app','public.tenants','DELETE')
    OR NOT EXISTS (SELECT 1 FROM pg_roles
       WHERE rolname='fr_m40070_auth' AND NOT rolsuper AND NOT rolbypassrls)
    OR NOT EXISTS (SELECT 1 FROM pg_roles
       WHERE rolname='fr_m40070_app' AND NOT rolsuper AND NOT rolbypassrls)
 THEN RAISE EXCEPTION 'M40070_LEAST_PRIVILEGE_DENIED'; END IF;
END $rights$;
COMMIT;
