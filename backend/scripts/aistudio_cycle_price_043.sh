#!/usr/bin/env bash
# Exclusive FR Caixinha AI Studio local 043 - no replay of 001-042.
set -euo pipefail
umask 077
ROOT="$HOME/frcaixinha-aistudio-mobile"
MODE="$1"
SHA="$(printenv AI_STUDIO_APPROVED_SHA || true)"
BRANCH="atualizacao-ai-studio-9b46a63187"
PGDATA="/data/data/com.termux/files/usr/var/lib/frcaixinha_aistudio_pg18"
deny(){ echo "M20700_BLOQUEADO: $*" >&2; exit 2; }
[[ "$MODE" == audit || "$MODE" == apply || "$MODE" == verify ]] || deny "use audit|apply|verify"
[[ "$SHA" =~ ^[a-f0-9]{40}$ ]] || deny "approved full SHA required"
cd "$ROOT" || deny "wrong repository"
[[ "$(git branch --show-current)" == "$BRANCH" && "$(git rev-parse HEAD)" == "$SHA" ]] || deny "branch/commit mismatch"
[[ -z "$(git status --porcelain)" ]] || deny "dirty working tree"
[[ -f "$PGDATA/PG_VERSION" && "$(cat "$PGDATA/PG_VERSION")" == 18 ]] || deny "wrong PG18"
for c in git pg_isready psql pg_dump pg_restore age sha256sum; do command -v "$c" >/dev/null || deny "missing $c"; done
pg_isready -q -h 127.0.0.1 -p 5433 || deny "PostgreSQL 5433 down"
read -r -s -p "Senha PostgreSQL frc_ai_owner (oculta): " PW </dev/tty || deny "missing password"
printf '\n' >/dev/tty
[[ -n "$PW" ]] || deny "empty password"
export PGPASSWORD="$PW"; unset PW
sql(){ psql -X -q -w -v ON_ERROR_STOP=1 -h 127.0.0.1 -p 5433 -U frc_ai_owner -d frcaixinha_aistudio_dev "$@"; }
DB_IDENTITY=$(sql -tAc "SELECT concat_ws('|',current_database(),current_user,inet_server_port(),current_setting('data_directory'))")
[[ "$DB_IDENTITY" == "frcaixinha_aistudio_dev|frc_ai_owner|5433|$PGDATA" ]] || deny "wrong database identity"
[[ "$(sql -tAc "SELECT count(*) FROM pg_catalog.pg_tables WHERE schemaname='public'")" == 45 ]] || deny "expected 45 tables"
CONSTRAINTS=$(sql -tAc "SELECT count(*) FROM pg_constraint WHERE conname IN ('policy_minimum_150_new','quota_minimum_150_new')")
if [[ "$MODE" == verify ]]; then
  [[ "$CONSTRAINTS" == 2 ]] || deny "minimum constraints missing"
  DEFAULTS=$(sql -tAc "SELECT count(*) FROM information_schema.columns WHERE table_schema='public' AND ((table_name='policies' AND column_name='contribution_per_quota') OR (table_name='quotas' AND column_name='value_brl')) AND column_default IS NOT NULL")
  [[ "$DEFAULTS" == 0 ]] || deny "legacy default still enabled"
  echo "M20700_LOCAL_043_VERIFY=PASS"
  exit 0
fi
[[ "$CONSTRAINTS" == 0 ]] || deny "043 already applied or partial"
echo "M20700_043_AUDIT=PASS"
if [[ "$MODE" == audit ]]; then echo "M20700_043_NOT_APPLIED=PASS"; exit 0; fi
[[ "$(printenv AI_STUDIO_APPROVE_QUOTA_MIN_043 || true)" == YES ]] || deny "manual approval required"
read -r -p "Digite AUTORIZO_MINIMO_COTA_043: " CONFIRM </dev/tty
[[ "$CONFIRM" == AUTORIZO_MINIMO_COTA_043 ]] || deny "confirmation denied"
DIR="$HOME/.local/share/frcaixinha-aistudio-mobile/backups"
[[ ! -L "$DIR" ]] || deny "backup folder symlink"
mkdir -p -m 700 "$DIR"; chmod 700 "$DIR"
BACKUP="$DIR/before_quota_min_043_$(date -u +%Y%m%dT%H%M%SZ)_$$.dump.age"
[[ ! -e "$BACKUP" && ! -e "$BACKUP.partial" ]] || deny "backup already exists"
trap 'rm -f "$BACKUP.partial"' EXIT
echo "=== BACKUP AGE: passphrase must be protected ==="
pg_dump -h 127.0.0.1 -p 5433 -U frc_ai_owner -w -d frcaixinha_aistudio_dev --format=custom --no-owner --no-acl | age --passphrase --output "$BACKUP.partial"
[[ -s "$BACKUP.partial" ]] || deny "backup empty"
mv -n "$BACKUP.partial" "$BACKUP"; trap - EXIT
sha256sum "$BACKUP"
age --decrypt "$BACKUP" | pg_restore --list >/dev/null || deny "backup unverified"
echo "M20700_BACKUP_VERIFIED=PASS"
sql --single-transaction -f "$ROOT/backend/local_migrations/043_cycle_contribution_contract_minimum.sql"
echo "M20700_LOCAL_043_APPLIED=PASS"
