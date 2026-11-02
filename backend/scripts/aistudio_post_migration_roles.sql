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
