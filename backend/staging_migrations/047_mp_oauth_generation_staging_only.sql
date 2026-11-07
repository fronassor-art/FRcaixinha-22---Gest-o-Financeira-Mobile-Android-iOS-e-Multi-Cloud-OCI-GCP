-- M23900: safe read of consent generation on isolated staging PostgreSQL.
-- GitHub disposable test only; never execute on Termux PostgreSQL 5433.
BEGIN;
DO $guard$
BEGIN
 IF current_database()<>'frcaixinha_staging'
    OR current_setting('frcaixinha.mp_oauth_staging_authorized',true) IS DISTINCT FROM '1'
    OR current_setting('is_superuser')<>'on'
    OR NOT EXISTS(SELECT 1 FROM pg_roles
       WHERE rolname='frcaixinha_mp_oauth_worker'
         AND NOT rolsuper AND NOT rolbypassrls
         AND NOT rolcreatedb AND NOT rolcreaterole) THEN
   RAISE EXCEPTION 'M23900 DENIED: isolated staging DBA authorization required';
 END IF;
END $guard$;

CREATE FUNCTION public.mp_staging_oauth_generation(
 p_tenant uuid,p_actor uuid,p_seller varchar
) RETURNS bigint
LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,public,pg_temp AS $fn$
DECLARE generation_number bigint;
BEGIN
 IF current_database()<>'frcaixinha_staging'
    OR session_user<>'frcaixinha_mp_oauth_worker'
    OR p_tenant IS NULL OR p_actor IS NULL OR p_seller IS NULL
    OR p_seller !~ '^[0-9]{1,40}$' THEN
   RAISE EXCEPTION 'M23900 DENIED: worker or subject mismatch';
 END IF;
 SELECT c.generation INTO generation_number
 FROM public.mp_oauth_seller_consents_staging c
 JOIN public.memberships m
   ON m.tenant_id=c.tenant_id AND m.user_id=c.actor_user_id
 WHERE c.tenant_id=p_tenant AND c.actor_user_id=p_actor
   AND c.seller_id=p_seller AND c.revoked_at IS NULL
   AND m.role='TENANT_ADMIN' AND m.status='ATIVA';
 RETURN generation_number;
END $fn$;

REVOKE ALL ON FUNCTION public.mp_staging_oauth_generation(uuid,uuid,varchar)
 FROM PUBLIC,frcaixinha_app_role,frcaixinha_auth_role,
 frcaixinha_verifier_role,frcaixinha_mp_webhook_ingest,
 frcaixinha_mp_financial_worker,frcaixinha_mp_oauth_worker;
GRANT EXECUTE ON FUNCTION public.mp_staging_oauth_generation(uuid,uuid,varchar)
 TO frcaixinha_mp_oauth_worker;
COMMIT;
