-- M24200: worker-only proof that an opaque credential revision is FAILED.
-- Never apply to local Termux PG5433; disposable GitHub staging database ONLY.
BEGIN;
DO $guard$
BEGIN
 IF current_database()<>'frcaixinha_staging'
    OR current_setting('frcaixinha.mp_oauth_staging_authorized',true) IS DISTINCT FROM '1'
    OR current_setting('is_superuser')<>'on'
    OR NOT EXISTS(SELECT 1 FROM pg_roles
      WHERE rolname='frcaixinha_mp_oauth_worker'
       AND NOT rolsuper AND NOT rolbypassrls
       AND NOT rolcreatedb AND NOT rolcreaterole)
 THEN RAISE EXCEPTION 'M24200 DENIED: isolated staging DBA required';
 END IF;
END $guard$;

-- No protected reference may be reused for another revision, even if
-- another actor or tenant tried to provide the same opaque identifier.
CREATE UNIQUE INDEX mp_oauth_unique_credential_ref_staging
 ON public.mp_oauth_token_revisions_staging(credential_ref);

CREATE FUNCTION public.mp_staging_oauth_failed_ref(
 p_tenant uuid,p_actor uuid,p_seller varchar,p_revision varchar
) RETURNS varchar
LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,public,pg_temp AS $fn$
DECLARE failed_ref varchar(512);
BEGIN
 IF current_database()<>'frcaixinha_staging'
    OR session_user<>'frcaixinha_mp_oauth_worker' THEN
   RAISE EXCEPTION 'M24200 DENIED: worker identity';
 END IF;
 IF p_tenant IS NULL OR p_actor IS NULL OR p_seller IS NULL
    OR p_seller !~ '^[0-9]{1,40}$'
    OR p_revision IS NULL
    OR p_revision !~ '^[A-Za-z0-9._:-]{16,128}$' THEN
   RETURN NULL;
 END IF;
 SELECT r.credential_ref INTO failed_ref
 FROM public.mp_oauth_token_revisions_staging r
 WHERE r.tenant_id=p_tenant
   AND r.actor_user_id=p_actor
   AND r.seller_id=p_seller
   AND r.revision=p_revision
   AND r.status='FAILED'
   AND NOT EXISTS (
     SELECT 1 FROM public.mp_oauth_seller_consents_staging c
     WHERE c.tenant_id=p_tenant AND c.seller_id=p_seller
       AND c.active_revision=r.revision
   );
 RETURN failed_ref;
END $fn$;
REVOKE ALL ON FUNCTION public.mp_staging_oauth_failed_ref(uuid,uuid,varchar,varchar)
 FROM PUBLIC,frcaixinha_app_role,frcaixinha_auth_role,
 frcaixinha_verifier_role,frcaixinha_mp_webhook_ingest,
 frcaixinha_mp_financial_worker,frcaixinha_mp_oauth_worker;
GRANT EXECUTE ON FUNCTION public.mp_staging_oauth_failed_ref(uuid,uuid,varchar,varchar)
 TO frcaixinha_mp_oauth_worker;
COMMIT;
