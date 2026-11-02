-- Execucao na mesma transacao das migracoes versionadas 001-025.
-- MASTER e um papel de aplicativo, jamais um SUPERUSER PostgreSQL.
GRANT frcaixinha_app_role TO frc_ai_app;
GRANT frcaixinha_auth_role TO frc_ai_auth;
-- A credencial separada do verificador sera provisionada SOMENTE na fase
-- autorizada. Nao conceder este papel a frc_ai_auth nem a frc_ai_app.
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
  IF to_regprocedure('public.auth_active_membership_contexts(text)') IS NULL
    OR to_regprocedure('public.auth_active_membership_contexts(uuid)') IS NOT NULL
    OR NOT has_function_privilege('frc_ai_auth',
       'public.auth_active_membership_contexts(text)','EXECUTE')
    OR has_function_privilege('frcaixinha_app_role',
       'public.auth_active_membership_contexts(text)','EXECUTE')
    OR has_table_privilege('frc_ai_auth','public.tenants','SELECT')
    OR has_table_privilege('frc_ai_auth','public.memberships','SELECT')
    OR has_table_privilege('frc_ai_app','public.sessions','SELECT')
    OR NOT has_column_privilege('frc_ai_auth','public.sessions','created_at','SELECT')
  THEN
    RAISE EXCEPTION 'BLOQUEADO: acesso unico ou sessoes com privilegios indevidos';
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
  IF has_column_privilege('frc_ai_auth','public.credentials','password_hash','SELECT')
     OR has_table_privilege('frc_ai_auth','public.sessions','INSERT')
     OR has_table_privilege('frc_ai_auth','public.auth_login_proofs','INSERT')
     OR NOT has_function_privilege('frc_ai_auth',
        'public.auth_issue_pending_session(uuid,text,text)','EXECUTE')
     OR pg_has_role('frc_ai_auth','frcaixinha_verifier_role','member')
     OR pg_has_role('frc_ai_app','frcaixinha_verifier_role','member')
  THEN
    RAISE EXCEPTION 'BLOQUEADO: papel Auth pode forjar prova sem verificador';
  END IF;
  IF has_column_privilege('frc_ai_auth','public.sessions','expires_at','UPDATE')
    OR has_column_privilege('frc_ai_auth','public.sessions','revoked_at','UPDATE')
    OR NOT has_function_privilege('frc_ai_auth',
       'public.auth_refresh_session(text)','EXECUTE')
    OR NOT has_function_privilege('frc_ai_auth',
       'public.auth_revoke_all_sessions(text)','EXECUTE')
    OR NOT has_function_privilege('frc_ai_auth',
       'public.auth_revoke_owned_session(text,uuid)','EXECUTE')
    OR has_function_privilege('frc_ai_app',
       'public.auth_revoke_all_sessions(text)','EXECUTE')
  THEN
    RAISE EXCEPTION 'BLOQUEADO: Auth pode renovar ou revogar sessao arbitraria';
  END IF;
  IF has_column_privilege('frc_ai_auth','public.sessions','active_role','UPDATE')
    OR has_column_privilege('frc_ai_auth','public.sessions','active_tenant_id','UPDATE')
    OR NOT has_function_privilege('frc_ai_auth',
      'public.auth_promote_pending_session(text,varchar,uuid)','EXECUTE')
    OR NOT has_function_privilege('frc_ai_auth',
      'public.auth_switch_session_context(text,varchar,uuid)','EXECUTE')
    OR has_function_privilege('frc_ai_app',
      'public.auth_switch_session_context(text,varchar,uuid)','EXECUTE')
  THEN
    RAISE EXCEPTION 'BLOQUEADO: role Auth pode forjar alteracao direta de contexto';
  END IF;
  IF NOT EXISTS (
       SELECT 1 FROM pg_constraint
       WHERE conrelid='public.sessions'::regclass
         AND conname='sessions_absolute_8h_guard'
     )
     OR NOT EXISTS (
       SELECT 1 FROM pg_policies
       WHERE schemaname='public' AND tablename='sessions'
         AND policyname='sessions_auth_insert'
         AND cmd='INSERT'
         AND with_check LIKE '%PENDING_CONTEXT%'
     )
  THEN
    RAISE EXCEPTION 'BLOQUEADO: duracao absoluta ou emissao provisoria invalida';
  END IF;
  IF to_regclass('public.platform_license_plans') IS NULL
     OR to_regclass('public.platform_license_price_versions') IS NULL
     OR to_regclass('public.users') IS NULL
     OR to_regclass('public.credentials') IS NULL
     OR to_regclass('public.sessions') IS NULL
     OR to_regprocedure('public.auth_active_memberships(text)') IS NULL
     OR to_regprocedure('public.auth_active_memberships(uuid)') IS NOT NULL
     OR NOT has_function_privilege('frc_ai_auth',
          'public.auth_active_memberships(text)','EXECUTE')
     OR has_function_privilege('frc_ai_app',
          'public.auth_active_memberships(text)','EXECUTE') THEN
    RAISE EXCEPTION 'Estrutura de identidade MASTER incompleta';
  END IF;
END
$verify$;
