-- M40540: classification of SQL112/113 metadata only; no application rows.
\set ON_ERROR_STOP on
BEGIN READ ONLY;
SET LOCAL statement_timeout = '10s';
SET LOCAL lock_timeout = '2s';
SELECT 1 / CASE WHEN (
 current_database()='frcaixinha_aistudio_dev'
 AND current_user='frc_ai_owner'
 AND session_user='frc_ai_owner'
 AND inet_server_addr()=inet '127.0.0.1'
 AND inet_server_port()=5433
 AND current_setting('data_directory')='/data/data/com.termux/files/usr/var/lib/frcaixinha_aistudio_pg18'
 AND current_setting('server_version_num')::int BETWEEN 180000 AND 189999
 AND current_setting('transaction_read_only')='on'
) THEN 1 ELSE 0 END AS m40540_identity;
\echo M40540_IDENTITY=PASS_ORIGINAL_PG18

WITH annual AS (
 SELECT attgenerated,attnotnull
 FROM pg_catalog.pg_attribute
 WHERE attrelid=pg_catalog.to_regclass('public.platform_license_price_versions')
   AND attname='annual_price' AND NOT attisdropped
)
SELECT CASE
 WHEN NOT EXISTS(SELECT 1 FROM annual) THEN 'BASELINE_MISSING'
 WHEN EXISTS(SELECT 1 FROM annual WHERE attgenerated='s')
   THEN 'PENDING_GENERATED_ANNUAL'
 WHEN EXISTS(SELECT 1 FROM annual WHERE attgenerated='' AND attnotnull)
   AND EXISTS (
    SELECT 1 FROM pg_catalog.pg_constraint
    WHERE conrelid=pg_catalog.to_regclass('public.platform_license_price_versions')
      AND conname='platform_license_annual_price_positive'
      AND contype='c' AND convalidated
   ) AND pg_catalog.to_regclass('public.platform_license_plans') IS NOT NULL
   THEN 'STRUCTURE_PRESENT_NOT_PROVENANCE'
 ELSE 'PARTIAL_OR_DRIFT'
END AS m40540_sql112 \gset
\echo M40540_SQL112=:m40540_sql112

WITH target AS (
 SELECT oid,relkind,relrowsecurity,relforcerowsecurity
 FROM pg_catalog.pg_class
 WHERE oid=pg_catalog.to_regclass('public.platform_saas_promotion_revisions')
), policies AS (
 SELECT polname,polcmd,polroles,
        pg_catalog.pg_get_expr(polqual,polrelid) AS using_expr,
        pg_catalog.pg_get_expr(polwithcheck,polrelid) AS check_expr
 FROM pg_catalog.pg_policy
 WHERE polrelid=pg_catalog.to_regclass('public.platform_saas_promotion_revisions')
), role AS (
 SELECT oid FROM pg_catalog.pg_roles WHERE rolname='frcaixinha_app_role'
), indexes AS (
 SELECT x.relname FROM pg_catalog.pg_index i
 JOIN pg_catalog.pg_class x ON x.oid=i.indexrelid
 WHERE i.indrelid=pg_catalog.to_regclass('public.platform_saas_promotion_revisions')
 AND x.relname IN ('platform_saas_promotions_latest','platform_saas_promotions_period')
), columns AS (
 SELECT attname FROM pg_catalog.pg_attribute
 WHERE attrelid=pg_catalog.to_regclass('public.platform_saas_promotion_revisions')
 AND attname IN ('id','campaign_id','revision','plan_tier','promotional_price','state','created_by')
 AND NOT attisdropped
), functions AS (
 SELECT
  pg_catalog.to_regprocedure('public.frfinance_guard_saas_promotion_append()') AS guard_oid,
  pg_catalog.to_regprocedure('public.frfinance_saas_new_admin_published_promotions()') AS reader_oid
)
SELECT CASE
 WHEN NOT EXISTS(SELECT 1 FROM target)
   AND NOT EXISTS(SELECT 1 FROM functions WHERE guard_oid IS NOT NULL OR reader_oid IS NOT NULL)
   THEN 'NOT_INSTALLED'
 WHEN EXISTS(SELECT 1 FROM target WHERE relkind='r' AND relrowsecurity AND relforcerowsecurity)
 AND (SELECT count(*) FROM policies)=2
 AND EXISTS(SELECT 1 FROM policies p, role r
            WHERE p.polname='frfinance_saas_promo_master_select'
            AND p.polcmd='r' AND p.polroles=ARRAY[r.oid]
            AND p.using_expr LIKE '%app.current_role%'
            AND p.using_expr LIKE '%rls_is_master%')
 AND EXISTS(SELECT 1 FROM policies p, role r
            WHERE p.polname='frfinance_saas_promo_master_insert'
            AND p.polcmd='a' AND p.polroles=ARRAY[r.oid]
            AND p.check_expr LIKE '%app.current_role%'
            AND p.check_expr LIKE '%rls_is_master%')
 AND EXISTS(SELECT 1 FROM pg_catalog.pg_trigger t, functions f
            WHERE t.tgrelid=pg_catalog.to_regclass('public.platform_saas_promotion_revisions')
              AND t.tgname='frfinance_guard_saas_promo_append'
              AND t.tgfoid=f.guard_oid AND t.tgenabled='O' AND NOT t.tgisinternal
              AND (t.tgtype::int & 1)=1 AND (t.tgtype::int & 2)=2 AND (t.tgtype::int & 4)=4)
 AND EXISTS(SELECT 1 FROM pg_catalog.pg_proc p, functions f
            WHERE p.oid=f.reader_oid AND p.prosecdef)
 AND (SELECT count(*) FROM indexes)=2
 AND (SELECT count(*) FROM columns)=7
   THEN 'STRUCTURE_PRESENT_NOT_PROVENANCE'
 ELSE 'PARTIAL_OR_DRIFT'
END AS m40540_sql113 \gset
\echo M40540_SQL113=:m40540_sql113
ROLLBACK;
\echo M40540_TRANSACTION=ROLLBACK_READ_ONLY
\echo M40540_APPLICATION_ROWS=NOT_QUERIED
\echo M40540_MIGRATIONS=NONE
\echo M40540_PRODUCTION=BLOCKED