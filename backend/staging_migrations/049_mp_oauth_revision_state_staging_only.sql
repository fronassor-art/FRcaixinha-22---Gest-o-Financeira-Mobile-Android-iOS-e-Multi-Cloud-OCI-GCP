-- M24300: inspect one exact OAuth revision state to recover from ambiguous ACK.
-- GitHub Actions disposable staging ONLY, never apply on Termux port 5433.
BEGIN;
DO $guard$
BEGIN
 IF current_database()<>'frcaixinha_staging'
    OR current_setting('frcaixinha.mp_oauth_staging_authorized',true) IS DISTINCT FROM '1'
    OR current_setting('is_superuser')<>'on'
    OR NOT EXISTS(SELECT 1 FROM pg_roles WHERE
      rolname='frcaixinha_mp_oauth_worker'
      AND NOT rolsuper AND NOT rolbypassrls
      AND NOT rolcreatedb AND NOT rolcreaterole)
 THEN RAISE EXCEPTION 'M24300 DENIED: isolated staging DBA required';
 END IF;
END $guard$;

-- Does NOT expose credential_ref, token fingerprints or secret material.
-- Returns state only when tenant/actor/seller/revision/reference all match.
-- Intentionally supports revocation recovery: revoked consent can make an
-- existing token unusable without changing its historical revision status.
CREATE FUNCTION public.mp_staging_oauth_revision_state(
 p_tenant uuid, p_actor uuid, p_seller varchar,
 p_revision varchar, p_ref varchar
) RETURNS varchar
LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,public,pg_temp AS $fn$
DECLARE revision_status varchar(12);
BEGIN
 IF current_database()<>'frcaixinha_staging'
    OR session_user<>'frcaixinha_mp_oauth_worker' THEN
   RAISE EXCEPTION 'M24300 DENIED: worker identity';
 END IF;
 IF p_tenant IS NULL OR p_actor IS NULL OR p_seller IS NULL
   OR p_seller !~ '^[0-9]{1,40}$'
   OR p_revision IS NULL OR p_revision !~ '^[A-Za-z0-9._:-]{16,128}$'
   OR p_ref IS NULL OR p_ref !~ '^[A-Za-z0-9._:/-]+$'
   OR char_length(p_ref) NOT BETWEEN 16 AND 512 THEN
  RETURN NULL;
 END IF;
 SELECT r.status INTO revision_status
 FROM public.mp_oauth_token_revisions_staging r
 WHERE r.tenant_id=p_tenant AND r.actor_user_id=p_actor
   AND r.seller_id=p_seller AND r.revision=p_revision
   AND r.credential_ref=p_ref;
 RETURN revision_status;
END $fn$;
REVOKE ALL ON FUNCTION
 public.mp_staging_oauth_revision_state(uuid,uuid,varchar,varchar,varchar)
 FROM PUBLIC,frcaixinha_app_role,frcaixinha_auth_role,
 frcaixinha_verifier_role,frcaixinha_mp_webhook_ingest,
 frcaixinha_mp_financial_worker,frcaixinha_mp_oauth_worker;
GRANT EXECUTE ON FUNCTION
 public.mp_staging_oauth_revision_state(uuid,uuid,varchar,varchar,varchar)
 TO frcaixinha_mp_oauth_worker;
COMMIT;
