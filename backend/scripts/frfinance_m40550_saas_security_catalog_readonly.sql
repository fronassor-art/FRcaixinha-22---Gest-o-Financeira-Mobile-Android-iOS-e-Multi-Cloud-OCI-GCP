-- FR Finance M40550: strict SQL112/113 catalog security; no application rows.
\set ON_ERROR_STOP on
BEGIN READ ONLY;
SET LOCAL statement_timeout='10s';
SET LOCAL lock_timeout='2s';
SELECT 1 / CASE WHEN (
 current_database()='frcaixinha_aistudio_dev'
 AND current_user='frc_ai_owner' AND session_user='frc_ai_owner'
 AND inet_server_addr()=inet '127.0.0.1' AND inet_server_port()=5433
 AND current_setting('data_directory')=
  '/data/data/com.termux/files/usr/var/lib/frcaixinha_aistudio_pg18'
 AND current_setting('server_version_num')::int BETWEEN 180000 AND 189999
 AND current_setting('transaction_read_only')='on'
) THEN 1 ELSE 0 END AS identity_guard;
\echo M40550_IDENTITY=PASS_ORIGINAL_READ_ONLY

SELECT 1 / CASE WHEN (
 EXISTS(SELECT 1 FROM pg_catalog.pg_class c
 JOIN pg_catalog.pg_attribute a ON a.attrelid=c.oid
 WHERE c.oid=pg_catalog.to_regclass('public.platform_license_price_versions')
 AND c.relrowsecurity AND c.relforcerowsecurity
 AND a.attname='annual_price' AND NOT a.attisdropped
 AND a.attgenerated='' AND a.attnotnull)
 AND EXISTS(SELECT 1 FROM pg_catalog.pg_constraint c
 WHERE c.conrelid=pg_catalog.to_regclass('public.platform_license_price_versions')
 AND c.conname='platform_license_annual_price_positive' AND c.contype='c'
 AND c.convalidated AND pg_catalog.pg_get_constraintdef(c.oid) LIKE '%annual_price%'
 AND pg_catalog.pg_get_constraintdef(c.oid) LIKE '%999999.99%')
) THEN 1 ELSE 0 END AS annual_guard;
\echo M40550_SQL112_PRICE_STRUCTURE=PASS

SELECT 1 / CASE WHEN (
 pg_catalog.has_column_privilege('frcaixinha_app_role',
  'public.platform_license_price_versions','annual_price','INSERT')
 AND NOT pg_catalog.has_column_privilege('frcaixinha_app_role',
  'public.platform_license_price_versions','annual_price','UPDATE')
 AND NOT pg_catalog.has_table_privilege('frcaixinha_app_role',
  'public.platform_license_price_versions','UPDATE')
 AND NOT pg_catalog.has_table_privilege('frcaixinha_app_role',
  'public.platform_license_price_versions','DELETE')
 AND NOT pg_catalog.has_table_privilege('frcaixinha_auth_role',
  'public.platform_license_price_versions','UPDATE')
 AND NOT pg_catalog.has_table_privilege('frcaixinha_auth_role',
  'public.platform_license_price_versions','DELETE')
) THEN 1 ELSE 0 END AS annual_privileges;
\echo M40550_SQL112_NO_HISTORICAL_UPDATE=PASS

WITH roles AS (
 SELECT oid FROM pg_catalog.pg_roles WHERE rolname='frcaixinha_app_role'
), policies AS (
 SELECT polname,polcmd,polpermissive,polroles,
 coalesce(pg_catalog.pg_get_expr(polqual,polrelid),'') AS use_expr,
 coalesce(pg_catalog.pg_get_expr(polwithcheck,polrelid),'') AS check_expr
 FROM pg_catalog.pg_policy
 WHERE polrelid=pg_catalog.to_regclass('public.platform_saas_promotion_revisions')
)
SELECT 1 / CASE WHEN (
 EXISTS(SELECT 1 FROM pg_catalog.pg_class
 WHERE oid=pg_catalog.to_regclass('public.platform_saas_promotion_revisions')
 AND relkind='r' AND relrowsecurity AND relforcerowsecurity)
 AND (SELECT count(*) FROM policies)=2
 AND EXISTS(SELECT 1 FROM policies p, roles r
 WHERE p.polname='frfinance_saas_promo_master_select' AND p.polcmd='r'
 AND p.polpermissive AND p.polroles=ARRAY[r.oid]
 AND p.use_expr LIKE '%app.current_role%'
 AND p.use_expr LIKE '%rls_is_master%')
 AND EXISTS(SELECT 1 FROM policies p, roles r
 WHERE p.polname='frfinance_saas_promo_master_insert' AND p.polcmd='a'
 AND p.polpermissive AND p.polroles=ARRAY[r.oid]
 AND p.check_expr LIKE '%app.current_role%'
 AND p.check_expr LIKE '%rls_is_master%'
 AND p.check_expr LIKE '%created_by%')
) THEN 1 ELSE 0 END AS master_policies;
\echo M40550_SQL113_MASTER_RLS=PASS

SELECT 1 / CASE WHEN (
 pg_catalog.has_table_privilege('frcaixinha_app_role',
  'public.platform_saas_promotion_revisions','SELECT')
 AND pg_catalog.has_column_privilege('frcaixinha_app_role',
  'public.platform_saas_promotion_revisions','campaign_id','INSERT')
 AND pg_catalog.has_column_privilege('frcaixinha_app_role',
  'public.platform_saas_promotion_revisions','created_by','INSERT')
 AND NOT pg_catalog.has_column_privilege('frcaixinha_app_role',
  'public.platform_saas_promotion_revisions','id','INSERT')
 AND NOT pg_catalog.has_column_privilege('frcaixinha_app_role',
  'public.platform_saas_promotion_revisions','created_at','INSERT')
 AND NOT pg_catalog.has_any_column_privilege('frcaixinha_app_role',
  'public.platform_saas_promotion_revisions','UPDATE')
 AND NOT pg_catalog.has_table_privilege('frcaixinha_app_role',
  'public.platform_saas_promotion_revisions','DELETE')
 AND NOT pg_catalog.has_table_privilege('frcaixinha_app_role',
  'public.platform_saas_promotion_revisions','TRUNCATE')
 AND NOT pg_catalog.has_table_privilege('frcaixinha_auth_role',
  'public.platform_saas_promotion_revisions','SELECT')
 AND NOT pg_catalog.has_any_column_privilege('frcaixinha_auth_role',
  'public.platform_saas_promotion_revisions','INSERT')
 AND NOT pg_catalog.has_any_column_privilege('frcaixinha_auth_role',
  'public.platform_saas_promotion_revisions','UPDATE')
 AND NOT pg_catalog.has_table_privilege('frcaixinha_auth_role',
  'public.platform_saas_promotion_revisions','DELETE')
) THEN 1 ELSE 0 END AS least_privilege;
\echo M40550_SQL113_LEAST_PRIVILEGE=PASS

WITH f AS (
 SELECT pg_catalog.to_regprocedure(
  'public.frfinance_guard_saas_promotion_append()') AS guard_id,
 pg_catalog.to_regprocedure(
  'public.frfinance_saas_new_admin_published_promotions()') AS reader_id
)
SELECT 1 / CASE WHEN (
 EXISTS(SELECT 1 FROM f JOIN pg_catalog.pg_proc p ON p.oid=f.reader_id
 WHERE p.prosecdef
 AND array_to_string(p.proconfig,',') LIKE '%search_path=pg_catalog, pg_temp%'
 AND pg_catalog.pg_get_functiondef(p.oid) LIKE '%rls_is_tenant_admin%'
 AND pg_catalog.pg_get_functiondef(p.oid) LIKE '%NEW_ADMIN_ONLY%')
 AND EXISTS(SELECT 1 FROM f JOIN pg_catalog.pg_proc p ON p.oid=f.guard_id
 WHERE array_to_string(p.proconfig,',') LIKE '%search_path=pg_catalog, pg_temp%'
 AND pg_catalog.pg_get_functiondef(p.oid)
  LIKE '%M39067_OVERLAPPING_PUBLISHED_PROMOTION%'
 AND pg_catalog.pg_get_functiondef(p.oid)
  LIKE '%M39067_REVIEW_CANNOT_REWRITE_COMMERCIAL_SNAPSHOT%')
 AND pg_catalog.has_function_privilege('frcaixinha_app_role',
  'public.frfinance_saas_new_admin_published_promotions()','EXECUTE')
 AND NOT pg_catalog.has_function_privilege('frcaixinha_auth_role',
  'public.frfinance_saas_new_admin_published_promotions()','EXECUTE')
 AND NOT pg_catalog.has_function_privilege('frcaixinha_app_role',
  'public.frfinance_guard_saas_promotion_append()','EXECUTE')
 AND NOT pg_catalog.has_function_privilege('frcaixinha_auth_role',
  'public.frfinance_guard_saas_promotion_append()','EXECUTE')
) THEN 1 ELSE 0 END AS function_guard;
\echo M40550_SQL113_FUNCTIONS_SECURITY=PASS

SELECT 1 / CASE WHEN (
 EXISTS(SELECT 1 FROM pg_catalog.pg_trigger t
 WHERE t.tgrelid=pg_catalog.to_regclass('public.platform_saas_promotion_revisions')
 AND t.tgname='frfinance_guard_saas_promo_append'
 AND t.tgfoid=pg_catalog.to_regprocedure('public.frfinance_guard_saas_promotion_append()')
 AND t.tgenabled='O' AND NOT t.tgisinternal
 AND (t.tgtype::int & 1)=1 AND (t.tgtype::int & 2)=2
 AND (t.tgtype::int & 4)=4 AND (t.tgtype::int & 8)=0
 AND (t.tgtype::int & 16)=0)
) THEN 1 ELSE 0 END AS trigger_guard;
\echo M40550_SQL113_GUARD_TRIGGER=PASS

ROLLBACK;
\echo M40550_TRANSACTION=ROLLBACK_READ_ONLY
\echo M40550_APPLICATION_ROWS=NONE
\echo M40550_FUNCTION_EXECUTION=NONE
\echo M40550_AUTHENTICATED_RLS_DATA_PLANE=NOT_TESTED
\echo M40550_MIGRATIONS=NONE
\echo M40550_PRODUCTION=BLOCKED