#!/usr/bin/env bash
# FR Caixinha AI Studio M21100: ONLY local 044, never previous migrations.
set -euo pipefail
umask 077
MODE="$(echo "$1")"
ROOT="$HOME/frcaixinha-aistudio-mobile"
PGDATA="/data/data/com.termux/files/usr/var/lib/frcaixinha_aistudio_pg18"
BRANCH="atualizacao-ai-studio-9b46a63187"
SHA="$(printenv AI_STUDIO_APPROVED_SHA || true)"
deny(){ echo "M21100_BLOQUEADO: $*" >&2; exit 2; }
[[ "$MODE" == "audit" || "$MODE" == "apply" || "$MODE" == "verify" ]] || deny "use audit|apply|verify"
[[ "$SHA" =~ ^[a-f0-9]{40}$ ]] || deny "full expected SHA required"
cd "$ROOT" || deny "repository missing"
[[ "$(git branch --show-current)" == "$BRANCH" ]] || deny "wrong branch"
[[ "$(git rev-parse HEAD)" == "$SHA" ]] || deny "SHA not approved"
[[ -z "$(git status --porcelain)" ]] || deny "working tree has changes"
[[ -f "$PGDATA/PG_VERSION" && "$(cat "$PGDATA/PG_VERSION")" == "18" ]] || deny "wrong PG cluster"
for c in git psql pg_isready pg_dump pg_restore sha256sum age; do
 command -v "$c" >/dev/null || deny "missing $c"
done
pg_isready -q -h 127.0.0.1 -p 5433 || deny "PG18 unavailable"
read -r -s -p "Senha PostgreSQL frc_ai_owner (oculta): " PW </dev/tty || deny "password input error"
printf '\n' >/dev/tty
[[ -n "$PW" ]] || deny "empty password"
export PGPASSWORD="$PW"
unset PW
sql(){ psql -X -q -w -v ON_ERROR_STOP=1 -h 127.0.0.1 -p 5433 \
 -U frc_ai_owner -d frcaixinha_aistudio_dev "$@"; }
identity="$(sql -tAc "SELECT concat_ws('|',current_database(),current_user,inet_server_port(),current_setting('data_directory'))")"
[[ "$identity" == "frcaixinha_aistudio_dev|frc_ai_owner|5433|$PGDATA" ]] || deny "DB identity mismatch"
[[ "$(sql -tAc "SELECT current_setting('server_version_num')::int BETWEEN 180000 AND 189999")" == "t" ]] || deny "PostgreSQL release mismatch"
tables="$(sql -tAc "SELECT count(*) FROM pg_catalog.pg_tables WHERE schemaname='public'")"
constraints="$(sql -tAc "SELECT count(*) FROM pg_constraint WHERE conname IN ('policy_minimum_150_new','quota_minimum_150_new') AND NOT convalidated")"
[[ "$constraints" == "2" ]] || deny "043 floor not verified"
audit="$(sql -tAc "SELECT count(*) FROM pg_class WHERE oid=to_regclass('public.cycle_opening_audit')")"
if [[ "$MODE" == "verify" ]]; then
 [[ "$tables" == "46" && "$audit" == "1" ]] || deny "044 incomplete"
 sql -tAc "SELECT count(*) FROM pg_trigger WHERE tgname IN ('cycle_opening_immutable_row','cycle_opening_immutable_truncate') AND tgenabled='O'" | grep -Fx "2" >/dev/null || deny "audit immutability missing"
 sql -tAc "SELECT has_function_privilege('frc_ai_app','public.cycle_open_create(text,uuid,integer,bigint,text,uuid)','EXECUTE') AND NOT has_table_privilege('frc_ai_app','public.cycle_opening_audit','INSERT')" | grep -Fx "t" >/dev/null || deny "incorrect grants"
 echo "M21100_LOCAL_044_VERIFY=PASS"
 exit 0
fi
[[ "$tables" == "45" && "$audit" == "0" ]] || deny "044 already applied or database modified"
echo "M21100_044_PREFLIGHT=PASS"
if [[ "$MODE" == "audit" ]]; then echo "M21100_044_NOT_APPLIED=PASS"; exit 0; fi
[[ "$(printenv AI_STUDIO_APPROVE_CYCLE_044 || true)" == "YES" ]] || deny "manual approval missing"
read -r -p "Digite AUTORIZO_ABERTURA_CICLO_044: " CONFIRM </dev/tty
[[ "$CONFIRM" == "AUTORIZO_ABERTURA_CICLO_044" ]] || deny "confirmation denied"
BACKUPDIR="$HOME/.local/share/frcaixinha-aistudio-mobile/backups"
[[ ! -L "$BACKUPDIR" ]] || deny "symlink backup folder"
mkdir -p -m 700 "$BACKUPDIR"
chmod 700 "$BACKUPDIR"
BACKUP="$BACKUPDIR/before_cycle_open_044_$(date -u +%Y%m%dT%H%M%SZ)_$$.dump.age"
[[ ! -e "$BACKUP" && ! -e "$BACKUP.partial" ]] || deny "backup exists"
trap 'rm -f "$BACKUP.partial"' EXIT
echo "=== AGE BACKUP / strong manual passphrase ==="
pg_dump -h 127.0.0.1 -p 5433 -U frc_ai_owner -w \
 -d frcaixinha_aistudio_dev --format=custom --no-owner --no-acl |
 age --passphrase --output "$BACKUP.partial"
[[ -s "$BACKUP.partial" ]] || deny "backup empty"
mv -n "$BACKUP.partial" "$BACKUP"
trap - EXIT
sha256sum "$BACKUP"
age --decrypt "$BACKUP" | pg_restore --list >/dev/null || deny "backup decrypt failed"
echo "M21100_BACKUP_VERIFIED=PASS"
sql --single-transaction -f "$ROOT/backend/local_migrations/044_cycle_opening_audit.sql"
echo "M21100_LOCAL_044_APPLIED=PASS"
echo "M21100_POST_VERIFY_REQUIRED"
