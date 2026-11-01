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
  IF to_regclass('public.users') IS NULL
     OR to_regclass('public.credentials') IS NULL
     OR to_regclass('public.sessions') IS NULL
     OR to_regprocedure('public.auth_active_memberships(uuid)') IS NULL THEN
    RAISE EXCEPTION 'Estrutura de identidade MASTER incompleta';
  END IF;
END
$verify$;
