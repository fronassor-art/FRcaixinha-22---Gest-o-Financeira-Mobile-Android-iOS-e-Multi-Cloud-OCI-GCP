-- A migração 002 criou contribuições após os GRANTs da migração 001.
-- Habilita somente leitura e limita o resultado ao vínculo autenticado.
GRANT SELECT ON public.contributions TO frcaixinha_app_role;
DROP POLICY IF EXISTS rls_contributions_select ON public.contributions;
CREATE POLICY rls_contributions_select ON public.contributions FOR SELECT USING (
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
