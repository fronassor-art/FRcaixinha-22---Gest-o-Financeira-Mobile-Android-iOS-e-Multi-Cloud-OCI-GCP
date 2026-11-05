#!/usr/bin/env bash
set -euo pipefail
[[ "$(printenv GITHUB_ACTIONS || true)" == true ]] || exit 2
[[ "$(printenv PGDATABASE || true)" == frcaixinha_ci ]] || exit 2
[[ "$(printenv PGUSER || true)" == postgres ]] || exit 2
[[ "$(printenv PGPORT || true)" == 5432 ]] || exit 2
SCRIPTS=()
for n in 034 035 036 037 038 039 040 041; do
 files=(backend/local_migrations/"$n"_*.sql)
 [[ "${#files[@]}" -eq 1 && -f "${files[0]}" ]] || exit 2
 SCRIPTS+=(-f "${files[0]}")
done
PGOPTIONS='-c frcaixinha.local_parity_ci=1' \
psql -X -v ON_ERROR_STOP=1 --single-transaction "${SCRIPTS[@]}"
psql -X -v ON_ERROR_STOP=1 <<'SQL'
BEGIN READ ONLY;
DO $test$
DECLARE n int; tbl text;
BEGIN
 SELECT count(*) INTO n FROM pg_catalog.pg_tables
 WHERE schemaname='public' AND tablename LIKE 'local_m0%';
 IF n<>8 THEN RAISE EXCEPTION 'M20100: expected 8 local simulation tables, got %',n; END IF;
 FOREACH tbl IN ARRAY ARRAY[
 'local_m034_webhook_evidence','local_m035_pix_dryrun',
 'local_m036_orders_inbox','local_m037_order_evidence',
 'local_m038_order_reservation','local_m039_reconciliation_hold',
 'local_m040_incident_audit','local_m041_notification_outbox'
 ] LOOP
  IF NOT EXISTS(SELECT 1 FROM pg_class WHERE oid=to_regclass('public.'||tbl)
   AND relrowsecurity AND relforcerowsecurity)
  OR has_table_privilege('frcaixinha_app_role','public.'||tbl,'SELECT')
  OR has_table_privilege('frcaixinha_app_role','public.'||tbl,'INSERT')
  OR has_table_privilege('frcaixinha_auth_role','public.'||tbl,'SELECT')
  THEN RAISE EXCEPTION 'M20100: unsafe RLS or GRANT: %',tbl; END IF;
 END LOOP;
 RAISE NOTICE 'M20100_PG16_18_LOCAL_SCHEMA_CI=PASS';
END $test$;
COMMIT;
SQL
echo "M20100_LOCAL_PARITY_PG_CI=PASS"
