-- FR CAIXINHA AI STUDIO M20700. ONLY local 043, never replay 001-042.
-- Existing 2027 R$100 contributions, policies and audit remain UNCHANGED.
DO $guard$
BEGIN
 IF NOT (
   (current_database()='frcaixinha_aistudio_dev'
    AND session_user='frc_ai_owner' AND current_user='frc_ai_owner'
    AND inet_server_port()=5433
    AND current_setting('data_directory')='/data/data/com.termux/files/usr/var/lib/frcaixinha_aistudio_pg18'
    AND current_setting('server_version_num')::int BETWEEN 180000 AND 189999)
   OR (current_database()='frcaixinha_ci'
       AND session_user='postgres'
       AND current_setting('is_superuser')='on'
       AND current_setting('frcaixinha.quota_floor_local_ci',true)='1')
 ) THEN RAISE EXCEPTION 'M20700 wrong PG18/CI environment'; END IF;
 IF (SELECT count(*) FROM pg_catalog.pg_tables WHERE schemaname='public')<>45
    OR to_regclass('public.cycle_contribution_price_audit') IS NULL
    OR to_regprocedure('public.cycle_price_change(text,uuid,uuid,bigint,text,uuid)') IS NULL
    OR to_regprocedure('public.cycle_price_change_legacy_m20400(text,uuid,uuid,bigint,text,uuid)') IS NOT NULL
 THEN RAISE EXCEPTION 'M20700 expected 45 table verified M042 baseline'; END IF;
END $guard$;

-- Remove silent R$100 defaults; require explicit quota values in all new policies.
ALTER TABLE public.policies ALTER COLUMN contribution_per_quota DROP DEFAULT;
ALTER TABLE public.quotas ALTER COLUMN value_brl DROP DEFAULT;

-- NOT VALID: historical data <R$150 remains readable and subject to review.
-- New inserts and any updates must meet R$150 minimum.
ALTER TABLE public.policies ADD CONSTRAINT policy_minimum_150_new
 CHECK (contribution_per_quota >= 150.00) NOT VALID;
ALTER TABLE public.quotas ADD CONSTRAINT quota_minimum_150_new
 CHECK (value_brl >= 150.00) NOT VALID;

-- Keep the signed PostgreSQL admin/session authorization from M042, but
-- replace the app-facing write entrypoint with an enforced R$150 floor.
ALTER FUNCTION public.cycle_price_change(text,uuid,uuid,bigint,text,uuid)
 RENAME TO cycle_price_change_legacy_m20400;
REVOKE ALL ON FUNCTION public.cycle_price_change_legacy_m20400(text,uuid,uuid,bigint,text,uuid)
 FROM PUBLIC,frcaixinha_app_role,frcaixinha_auth_role,frcaixinha_verifier_role;
CREATE FUNCTION public.cycle_price_change(
 p_raw_token text,p_tenant uuid,p_cycle uuid,p_amount_cents bigint,
 p_reason text,p_idempotency uuid
) RETURNS TABLE(change_status text,amount_cents bigint,request_id uuid)
LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,public,pg_temp AS $fn$
BEGIN
 IF p_amount_cents IS NULL OR p_amount_cents NOT BETWEEN 15000 AND 1000000 THEN
   RAISE EXCEPTION 'M20700 minimum R$150 per quota' USING ERRCODE='22023';
 END IF;
 RETURN QUERY SELECT x.change_status,x.amount_cents,x.request_id
 FROM public.cycle_price_change_legacy_m20400(
   p_raw_token,p_tenant,p_cycle,p_amount_cents,p_reason,p_idempotency) AS x;
END $fn$;
REVOKE ALL ON FUNCTION public.cycle_price_change(text,uuid,uuid,bigint,text,uuid)
 FROM PUBLIC,frcaixinha_auth_role,frcaixinha_verifier_role;
GRANT EXECUTE ON FUNCTION public.cycle_price_change(text,uuid,uuid,bigint,text,uuid)
 TO frcaixinha_app_role;

DO $post$
BEGIN
 IF (SELECT count(*) FROM pg_constraint WHERE conname IN
    ('policy_minimum_150_new','quota_minimum_150_new')
    AND NOT convalidated)<>2
    OR EXISTS(SELECT 1 FROM information_schema.columns
      WHERE table_schema='public' AND
       ((table_name='policies' AND column_name='contribution_per_quota')
       OR (table_name='quotas' AND column_name='value_brl'))
       AND column_default IS NOT NULL)
    OR has_function_privilege('frcaixinha_app_role',
     'public.cycle_price_change_legacy_m20400(text,uuid,uuid,bigint,text,uuid)','EXECUTE')
    OR NOT has_function_privilege('frcaixinha_app_role',
     'public.cycle_price_change(text,uuid,uuid,bigint,text,uuid)','EXECUTE')
 THEN RAISE EXCEPTION 'M20700 postguard did not confirm minimum contract'; END IF;
END $post$;
