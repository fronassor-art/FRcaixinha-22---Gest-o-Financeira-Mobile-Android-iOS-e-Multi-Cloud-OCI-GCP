-- AI Studio M23200: pre-OAuth state ledger for dedicated OCI staging only.
-- No real token, verifier or refresh secret may be stored in this table.
-- Never execute in Termux PostgreSQL 5433 or production.
BEGIN;
DO $guard$
BEGIN
 IF current_database()<>'frcaixinha_staging'
    OR current_setting('frcaixinha.mp_oauth_staging_authorized',true) IS DISTINCT FROM '1'
    OR current_setting('is_superuser')<>'on'
    OR NOT EXISTS (
      SELECT 1 FROM pg_roles
      WHERE rolname='frcaixinha_mp_oauth_worker'
      AND NOT rolsuper AND NOT rolbypassrls
      AND NOT rolcreatedb AND NOT rolcreaterole
    ) THEN
   RAISE EXCEPTION 'M23200 DENIED: dedicated OCI staging DBA required';
 END IF;
END $guard$;

CREATE TABLE public.mp_oauth_attempts_staging (
 attempt_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 tenant_id uuid NOT NULL REFERENCES public.tenants(id) ON DELETE RESTRICT,
 actor_user_id uuid NOT NULL REFERENCES public.users(id) ON DELETE RESTRICT,
 state_sha256 char(64) NOT NULL UNIQUE
    CHECK (state_sha256 ~ '^[a-f0-9]{64}$'),
 redirect_sha256 char(64) NOT NULL
    CHECK (redirect_sha256 ~ '^[a-f0-9]{64}$'),
 pkce_challenge varchar(128) NOT NULL
    CHECK (pkce_challenge ~ '^[A-Za-z0-9_-]{43,128}$'),
 pkce_verifier_secret_ocid text NOT NULL
    CHECK (pkce_verifier_secret_ocid ~ '^ocid1[.]secret[.][A-Za-z0-9._-]+
 client_id varchar(40) NOT NULL CHECK (client_id ~ '^[0-9]{1,40}$'),
 redirect_uri text NOT NULL CHECK (
    redirect_uri ~ '^https://[A-Za-z0-9.-]{4,250}/[^?#]{1,250}$'
    AND char_length(redirect_uri)<=512
 ),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 expires_at timestamptz NOT NULL,
 consumed_at timestamptz,
 source varchar(64) NOT NULL DEFAULT 'SANDBOX_OAUTH_NOT_CONNECTED'
    CHECK (source='SANDBOX_OAUTH_NOT_CONNECTED'),
 CHECK (expires_at>created_at AND expires_at<=created_at+interval '10 minutes'),
 CHECK (consumed_at IS NULL OR consumed_at>=created_at)
);
CREATE INDEX mp_oauth_attempts_staging_actor
 ON public.mp_oauth_attempts_staging(tenant_id,actor_user_id,expires_at DESC);

ALTER TABLE public.mp_oauth_attempts_staging ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.mp_oauth_attempts_staging FORCE ROW LEVEL SECURITY;
REVOKE ALL ON public.mp_oauth_attempts_staging
 FROM PUBLIC,frcaixinha_app_role,frcaixinha_auth_role,
 frcaixinha_verifier_role,frcaixinha_mp_oauth_worker,
 frcaixinha_mp_webhook_ingest,frcaixinha_mp_financial_worker;

CREATE FUNCTION public.mp_staging_oauth_begin(
 p_tenant uuid,p_actor uuid,p_state_sha text,p_redirect_sha text,
 p_challenge text,p_verifier_secret_ocid text,p_client text,
 p_redirect_uri text,p_ttl_seconds integer
) RETURNS uuid
LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,public,pg_temp AS $fn$
DECLARE v_attempt uuid; v_start timestamptz;
BEGIN
 IF current_database()<>'frcaixinha_staging'
    OR session_user<>'frcaixinha_mp_oauth_worker'
    OR p_tenant IS NULL OR p_actor IS NULL
    OR p_state_sha IS NULL OR p_state_sha !~ '^[a-f0-9]{64}$'
    OR p_redirect_sha IS NULL OR p_redirect_sha !~ '^[a-f0-9]{64}$'
    OR p_challenge IS NULL OR p_challenge !~ '^[A-Za-z0-9_-]{43,128}$'
    OR p_verifier_secret_ocid IS NULL
    OR p_verifier_secret_ocid !~ '^ocid1[.]secret[.][A-Za-z0-9._-]+
    OR p_client IS NULL OR p_client !~ '^[0-9]{1,40}$'
    OR p_redirect_uri IS NULL OR p_redirect_uri !~
       '^https://[A-Za-z0-9.-]{4,250}/[^?#]{1,250}$'
    OR char_length(p_redirect_uri)>512
    OR p_ttl_seconds IS NULL OR p_ttl_seconds NOT BETWEEN 1 AND 600
    OR NOT EXISTS (
      SELECT 1 FROM public.memberships m
      WHERE m.tenant_id=p_tenant AND m.user_id=p_actor
       AND m.role='TENANT_ADMIN' AND m.status='ATIVA'
    ) THEN
    RAISE EXCEPTION 'M23200 DENIED: invalid OAuth admin or attempt';
 END IF;
 v_start:=clock_timestamp();
 INSERT INTO public.mp_oauth_attempts_staging(
   tenant_id,actor_user_id,state_sha256,redirect_sha256,pkce_challenge,
   pkce_verifier_secret_ocid,client_id,redirect_uri,created_at,expires_at
 ) VALUES(
   p_tenant,p_actor,p_state_sha,p_redirect_sha,p_challenge,
   p_verifier_secret_ocid,p_client,p_redirect_uri,v_start,
   v_start+make_interval(secs=>p_ttl_seconds)
 ) RETURNING attempt_id INTO v_attempt;
 RETURN v_attempt;
END $fn$;

-- The only permitted read is an atomic UPDATE/RETURNING after matching
-- state, tenant, actor and redirect. No plaintext verifier or token in DB.
CREATE FUNCTION public.mp_staging_oauth_consume(
 p_tenant uuid,p_actor uuid,p_state_sha text,p_redirect_sha text
) RETURNS TABLE(
 client_id varchar(40),
 redirect_uri text,
 pkce_verifier_secret_ocid text,
 pkce_challenge varchar(128),
 created_at timestamptz
)
LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,public,pg_temp AS $fn$
BEGIN
 IF current_database()<>'frcaixinha_staging'
    OR session_user<>'frcaixinha_mp_oauth_worker'
    OR p_tenant IS NULL OR p_actor IS NULL
    OR p_state_sha IS NULL OR p_state_sha !~ '^[a-f0-9]{64}$'
    OR p_redirect_sha IS NULL OR p_redirect_sha !~ '^[a-f0-9]{64}$' THEN
    RAISE EXCEPTION 'M23200 DENIED: consume invalid context';
 END IF;
 RETURN QUERY
 UPDATE public.mp_oauth_attempts_staging a
 SET consumed_at=clock_timestamp()
 WHERE a.tenant_id=p_tenant AND a.actor_user_id=p_actor
   AND a.state_sha256=p_state_sha AND a.redirect_sha256=p_redirect_sha
   AND a.consumed_at IS NULL AND a.expires_at>clock_timestamp()
 RETURNING a.client_id,a.redirect_uri,a.pkce_verifier_secret_ocid,
           a.pkce_challenge,a.created_at;
END $fn$;

REVOKE ALL ON FUNCTION
 public.mp_staging_oauth_begin(uuid,uuid,text,text,text,text,text,text,integer),
 public.mp_staging_oauth_consume(uuid,uuid,text,text)
 FROM PUBLIC,frcaixinha_app_role,frcaixinha_auth_role,
 frcaixinha_verifier_role,frcaixinha_mp_webhook_ingest,
 frcaixinha_mp_financial_worker,frcaixinha_mp_oauth_worker;
GRANT EXECUTE ON FUNCTION
 public.mp_staging_oauth_begin(uuid,uuid,text,text,text,text,text,text,integer),
 public.mp_staging_oauth_consume(uuid,uuid,text,text)
 TO frcaixinha_mp_oauth_worker;
COMMIT;

       AND char_length(pkce_verifier_secret_ocid) BETWEEN 21 AND 525),
 client_id varchar(40) NOT NULL CHECK (client_id ~ '^[0-9]{1,40}$'),
 redirect_uri text NOT NULL CHECK (
    redirect_uri ~ '^https://[A-Za-z0-9.-]{4,250}/[^?#]{1,250}$'
    AND char_length(redirect_uri)<=512
 ),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 expires_at timestamptz NOT NULL,
 consumed_at timestamptz,
 source varchar(64) NOT NULL DEFAULT 'SANDBOX_OAUTH_NOT_CONNECTED'
    CHECK (source='SANDBOX_OAUTH_NOT_CONNECTED'),
 CHECK (expires_at>created_at AND expires_at<=created_at+interval '10 minutes'),
 CHECK (consumed_at IS NULL OR consumed_at>=created_at)
);
CREATE INDEX mp_oauth_attempts_staging_actor
 ON public.mp_oauth_attempts_staging(tenant_id,actor_user_id,expires_at DESC);

ALTER TABLE public.mp_oauth_attempts_staging ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.mp_oauth_attempts_staging FORCE ROW LEVEL SECURITY;
REVOKE ALL ON public.mp_oauth_attempts_staging
 FROM PUBLIC,frcaixinha_app_role,frcaixinha_auth_role,
 frcaixinha_verifier_role,frcaixinha_mp_oauth_worker,
 frcaixinha_mp_webhook_ingest,frcaixinha_mp_financial_worker;

CREATE FUNCTION public.mp_staging_oauth_begin(
 p_tenant uuid,p_actor uuid,p_state_sha text,p_redirect_sha text,
 p_challenge text,p_verifier_secret_ocid text,p_client text,
 p_redirect_uri text,p_ttl_seconds integer
) RETURNS uuid
LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,public,pg_temp AS $fn$
DECLARE v_attempt uuid; v_start timestamptz;
BEGIN
 IF current_database()<>'frcaixinha_staging'
    OR session_user<>'frcaixinha_mp_oauth_worker'
    OR p_tenant IS NULL OR p_actor IS NULL
    OR p_state_sha IS NULL OR p_state_sha !~ '^[a-f0-9]{64}$'
    OR p_redirect_sha IS NULL OR p_redirect_sha !~ '^[a-f0-9]{64}$'
    OR p_challenge IS NULL OR p_challenge !~ '^[A-Za-z0-9_-]{43,128}$'
    OR p_verifier_secret_ocid IS NULL
    OR p_verifier_secret_ocid !~ '^ocid1[.]secret[.][A-Za-z0-9._-]+$'
    OR p_client IS NULL OR p_client !~ '^[0-9]{1,40}$'
    OR p_redirect_uri IS NULL OR p_redirect_uri !~
       '^https://[A-Za-z0-9.-]{4,250}/[^?#]{1,250}$'
    OR char_length(p_redirect_uri)>512
    OR p_ttl_seconds IS NULL OR p_ttl_seconds NOT BETWEEN 1 AND 600
    OR NOT EXISTS (
      SELECT 1 FROM public.memberships m
      WHERE m.tenant_id=p_tenant AND m.user_id=p_actor
       AND m.role='TENANT_ADMIN' AND m.status='ATIVA'
    ) THEN
    RAISE EXCEPTION 'M23200 DENIED: invalid OAuth admin or attempt';
 END IF;
 v_start:=clock_timestamp();
 INSERT INTO public.mp_oauth_attempts_staging(
   tenant_id,actor_user_id,state_sha256,redirect_sha256,pkce_challenge,
   pkce_verifier_secret_ocid,client_id,redirect_uri,created_at,expires_at
 ) VALUES(
   p_tenant,p_actor,p_state_sha,p_redirect_sha,p_challenge,
   p_verifier_secret_ocid,p_client,p_redirect_uri,v_start,
   v_start+make_interval(secs=>p_ttl_seconds)
 ) RETURNING attempt_id INTO v_attempt;
 RETURN v_attempt;
END $fn$;

-- The only permitted read is an atomic UPDATE/RETURNING after matching
-- state, tenant, actor and redirect. No plaintext verifier or token in DB.
CREATE FUNCTION public.mp_staging_oauth_consume(
 p_tenant uuid,p_actor uuid,p_state_sha text,p_redirect_sha text
) RETURNS TABLE(
 client_id varchar(40),
 redirect_uri text,
 pkce_verifier_secret_ocid text,
 pkce_challenge varchar(128),
 created_at timestamptz
)
LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,public,pg_temp AS $fn$
BEGIN
 IF current_database()<>'frcaixinha_staging'
    OR session_user<>'frcaixinha_mp_oauth_worker'
    OR p_tenant IS NULL OR p_actor IS NULL
    OR p_state_sha IS NULL OR p_state_sha !~ '^[a-f0-9]{64}$'
    OR p_redirect_sha IS NULL OR p_redirect_sha !~ '^[a-f0-9]{64}$' THEN
    RAISE EXCEPTION 'M23200 DENIED: consume invalid context';
 END IF;
 RETURN QUERY
 UPDATE public.mp_oauth_attempts_staging a
 SET consumed_at=clock_timestamp()
 WHERE a.tenant_id=p_tenant AND a.actor_user_id=p_actor
   AND a.state_sha256=p_state_sha AND a.redirect_sha256=p_redirect_sha
   AND a.consumed_at IS NULL AND a.expires_at>clock_timestamp()
 RETURNING a.client_id,a.redirect_uri,a.pkce_verifier_secret_ocid,
           a.pkce_challenge,a.created_at;
END $fn$;

REVOKE ALL ON FUNCTION
 public.mp_staging_oauth_begin(uuid,uuid,text,text,text,text,text,text,integer),
 public.mp_staging_oauth_consume(uuid,uuid,text,text)
 FROM PUBLIC,frcaixinha_app_role,frcaixinha_auth_role,
 frcaixinha_verifier_role,frcaixinha_mp_webhook_ingest,
 frcaixinha_mp_financial_worker,frcaixinha_mp_oauth_worker;
GRANT EXECUTE ON FUNCTION
 public.mp_staging_oauth_begin(uuid,uuid,text,text,text,text,text,text,integer),
 public.mp_staging_oauth_consume(uuid,uuid,text,text)
 TO frcaixinha_mp_oauth_worker;
COMMIT;

    OR char_length(p_verifier_secret_ocid) NOT BETWEEN 21 AND 525
    OR p_client IS NULL OR p_client !~ '^[0-9]{1,40}$'
    OR p_redirect_uri IS NULL OR p_redirect_uri !~
       '^https://[A-Za-z0-9.-]{4,250}/[^?#]{1,250}$'
    OR char_length(p_redirect_uri)>512
    OR p_ttl_seconds IS NULL OR p_ttl_seconds NOT BETWEEN 1 AND 600
    OR NOT EXISTS (
      SELECT 1 FROM public.memberships m
      WHERE m.tenant_id=p_tenant AND m.user_id=p_actor
       AND m.role='TENANT_ADMIN' AND m.status='ATIVA'
    ) THEN
    RAISE EXCEPTION 'M23200 DENIED: invalid OAuth admin or attempt';
 END IF;
 v_start:=clock_timestamp();
 INSERT INTO public.mp_oauth_attempts_staging(
   tenant_id,actor_user_id,state_sha256,redirect_sha256,pkce_challenge,
   pkce_verifier_secret_ocid,client_id,redirect_uri,created_at,expires_at
 ) VALUES(
   p_tenant,p_actor,p_state_sha,p_redirect_sha,p_challenge,
   p_verifier_secret_ocid,p_client,p_redirect_uri,v_start,
   v_start+make_interval(secs=>p_ttl_seconds)
 ) RETURNING attempt_id INTO v_attempt;
 RETURN v_attempt;
END $fn$;

-- The only permitted read is an atomic UPDATE/RETURNING after matching
-- state, tenant, actor and redirect. No plaintext verifier or token in DB.
CREATE FUNCTION public.mp_staging_oauth_consume(
 p_tenant uuid,p_actor uuid,p_state_sha text,p_redirect_sha text
) RETURNS TABLE(
 client_id varchar(40),
 redirect_uri text,
 pkce_verifier_secret_ocid text,
 pkce_challenge varchar(128),
 created_at timestamptz
)
LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,public,pg_temp AS $fn$
BEGIN
 IF current_database()<>'frcaixinha_staging'
    OR session_user<>'frcaixinha_mp_oauth_worker'
    OR p_tenant IS NULL OR p_actor IS NULL
    OR p_state_sha IS NULL OR p_state_sha !~ '^[a-f0-9]{64}$'
    OR p_redirect_sha IS NULL OR p_redirect_sha !~ '^[a-f0-9]{64}$' THEN
    RAISE EXCEPTION 'M23200 DENIED: consume invalid context';
 END IF;
 RETURN QUERY
 UPDATE public.mp_oauth_attempts_staging a
 SET consumed_at=clock_timestamp()
 WHERE a.tenant_id=p_tenant AND a.actor_user_id=p_actor
   AND a.state_sha256=p_state_sha AND a.redirect_sha256=p_redirect_sha
   AND a.consumed_at IS NULL AND a.expires_at>clock_timestamp()
 RETURNING a.client_id,a.redirect_uri,a.pkce_verifier_secret_ocid,
           a.pkce_challenge,a.created_at;
END $fn$;

REVOKE ALL ON FUNCTION
 public.mp_staging_oauth_begin(uuid,uuid,text,text,text,text,text,text,integer),
 public.mp_staging_oauth_consume(uuid,uuid,text,text)
 FROM PUBLIC,frcaixinha_app_role,frcaixinha_auth_role,
 frcaixinha_verifier_role,frcaixinha_mp_webhook_ingest,
 frcaixinha_mp_financial_worker,frcaixinha_mp_oauth_worker;
GRANT EXECUTE ON FUNCTION
 public.mp_staging_oauth_begin(uuid,uuid,text,text,text,text,text,text,integer),
 public.mp_staging_oauth_consume(uuid,uuid,text,text)
 TO frcaixinha_mp_oauth_worker;
COMMIT;

       AND char_length(pkce_verifier_secret_ocid) BETWEEN 21 AND 525),
 client_id varchar(40) NOT NULL CHECK (client_id ~ '^[0-9]{1,40}$'),
 redirect_uri text NOT NULL CHECK (
    redirect_uri ~ '^https://[A-Za-z0-9.-]{4,250}/[^?#]{1,250}$'
    AND char_length(redirect_uri)<=512
 ),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 expires_at timestamptz NOT NULL,
 consumed_at timestamptz,
 source varchar(64) NOT NULL DEFAULT 'SANDBOX_OAUTH_NOT_CONNECTED'
    CHECK (source='SANDBOX_OAUTH_NOT_CONNECTED'),
 CHECK (expires_at>created_at AND expires_at<=created_at+interval '10 minutes'),
 CHECK (consumed_at IS NULL OR consumed_at>=created_at)
);
CREATE INDEX mp_oauth_attempts_staging_actor
 ON public.mp_oauth_attempts_staging(tenant_id,actor_user_id,expires_at DESC);

ALTER TABLE public.mp_oauth_attempts_staging ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.mp_oauth_attempts_staging FORCE ROW LEVEL SECURITY;
REVOKE ALL ON public.mp_oauth_attempts_staging
 FROM PUBLIC,frcaixinha_app_role,frcaixinha_auth_role,
 frcaixinha_verifier_role,frcaixinha_mp_oauth_worker,
 frcaixinha_mp_webhook_ingest,frcaixinha_mp_financial_worker;

CREATE FUNCTION public.mp_staging_oauth_begin(
 p_tenant uuid,p_actor uuid,p_state_sha text,p_redirect_sha text,
 p_challenge text,p_verifier_secret_ocid text,p_client text,
 p_redirect_uri text,p_ttl_seconds integer
) RETURNS uuid
LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,public,pg_temp AS $fn$
DECLARE v_attempt uuid; v_start timestamptz;
BEGIN
 IF current_database()<>'frcaixinha_staging'
    OR session_user<>'frcaixinha_mp_oauth_worker'
    OR p_tenant IS NULL OR p_actor IS NULL
    OR p_state_sha IS NULL OR p_state_sha !~ '^[a-f0-9]{64}$'
    OR p_redirect_sha IS NULL OR p_redirect_sha !~ '^[a-f0-9]{64}$'
    OR p_challenge IS NULL OR p_challenge !~ '^[A-Za-z0-9_-]{43,128}$'
    OR p_verifier_secret_ocid IS NULL
    OR p_verifier_secret_ocid !~ '^ocid1[.]secret[.][A-Za-z0-9._-]+$'
    OR p_client IS NULL OR p_client !~ '^[0-9]{1,40}$'
    OR p_redirect_uri IS NULL OR p_redirect_uri !~
       '^https://[A-Za-z0-9.-]{4,250}/[^?#]{1,250}$'
    OR char_length(p_redirect_uri)>512
    OR p_ttl_seconds IS NULL OR p_ttl_seconds NOT BETWEEN 1 AND 600
    OR NOT EXISTS (
      SELECT 1 FROM public.memberships m
      WHERE m.tenant_id=p_tenant AND m.user_id=p_actor
       AND m.role='TENANT_ADMIN' AND m.status='ATIVA'
    ) THEN
    RAISE EXCEPTION 'M23200 DENIED: invalid OAuth admin or attempt';
 END IF;
 v_start:=clock_timestamp();
 INSERT INTO public.mp_oauth_attempts_staging(
   tenant_id,actor_user_id,state_sha256,redirect_sha256,pkce_challenge,
   pkce_verifier_secret_ocid,client_id,redirect_uri,created_at,expires_at
 ) VALUES(
   p_tenant,p_actor,p_state_sha,p_redirect_sha,p_challenge,
   p_verifier_secret_ocid,p_client,p_redirect_uri,v_start,
   v_start+make_interval(secs=>p_ttl_seconds)
 ) RETURNING attempt_id INTO v_attempt;
 RETURN v_attempt;
END $fn$;

-- The only permitted read is an atomic UPDATE/RETURNING after matching
-- state, tenant, actor and redirect. No plaintext verifier or token in DB.
CREATE FUNCTION public.mp_staging_oauth_consume(
 p_tenant uuid,p_actor uuid,p_state_sha text,p_redirect_sha text
) RETURNS TABLE(
 client_id varchar(40),
 redirect_uri text,
 pkce_verifier_secret_ocid text,
 pkce_challenge varchar(128),
 created_at timestamptz
)
LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,public,pg_temp AS $fn$
BEGIN
 IF current_database()<>'frcaixinha_staging'
    OR session_user<>'frcaixinha_mp_oauth_worker'
    OR p_tenant IS NULL OR p_actor IS NULL
    OR p_state_sha IS NULL OR p_state_sha !~ '^[a-f0-9]{64}$'
    OR p_redirect_sha IS NULL OR p_redirect_sha !~ '^[a-f0-9]{64}$' THEN
    RAISE EXCEPTION 'M23200 DENIED: consume invalid context';
 END IF;
 RETURN QUERY
 UPDATE public.mp_oauth_attempts_staging a
 SET consumed_at=clock_timestamp()
 WHERE a.tenant_id=p_tenant AND a.actor_user_id=p_actor
   AND a.state_sha256=p_state_sha AND a.redirect_sha256=p_redirect_sha
   AND a.consumed_at IS NULL AND a.expires_at>clock_timestamp()
 RETURNING a.client_id,a.redirect_uri,a.pkce_verifier_secret_ocid,
           a.pkce_challenge,a.created_at;
END $fn$;

REVOKE ALL ON FUNCTION
 public.mp_staging_oauth_begin(uuid,uuid,text,text,text,text,text,text,integer),
 public.mp_staging_oauth_consume(uuid,uuid,text,text)
 FROM PUBLIC,frcaixinha_app_role,frcaixinha_auth_role,
 frcaixinha_verifier_role,frcaixinha_mp_webhook_ingest,
 frcaixinha_mp_financial_worker,frcaixinha_mp_oauth_worker;
GRANT EXECUTE ON FUNCTION
 public.mp_staging_oauth_begin(uuid,uuid,text,text,text,text,text,text,integer),
 public.mp_staging_oauth_consume(uuid,uuid,text,text)
 TO frcaixinha_mp_oauth_worker;
COMMIT;
