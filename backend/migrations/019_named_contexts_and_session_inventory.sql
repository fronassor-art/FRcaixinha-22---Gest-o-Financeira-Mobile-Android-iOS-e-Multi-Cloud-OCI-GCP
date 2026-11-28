-- AI Studio 019 — nome da caixinha no acesso único e inventário de sessões.
-- Somente artefato versionado. Não aplicar no Termux sem autorização.
-- A autenticação não ganha SELECT na tabela de tenants, apenas função restrita.

CREATE OR REPLACE FUNCTION public.auth_active_membership_contexts(p_user_id uuid)
RETURNS TABLE (tenant_id uuid, role varchar, tenant_name varchar)
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, public, pg_temp
AS $$
  SELECT m.tenant_id,m.role,t.display_name AS tenant_name
  FROM public.memberships m
  JOIN public.tenants t ON t.id=m.tenant_id
  JOIN public.users u ON u.id=m.user_id
  WHERE m.user_id=p_user_id
    AND u.status='ACTIVE'
    AND m.status='ATIVA'
    AND t.status='ATIVO'
    AND m.role IN ('TENANT_ADMIN','TENANT_MEMBER')
  ORDER BY t.display_name,m.tenant_id,m.role;
$$;
REVOKE ALL ON FUNCTION public.auth_active_membership_contexts(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.auth_active_membership_contexts(uuid)
  TO frcaixinha_auth_role;

-- Metadado não sensível para cada usuário consultar as próprias sessões.
-- O auth role já tem SELECT em id/user_id/role/tenant/expiry/revoked na 008.
GRANT SELECT (created_at) ON public.sessions TO frcaixinha_auth_role;

DO $guard$
BEGIN
  IF has_table_privilege('frcaixinha_auth_role','public.tenants','SELECT')
    OR has_table_privilege('frcaixinha_auth_role','public.memberships','SELECT')
    OR has_table_privilege('frcaixinha_app_role','public.sessions','SELECT')
    OR NOT has_function_privilege('frcaixinha_auth_role',
      'public.auth_active_membership_contexts(uuid)','EXECUTE')
    OR has_function_privilege('frcaixinha_app_role',
      'public.auth_active_membership_contexts(uuid)','EXECUTE')
  THEN
    RAISE EXCEPTION 'Contexto nomeado ou sessões expõem permissões indevidas';
  END IF;
END $guard$;
