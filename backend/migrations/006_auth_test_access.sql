-- Acesso separado para a autenticação experimental. Sem LOGIN e sem senha.
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='frcaixinha_auth_role') THEN
    CREATE ROLE frcaixinha_auth_role NOLOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION;
  END IF;
END $$;
GRANT USAGE ON SCHEMA public TO frcaixinha_auth_role;
GRANT SELECT (id,email,full_name,status,is_master) ON public.users TO frcaixinha_auth_role;
GRANT SELECT (user_id,password_hash) ON public.credentials TO frcaixinha_auth_role;

-- Evita depender do contexto de RLS para descobrir os vínculos após autenticar.
-- Somente o serviço de autenticação pode executar; não concede acesso ao app.
CREATE OR REPLACE FUNCTION public.auth_active_memberships(p_user_id uuid)
RETURNS TABLE (tenant_id uuid, role varchar)
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, public, pg_temp
AS $$
  SELECT m.tenant_id, m.role FROM public.memberships m
  JOIN public.tenants t ON t.id=m.tenant_id
  WHERE m.user_id=p_user_id AND m.status='ATIVA' AND t.status='ATIVO';
$$;
REVOKE ALL ON FUNCTION public.auth_active_memberships(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.auth_active_memberships(uuid) TO frcaixinha_auth_role;
