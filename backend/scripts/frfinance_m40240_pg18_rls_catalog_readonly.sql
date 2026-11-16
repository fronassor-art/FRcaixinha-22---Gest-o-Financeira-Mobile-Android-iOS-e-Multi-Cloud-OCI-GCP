-- FR Finance M40240: catalogue-only PostgreSQL 18 original on Termux.
-- No member rows, tenant rows, session rows, credentials, DML or DDL.
-- Fail closed via 1/0 when any identity / catalog invariant is unproven.
\set ON_ERROR_STOP on
BEGIN READ ONLY;
SET LOCAL statement_timeout = '10s';
SET LOCAL lock_timeout = '2s';

SELECT 1 / CASE WHEN (
  current_database() = 'frcaixinha_aistudio_dev'
  AND current_user = 'frc_ai_owner'
  AND session_user = 'frc_ai_owner'
  AND inet_server_addr() = inet '127.0.0.1'
  AND inet_server_port() = 5433
  AND current_setting('data_directory') =
      '/data/data/com.termux/files/usr/var/lib/frcaixinha_aistudio_pg18'
  AND current_setting('server_version_num')::integer BETWEEN 180000 AND 189999
  AND current_setting('transaction_read_only') = 'on'
) THEN 1 ELSE 0 END AS m40240_identity_guard;
\echo M40240_DATABASE_IDENTITY=PASS_FR_FINANCE_PG18_ORIGINAL

-- Require the three existing application technical roles to be LOGIN,
-- neither superuser nor BYPASSRLS; owner is NOT used to test data-plane RLS.
SELECT 1 / CASE WHEN (
    SELECT count(*) FROM pg_catalog.pg_roles
    WHERE rolname IN ('frc_ai_app','frc_ai_auth','frc_ai_verifier')
      AND rolcanlogin AND NOT rolsuper AND NOT rolbypassrls
) = 3 THEN 1 ELSE 0 END AS m40240_technical_role_guard;
\echo M40240_TECHNICAL_ROLES=PASS_3_OF_3_NO_SUPERUSER_NO_BYPASSRLS

-- Policy catalogue names are defined in migration 110 and checked below.
-- NEVER read actual application rows in this preflight.
WITH expected(table_name) AS (
  VALUES
    ('special_credit_grants'),
    ('special_credit_campaigns'),
    ('special_credit_recipients'),
    ('special_credit_preferences'),
    ('special_credit_outbox'),
    ('special_credit_audit')
)
SELECT 1 / CASE WHEN (
   count(*) = 6 AND coalesce(bool_and(
     c.oid IS NOT NULL AND c.relkind = 'r'
     AND c.relrowsecurity AND c.relforcerowsecurity
   ), FALSE)
) THEN 1 ELSE 0 END AS m40240_six_table_rls_guard
FROM expected e
LEFT JOIN pg_catalog.pg_class c
  ON c.oid = pg_catalog.to_regclass('public.' || e.table_name);
\echo M40240_SPECIAL_CREDIT_TABLES=PASS_6_OF_6_RLS_AND_FORCE_RLS

WITH expected(table_name,policy_name) AS (
  VALUES
    ('special_credit_grants','sc_grant_read'),
    ('special_credit_grants','sc_grant_admin_insert'),
    ('special_credit_grants','sc_grant_admin_update'),
    ('special_credit_campaigns','sc_campaign_read'),
    ('special_credit_campaigns','sc_campaign_insert'),
    ('special_credit_campaigns','sc_campaign_update'),
    ('special_credit_recipients','sc_recipient_read'),
    ('special_credit_recipients','sc_recipient_insert'),
    ('special_credit_recipients','sc_recipient_reply'),
    ('special_credit_preferences','sc_pref_read'),
    ('special_credit_preferences','sc_pref_write'),
    ('special_credit_preferences','sc_pref_update'),
    ('special_credit_outbox','sc_outbox_read'),
    ('special_credit_outbox','sc_outbox_insert'),
    ('special_credit_audit','sc_audit_read'),
    ('special_credit_audit','sc_audit_insert')
)
SELECT 1 / CASE WHEN (
    count(*) = 16 AND coalesce(bool_and(p.oid IS NOT NULL), FALSE)
) THEN 1 ELSE 0 END AS m40240_named_policies_guard
FROM expected e
LEFT JOIN pg_catalog.pg_class c
  ON c.oid = pg_catalog.to_regclass('public.' || e.table_name)
LEFT JOIN pg_catalog.pg_policy p
  ON p.polrelid = c.oid AND p.polname = e.policy_name;
\echo M40240_POLICY_CATALOG=PASS_16_OF_16_NAMED_POLICIES

ROLLBACK;
\echo M40240_TRANSACTION=ROLLBACK_READ_ONLY
\echo M40240_LIVE_POLICY_CATALOG=PASS_METADATA_ONLY
\echo M40240_AUTHENTICATED_RLS_DATA_PLANE=NOT_TESTED
\echo M40240_REAL_LOGIN_SESSIONS=NOT_CREATED
\echo M40240_DATABASE_WRITES=NONE
\echo M40240_MIGRATIONS=NONE
\echo M40240_PIX_REAL=OFF
\echo M40240_PRODUCTION=BLOCKED
