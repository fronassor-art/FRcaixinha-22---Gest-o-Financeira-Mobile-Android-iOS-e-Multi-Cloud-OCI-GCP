-- M37464: CI-ONLY token session lock and synthetic SaaS transition.
-- Disposable PostgreSQL, no product migration, no legal consent.
BEGIN;
DO $m37464_guard$
BEGIN
 IF current_database()<>'frcaixinha_staging'
  OR session_user<>'postgres'
  OR current_setting('is_superuser')<>'on'
  OR current_setting('frcaixinha.saas_atomic_ci',true) IS DISTINCT FROM '1'
  OR to_regclass('public.saas_preprep_sessions_m37458_ci') IS NULL
  OR to_regprocedure('public.m37458_transition_ci(text,uuid,uuid,uuid,uuid,uuid,uuid,uuid,text,text)') IS NULL
  OR to_regprocedure('public.auth_revoke_session(text)') IS NULL
  OR NOT EXISTS (
    SELECT 1 FROM pg_roles
    WHERE rolname='frcaixinha_saas_preprep_ci'
      AND NOT rolsuper AND NOT rolbypassrls
  )
  OR NOT EXISTS (
    SELECT 1 FROM pg_roles
    WHERE rolname='frcaixinha_auth_role'
      AND NOT rolsuper AND NOT rolbypassrls
  )
  OR EXISTS (
    SELECT 1 FROM pg_roles
    WHERE rolname='frcaixinha_auth_atomic_ci'
  )
 THEN RAISE EXCEPTION 'M37464_DISPOSABLE_POSTGRES_ONLY'; END IF;
END $m37464_guard$;

CREATE ROLE frcaixinha_auth_atomic_ci LOGIN INHERIT PASSWORD 'ci-test-only'
  NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION;
GRANT frcaixinha_auth_role TO frcaixinha_auth_atomic_ci;
GRANT CONNECT ON DATABASE frcaixinha_staging TO frcaixinha_auth_atomic_ci;

-- Two independent synthetic sessions, one for commit/replay/race, one
-- to prove that revocation strictly BEFORE issuance rejects all writes.
INSERT INTO public.sessions(
 id,token_hash,user_id,active_role,active_tenant_id,expires_at
) VALUES
 ('daba0000-0000-4000-8000-000000000664',
  encode(public.digest('m37464-ci-only-lock-session-NEVER-REAL-01','sha256'),'hex'),
  'daba0000-0000-4000-8000-000000000001',
  'TENANT_ADMIN','daba0000-0000-4000-8000-000000000010',
  clock_timestamp()+interval '40 minutes'),
 ('daba0000-0000-4000-8000-000000000665',
  encode(public.digest('m37464-ci-only-pre-revoked-NEVER-REAL-02','sha256'),'hex'),
  'daba0000-0000-4000-8000-000000000001',
  'TENANT_ADMIN','daba0000-0000-4000-8000-000000000010',
  clock_timestamp()+interval '40 minutes');
INSERT INTO public.saas_preprep_sessions_m37458_ci(
 session_id,tenant_id,admin_id,role,session_active,email_verified
) VALUES
 ('daba0000-0000-4000-8000-000000000664',
  'daba0000-0000-4000-8000-000000000010',
  'daba0000-0000-4000-8000-000000000001',
  'TENANT_ADMIN',true,true),
 ('daba0000-0000-4000-8000-000000000665',
  'daba0000-0000-4000-8000-000000000010',
  'daba0000-0000-4000-8000-000000000001',
  'TENANT_ADMIN',true,true);

-- The worker cannot see credentials, tokens or financial records. The
-- SECURITY DEFINER function alone can hold the session row lock, and
-- only in an exact isolated CI database with two explicit GUCs.
CREATE FUNCTION public.m37464_atomic_consent_ci(
 p_action text,p_token_hash text,p_session uuid,p_challenge uuid,
 p_request uuid,p_tenant uuid,p_admin uuid,p_document uuid,
 p_price uuid,p_period text,p_confirmation text
) RETURNS text LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,public,pg_temp AS $atomic$
DECLARE
 s record;
 v_result text;
BEGIN
 IF current_database()<>'frcaixinha_staging'
 OR session_user<>'frcaixinha_saas_preprep_ci'
 OR current_setting('frcaixinha.saas_atomic_ci',true) IS DISTINCT FROM '1'
 OR current_setting('frcaixinha.saas_preprep_ci',true) IS DISTINCT FROM '1'
 THEN RAISE EXCEPTION 'M37464_WORKER_DISPOSABLE_CI_ONLY'; END IF;
 IF p_action IS NULL OR p_action NOT IN ('ISSUE','ACCEPT','PREPARE')
 OR p_token_hash IS NULL OR p_token_hash !~ '^[0-9a-f]{64}$'
 OR p_session IS NULL OR p_challenge IS NULL OR p_request IS NULL
 OR p_tenant IS NULL OR p_admin IS NULL OR p_document IS NULL
 OR p_price IS NULL OR p_period NOT IN ('MONTHLY','ANNUAL')
 OR p_session='00000000-0000-0000-0000-000000000000'::uuid
 OR p_request='00000000-0000-0000-0000-000000000000'::uuid
 OR p_challenge='00000000-0000-0000-0000-000000000000'::uuid
 OR (p_action='ACCEPT' AND p_confirmation IS DISTINCT FROM
    'ACEITO_CONTRATO_DE_LICENCA_FR_FINANCE')
 OR (p_action<>'ACCEPT' AND p_confirmation IS NOT NULL)
 THEN RETURN 'DENIED_CI_INVALID_REQUEST'; END IF;

 -- CRITICAL: this is a row-level lock on canonical public.sessions.
 -- The token-bound revocation function updates the same row. At READ
 -- COMMITTED, a transaction waiting behind revocation reevaluates the
 -- predicate and finds revoked_at non-null; if consent wins, revocation
 -- waits for the whole consent transaction to commit/rollback first.
 SELECT s.id,s.user_id,s.active_role,s.active_tenant_id,s.expires_at,
        s.revoked_at
 INTO s
 FROM public.sessions s
 WHERE s.id=p_session AND s.token_hash=p_token_hash
   AND s.user_id=p_admin AND s.active_tenant_id=p_tenant
   AND s.active_role='TENANT_ADMIN'
   AND s.revoked_at IS NULL AND s.expires_at>clock_timestamp()
 FOR UPDATE OF s;
 IF NOT FOUND OR s.revoked_at IS NOT NULL OR s.expires_at<=clock_timestamp()
 OR NOT EXISTS(
   SELECT 1 FROM public.users u
   WHERE u.id=p_admin AND u.status='ACTIVE' AND u.is_master=false
 ) OR NOT EXISTS(
   SELECT 1 FROM public.tenants t
   WHERE t.id=p_tenant AND t.admin_user_id=p_admin AND t.status='ATIVO'
 ) OR NOT EXISTS(
   SELECT 1 FROM public.memberships m
   WHERE m.tenant_id=p_tenant AND m.user_id=p_admin
   AND m.role='TENANT_ADMIN' AND m.status='ATIVA'
 )
 THEN RETURN 'DENIED_CI_TOKEN_REVOKED_OR_SCOPE'; END IF;

 -- M37458 verifies the CURRENT published contract, pricing and
 -- challenge on every transition under the SAME transaction.
 v_result := public.m37458_transition_ci(
   p_action,p_session,p_challenge,p_request,
   p_tenant,p_admin,p_document,p_price,p_period,p_confirmation
 );
 RETURN v_result;
END $atomic$;

REVOKE ALL ON FUNCTION public.m37464_atomic_consent_ci(
 text,text,uuid,uuid,uuid,uuid,uuid,uuid,uuid,text,text
) FROM PUBLIC,frcaixinha_app_role,frcaixinha_auth_role,
       frcaixinha_auth_atomic_ci,frcaixinha_saas_preprep_ci;
GRANT EXECUTE ON FUNCTION public.m37464_atomic_consent_ci(
 text,text,uuid,uuid,uuid,uuid,uuid,uuid,uuid,text,text
) TO frcaixinha_saas_preprep_ci;

DO $privs$
BEGIN
 IF has_table_privilege('frcaixinha_app_role','public.sessions','SELECT')
 OR has_column_privilege('frcaixinha_saas_preprep_ci','public.sessions','token_hash','SELECT')
 OR NOT has_function_privilege('frcaixinha_saas_preprep_ci',
  'public.m37464_atomic_consent_ci(text,text,uuid,uuid,uuid,uuid,uuid,uuid,uuid,text,text)','EXECUTE')
 OR has_function_privilege('frcaixinha_auth_atomic_ci',
  'public.m37464_atomic_consent_ci(text,text,uuid,uuid,uuid,uuid,uuid,uuid,uuid,text,text)','EXECUTE')
 THEN RAISE EXCEPTION 'M37464_CI_ROLE_PRIVILEGE_ISOLATION'; END IF;
END $privs$;
COMMIT;
