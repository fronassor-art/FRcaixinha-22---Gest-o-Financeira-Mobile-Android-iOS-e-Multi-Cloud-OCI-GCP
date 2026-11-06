-- M23600: OCI staging ONLY. Token metadata CAS; never real secrets.
-- Run only on isolated frcaixinha_staging with explicit DBA authorization.
-- Absolutely never execute in Termux PG5433, production or live tenant DB.
BEGIN;
DO $guard$
BEGIN
 IF current_database()<>'frcaixinha_staging'
   OR current_setting('frcaixinha.mp_oauth_staging_authorized',true) IS DISTINCT FROM '1'
   OR current_setting('is_superuser')<>'on'
   OR NOT EXISTS (SELECT 1 FROM pg_roles
      WHERE rolname='frcaixinha_mp_oauth_worker'
        AND NOT rolsuper AND NOT rolbypassrls AND NOT rolcreatedb AND NOT rolcreaterole)
 THEN RAISE EXCEPTION 'M23600 DENIED: staging DBA, role and flag required';
 END IF;
END $guard$;

-- Consent is DBA-seeded only in CI. A production consent issuer, with
-- authenticated tenant administrator, has NOT been implemented.
CREATE TABLE public.mp_oauth_seller_consents_staging (
 tenant_id uuid NOT NULL REFERENCES public.tenants(id) ON DELETE RESTRICT,
 actor_user_id uuid NOT NULL REFERENCES public.users(id) ON DELETE RESTRICT,
 seller_id varchar(40) NOT NULL UNIQUE CHECK(seller_id ~ '^[0-9]{1,40}$'),
 consent_version varchar(128) NOT NULL
     CHECK (consent_version ~ '^[A-Za-z0-9._:-]{8,128}$'),
 approved_at timestamptz NOT NULL,
 revoked_at timestamptz,
 generation bigint NOT NULL DEFAULT 0 CHECK (generation>=0),
 active_revision varchar(128),
 PRIMARY KEY(tenant_id,seller_id),
 CHECK (revoked_at IS NULL OR revoked_at>=approved_at)
);

-- Only protected credential *references* and SHA-256 fingerprints.
-- No OAuth access/refresh tokens, provider code, PKCE or Pix data.
CREATE TABLE public.mp_oauth_token_revisions_staging (
 revision varchar(128) PRIMARY KEY
    CHECK(revision ~ '^[A-Za-z0-9._:-]{16,128}$'),
 tenant_id uuid NOT NULL,
 actor_user_id uuid NOT NULL REFERENCES public.users(id) ON DELETE RESTRICT,
 seller_id varchar(40) NOT NULL,
 credential_ref varchar(512) NOT NULL
    CHECK(credential_ref ~ '^[A-Za-z0-9._:/-]+$'
      AND char_length(credential_ref) BETWEEN 16 AND 512),
 expected_generation bigint NOT NULL CHECK(expected_generation>=0),
 access_sha256 char(64) CHECK(access_sha256 ~ '^[a-f0-9]{64}$'),
 refresh_sha256 char(64) CHECK(refresh_sha256 ~ '^[a-f0-9]{64}$'),
 status varchar(12) NOT NULL DEFAULT 'PENDING'
    CHECK(status IN ('PENDING','ACTIVE','RETIRED','FAILED')),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 activated_at timestamptz,
 FOREIGN KEY(tenant_id,seller_id)
   REFERENCES public.mp_oauth_seller_consents_staging(tenant_id,seller_id)
   ON DELETE RESTRICT,
 CHECK ((status='ACTIVE' AND access_sha256 IS NOT NULL
         AND refresh_sha256 IS NOT NULL AND activated_at IS NOT NULL)
        OR status<>'ACTIVE')
);
CREATE UNIQUE INDEX mp_oauth_only_one_active_staging
 ON public.mp_oauth_token_revisions_staging(tenant_id,seller_id)
 WHERE status='ACTIVE';
CREATE INDEX mp_oauth_revision_lookup_staging
 ON public.mp_oauth_token_revisions_staging(tenant_id,seller_id,created_at DESC);

ALTER TABLE public.mp_oauth_seller_consents_staging ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.mp_oauth_seller_consents_staging FORCE ROW LEVEL SECURITY;
ALTER TABLE public.mp_oauth_token_revisions_staging ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.mp_oauth_token_revisions_staging FORCE ROW LEVEL SECURITY;
REVOKE ALL ON public.mp_oauth_seller_consents_staging,
 public.mp_oauth_token_revisions_staging
 FROM PUBLIC,frcaixinha_mp_oauth_worker,frcaixinha_app_role,
 frcaixinha_auth_role,frcaixinha_verifier_role,
 frcaixinha_mp_webhook_ingest,frcaixinha_mp_financial_worker;

CREATE FUNCTION public.mp_staging_oauth_eligible(
 p_tenant uuid,p_actor uuid,p_seller varchar
) RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,public,pg_temp AS $fn$
DECLARE is_valid boolean;
BEGIN
 IF current_database()<>'frcaixinha_staging'
    OR session_user<>'frcaixinha_mp_oauth_worker' THEN
    RAISE EXCEPTION 'M23600 DENIED: worker identity';
 END IF;
 SELECT EXISTS(
   SELECT 1 FROM public.mp_oauth_seller_consents_staging c
   JOIN public.memberships m
    ON m.tenant_id=c.tenant_id AND m.user_id=c.actor_user_id
   WHERE c.tenant_id=p_tenant AND c.actor_user_id=p_actor
    AND c.seller_id=p_seller AND c.revoked_at IS NULL
    AND m.role='TENANT_ADMIN' AND m.status='ATIVA'
 ) INTO is_valid;
 RETURN is_valid;
END $fn$;

CREATE FUNCTION public.mp_staging_oauth_stage(
 p_tenant uuid,p_actor uuid,p_seller varchar,
 p_revision varchar,p_ref varchar,p_expected_generation bigint
) RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,public,pg_temp AS $fn$
DECLARE c public.mp_oauth_seller_consents_staging%ROWTYPE;
BEGIN
 IF current_database()<>'frcaixinha_staging'
    OR session_user<>'frcaixinha_mp_oauth_worker' THEN
    RAISE EXCEPTION 'M23600 DENIED: worker identity';
 END IF;
 IF p_tenant IS NULL OR p_actor IS NULL OR p_seller IS NULL
   OR p_seller !~ '^[0-9]{1,40}$'
   OR p_revision IS NULL OR p_revision !~ '^[A-Za-z0-9._:-]{16,128}$'
   OR p_ref IS NULL OR p_ref !~ '^[A-Za-z0-9._:/-]+$'
   OR char_length(p_ref) NOT BETWEEN 16 AND 512
   OR p_expected_generation IS NULL OR p_expected_generation<0 THEN
   RETURN false;
 END IF;
 SELECT * INTO c FROM public.mp_oauth_seller_consents_staging
  WHERE tenant_id=p_tenant AND seller_id=p_seller FOR SHARE;
 IF NOT FOUND OR c.actor_user_id<>p_actor OR c.revoked_at IS NOT NULL
    OR c.generation<>p_expected_generation
    OR NOT EXISTS (
       SELECT 1 FROM public.memberships m
       WHERE m.tenant_id=p_tenant AND m.user_id=p_actor
         AND m.role='TENANT_ADMIN' AND m.status='ATIVA'
    ) THEN RETURN false;
 END IF;
 INSERT INTO public.mp_oauth_token_revisions_staging(
   revision,tenant_id,actor_user_id,seller_id,credential_ref,expected_generation
 ) VALUES (
   p_revision,p_tenant,p_actor,p_seller,p_ref,p_expected_generation
 );
 RETURN true;
END $fn$;

CREATE FUNCTION public.mp_staging_oauth_activate(
 p_tenant uuid,p_actor uuid,p_seller varchar,p_revision varchar,
 p_access_hash text,p_refresh_hash text
) RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,public,pg_temp AS $fn$
DECLARE c public.mp_oauth_seller_consents_staging%ROWTYPE;
 r public.mp_oauth_token_revisions_staging%ROWTYPE;
BEGIN
 IF current_database()<>'frcaixinha_staging'
    OR session_user<>'frcaixinha_mp_oauth_worker' THEN
   RAISE EXCEPTION 'M23600 DENIED: worker identity';
 END IF;
 IF p_tenant IS NULL OR p_actor IS NULL OR p_seller IS NULL
    OR p_revision IS NULL OR p_access_hash IS NULL OR p_refresh_hash IS NULL
    OR p_access_hash !~ '^[a-f0-9]{64}$'
    OR p_refresh_hash !~ '^[a-f0-9]{64}$' THEN
   RETURN false;
 END IF;
 -- The consent row lock serializes changes of active revisions.
 SELECT * INTO c FROM public.mp_oauth_seller_consents_staging
   WHERE tenant_id=p_tenant AND seller_id=p_seller FOR UPDATE;
 IF NOT FOUND OR c.actor_user_id<>p_actor OR c.revoked_at IS NOT NULL
    OR NOT EXISTS (
      SELECT 1 FROM public.memberships m
      WHERE m.tenant_id=p_tenant AND m.user_id=p_actor
       AND m.role='TENANT_ADMIN' AND m.status='ATIVA'
    ) THEN RETURN false;
 END IF;
 SELECT * INTO r FROM public.mp_oauth_token_revisions_staging
  WHERE revision=p_revision FOR UPDATE;
 IF NOT FOUND OR r.tenant_id<>p_tenant OR r.actor_user_id<>p_actor
    OR r.seller_id<>p_seller OR r.status<>'PENDING'
    OR r.expected_generation<>c.generation THEN
   RETURN false;
 END IF;
 UPDATE public.mp_oauth_token_revisions_staging
   SET status='RETIRED'
   WHERE tenant_id=p_tenant AND seller_id=p_seller AND status='ACTIVE';
 UPDATE public.mp_oauth_token_revisions_staging
   SET status='ACTIVE',access_sha256=p_access_hash,
       refresh_sha256=p_refresh_hash,activated_at=clock_timestamp()
   WHERE revision=p_revision;
 UPDATE public.mp_oauth_seller_consents_staging
   SET generation=generation+1,active_revision=p_revision
   WHERE tenant_id=p_tenant AND seller_id=p_seller;
 RETURN true;
END $fn$;

CREATE FUNCTION public.mp_staging_oauth_fail_pending(
 p_tenant uuid,p_actor uuid,p_seller varchar,p_revision varchar
) RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,public,pg_temp AS $fn$
BEGIN
 IF current_database()<>'frcaixinha_staging'
    OR session_user<>'frcaixinha_mp_oauth_worker' THEN
   RAISE EXCEPTION 'M23600 DENIED: worker identity';
 END IF;
 UPDATE public.mp_oauth_token_revisions_staging
  SET status='FAILED'
  WHERE tenant_id=p_tenant AND actor_user_id=p_actor
    AND seller_id=p_seller AND revision=p_revision AND status='PENDING';
 RETURN FOUND;
END $fn$;

CREATE FUNCTION public.mp_staging_oauth_active_ref(
 p_tenant uuid,p_actor uuid,p_seller varchar
) RETURNS varchar
LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,public,pg_temp AS $fn$
DECLARE ref varchar(512);
BEGIN
 IF current_database()<>'frcaixinha_staging'
    OR session_user<>'frcaixinha_mp_oauth_worker' THEN
   RAISE EXCEPTION 'M23600 DENIED: worker identity';
 END IF;
 SELECT r.credential_ref INTO ref
  FROM public.mp_oauth_seller_consents_staging c
  JOIN public.mp_oauth_token_revisions_staging r
   ON r.revision=c.active_revision AND r.tenant_id=c.tenant_id
     AND r.seller_id=c.seller_id AND r.status='ACTIVE'
  JOIN public.memberships m
   ON m.tenant_id=c.tenant_id AND m.user_id=c.actor_user_id
  WHERE c.tenant_id=p_tenant AND c.actor_user_id=p_actor
    AND c.seller_id=p_seller AND c.revoked_at IS NULL
    AND m.role='TENANT_ADMIN' AND m.status='ATIVA';
 RETURN ref;
END $fn$;

REVOKE ALL ON FUNCTION
 public.mp_staging_oauth_eligible(uuid,uuid,varchar),
 public.mp_staging_oauth_stage(uuid,uuid,varchar,varchar,varchar,bigint),
 public.mp_staging_oauth_activate(uuid,uuid,varchar,varchar,text,text),
 public.mp_staging_oauth_fail_pending(uuid,uuid,varchar,varchar),
 public.mp_staging_oauth_active_ref(uuid,uuid,varchar)
 FROM PUBLIC,frcaixinha_app_role,frcaixinha_auth_role,
 frcaixinha_verifier_role,frcaixinha_mp_webhook_ingest,
 frcaixinha_mp_financial_worker,frcaixinha_mp_oauth_worker;
GRANT EXECUTE ON FUNCTION
 public.mp_staging_oauth_eligible(uuid,uuid,varchar),
 public.mp_staging_oauth_stage(uuid,uuid,varchar,varchar,varchar,bigint),
 public.mp_staging_oauth_activate(uuid,uuid,varchar,varchar,text,text),
 public.mp_staging_oauth_fail_pending(uuid,uuid,varchar,varchar),
 public.mp_staging_oauth_active_ref(uuid,uuid,varchar)
 TO frcaixinha_mp_oauth_worker;
COMMIT;
