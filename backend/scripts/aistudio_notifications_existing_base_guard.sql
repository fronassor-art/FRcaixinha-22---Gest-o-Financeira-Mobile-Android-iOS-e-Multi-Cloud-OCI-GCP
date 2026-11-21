-- M19100: no changes. A populated AI Studio DB may receive only M031.
BEGIN READ ONLY;
DO $safe$
DECLARE n integer;
BEGIN
 IF current_database()<>'frcaixinha_aistudio_dev'
 OR current_user<>'frc_ai_owner'
 OR inet_server_port()<>5433
 OR current_setting('data_directory')<>
 '/data/data/com.termux/files/usr/var/lib/frcaixinha_aistudio_pg18'
 OR current_setting('server_version_num')::integer NOT BETWEEN 180000 AND 189999
 THEN RAISE EXCEPTION 'M19100: wrong cluster/role'; END IF;
 SELECT count(*) INTO n FROM pg_catalog.pg_tables WHERE schemaname='public';
 IF n<25 THEN RAISE EXCEPTION 'M19100: expected populated 001-027 base, found % tables',n; END IF;
 IF to_regclass('public.notification_inbox') IS NOT NULL
 THEN RAISE EXCEPTION 'M19100: notification_inbox already exists; do not reapply'; END IF;
 IF to_regclass('public.users') IS NULL
 OR to_regclass('public.memberships') IS NULL
 OR to_regclass('public.tenants') IS NULL
 OR to_regclass('public.credentials') IS NULL
 OR to_regclass('public.sessions') IS NULL
 OR to_regclass('public.auth_login_proofs') IS NULL
 OR to_regclass('public.auth_login_rate_limits') IS NULL
 OR to_regclass('public.password_reset_tokens') IS NULL
 OR to_regclass('public.saas_payment_intents') IS NULL
 OR to_regclass('public.contract_documents') IS NULL
 OR to_regprocedure('public.auth_active_memberships(text)') IS NULL
 OR to_regprocedure('public.auth_issue_pending_session(uuid,text,text)') IS NULL
 OR to_regprocedure('public.auth_refresh_session(text)') IS NULL
 OR to_regprocedure('public.auth_login_rate_check(text)') IS NULL
 THEN RAISE EXCEPTION 'M19100: incomplete baseline functions/tables'; END IF;
 IF NOT pg_has_role('frc_ai_app','frcaixinha_app_role','member')
 OR NOT pg_has_role('frc_ai_auth','frcaixinha_auth_role','member')
 OR has_table_privilege('frc_ai_app','public.sessions','SELECT')
 OR has_table_privilege('frc_ai_app','public.credentials','SELECT')
 OR has_column_privilege('frc_ai_auth','public.credentials','password_hash','SELECT')
 OR NOT EXISTS(SELECT 1 FROM pg_class
 WHERE oid='public.users'::regclass AND relrowsecurity AND relforcerowsecurity)
 THEN RAISE EXCEPTION 'M19100: role isolation / RLS invalid'; END IF;
 RAISE NOTICE 'M19100_EXISTING_DATABASE_GUARD_PASS: % public tables, 031 absent',n;
END $safe$;
COMMIT;
