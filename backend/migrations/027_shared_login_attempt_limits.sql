-- AI Studio 027: estado de limite de login compartilhado (HOMOLOGACAO/CI).
-- Nao aplicar no banco Termux; contas e dados de CI devem ser descartaveis.
CREATE TABLE public.auth_login_rate_limits (
 key_hash text PRIMARY KEY CHECK (key_hash ~ '^[0-9a-f]{64}$'),
 attempts integer NOT NULL DEFAULT 0 CHECK (attempts BETWEEN 0 AND 5),
 blocked_until timestamptz,
 updated_at timestamptz NOT NULL DEFAULT now()
);
REVOKE ALL ON public.auth_login_rate_limits
 FROM PUBLIC,frcaixinha_app_role,frcaixinha_auth_role,frcaixinha_verifier_role;
ALTER TABLE public.auth_login_rate_limits ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.auth_login_rate_limits FORCE ROW LEVEL SECURITY;

CREATE FUNCTION public.auth_login_rate_check(p_key text)
RETURNS integer LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,public,pg_temp AS $$
DECLARE v_until timestamptz;
BEGIN
 IF p_key IS NULL OR p_key !~ '^[0-9a-f]{64}$' THEN RETURN -1; END IF;
 SELECT blocked_until INTO v_until FROM public.auth_login_rate_limits
 WHERE key_hash=p_key;
 IF v_until IS NOT NULL AND v_until>clock_timestamp() THEN
  RETURN GREATEST(1,CEIL(EXTRACT(EPOCH FROM
    (v_until-clock_timestamp())))::integer);
 END IF;
 RETURN 0;
END $$;

CREATE FUNCTION public.auth_login_rate_failure(p_key text)
RETURNS integer LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,public,pg_temp AS $$
DECLARE v_attempts integer; v_until timestamptz; v_now timestamptz;
BEGIN
 IF p_key IS NULL OR p_key !~ '^[0-9a-f]{64}$' THEN RETURN -1; END IF;
 INSERT INTO public.auth_login_rate_limits(key_hash,attempts,updated_at)
 VALUES(p_key,0,clock_timestamp()) ON CONFLICT DO NOTHING;
 SELECT attempts,blocked_until INTO v_attempts,v_until
 FROM public.auth_login_rate_limits WHERE key_hash=p_key FOR UPDATE;
 v_now:=clock_timestamp();
 IF v_until IS NOT NULL AND v_until>v_now THEN
  RETURN GREATEST(1,CEIL(EXTRACT(EPOCH FROM (v_until-v_now)))::integer);
 END IF;
 IF v_until IS NOT NULL THEN v_attempts:=0; END IF;
 v_attempts:=LEAST(v_attempts+1,5);
 IF v_attempts=5 THEN v_until:=v_now+INTERVAL '60 seconds';
 ELSE v_until:=NULL; END IF;
 UPDATE public.auth_login_rate_limits
  SET attempts=v_attempts,blocked_until=v_until,updated_at=v_now
  WHERE key_hash=p_key;
 IF v_until IS NOT NULL THEN
   RETURN GREATEST(1,CEIL(EXTRACT(EPOCH FROM (v_until-v_now)))::integer);
 END IF;
 RETURN 0;
END $$;

CREATE FUNCTION public.auth_login_rate_success(p_key text)
RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,public,pg_temp AS $$
BEGIN
 IF p_key IS NULL OR p_key !~ '^[0-9a-f]{64}$' THEN RETURN false; END IF;
 DELETE FROM public.auth_login_rate_limits WHERE key_hash=p_key;
 RETURN true;
END $$;

REVOKE ALL ON FUNCTION public.auth_login_rate_check(text)
 FROM PUBLIC,frcaixinha_app_role,frcaixinha_verifier_role;
REVOKE ALL ON FUNCTION public.auth_login_rate_failure(text)
 FROM PUBLIC,frcaixinha_app_role,frcaixinha_verifier_role;
REVOKE ALL ON FUNCTION public.auth_login_rate_success(text)
 FROM PUBLIC,frcaixinha_app_role,frcaixinha_verifier_role;
GRANT EXECUTE ON FUNCTION public.auth_login_rate_check(text) TO frcaixinha_auth_role;
GRANT EXECUTE ON FUNCTION public.auth_login_rate_failure(text) TO frcaixinha_auth_role;
GRANT EXECUTE ON FUNCTION public.auth_login_rate_success(text) TO frcaixinha_auth_role;

DO $g$
BEGIN
 IF NOT EXISTS (SELECT 1 FROM pg_class WHERE
   oid='public.auth_login_rate_limits'::regclass AND relrowsecurity AND relforcerowsecurity)
   OR has_table_privilege('frcaixinha_auth_role','public.auth_login_rate_limits','SELECT')
   OR has_table_privilege('frcaixinha_app_role','public.auth_login_rate_limits','SELECT')
   OR has_function_privilege('frcaixinha_app_role','public.auth_login_rate_check(text)','EXECUTE')
   OR has_function_privilege('frcaixinha_verifier_role','public.auth_login_rate_check(text)','EXECUTE')
   OR NOT has_function_privilege('frcaixinha_auth_role','public.auth_login_rate_failure(text)','EXECUTE')
 THEN RAISE EXCEPTION 'BLOQUEADO: isolamento do limite de login'; END IF;
END $g$;
