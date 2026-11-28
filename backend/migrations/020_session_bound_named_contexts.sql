-- AI Studio 020: protege nomes de caixinhas vinculadas à identidade por
-- posse de token de sessão válido. Documento versionado; NÃO aplicar no Termux.
--
-- A função anterior (019) recebia UUID arbitrário. A credencial de autenticação
-- não deve conseguir enumerar nomes de caixinhas por UUID sem token bruto válido.
-- O token NÃO é persistido: apenas SHA-256 está armazenado em public.sessions.
-- pgcrypto já é criada pela migração 001.

DROP FUNCTION public.auth_active_membership_contexts(uuid);

CREATE FUNCTION public.auth_active_membership_contexts(p_raw_session_token text)
RETURNS TABLE (tenant_id uuid, role varchar, tenant_name varchar)
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, public, pg_temp
AS $$
  WITH verified_session AS (
    SELECT s.user_id
    FROM public.sessions AS s
    JOIN public.users AS u ON u.id = s.user_id
    WHERE length(p_raw_session_token) BETWEEN 24 AND 512
      AND s.token_hash = encode(public.digest(p_raw_session_token, 'sha256'), 'hex')
      AND s.revoked_at IS NULL
      AND s.expires_at > NOW()
      AND u.status = 'ACTIVE'
      AND (
        (s.active_role = 'MASTER'
         AND s.active_tenant_id IS NULL
         AND u.is_master)
        OR
        (s.active_role IN ('TENANT_ADMIN','TENANT_MEMBER')
         AND EXISTS (
           SELECT 1
           FROM public.memberships AS active_membership
           JOIN public.tenants AS active_tenant
             ON active_tenant.id = active_membership.tenant_id
           WHERE active_membership.user_id = s.user_id
             AND active_membership.tenant_id = s.active_tenant_id
             AND active_membership.role = s.active_role
             AND active_membership.status = 'ATIVA'
             AND active_tenant.status = 'ATIVO'
         ))
      )
  )
  SELECT m.tenant_id, m.role, t.display_name AS tenant_name
  FROM verified_session AS v
  JOIN public.memberships AS m ON m.user_id = v.user_id
  JOIN public.tenants AS t ON t.id = m.tenant_id
  WHERE m.status = 'ATIVA'
    AND t.status = 'ATIVO'
    AND m.role IN ('TENANT_ADMIN','TENANT_MEMBER')
  ORDER BY t.display_name, m.tenant_id, m.role;
$$;

REVOKE ALL ON FUNCTION public.auth_active_membership_contexts(text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.auth_active_membership_contexts(text)
  TO frcaixinha_auth_role;

DO $guard$
BEGIN
  IF to_regprocedure('public.auth_active_membership_contexts(uuid)') IS NOT NULL
    OR to_regprocedure('public.auth_active_membership_contexts(text)') IS NULL
    OR NOT has_function_privilege('frcaixinha_auth_role',
      'public.auth_active_membership_contexts(text)', 'EXECUTE')
    OR has_function_privilege('frcaixinha_app_role',
      'public.auth_active_membership_contexts(text)', 'EXECUTE')
    OR has_table_privilege('frcaixinha_auth_role', 'public.tenants', 'SELECT')
    OR has_table_privilege('frcaixinha_auth_role', 'public.memberships', 'SELECT')
    OR has_table_privilege('frcaixinha_app_role', 'public.sessions', 'SELECT')
  THEN
    RAISE EXCEPTION 'BLOQUEADO: enumeracao de contextos ou privilegios excessivos';
  END IF;
END
$guard$;
