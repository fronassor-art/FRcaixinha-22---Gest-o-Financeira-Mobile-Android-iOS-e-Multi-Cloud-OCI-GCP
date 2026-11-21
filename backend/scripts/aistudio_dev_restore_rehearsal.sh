#!/usr/bin/env bash
# FR Finance M37432 — verify encrypted backup via an ISOLATED temporary DB.
# Original frcaixinha_aistudio_dev is never altered.
set +x
set -euo pipefail
umask 077
mode="$*"
deny(){ echo "M37432_BLOCKED=$1" >&2; exit 2; }
[[ "$mode" == preflight || "$mode" == rehearse ]] || deny "MODE_INVALID"
[[ "$(printenv ENVIRONMENT || true)" != production ]] || deny "PRODUCTION_DENIED"
[[ "$(printenv FR_FINANCE_PIX_REAL || true)" != ON ]] || deny "PIX_ON_DENIED"
[[ "$(printenv FR_FINANCE_REAL_USER_ACTIVATION || true)" != ON ]] || deny "REAL_USERS_DENIED"
repo="$HOME/fr-finance"
pgdata="/data/data/com.termux/files/usr/var/lib/frcaixinha_aistudio_pg18"
database="frcaixinha_aistudio_dev"
role="frc_ai_owner"
scratch="frfinance_restore_check_m37432"
dir="$HOME/.local/share/fr-finance/dev-backups"
file="$(printenv FR_FINANCE_BACKUP_FILE || true)"
checksum="$(printenv FR_FINANCE_BACKUP_SHA256 || true)"
cd "$repo" || deny "WRONG_REPO_PATH"
[[ "$(git branch --show-current)" == atualizacao-ai-studio-9b46a63187 ]] || deny "WRONG_BRANCH"
[[ -z "$(git status --porcelain)" ]] || deny "DIRTY_WORKTREE"
[[ -f "$pgdata/PG_VERSION" && "$(cat "$pgdata/PG_VERSION")" == 18 ]] || deny "WRONG_PG18_CLUSTER"
for cmd in git psql pg_isready pg_restore createdb dropdb age sha256sum df; do
 command -v "$cmd" >/dev/null 2>&1 || deny "REQUIRED_TOOL_MISSING"
done
[[ -d "$dir" && ! -L "$dir" ]] || deny "BACKUP_DIR_NOT_SAFE"
[[ -n "$file" && "$file" == "$dir"/before_clean_dev_*.dump.age ]] || deny "BACKUP_FILE_PATH_NOT_ALLOWED"
[[ -f "$file" && -s "$file" && ! -L "$file" ]] || deny "BACKUP_FILE_INVALID"
[[ "$checksum" =~ ^[0-9a-f]{64}$ ]] || deny "SHA256_REQUIRED"
[[ "$(sha256sum "$file" | cut -d' ' -f1)" == "$checksum" ]] || deny "BACKUP_INTEGRITY_MISMATCH"
if [[ "$mode" == rehearse ]]; then
 approved="$(printenv FR_FINANCE_APPROVED_SHA || true)"
 [[ "$approved" =~ ^[0-9a-f]{40}$ && "$(git rev-parse HEAD)" == "$approved" ]] || deny "APPROVED_COMMIT_MISMATCH"
fi
pg_isready -q -h 127.0.0.1 -p 5433 || deny "PG18_NOT_READY"
[[ -r /dev/tty ]] || deny "TTY_MISSING"
read -r -s -p "Senha local PostgreSQL (oculta): " pw </dev/tty || deny "PASSWORD_ABORTED"
printf '\n' >/dev/tty
[[ -n "$pw" ]] || deny "PASSWORD_EMPTY"
export PGPASSWORD="$pw"
unset pw
created=0
log=""
finish(){
 rc="$?"
 trap - EXIT
 if [[ "$created" == 1 ]]; then
  if dropdb -w -h 127.0.0.1 -p 5433 -U "$role" --maintenance-db=postgres "$scratch" >>"$log" 2>&1; then
   echo "M37432_DISPOSABLE_CLEANUP=PASS"
  else
   echo "M37432_DISPOSABLE_CLEANUP=BLOCKED"
   rc=2
  fi
 fi
 if [[ -n "$log" && -f "$log" ]]; then rm -f -- "$log"; fi
 unset PGPASSWORD
 exit "$rc"
}
trap finish EXIT
sql(){ psql -X -A -t -q -w -v ON_ERROR_STOP=1 -h 127.0.0.1 -p 5433 -U "$role" -d "$1" -c "$2"; }
id="$(sql "$database" "SELECT current_database()||'|'||current_user||'|'||inet_server_port()||'|'||current_setting('data_directory')||'|'||current_setting('server_version_num');")" || deny "IDENTITY_QUERY_FAILED"
IFS='|' read -r db_name db_role db_port cluster ver <<<"$id"
[[ "$db_name" == "$database" && "$db_role" == "$role" && "$db_port" == 5433 && "$cluster" == "$pgdata" ]] || deny "SOURCE_IDENTITY_MISMATCH"
[[ "$ver" =~ ^[0-9]+$ ]] || deny "PG_VERSION_INVALID"
(( ver>=180000 && ver<190000 )) || deny "PG_VERSION_NOT_18"
exists="$(sql postgres "SELECT count(*) FROM pg_database WHERE datname='$scratch';")" || deny "SCRATCH_CATALOG_FAILED"
[[ "$exists" == 0 ]] || deny "SCRATCH_ALREADY_EXISTS_NO_OVERWRITE"
echo "=== FR FINANCE M37432 — RECOVERY REHEARSAL ==="
echo "M37432_SOURCE=LOCAL_PG18_VERIFIED"
echo "M37432_BACKUP_SHA256=PASS"
echo "M37432_ORIGINAL_DB_WRITES=NO"
if [[ "$mode" == preflight ]]; then
 echo "M37432_PREFLIGHT=PASS"
 echo "M37432_RESTORE=NOT_EXECUTED"
 exit 0
fi
used="$(sql postgres "SELECT pg_database_size('$database');")" || deny "DB_SIZE_QUERY_FAILED"
available="$(df -Pk "$HOME" | awk 'NR==2 {print $4}')" || deny "DISK_SPACE_QUERY_FAILED"
[[ "$used" =~ ^[0-9]+$ && "$available" =~ ^[0-9]+$ ]] || deny "DISK_SPACE_INVALID"
(( available*1024 > used*2 + 134217728 )) || deny "SCRATCH_DISK_INSUFFICIENT"
echo "This only creates and later deletes an isolated temporary database."
echo "The original DB and encrypted backup are never deleted."
read -r -p "Digite AUTORIZO_ENSAIO_M37432: " confirm </dev/tty || deny "APPROVAL_ABORTED"
[[ "$confirm" == AUTORIZO_ENSAIO_M37432 ]] || deny "APPROVAL_DENIED"
mkdir -p -m 700 "$HOME/.cache"
log="$(mktemp "$HOME/.cache/m37432_XXXXXXXX.log")" || deny "RESTORE_LOG_FAILED"
chmod 600 "$log"
createdb -w -h 127.0.0.1 -p 5433 -U "$role" --maintenance-db=postgres \
 --template=template0 --owner="$role" "$scratch" >>"$log" 2>&1 || deny "SCRATCH_CREATE_FAILED"
created=1
echo "M37432_SCRATCH_CREATED=PASS"
if age --decrypt "$file" | pg_restore --no-password -h 127.0.0.1 -p 5433 -U "$role" \
 -d "$scratch" --no-owner --no-acl --exit-on-error --single-transaction >>"$log" 2>&1; then
 echo "M37432_FULL_RESTORE=PASS"
else
 deny "FULL_RESTORE_FAILED"
fi
row="$(sql "$scratch" "SELECT
 (SELECT count(*) FROM public.users)::text||'|'||
 (SELECT count(*) FROM public.tenants)::text||'|'||
 (SELECT count(*) FROM public.memberships)::text||'|'||
 (SELECT count(*) FROM public.sessions)::text||'|'||
 (SELECT count(*) FROM public.policies WHERE contribution_per_quota<150)::text||'|'||
 (SELECT count(*) FROM public.quotas WHERE value_brl<150)::text||'|'||
 (SELECT count(*) FROM public.contributions WHERE amount_due<150)::text||'|'||
 (SELECT count(*) FROM public.cycle_contribution_price_audit WHERE old_price_cents<15000 OR requested_price_cents<15000)::text;")" || deny "RESTORED_COUNTS_FAILED"
IFS='|' read -r users tenants members sessions policies quotas contributions audits <<<"$row"
for n in "$users" "$tenants" "$members" "$sessions" "$policies" "$quotas" "$contributions" "$audits"; do
 [[ "$n" =~ ^[0-9]+$ ]] || deny "RESTORED_VALUE_INVALID"
done
[[ "$users" == 1 && "$tenants" == 1 && "$members" == 2 ]] || deny "RESTORED_IDENTITY_MISMATCH"
[[ "$policies" == 1 && "$quotas" == 1 && "$contributions" == 12 && "$audits" == 1 ]] || deny "RESTORED_LEGACY_COUNTS_MISMATCH"
echo "M37432_IDENTITIES=1_USER_1_TENANT_2_MEMBERSHIPS"
echo "M37432_SESSIONS_IN_BACKUP=$sessions"
echo "M37432_FINANCIAL_FIXTURES=1_1_12_1_VERIFIED"
echo "M37432_RECOVERABILITY=PROVEN_DISPOSABLE"
echo "M37432_OLD_DATABASE_CHANGED=NO"
echo "M37432_PRODUCTION_IMPORT=FORBIDDEN"
echo "M37432_CLEAN_DB_REBUILD=NOT_STARTED"
echo "M37432_PIX_REAL=OFF"
echo "M37432_STATUS=PASS"
