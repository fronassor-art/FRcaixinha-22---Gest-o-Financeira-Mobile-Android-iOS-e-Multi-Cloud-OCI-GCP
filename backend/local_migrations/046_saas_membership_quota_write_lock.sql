-- FR FINANCE AI Studio M33900-M34300: protective write lock (CANDIDATE ONLY).
-- Never run on Termux 5433 or OCI/production without a reviewed migration plan.
-- This revokes generic app write access; it does NOT implement licensed admission.
BEGIN;
DO $guard$ BEGIN
  IF NOT (
    (current_database()='frcaixinha_ci' AND session_user='postgres'
      AND current_setting('frcaixinha.saas_write_lock_ci',true)='1')
    OR
    (current_database()='frcaixinha_aistudio_dev' AND session_user='frc_ai_owner'
      AND current_setting('frcaixinha.local_migration_046_approved',true)='1')
  ) THEN RAISE EXCEPTION 'M33900_WRITE_LOCK_MIGRATION_NOT_AUTHORIZED'; END IF;
END $guard$;

-- The 001 baseline broadly granted INSERT/UPDATE/DELETE. RLS alone does not
-- check SaaS licensing. Remove the independent, unsafe write path.
REVOKE INSERT,UPDATE,DELETE,TRUNCATE ON
  public.memberships,public.quotas
  FROM PUBLIC,frcaixinha_app_role,frcaixinha_auth_role,
       frcaixinha_verifier_role,frc_ai_app,frc_ai_auth;
ALTER TABLE public.memberships ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.memberships FORCE ROW LEVEL SECURITY;
ALTER TABLE public.quotas ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.quotas FORCE ROW LEVEL SECURITY;

-- Defence in depth: even if an app role can call an old SECURITY DEFINER
-- routine, the trigger evaluates SESSION_USER, not the definer CURRENT_USER.
-- Only isolated CI DBA and the dedicated local owner may write; neither
-- identity is a credential for a normal backend runtime.
CREATE FUNCTION public.saas_unlicensed_member_quota_guard()
RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER
SET search_path=pg_catalog,public,pg_temp AS $fn$
BEGIN
  IF (session_user='postgres' AND current_database()
        IN ('frcaixinha_ci','frcaixinha_staging'))
     OR (session_user='frc_ai_owner'
         AND current_database()='frcaixinha_aistudio_dev') THEN
    IF TG_OP='DELETE' THEN RETURN OLD; END IF;
    RETURN NEW;
  END IF;
  RAISE EXCEPTION 'M34300_MEMBER_QUOTA_WRITE_GATE_CLOSED'
    USING ERRCODE='42501';
END $fn$;
REVOKE ALL ON FUNCTION public.saas_unlicensed_member_quota_guard()
  FROM PUBLIC,frcaixinha_app_role,frcaixinha_auth_role,
       frcaixinha_verifier_role,frc_ai_app,frc_ai_auth;
CREATE TRIGGER memberships_unlicensed_write_lock
  BEFORE INSERT OR UPDATE OR DELETE ON public.memberships
  FOR EACH ROW EXECUTE FUNCTION public.saas_unlicensed_member_quota_guard();
CREATE TRIGGER quotas_unlicensed_write_lock
  BEFORE INSERT OR UPDATE OR DELETE ON public.quotas
  FOR EACH ROW EXECUTE FUNCTION public.saas_unlicensed_member_quota_guard();

DO $audit$ DECLARE role_name text; tbl text;
BEGIN
  FOREACH role_name IN ARRAY ARRAY[
   'frcaixinha_app_role','frcaixinha_auth_role',
   'frcaixinha_verifier_role','frc_ai_app','frc_ai_auth'
  ] LOOP
    FOREACH tbl IN ARRAY ARRAY['public.memberships','public.quotas'] LOOP
      IF has_table_privilege(role_name,tbl,'INSERT')
      OR has_table_privilege(role_name,tbl,'UPDATE')
      OR has_table_privilege(role_name,tbl,'DELETE')
      OR has_table_privilege(role_name,tbl,'TRUNCATE')
      THEN RAISE EXCEPTION 'M34100_UNSAFE_DIRECT_WRITE_PRIVILEGES: % %',
        role_name,tbl; END IF;
    END LOOP;
  END LOOP;
  IF NOT EXISTS (
    SELECT 1 FROM pg_class
    WHERE oid='public.memberships'::regclass
      AND relrowsecurity AND relforcerowsecurity
  ) OR NOT EXISTS (
    SELECT 1 FROM pg_class
    WHERE oid='public.quotas'::regclass
      AND relrowsecurity AND relforcerowsecurity
  ) THEN RAISE EXCEPTION 'M34200_RLS_NOT_FORCED'; END IF;
END $audit$;
COMMIT;
