#!/usr/bin/env bash
# AI Studio M20400: ONLY local migration 042. Never replays 001-041.
set -euo pipefail
umask 077
ROOT="$HOME/frcaixinha-aistudio-mobile"
MODE="${1:-}"
SHA="${AI_STUDIO_APPROVED_SHA:-}"
BRANCH="atualizacao-ai-studio-9b46a63187"
ORIGIN="https://github.com/fronassor-art/FRcaixinha-22---Gest-o-Financeira-Mobile-Android-iOS-e-Multi-Cloud-OCI-GCP.git"
PGDATA="/data/data/com.termux/files/usr/var/lib/frcaixinha_aistudio_pg18"
fail(){ echo "M20400_BLOQUEADO: $*" >&2; exit 2; }
[[ "$MODE" == audit || "$MODE" == apply || "$MODE" == verify ]] || fail "use audit|apply|verify"
cd "$ROOT" || fail "project not found"
[[ "$(git remote get-url origin)" == "$ORIGIN" ]] || fail "wrong origin"
[[ "$(git branch --show-current)" == "$BRANCH" ]] || fail "wrong branch"
[[ "$SHA" =~ ^[0-9a-f]{40}$ && "$(git rev-parse HEAD)" == "$SHA" ]] || fail "SHA mismatch"
[[ -z "$(git status --porcelain)" ]] || fail "dirty tree"
[[ -f "$PGDATA/PG_VERSION" && "$(cat "$PGDATA/PG_VERSION")" == 18 ]] || fail "PG18 incorrect"
for c in psql pg_dump pg_restore age sha256sum pg_isready git; do command -v "$c" >/dev/null || fail "missing $c"; done
pg_isready -q -h 127.0.0.1 -p 5433 || fail "PG18 5433 down"
[[ -r /dev/tty ]] || fail "interactive terminal needed"
read -r -s -p "Senha PostgreSQL frc_ai_owner (oculta): " PW </dev/tty || fail "password missing"
printf '\n' >/dev/tty
[[ -n "$PW" ]] || fail "empty password"
export PGPASSWORD="$PW"
unset PW
sql(){ psql -X -q -w -v ON_ERROR_STOP=1 -h 127.0.0.1 -p 5433 \
 -U frc_ai_owner -d frcaixinha_aistudio_dev "$@"; }

if [[ "$MODE" == verify ]]; then
 sql <<'SQL'
BEGIN READ ONLY;
DO $check$
DECLARE n int;
BEGIN
 IF current_database()<>'frcaixinha_aistudio_dev'
 OR current_user<>'frc_ai_owner' OR inet_server_port()<>5433
 OR current_setting('data_directory')<>
 '/data/data/com.termux/files/usr/var/lib/frcaixinha_aistudio_pg18'
 THEN RAISE EXCEPTION 'wrong PG18'; END IF;
 SELECT count(*) INTO n FROM pg_catalog.pg_tables WHERE schemaname='public';
 IF n<>45 OR to_regclass('public.cycle_contribution_price_audit') IS NULL
 OR NOT EXISTS(SELECT 1 FROM pg_class
  WHERE oid='public.cycle_contribution_price_audit'::regclass
  AND relrowsecurity AND relforcerowsecurity)
 OR has_table_privilege('frc_ai_app','public.cycle_contribution_price_audit','INSERT')
 OR has_table_privilege('frc_ai_app','public.cycle_contribution_price_audit','UPDATE')
 OR has_table_privilege('frc_ai_auth','public.cycle_contribution_price_audit','SELECT')
 OR NOT has_function_privilege('frc_ai_app','public.cycle_price_change(text,uuid,uuid,bigint,text,uuid)','EXECUTE')
 OR NOT has_function_privilege('frc_ai_app','public.cycle_price_status(text,uuid)','EXECUTE')
 OR has_function_privilege('frc_ai_app','public.cycle_price_admin_actor(text,uuid)','EXECUTE')
 OR NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='cycle_price_immutable_row' AND tgenabled='O')
 OR NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='cycle_price_immutable_truncate' AND tgenabled='O')
 THEN RAISE EXCEPTION 'M20400 audit schema/roles invalid'; END IF;
 RAISE NOTICE 'M20400_POLICY_042_RLS_PASS: 45 tables';
END $check$;
COMMIT;
SQL
 echo "M20400_LOCAL_042_VERIFY=PASS"
 echo "M20400_EXISTING_CONTRIBUTIONS=NOT_REPRICED"
 exit 0
fi
echo "=== M20400 PREFLIGHT READ ONLY ==="
sql <<'SQL'
BEGIN READ ONLY;
DO $guard$
DECLARE n int;
BEGIN
 IF current_database()<>'frcaixinha_aistudio_dev'
 OR current_user<>'frc_ai_owner' OR session_user<>'frc_ai_owner'
 OR inet_server_port()<>5433 OR current_setting('data_directory')<>
 '/data/data/com.termux/files/usr/var/lib/frcaixinha_aistudio_pg18'
 OR current_setting('server_version_num')::int NOT BETWEEN 180000 AND 189999
 THEN RAISE EXCEPTION 'M20400 wrong PG18'; END IF;
 SELECT count(*) INTO n FROM pg_catalog.pg_tables WHERE schemaname='public';
 IF n<>44 OR to_regclass('public.local_m041_notification_outbox') IS NULL
 OR to_regclass('public.cycle_contribution_price_audit') IS NOT NULL
 OR to_regclass('public.notification_inbox') IS NULL
 THEN RAISE EXCEPTION 'M20400 requires 44-table M20200 baseline'; END IF;
 RAISE NOTICE 'M20400_PREFLIGHT_PASS: 44 tables';
END $guard$;
COMMIT;
SQL
echo "M20400_AUDIT=PASS"
if [[ "$MODE" == audit ]]; then echo "M20400_MIGRATION_042_NOT_APPLIED=PASS"; exit 0; fi
[[ "${AI_STUDIO_APPROVE_POLICY_042:-}" == YES ]] || fail "requires AI_STUDIO_APPROVE_POLICY_042=YES"
read -r -p "Digite AUTORIZO_POLITICA_COTA_042: " CONFIRM
[[ "$CONFIRM" == AUTORIZO_POLITICA_COTA_042 ]] || fail "confirmation denied"
DIR="$HOME/.local/share/frcaixinha-aistudio-mobile/backups"
[[ ! -L "$DIR" ]] || fail "backup directory symlink"
mkdir -p -m 700 "$DIR"
chmod 700 "$DIR"
BACKUP="$DIR/before_cycle_price_042_$(date -u +%Y%m%dT%H%M%SZ)_$$.dump.age"
[[ ! -e "$BACKUP" && ! -e "$BACKUP.partial" ]] || fail "backup exists"
trap 'rm -f "$BACKUP.partial"' EXIT
echo "=== BACKUP AGE (STRONG MANUAL PASSPHRASE, NEVER EMPTY) ==="
pg_dump -h 127.0.0.1 -p 5433 -U frc_ai_owner -w \
 -d frcaixinha_aistudio_dev --format=custom --no-owner --no-acl |
 age --passphrase --output "$BACKUP.partial"
[[ -s "$BACKUP.partial" ]] || fail "backup empty"
mv -n "$BACKUP.partial" "$BACKUP"
trap - EXIT
sha256sum "$BACKUP"
age --decrypt "$BACKUP" | pg_restore --list >/dev/null
echo "M20400_BACKUP_VERIFIED=PASS"
echo "=== APPLY ONLY LOCAL 042 IN ONE TRANSACTION ==="
sql --single-transaction -f "$ROOT/backend/local_migrations/042_cycle_contribution_price_audit.sql"
echo "M20400_LOCAL_042_APPLIED=PASS"
echo "M20400_POST_VERIFY_REQUIRED"
