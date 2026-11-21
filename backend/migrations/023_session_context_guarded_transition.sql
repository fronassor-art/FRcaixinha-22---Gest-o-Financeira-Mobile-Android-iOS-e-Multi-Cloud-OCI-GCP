-- AI Studio 023 — promoção e troca de contexto vinculadas ao token autenticado.
-- Arquivo VERSIONADO; usar APENAS PostgreSQL descartável no GitHub Actions.
-- Nunca aplicar no banco do Termux sem autorização específica.
--
-- A conta frcaixinha_auth_role perde UPDATE direto em active_role/active_tenant_id.
-- As duas mudanças devem passar por funções SECURITY DEFINER, com row lock,
-- token bruto validado por SHA-256, usuário ACTIVE e vínculo/papel verificados.
-- O login ainda cria PENDING_CONTEXT após conferir senha no FastAPI.
--
-- RISCO RESIDUAL: credencial técnica Auth comprometida ainda pode inserir
-- sessões PENDING_CONTEXT para identidades arbitrárias e invocar promoção;
-- a cadeia de emissão exige segregação independente antes de produção.

REVOKE UPDATE (active_role, active_tenant_id)
  ON public.sessions FROM frcaixinha_auth_role;

CREATE OR REPLACE FUNCTION public.auth_promote_pending_session(
  p_raw_token text, p_role varchar, p_tenant_id uuid
)
RETURNS timestamptz
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, public, pg_temp
AS $$
DECLARE
  v_user_id uuid;
  v_created_at timestamptz;
  v_expires_at timestamptz;
  v_is_master boolean;
  v_user_status varchar;
  v_allowed boolean := false;
  v_new_expiry timestamptz;
BEGIN
  IF p_raw_token IS NULL OR length(p_raw_token) NOT BETWEEN 24 AND 512 THEN
    RETURN NULL;
  END IF;

  SELECT s.user_id, s.created_at, s.expires_at, u.is_master, u.status
    INTO v_user_id, v_created_at, v_expires_at, v_is_master, v_user_status
  FROM public.sessions s
  JOIN public.users u ON u.id = s.user_id
  WHERE s.token_hash = encode(public.digest(p_raw_token, 'sha256'), 'hex')
    AND s.active_role = 'PENDING_CONTEXT'
    AND s.active_tenant_id IS NULL
    AND s.revoked_at IS NULL
  FOR UPDATE OF s;

  IF NOT FOUND OR v_user_status <> 'ACTIVE'
     OR v_expires_at <= NOW()
     OR v_expires_at > v_created_at + INTERVAL '2 minutes'
  THEN
    RETURN NULL;
  END IF;

  IF p_role = 'MASTER' AND p_tenant_id IS NULL THEN
    v_allowed := v_is_master;
  ELSIF p_role IN ('TENANT_ADMIN','TENANT_MEMBER') AND p_tenant_id IS NOT NULL THEN
    SELECT EXISTS (
      SELECT 1 FROM public.memberships m
      JOIN public.tenants t ON t.id = m.tenant_id
      WHERE m.user_id = v_user_id
        AND m.tenant_id = p_tenant_id
        AND m.role = p_role
        AND m.status = 'ATIVA'
        AND t.status = 'ATIVO'
    ) INTO v_allowed;
  END IF;

  IF NOT v_allowed THEN
    RETURN NULL;
  END IF;

  UPDATE public.sessions
  SET active_role = p_role,
      active_tenant_id = p_tenant_id,
      expires_at = LEAST(NOW() + INTERVAL '15 minutes',
                         v_created_at + INTERVAL '8 hours')
  WHERE token_hash = encode(public.digest(p_raw_token,'sha256'),'hex')
    AND user_id = v_user_id
    AND active_role = 'PENDING_CONTEXT'
    AND revoked_at IS NULL
    AND expires_at > NOW()
  RETURNING expires_at INTO v_new_expiry;

  RETURN v_new_expiry;
END;
$$;

REVOKE ALL ON FUNCTION public.auth_promote_pending_session(text,varchar,uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.auth_promote_pending_session(text,varchar,uuid)
  TO frcaixinha_auth_role;

CREATE OR REPLACE FUNCTION public.auth_switch_session_context(
  p_raw_token text, p_role varchar, p_tenant_id uuid
)
RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, public, pg_temp
AS $$
DECLARE
  v_user_id uuid;
  v_current_role varchar;
  v_current_tenant uuid;
  v_expiry timestamptz;
  v_revoked timestamptz;
  v_is_master boolean;
  v_user_status varchar;
  v_source_allowed boolean := false;
  v_target_allowed boolean := false;
BEGIN
  IF p_raw_token IS NULL OR length(p_raw_token) NOT BETWEEN 24 AND 512 THEN
    RETURN false;
  END IF;

  SELECT s.user_id,s.active_role,s.active_tenant_id,s.expires_at,
         s.revoked_at,u.is_master,u.status
    INTO v_user_id,v_current_role,v_current_tenant,v_expiry,
         v_revoked,v_is_master,v_user_status
  FROM public.sessions s
  JOIN public.users u ON u.id = s.user_id
  WHERE s.token_hash = encode(public.digest(p_raw_token,'sha256'),'hex')
  FOR UPDATE OF s;

  IF NOT FOUND OR v_revoked IS NOT NULL OR v_expiry <= NOW()
     OR v_user_status <> 'ACTIVE' THEN
    RETURN false;
  END IF;

  IF v_current_role = 'MASTER' AND v_current_tenant IS NULL THEN
    v_source_allowed := v_is_master;
  ELSIF v_current_role IN ('TENANT_ADMIN','TENANT_MEMBER')
        AND v_current_tenant IS NOT NULL THEN
    SELECT EXISTS (
      SELECT 1 FROM public.memberships m
      JOIN public.tenants t ON t.id = m.tenant_id
      WHERE m.user_id=v_user_id AND m.tenant_id=v_current_tenant
        AND m.role=v_current_role AND m.status='ATIVA' AND t.status='ATIVO'
    ) INTO v_source_allowed;
  END IF;

  IF NOT v_source_allowed THEN
    RETURN false;
  END IF;

  IF p_role = 'MASTER' AND p_tenant_id IS NULL THEN
    v_target_allowed := v_is_master;
  ELSIF p_role IN ('TENANT_ADMIN','TENANT_MEMBER')
        AND p_tenant_id IS NOT NULL THEN
    SELECT EXISTS (
      SELECT 1 FROM public.memberships m
      JOIN public.tenants t ON t.id = m.tenant_id
      WHERE m.user_id=v_user_id AND m.tenant_id=p_tenant_id
        AND m.role=p_role AND m.status='ATIVA' AND t.status='ATIVO'
    ) INTO v_target_allowed;
  END IF;

  IF NOT v_target_allowed THEN
    RETURN false;
  END IF;

  UPDATE public.sessions
  SET active_role=p_role,active_tenant_id=p_tenant_id
  WHERE token_hash=encode(public.digest(p_raw_token,'sha256'),'hex')
    AND user_id=v_user_id AND revoked_at IS NULL AND expires_at>NOW();
  RETURN FOUND;
END;
$$;

REVOKE ALL ON FUNCTION public.auth_switch_session_context(text,varchar,uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.auth_switch_session_context(text,varchar,uuid)
  TO frcaixinha_auth_role;

DO $guard$
BEGIN
  IF has_column_privilege('frcaixinha_auth_role','public.sessions','active_role','UPDATE')
    OR has_column_privilege('frcaixinha_auth_role','public.sessions','active_tenant_id','UPDATE')
    OR has_function_privilege('frcaixinha_app_role',
         'public.auth_promote_pending_session(text,varchar,uuid)','EXECUTE')
    OR has_function_privilege('frcaixinha_app_role',
         'public.auth_switch_session_context(text,varchar,uuid)','EXECUTE')
    OR NOT has_function_privilege('frcaixinha_auth_role',
         'public.auth_promote_pending_session(text,varchar,uuid)','EXECUTE')
    OR NOT has_function_privilege('frcaixinha_auth_role',
         'public.auth_switch_session_context(text,varchar,uuid)','EXECUTE')
  THEN
    RAISE EXCEPTION 'BLOQUEADO: troca de contexto pode ser alterada fora das funcoes';
  END IF;
END $guard$;
