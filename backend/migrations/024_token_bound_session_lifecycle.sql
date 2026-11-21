-- AI Studio 024 — renovacao e revogacao vinculadas a token bruto.
-- Apenas codigo versionado; executar SOMENTE em CI descartavel nesta fase.
-- Nao aplicar migracoes no PostgreSQL do Termux sem autorizacao especifica.

-- O papel Auth deixa de poder estender ou revogar sessoes arbitrarias por SQL.
REVOKE UPDATE (expires_at, revoked_at) ON public.sessions
  FROM frcaixinha_auth_role;

CREATE FUNCTION public.auth_refresh_session(p_raw_token text)
RETURNS timestamptz
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, public, pg_temp
AS $$
DECLARE
  v_user_id uuid;
  v_role varchar;
  v_tenant uuid;
  v_expiry timestamptz;
  v_created timestamptz;
  v_master boolean;
  v_status varchar;
  v_valid boolean := false;
  v_new_expiry timestamptz;
BEGIN
  IF p_raw_token IS NULL OR length(p_raw_token) NOT BETWEEN 24 AND 512
  THEN RETURN NULL; END IF;

  SELECT s.user_id,s.active_role,s.active_tenant_id,s.expires_at,
         s.created_at,u.is_master,u.status
  INTO v_user_id,v_role,v_tenant,v_expiry,v_created,v_master,v_status
  FROM public.sessions s
  JOIN public.users u ON u.id=s.user_id
  WHERE s.token_hash=encode(public.digest(p_raw_token,'sha256'),'hex')
    AND s.revoked_at IS NULL
  FOR UPDATE OF s;

  IF NOT FOUND OR v_status <> 'ACTIVE' OR v_expiry <= NOW()
  THEN RETURN NULL; END IF;
  IF v_role='MASTER' AND v_tenant IS NULL THEN
    v_valid := v_master;
  ELSIF v_role IN ('TENANT_ADMIN','TENANT_MEMBER') AND v_tenant IS NOT NULL THEN
    SELECT EXISTS(
      SELECT 1 FROM public.memberships m
      JOIN public.tenants t ON t.id=m.tenant_id
      WHERE m.user_id=v_user_id AND m.tenant_id=v_tenant
        AND m.role=v_role AND m.status='ATIVA' AND t.status='ATIVO'
    ) INTO v_valid;
  END IF;

  IF NOT v_valid THEN RETURN NULL; END IF;
  UPDATE public.sessions
  SET expires_at=LEAST(NOW()+INTERVAL '15 minutes',
                       v_created+INTERVAL '8 hours')
  WHERE token_hash=encode(public.digest(p_raw_token,'sha256'),'hex')
    AND user_id=v_user_id AND revoked_at IS NULL AND expires_at>NOW()
  RETURNING expires_at INTO v_new_expiry;
  RETURN v_new_expiry;
END;
$$;

CREATE FUNCTION public.auth_revoke_session(p_raw_token text)
RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, public, pg_temp
AS $$
BEGIN
  IF p_raw_token IS NULL OR length(p_raw_token) NOT BETWEEN 24 AND 512
  THEN RETURN false; END IF;
  UPDATE public.sessions SET revoked_at=NOW()
  WHERE token_hash=encode(public.digest(p_raw_token,'sha256'),'hex')
    AND revoked_at IS NULL;
  RETURN FOUND;
END;
$$;

CREATE FUNCTION public.auth_revoke_all_sessions(p_raw_token text)
RETURNS integer
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, public, pg_temp
AS $$
DECLARE
  v_user_id uuid;
  v_status varchar;
  v_count integer;
BEGIN
  IF p_raw_token IS NULL OR length(p_raw_token) NOT BETWEEN 24 AND 512
  THEN RETURN -1; END IF;
  SELECT s.user_id,u.status INTO v_user_id,v_status
  FROM public.sessions s JOIN public.users u ON u.id=s.user_id
  WHERE s.token_hash=encode(public.digest(p_raw_token,'sha256'),'hex')
    AND s.revoked_at IS NULL AND s.expires_at>NOW()
  FOR UPDATE OF s;
  IF NOT FOUND OR v_status <> 'ACTIVE' THEN RETURN -1; END IF;
  UPDATE public.sessions SET revoked_at=NOW()
  WHERE user_id=v_user_id AND revoked_at IS NULL;
  GET DIAGNOSTICS v_count=ROW_COUNT;
  RETURN v_count;
END;
$$;

CREATE FUNCTION public.auth_revoke_owned_session(
  p_raw_token text, p_session_id uuid
)
RETURNS integer
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, public, pg_temp
AS $$
DECLARE
  v_user_id uuid;
  v_status varchar;
  v_target_hash varchar;
  v_own_hash text;
BEGIN
  -- Retorna 0 se nao encontrada, 1 para outra sessao propria,
  -- 2 para a sessao atual. Nunca indica existencia de sessao alheia.
  IF p_raw_token IS NULL OR length(p_raw_token) NOT BETWEEN 24 AND 512
    OR p_session_id IS NULL THEN
    RETURN 0;
  END IF;
  v_own_hash := encode(public.digest(p_raw_token,'sha256'),'hex');
  SELECT s.user_id,u.status INTO v_user_id,v_status
  FROM public.sessions s JOIN public.users u ON u.id=s.user_id
  WHERE s.token_hash=v_own_hash AND s.revoked_at IS NULL
    AND s.expires_at>NOW()
  FOR UPDATE OF s;
  IF NOT FOUND OR v_status <> 'ACTIVE' THEN RETURN 0; END IF;
  UPDATE public.sessions SET revoked_at=NOW()
  WHERE id=p_session_id AND user_id=v_user_id
    AND revoked_at IS NULL AND expires_at>NOW()
  RETURNING token_hash INTO v_target_hash;
  IF NOT FOUND THEN RETURN 0; END IF;
  IF v_target_hash=v_own_hash THEN RETURN 2; END IF;
  RETURN 1;
END;
$$;

REVOKE ALL ON FUNCTION public.auth_refresh_session(text) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.auth_revoke_session(text) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.auth_revoke_all_sessions(text) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.auth_revoke_owned_session(text,uuid) FROM PUBLIC;

GRANT EXECUTE ON FUNCTION public.auth_refresh_session(text) TO frcaixinha_auth_role;
GRANT EXECUTE ON FUNCTION public.auth_revoke_session(text) TO frcaixinha_auth_role;
GRANT EXECUTE ON FUNCTION public.auth_revoke_all_sessions(text) TO frcaixinha_auth_role;
GRANT EXECUTE ON FUNCTION public.auth_revoke_owned_session(text,uuid)
  TO frcaixinha_auth_role;

DO $guard$
BEGIN
  IF has_column_privilege('frcaixinha_auth_role','public.sessions','expires_at','UPDATE')
     OR has_column_privilege('frcaixinha_auth_role','public.sessions','revoked_at','UPDATE')
     OR has_function_privilege('frcaixinha_app_role','public.auth_refresh_session(text)','EXECUTE')
     OR has_function_privilege('frcaixinha_app_role','public.auth_revoke_all_sessions(text)','EXECUTE')
     OR NOT has_function_privilege('frcaixinha_auth_role','public.auth_refresh_session(text)','EXECUTE')
     OR NOT has_function_privilege('frcaixinha_auth_role','public.auth_revoke_session(text)','EXECUTE')
     OR NOT has_function_privilege('frcaixinha_auth_role','public.auth_revoke_all_sessions(text)','EXECUTE')
     OR NOT has_function_privilege('frcaixinha_auth_role','public.auth_revoke_owned_session(text,uuid)','EXECUTE')
  THEN
    RAISE EXCEPTION 'BLOQUEADO: renovacao/revogacao direta indevida';
  END IF;
END $guard$;
