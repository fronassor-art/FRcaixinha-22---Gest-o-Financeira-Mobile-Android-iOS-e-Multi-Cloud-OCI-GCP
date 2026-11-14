-- M37462: disposable-only authentication token -> PostgreSQL session fixture.
-- This is NOT a production login, legal contract or credential migration.
BEGIN;
DO $m37462_guard$
BEGIN
 IF current_database()<>'frcaixinha_staging'
  OR session_user<>'postgres' OR current_setting('is_superuser')<>'on'
  OR current_setting('frcaixinha.saas_token_ci',true) IS DISTINCT FROM '1'
  OR to_regclass('public.sessions') IS NULL
  OR to_regclass('public.saas_preprep_sessions_m37458_ci') IS NULL
  OR to_regprocedure('public.auth_refresh_session(text)') IS NULL
  OR to_regprocedure('public.auth_revoke_session(text)') IS NULL
  OR NOT EXISTS (
   SELECT 1 FROM pg_roles WHERE rolname='frcaixinha_auth_role'
   AND NOT rolsuper AND NOT rolbypassrls
  )
  OR EXISTS(SELECT 1 FROM pg_roles WHERE rolname='frcaixinha_auth_token_ci')
 THEN RAISE EXCEPTION 'M37462_DISPOSABLE_POSTGRESQL_ONLY'; END IF;
END $m37462_guard$;

CREATE ROLE frcaixinha_auth_token_ci LOGIN INHERIT PASSWORD 'ci-test-only'
  NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION;
GRANT frcaixinha_auth_role TO frcaixinha_auth_token_ci;
GRANT CONNECT ON DATABASE frcaixinha_staging TO frcaixinha_auth_token_ci;

-- Three independent token hashes, generated inside disposable SQL.
-- S1 is the separate synthetic M37458 context ID, S2 a rotated token
-- for the same admin, S3 another tenant/admin, S4 a deliberately expired
-- session. No raw bearer is ever persisted in public.sessions.
INSERT INTO public.sessions(
 id,token_hash,user_id,active_role,active_tenant_id,expires_at
) VALUES
 ('daba0000-0000-4000-8000-000000000581',
  encode(public.digest('m37462-ci-only-first-bearer-NEVER-REAL-01','sha256'),'hex'),
  'daba0000-0000-4000-8000-000000000001',
  'TENANT_ADMIN','daba0000-0000-4000-8000-000000000010',
  clock_timestamp()+interval '30 minutes'),
 ('daba0000-0000-4000-8000-000000000588',
  encode(public.digest('m37462-ci-only-rotated-bearer-NEVER-REAL-02','sha256'),'hex'),
  'daba0000-0000-4000-8000-000000000001',
  'TENANT_ADMIN','daba0000-0000-4000-8000-000000000010',
  clock_timestamp()+interval '30 minutes'),
 ('daba0000-0000-4000-8000-000000000589',
  encode(public.digest('m37462-ci-only-foreign-bearer-NEVER-REAL-03','sha256'),'hex'),
  'daba0000-0000-4000-8000-000000000002',
  'TENANT_ADMIN','daba0000-0000-4000-8000-000000000020',
  clock_timestamp()+interval '30 minutes'),
 ('daba0000-0000-4000-8000-000000000590',
  encode(public.digest('m37462-ci-only-expired-bearer-NEVER-REAL-04','sha256'),'hex'),
  'daba0000-0000-4000-8000-000000000001',
  'TENANT_ADMIN','daba0000-0000-4000-8000-000000000010',
  clock_timestamp()-interval '1 second');

DO $m37462_permission_guard$
BEGIN
 IF has_table_privilege('frcaixinha_app_role','public.sessions','SELECT')
  OR has_column_privilege('frcaixinha_auth_token_ci',
     'public.sessions','token_hash','UPDATE')
  OR NOT has_column_privilege('frcaixinha_auth_token_ci',
     'public.sessions','id','SELECT')
  OR NOT has_function_privilege('frcaixinha_auth_token_ci',
     'public.auth_refresh_session(text)','EXECUTE')
  OR NOT has_function_privilege('frcaixinha_auth_token_ci',
     'public.auth_revoke_session(text)','EXECUTE')
 THEN RAISE EXCEPTION 'M37462_AUTH_ROLE_OR_SESSION_PRIVILEGES'; END IF;
END $m37462_permission_guard$;
COMMIT;
