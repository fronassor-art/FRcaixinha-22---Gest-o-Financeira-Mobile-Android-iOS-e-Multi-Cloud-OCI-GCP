-- Restringe leitura das cotas por papel e vínculo confirmado no banco.
-- Outras tabelas e operações exigem auditoria própria.
DROP POLICY IF EXISTS quotas_select_policy ON public.quotas;
CREATE POLICY quotas_select_policy ON public.quotas FOR SELECT USING (
    tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
    AND NOT public.rls_is_master(NULLIF(current_setting('app.current_user_id', true), '')::uuid)
    AND (
        (current_setting('app.current_role', true) = 'TENANT_ADMIN'
         AND public.rls_is_tenant_admin(NULLIF(current_setting('app.current_user_id', true), '')::uuid, tenant_id))
        OR
        (current_setting('app.current_role', true) = 'TENANT_MEMBER'
         AND membership_id IN (SELECT public.rls_user_membership_ids(
             NULLIF(current_setting('app.current_user_id', true), '')::uuid, tenant_id)))
    )
);
