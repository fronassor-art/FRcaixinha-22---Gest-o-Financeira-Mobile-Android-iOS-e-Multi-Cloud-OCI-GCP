-- AI Studio 021 — vinculos acessiveis apenas mediante posse de sessao.
-- SOMENTE CI descartavel. NAO aplicar SQL no PostgreSQL do Termux.
-- Requer 001 (pgcrypto e sessions), 006 (papel auth), 008 (RLS sessions), 020.

-- Uma sessao provisoria existe somente DENTRO da transacao de login e nao
-- autoriza endpoints. O token bruto é gerado após verificar a senha.
ALTER TABLE public.sessions DROP CONSTRAINT sessions_active_role_check;
ALTER TABLE public.sessions
  ADD CONSTRAINT sessions_active_role_check
  CHECK (active_role IN ('MASTER','TENANT_ADMIN','TENANT_MEMBER','PENDING_CONTEXT'));

DROP FUNCTION public.auth_active_memberships(uuid);

CREATE FUNCTION public.auth_active_memberships(p_raw_session_token text)
RETURNS TABLE (tenant_id uuid, role varchar)
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, public, pg_temp
AS $$
  WITH verified_session AS (
    SELECT s.user_id
    FROM public.sessions AS s
    JOIN public.users AS u ON u.id=s.user_id
    WHERE length(p_raw_session_token) BETWEEN 24 AND 512
      AND s.token_hash=encode(public.digest(p_raw_session_token,'sha256'),'hex')
      AND s.revoked_at IS NULL
      AND s.expires_at > NOW()
      AND u.status='ACTIVE'
      AND (
        (s.active_role='PENDING_CONTEXT'
          AND s.active_tenant_id IS NULL
          AND s.expires_at <= s.created_at + INTERVAL '2 minutes')
        OR
        (s.active_role='MASTER'
          AND s.active_tenant_id IS NULL
          AND u.is_master)
        OR
        (s.active_role IN ('TENANT_ADMIN','TENANT_MEMBER')
          AND EXISTS (
            SELECT 1 FROM public.memberships AS active_m
            JOIN public.tenants AS active_t ON active_t.id=active_m.tenant_id
            WHERE active_m.user_id=s.user_id
              AND active_m.tenant_id=s.active_tenant_id
              AND active_m.role=s.active_role
              AND active_m.status='ATIVA'
              AND active_t.status='ATIVO'
          ))
      )
  )
  SELECT m.tenant_id,m.role
  FROM verified_session AS v
  JOIN public.memberships AS m ON m.user_id=v.user_id
  JOIN public.tenants AS t ON t.id=m.tenant_id
  WHERE m.status='ATIVA'
    AND t.status='ATIVO'
    AND m.role IN ('TENANT_ADMIN','TENANT_MEMBER')
  ORDER BY m.tenant_id,m.role;
$$;

REVOKE ALL ON FUNCTION public.auth_active_memberships(text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.auth_active_memberships(text)
  TO frcaixinha_auth_role;

DO $guard$
BEGIN
  IF to_regprocedure('public.auth_active_memberships(uuid)') IS NOT NULL
    OR to_regprocedure('public.auth_active_memberships(text)') IS NULL
    OR NOT has_function_privilege('frcaixinha_auth_role',
      'public.auth_active_memberships(text)','EXECUTE')
    OR has_function_privilege('frcaixinha_app_role',
      'public.auth_active_memberships(text)','EXECUTE')
    OR has_table_privilege('frcaixinha_auth_role','public.memberships','SELECT')
  THEN
    RAISE EXCEPTION 'BLOQUEADO: vinculos via UUID ou privilegio excessivo';
  END IF;
END $guard$;
