-- M33400-M33800: READ-ONLY plan capacity visibility for currently scoped admins.
-- A local *candidate* migration: DO NOT APPLY TO TERMUX 5433 without approval.
-- No grants on payments, tokens, users, member/quotas writes, or Pix.
BEGIN;
DO $guard$ BEGIN
 IF NOT (
  (current_database()='frcaixinha_ci' AND session_user='postgres'
    AND current_setting('frcaixinha.saas_admission_ci',true)='1')
  OR
  (current_database()='frcaixinha_aistudio_dev' AND session_user='frc_ai_owner'
    AND current_setting('frcaixinha.local_migration_045_approved',true)='1')
 ) THEN RAISE EXCEPTION 'M33400_LOCAL_MIGRATION_NOT_AUTHORIZED'; END IF;
END $guard$;

-- Entitlement policies (017) already bind the session to the tenant.
-- The global plan table stays Master-visible; an admin can SELECT only
-- a tier attached to its own tenant through the existing entitlement RLS.
CREATE POLICY platform_license_plans_admin_licensed_read
ON public.platform_license_plans FOR SELECT TO frcaixinha_app_role
USING (
 current_setting('app.current_role',true)='TENANT_ADMIN'
 AND NULLIF(current_setting('app.current_tenant_id',true),'') IS NOT NULL
 AND NULLIF(current_setting('app.current_user_id',true),'') IS NOT NULL
 AND public.rls_is_tenant_admin(
  NULLIF(current_setting('app.current_user_id',true),'')::uuid,
  NULLIF(current_setting('app.current_tenant_id',true),'')::uuid)
 AND EXISTS(
  SELECT 1 FROM public.saas_license_entitlements e
  WHERE e.plan_tier=tier
   AND e.tenant_id=NULLIF(current_setting('app.current_tenant_id',true),'')::uuid
 )
);
-- No extra grants: existing SELECT on the catalog remains sufficient.
DO $audit$ BEGIN
 IF has_table_privilege('frcaixinha_app_role','public.saas_license_entitlements','INSERT')
 OR has_table_privilege('frcaixinha_app_role','public.saas_payment_intents','UPDATE')
 OR has_table_privilege('frcaixinha_app_role','public.memberships','INSERT')
 OR has_table_privilege('frcaixinha_app_role','public.quotas','INSERT')
 OR has_table_privilege('frcaixinha_auth_role','public.platform_license_plans','SELECT')
 THEN RAISE EXCEPTION 'M33800_UNSAFE_ROLE_PRIVILEGES'; END IF;
END $audit$;
COMMIT;
