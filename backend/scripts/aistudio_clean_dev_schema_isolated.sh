#!/usr/bin/env bash
# FR Finance M37433: provision a separate EMPTY schema-only development DB.
set +x
set -euo pipefail
umask 077
mode="$*"
deny(){ echo "M37433_BLOCKED=$1" >&2; exit 2; }
[[ "$mode" == "preflight" || "$mode" == "build" ]] || deny "MODE_INVALID"
[[ "$(printenv ENVIRONMENT || true)" != "production" ]] || deny "PRODUCTION_DENIED"
[[ "$(printenv FR_FINANCE_PIX_REAL || true)" != ON ]] || deny "PIX_ENABLED"
[[ "$(printenv FR_FINANCE_REAL_USER_ACTIVATION || true)" != ON ]] || deny "USERS_ENABLED"
repo="$HOME/fr-finance"
source_db="frcaixinha_aistudio_dev"
target_db="frfinance_clean_dev_m37433"
pgdata="/data/data/com.termux/files/usr/var/lib/frcaixinha_aistudio_pg18"
role="frc_ai_owner"
backupdir="$HOME/.local/share/fr-finance/dev-backups"
backup="$(printenv FR_FINANCE_BACKUP_FILE || true)"
sha="$(printenv FR_FINANCE_BACKUP_SHA256 || true)"
cd "$repo" || deny "REPO_NOT_FOUND"
[[ "$(git branch --show-current)" == "atualizacao-ai-studio-9b46a63187" ]] || deny "BRANCH_MISMATCH"
[[ -z "$(git status --porcelain)" ]] || deny "DIRTY_CHECKOUT"
[[ -f "$pgdata/PG_VERSION" && "$(cat "$pgdata/PG_VERSION")" == "18" ]] || deny "PG18_MISMATCH"
for tool in git psql pg_isready pg_dump pg_restore createdb dropdb sha256sum df; do
 command -v "$tool" >/dev/null 2>&1 || deny "MISSING_COMMAND"
done
[[ ! -L "$backupdir" && -d "$backupdir" ]] || deny "BACKUP_DIR_UNSAFE"
[[ "$backup" == "$backupdir"/before_clean_dev_*.dump.age && -f "$backup" && -s "$backup" && ! -L "$backup" ]] || deny "BACKUP_PATH_INVALID"
[[ "$sha" =~ ^[0-9a-f]{64}$ ]] || deny "BACKUP_SHA_MISSING"
[[ "$(sha256sum "$backup" | cut -d' ' -f1)" == "$sha" ]] || deny "BACKUP_SHA_MISMATCH"
if [[ "$mode" == build ]]; then
 approved="$(printenv FR_FINANCE_APPROVED_SHA || true)"
 [[ "$approved" =~ ^[0-9a-f]{40}$ && "$(git rev-parse HEAD)" == "$approved" ]] || deny "APPROVED_COMMIT_MISMATCH"
fi
pg_isready -q -h 127.0.0.1 -p 5433 || deny "PG18_NOT_READY"
[[ -r /dev/tty ]] || deny "TTY_MISSING"
read -r -s -p "Senha local frc_ai_owner (oculta): " pw </dev/tty || deny "DB_PASSWORD_ABORTED"
printf '\n' >/dev/tty
[[ -n "$pw" ]] || deny "DB_PASSWORD_EMPTY"
export PGPASSWORD="$pw"
unset pw
created=0
private_log=""
cleanup(){
 rc="$?"
 trap - EXIT
 if [[ "$created" == 1 ]]; then
  if dropdb -w -h 127.0.0.1 -p 5433 -U "$role" --maintenance-db=postgres "$target_db" >>"$private_log" 2>&1; then
   echo "M37433_FAILED_BUILD_CLEANUP=PASS"
  else
   echo "M37433_FAILED_BUILD_CLEANUP=BLOCKED"
   rc=2
  fi
 fi
 if [[ -n "$private_log" && -f "$private_log" ]]; then rm -f "$private_log"; fi
 unset PGPASSWORD
 exit "$rc"
}
trap cleanup EXIT
sql(){ psql -X -q -A -t -w -v ON_ERROR_STOP=1 -h 127.0.0.1 -p 5433 -U "$role" -d "$1" -c "$2"; }
identity="$(sql "$source_db" "SELECT current_database()||'|'||current_user||'|'||inet_server_port()||'|'||current_setting('data_directory')||'|'||current_setting('server_version_num');")" || deny "DB_IDENTITY_QUERY_FAILED"
IFS='|' read -r db_user role_user db_port cluster ver <<<"$identity"
[[ "$db_user" == "$source_db" && "$role_user" == "$role" && "$db_port" == 5433 && "$cluster" == "$pgdata" ]] || deny "SOURCE_DB_IDENTITY_MISMATCH"
[[ "$ver" =~ ^[0-9]+$ ]] || deny "SOURCE_PG_VERSION_INVALID"
(( ver>=180000 && ver<190000 )) || deny "SOURCE_NOT_PG18"
exists="$(sql postgres "SELECT count(*) FROM pg_database WHERE datname='$target_db';")" || deny "TARGET_DB_CATALOG_FAILED"
[[ "$exists" == 0 ]] || deny "TARGET_EXISTS_NO_OVERWRITE"
guards="$(sql "$source_db" "SELECT
 (SELECT count(*) FROM pg_constraint WHERE conname IN ('policy_minimum_150_new','quota_minimum_150_new'))::text||'|'||
 (SELECT count(*) FROM information_schema.columns WHERE table_schema='public' AND column_default IS NOT NULL
 AND ((table_name='policies' AND column_name='contribution_per_quota') OR (table_name='quotas' AND column_name='value_brl')))::text||'|'||
 (SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relkind IN ('r','p'))::text;")" || deny "SOURCE_SCHEMA_GUARD_FAILED"
IFS='|' read -r floor_constraints price_defaults source_tables <<<"$guards"
[[ "$floor_constraints" == 2 && "$price_defaults" == 0 ]] || deny "SOURCE_MINIMUM_NOT_ATTESTED"
[[ "$source_tables" =~ ^[0-9]+$ ]] || deny "SOURCE_TABLE_COUNT_INVALID"
((source_tables>=40 && source_tables<=80)) || deny "SOURCE_SCHEMA_UNEXPECTED"
free_kb="$(df -Pk "$HOME" | awk 'NR==2{print $4}')" || deny "FREE_SPACE_QUERY_FAILED"
[[ "$free_kb" =~ ^[0-9]+$ ]] || deny "FREE_SPACE_INVALID"
((free_kb>262144)) || deny "INSUFFICIENT_FREE_SPACE"
echo "=== FR FINANCE M37433 — EMPTY ISOLATED SCHEMA ==="
echo "M37433_BACKUP_SHA256=PASS"
echo "M37433_SOURCE_MINIMUM_150=PASS"
echo "M37433_TARGET=frfinance_clean_dev_m37433"
echo "M37433_ORIGINAL_DATABASE=UNCHANGED"
if [[ "$mode" == "preflight" ]]; then
 echo "M37433_PREFLIGHT=PASS"
 echo "M37433_NEW_DB_CREATED=NO"
 exit 0
fi
echo "Esta operacao cria apenas um NOVO banco com esquema vazio; nao troca a API."
read -r -p "Digite AUTORIZO_BASE_LIMPA_M37433: " confirm </dev/tty || deny "CONSENT_ABORTED"
[[ "$confirm" == AUTORIZO_BASE_LIMPA_M37433 ]] || deny "CONSENT_DENIED"
mkdir -p -m 700 "$HOME/.cache"
private_log="$(mktemp "$HOME/.cache/frfinance_m37433_XXXXXXXX.log")" || deny "PRIVATE_LOG_FAILED"
chmod 600 "$private_log"
createdb -w -h 127.0.0.1 -p 5433 -U "$role" --maintenance-db=postgres \
 --template=template0 --owner="$role" "$target_db" >>"$private_log" 2>&1 || deny "NEW_DB_CREATE_FAILED"
created=1
sql postgres "REVOKE ALL ON DATABASE $target_db FROM PUBLIC" >>"$private_log" 2>&1 || deny "PUBLIC_CONNECT_REVOKE_FAILED"
if pg_dump -w -h 127.0.0.1 -p 5433 -U "$role" -d "$source_db" --schema-only --format=custom --no-owner --no-acl \
 | pg_restore -w -h 127.0.0.1 -p 5433 -U "$role" -d "$target_db" --schema-only \
 --no-owner --no-acl --clean --if-exists --exit-on-error --single-transaction >>"$private_log" 2>&1; then
 echo "M37433_SCHEMA_ONLY_RESTORE=PASS"
else
 deny "SCHEMA_ONLY_RESTORE_FAILED"
fi
check="$(sql "$target_db" "SELECT
 (SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relkind IN ('r','p'))::text||'|'||
 (SELECT count(*) FROM public.users)::text||'|'||
 (SELECT count(*) FROM public.tenants)::text||'|'||
 (SELECT count(*) FROM public.memberships)::text||'|'||
 (SELECT count(*) FROM public.sessions)::text||'|'||
 (SELECT count(*) FROM public.policies)::text||'|'||
 (SELECT count(*) FROM public.quotas)::text||'|'||
 (SELECT count(*) FROM public.contributions)::text||'|'||
 (SELECT count(*) FROM public.cycle_contribution_price_audit)::text||'|'||
 (SELECT count(*) FROM pg_constraint WHERE conname IN ('policy_minimum_150_new','quota_minimum_150_new'))::text||'|'||
 (SELECT count(*) FROM information_schema.columns WHERE table_schema='public' AND column_default IS NOT NULL
 AND ((table_name='policies' AND column_name='contribution_per_quota') OR (table_name='quotas' AND column_name='value_brl')))::text||'|'||
 (SELECT count(*) FROM pg_class WHERE oid='public.users'::regclass AND relrowsecurity AND relforcerowsecurity)::text||'|'||
 (SELECT has_database_privilege('frc_ai_app','$target_db','CONNECT'))::text||'|'||
 (SELECT has_database_privilege('frc_ai_auth','$target_db','CONNECT'))::text;")" || deny "NEW_DB_CATALOG_FAILED"
IFS='|' read -r ntab users tenants memberships sessions policies quotas contrib audits minimum defaults rls app_connect auth_connect <<<"$check"
[[ "$ntab" == "$source_tables" ]] || deny "NEW_DB_SCHEMA_MISMATCH"
for n in "$users" "$tenants" "$memberships" "$sessions" "$policies" "$quotas" "$contrib" "$audits" "$defaults"; do
 [[ "$n" == 0 ]] || deny "NEW_DB_NOT_EMPTY"
done
[[ "$minimum" == 2 && "$rls" == 1 && "$app_connect" == f && "$auth_connect" == f ]] || deny "NEW_DB_SECURITY_INCOMPLETE"
created=0
echo "M37433_EMPTY_IDENTITIES=PASS"
echo "M37433_EMPTY_FINANCIAL_HISTORY=PASS"
echo "M37433_RLS_AND_MINIMUM_150=PASS"
echo "M37433_APP_AUTH_CONNECT=DENIED"
echo "M37433_BACKEND_CUTOVER=NOT_AUTHORIZED"
echo "M37433_ORIGINAL_DB_WRITES=NO"
echo "M37433_PIX_REAL=OFF"
echo "M37433_STATUS=NEW_ISOLATED_SCHEMA_READY"
