-- Guarda transacional: SOMENTE o cluster local do AI Studio.
DO $guard$
DECLARE table_count integer;
BEGIN
  IF current_database() <> 'frcaixinha_aistudio_dev'
     OR inet_server_port() <> 5433
     OR current_user <> 'frc_ai_owner'
     OR current_setting('data_directory') <>
        '/data/data/com.termux/files/usr/var/lib/frcaixinha_aistudio_pg18'
     OR current_setting('server_version_num')::integer < 180000
     OR current_setting('server_version_num')::integer >= 190000
  THEN
    RAISE EXCEPTION 'BLOQUEADO: cluster nao e o PostgreSQL 18 exclusivo do AI Studio';
  END IF;
  SELECT count(*) INTO table_count FROM pg_catalog.pg_tables WHERE schemaname='public';
  IF table_count <> 0 THEN
    RAISE EXCEPTION 'BLOQUEADO: banco contem % tabelas; migracao cancelada',table_count;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='frc_ai_app'
                  AND rolcanlogin AND NOT rolsuper AND NOT rolbypassrls)
    OR NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='frc_ai_auth'
                  AND rolcanlogin AND NOT rolsuper AND NOT rolbypassrls)
  THEN
    RAISE EXCEPTION 'BLOQUEADO: usuarios tecnicos do AI Studio ausentes ou privilegiados';
  END IF;
  IF NOT has_database_privilege('frc_ai_app',current_database(),'CONNECT')
     OR NOT has_database_privilege('frc_ai_auth',current_database(),'CONNECT') THEN
    RAISE EXCEPTION 'BLOQUEADO: privilegio CONNECT nao confirmado';
  END IF;
  PERFORM pg_advisory_xact_lock(70714332181);
END
$guard$;
