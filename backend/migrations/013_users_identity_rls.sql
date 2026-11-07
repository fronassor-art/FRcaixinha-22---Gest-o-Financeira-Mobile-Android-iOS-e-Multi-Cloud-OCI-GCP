-- AI Studio / somente banco descartavel no CI até autorizar a migração local.
-- Identities: 012 restringiu colunas; 013 restringe linhas pela sessao.
-- Papel AUTH possui acesso estritamente necessário para login em qualquer conta,
-- sem transitar pelo papel financeiro frcaixinha_app_role.

ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.users FORCE ROW LEVEL SECURITY;

-- Serviço separado da autenticacao, com concessoes de COLUNAS da 006/012.
-- Sem acesso de escrita a users e sem acesso a CPF e telefone.
CREATE POLICY users_auth_identification_read
  ON public.users
  FOR SELECT TO frcaixinha_auth_role
  USING (true);

-- O usuário autenticado lê apenas o próprio identificador/nome.
CREATE POLICY users_app_self_read
  ON public.users
  FOR SELECT TO frcaixinha_app_role
  USING (
    id = NULLIF(current_setting('app.current_user_id',true),'')::uuid
    AND status='ACTIVE'
    AND current_setting('app.current_role',true)
         IN ('MASTER','TENANT_ADMIN','TENANT_MEMBER')
  );

-- Administrador pode exibir os NOMES dos membros ativos do seu tenant.
-- Não habilita e-mail, CPF ou telefone; coluna permitida permanece (id,full_name).
CREATE POLICY users_app_tenant_admin_members_read
  ON public.users
  FOR SELECT TO frcaixinha_app_role
  USING (
    current_setting('app.current_role',true)='TENANT_ADMIN'
    AND EXISTS (
      SELECT 1 FROM public.memberships m
      WHERE m.user_id=users.id
        AND m.status='ATIVA'
        AND m.tenant_id=NULLIF(current_setting('app.current_tenant_id',true),'')::uuid
        AND public.rls_is_tenant_admin(
          NULLIF(current_setting('app.current_user_id',true),'')::uuid,
          m.tenant_id
        )
    )
  );

DO $identity_guard$
BEGIN
  IF NOT EXISTS (
     SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
     WHERE n.nspname='public' AND c.relname='users'
       AND c.relrowsecurity AND c.relforcerowsecurity
  ) THEN
    RAISE EXCEPTION 'BLOQUEADO: RLS FORCE em public.users nao ativada';
  END IF;
  IF has_column_privilege('frcaixinha_app_role','public.users','cpf','SELECT')
    OR has_column_privilege('frcaixinha_app_role','public.users','email','SELECT')
    OR has_column_privilege('frcaixinha_app_role','public.users','phone','SELECT')
    OR has_table_privilege('frcaixinha_app_role','public.credentials','SELECT')
  THEN
    RAISE EXCEPTION 'BLOQUEADO: privilégio de dados privados indevido';
  END IF;
END
$identity_guard$;
