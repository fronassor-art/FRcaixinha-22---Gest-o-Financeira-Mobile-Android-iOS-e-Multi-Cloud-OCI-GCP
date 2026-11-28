#!/usr/bin/env bash
# M37431 — local development encrypted backup only; never resets the DB.
set +x
set -euo pipefail
umask 077
mode="$*"
deny(){ echo "M37431_BLOCKED=$1" >&2; exit 2; }
[[ "$mode" == "audit" || "$mode" == "backup" ]] || deny "MODE_AUDIT_OR_BACKUP_REQUIRED"
[[ "$(printenv ENVIRONMENT || true)" != "production" ]] || deny "PRODUCTION_DENIED"
[[ "$(printenv FR_FINANCE_PIX_REAL || true)" != "ON" ]] || deny "PIX_MODE_DENIED"
[[ "$(printenv FR_FINANCE_REAL_USER_ACTIVATION || true)" != "ON" ]] || deny "USER_ACTIVATION_DENIED"
repo="$HOME/fr-finance"
branch="atualizacao-ai-studio-9b46a63187"
pgdata="/data/data/com.termux/files/usr/var/lib/frcaixinha_aistudio_pg18"
database="frcaixinha_aistudio_dev"
role="frc_ai_owner"
cd "$repo" || deny "REPO_DIRECTORY_NOT_FOUND"
[[ "$(git branch --show-current)" == "$branch" ]] || deny "BRANCH_MISMATCH"
[[ -z "$(git status --porcelain)" ]] || deny "WORKTREE_NOT_CLEAN"
[[ -f "$pgdata/PG_VERSION" && "$(cat "$pgdata/PG_VERSION")" == 18 ]] || deny "PG18_CLUSTER_NOT_MATCHED"
for app in git psql pg_isready; do
 command -v "$app" >/dev/null 2>&1 || deny "REQUIRED_TOOL_NOT_FOUND"
done
if [[ "$mode" == "backup" ]]; then
 for app in pg_dump pg_restore age sha256sum; do
  command -v "$app" >/dev/null 2>&1 || deny "BACKUP_TOOL_NOT_FOUND"
 done
 approved="$(printenv FR_FINANCE_APPROVED_SHA || true)"
 [[ "$approved" =~ ^[a-f0-9]{40}$ && "$(git rev-parse HEAD)" == "$approved" ]] || deny "APPROVED_SHA_MISMATCH"
fi
pg_isready -q -h 127.0.0.1 -p 5433 || deny "POSTGRESQL_5433_NOT_READY"
[[ -r /dev/tty ]] || deny "TTY_REQUIRED"
read -r -s -p "Senha local PostgreSQL (oculta): " pw </dev/tty || deny "PASSWORD_ABORTED"
printf '\n' >/dev/tty
[[ -n "$pw" ]] || deny "PASSWORD_EMPTY"
export PGPASSWORD="$pw"
unset pw
partial=""
cleanup(){ unset PGPASSWORD; if [[ -n "$partial" ]]; then rm -f -- "$partial"; fi; }
trap cleanup EXIT
sql(){ psql -X -A -t -q -w -v ON_ERROR_STOP=1 -h 127.0.0.1 -p 5433 -U "$role" -d "$database" -c "$1"; }
identity="$(sql "SELECT current_database()||'|'||current_user||'|'||inet_server_port()||'|'||current_setting('data_directory')||'|'||current_setting('server_version_num');")" || deny "DB_IDENTITY_QUERY_FAILED"
IFS='|' read -r db_name db_role db_port db_dir db_ver <<<"$identity"
[[ "$db_name" == "$database" && "$db_role" == "$role" && "$db_port" == 5433 && "$db_dir" == "$pgdata" ]] || deny "ISOLATED_LOCAL_DB_MISMATCH"
[[ "$db_ver" =~ ^[0-9]+$ ]] || deny "PG_VERSION_INVALID"
(( db_ver >= 180000 && db_ver < 190000 )) || deny "PG_VERSION_NOT_18"
counts="$(sql "SELECT
 (SELECT count(*) FROM public.policies WHERE contribution_per_quota<150.00)::text||'|'||
 (SELECT count(*) FROM public.quotas WHERE value_brl<150.00)::text||'|'||
 (SELECT count(*) FROM public.contributions WHERE amount_due<150.00)::text||'|'||
 (SELECT count(*) FROM public.cycle_contribution_price_audit WHERE old_price_cents<15000 OR requested_price_cents<15000)::text||'|'||
 (SELECT count(*) FROM public.contributions WHERE amount_paid>0 OR paid_at IS NOT NULL OR payment_status='QUITADA')::text||'|'||
 (SELECT count(*) FROM public.pix_payment_intents)::text||'|'||
 (SELECT count(*) FROM public.ledger_transactions)::text||'|'||
 (SELECT count(*) FROM public.loans)::text;")" || deny "PRICE_COUNTS_QUERY_FAILED"
IFS='|' read -r policies quotas contributions audits payments pix ledger loans <<<"$counts"
for n in "$policies" "$quotas" "$contributions" "$audits" "$payments" "$pix" "$ledger" "$loans"; do
 [[ "$n" =~ ^[0-9]+$ ]] || deny "NON_NUMERIC_COUNTS"
done
accounts="$(sql "SELECT
 (SELECT count(*) FROM public.users)::text||'|'||
 (SELECT count(*) FROM public.tenants)::text||'|'||
 (SELECT count(*) FROM public.memberships)::text||'|'||
 (SELECT count(*) FROM public.sessions)::text;")" || deny "IDENTITY_COUNTS_QUERY_FAILED"
IFS='|' read -r users tenants memberships sessions <<<"$accounts"
for n in "$users" "$tenants" "$memberships" "$sessions"; do
 [[ "$n" =~ ^[0-9]+$ ]] || deny "NON_NUMERIC_ACCOUNT_COUNT"
done
echo "=== FR FINANCE M37431 DEV BACKUP PREFLIGHT ==="
echo "M37431_DB_IDENTITY=LOCAL_PG18_PASS"
echo "M37431_OLD_POLICIES=$policies"
echo "M37431_OLD_QUOTAS=$quotas"
echo "M37431_OLD_CONTRIBUTIONS=$contributions"
echo "M37431_OLD_PRICE_AUDITS=$audits"
echo "M37431_PAYMENT_OR_LEDGER_TRACES=$((payments+pix+ledger+loans))"
echo "M37431_USERS_COUNT=$users"
echo "M37431_TENANTS_COUNT=$tenants"
echo "M37431_MEMBERSHIPS_COUNT=$memberships"
echo "M37431_SESSIONS_COUNT=$sessions"
echo "M37431_NO_PRODUCTION_IMPORT=PASS"
if [[ "$mode" == "audit" ]]; then
 echo "M37431_AUDIT=READ_ONLY_PASS"
 echo "M37431_DB_WRITES=NONE"
 exit 0
fi
[[ "$policies" == 1 && "$quotas" == 1 && "$contributions" == 12 && "$audits" == 1 ]] || deny "BASELINE_CHANGED"
[[ "$payments" == 0 && "$pix" == 0 && "$ledger" == 0 && "$loans" == 0 ]] || deny "REAL_FINANCIAL_TRACES_PRESENT"
echo "Backup cifrado de TODO o banco DEV, incluindo contas e senhas HASH."
echo "Guarde a nova senha de cifragem fora do chat; nao e a senha do banco."
read -r -p "Digite AUTORIZO_BACKUP_DEV_CIFRADO: " confirm </dev/tty || deny "USER_CONFIRMATION_CANCELLED"
[[ "$confirm" == AUTORIZO_BACKUP_DEV_CIFRADO ]] || deny "USER_CONFIRMATION_DENIED"
base="$HOME/.local/share/fr-finance/dev-backups"
[[ ! -L "$base" ]] || deny "BACKUP_DIRECTORY_SYMLINK"
mkdir -p -m 700 "$base"
chmod 700 "$base"
backup="$base/before_clean_dev_$(date -u +%Y%m%dT%H%M%SZ)_$$.dump.age"
partial="$backup.partial"
[[ ! -e "$backup" && ! -e "$partial" ]] || deny "BACKUP_ALREADY_EXISTS"
echo "M37431_ENCRYPTION=STARTED"
pg_dump -w -h 127.0.0.1 -p 5433 -U "$role" -d "$database" --format=custom \
 | age --passphrase --output "$partial"
[[ -s "$partial" ]] || deny "ENCRYPTED_BACKUP_EMPTY"
mv -n "$partial" "$backup"
partial=""
chmod 600 "$backup"
age --decrypt "$backup" | pg_restore --list >/dev/null || deny "BACKUP_TOC_VERIFICATION_FAILED"
echo "M37431_BACKUP_TOC=PASS"
echo "M37431_BACKUP_SHA256=$(sha256sum "$backup" | cut -d' ' -f1)"
echo "M37431_BACKUP_FILE=$backup"
echo "M37431_FULL_RESTORE=NOT_TESTED"
echo "M37431_DEV_RESET=NOT_EXECUTED"
echo "M37431_DB_WRITES=NONE"
echo "M37431_PIX_REAL=OFF"
echo "M37431_BACKUP=PASS"
