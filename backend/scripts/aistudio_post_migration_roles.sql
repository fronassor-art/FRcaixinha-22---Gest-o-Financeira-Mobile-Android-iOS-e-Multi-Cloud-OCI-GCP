-- Execucao na mesma transacao das migracoes 001-010.
-- MASTER e um papel de aplicativo, jamais um SUPERUSER PostgreSQL.
GRANT frcaixinha_app_role TO frc_ai_app;
GRANT frcaixinha_auth_role TO frc_ai_auth;
DO $verify$
BEGIN
  IF NOT pg_has_role('frc_ai_app','frcaixinha_app_role','member')
     OR NOT pg_has_role('frc_ai_auth','frcaixinha_auth_role','member') THEN
    RAISE EXCEPTION 'Falha ao vincular papeis tecnicos';
  END IF;
  IF (SELECT rolsuper OR rolbypassrls FROM pg_roles WHERE rolname='frc_ai_app')
     OR (SELECT rolsuper OR rolbypassrls FROM pg_roles WHERE rolname='frc_ai_auth') THEN
    RAISE EXCEPTION 'Usuários técnicos privilegiados indevidamente';
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM pg_class
    WHERE oid='public.users'::regclass AND relrowsecurity AND relforcerowsecurity
  ) THEN
    RAISE EXCEPTION 'BLOQUEADO: FORCE RLS em users ausente';
  END IF;
  IF has_column_privilege('frcaixinha_app_role','public.users','cpf','SELECT')
    OR has_column_privilege('frcaixinha_app_role','public.users','email','SELECT')
    OR has_column_privilege('frc_ai_app','public.credentials','SELECT')
  THEN
    RAISE EXCEPTION 'BLOQUEADO: identidade/credenciais expostas a aplicacao';
  END IF;
  IF to_regclass('public.saas_payment_intents') IS NULL
    OR to_regclass('public.saas_license_entitlements') IS NULL
    OR to_regclass('public.saas_provider_webhook_receipts') IS NULL
    OR to_regclass('public.invite_email_verification') IS NULL
    OR has_table_privilege('frc_ai_app','public.saas_payment_intents','INSERT')
    OR has_table_privilege('frc_ai_auth','public.saas_license_entitlements','SELECT')
    OR has_table_privilege('frc_ai_app','public.saas_provider_webhook_receipts','SELECT')
    OR has_table_privilege('frc_ai_auth','public.invite_email_verification','SELECT')
    OR has_column_privilege('frcaixinha_app_role','public.users','email_verified_at','UPDATE')
    OR NOT EXISTS (
      SELECT 1 FROM pg_class WHERE oid='public.saas_payment_intents'::regclass
        AND relrowsecurity AND relforcerowsecurity
    )
    OR NOT EXISTS (
      SELECT 1 FROM pg_class WHERE oid='public.invite_email_verification'::regclass
        AND relrowsecurity AND relforcerowsecurity
    )
  THEN
    RAISE EXCEPTION 'BLOQUEADO: cobranças/ingressos expostos a papeis comuns';
  END IF;
  IF to_regclass('public.contract_documents') IS NULL
    OR to_regclass('public.contract_acceptances') IS NULL
    OR to_regclass('public.saas_subscription_preparations') IS NULL
    OR has_table_privilege('frc_ai_app','public.contract_acceptances','INSERT')
    OR has_table_privilege('frc_ai_auth','public.contract_acceptances','SELECT')
    OR has_table_privilege('frc_ai_app','public.saas_subscription_preparations','INSERT')
    OR NOT EXISTS (
      SELECT 1 FROM pg_class WHERE oid='public.contract_acceptances'::regclass
        AND relrowsecurity AND relforcerowsecurity
    )
  THEN
    RAISE EXCEPTION 'BLOQUEADO: contratos/assinaturas com privilegios indevidos';
  END IF;
  IF to_regclass('public.password_reset_tokens') IS NULL
    OR NOT EXISTS (SELECT 1 FROM pg_class
       WHERE oid='public.invitations'::regclass AND relrowsecurity AND relforcerowsecurity)
    OR NOT EXISTS (SELECT 1 FROM pg_class
       WHERE oid='public.password_reset_tokens'::regclass AND relrowsecurity AND relforcerowsecurity)
    OR has_table_privilege('frc_ai_app','public.invitations','SELECT')
    OR has_table_privilege('frc_ai_auth','public.password_reset_tokens','SELECT')
  THEN
    RAISE EXCEPTION 'BLOQUEADO: motor de convites/recuperacao nao protegido';
  END IF;
  IF to_regclass('public.platform_license_plans') IS NULL
     OR to_regclass('public.platform_license_price_versions') IS NULL
     OR to_regclass('public.users') IS NULL
     OR to_regclass('public.credentials') IS NULL
     OR to_regclass('public.sessions') IS NULL
     OR to_regprocedure('public.auth_active_memberships(uuid)') IS NULL THEN
    RAISE EXCEPTION 'Estrutura de identidade MASTER incompleta';
  END IF;
END
$verify$;
