#!/usr/bin/env bash
# AI Studio M20100: local synthetic parity 034–041. NO REAL FINANCE/API SENDS.
set -euo pipefail
umask 077
ROOT="$HOME/frcaixinha-aistudio-mobile"
BRANCH="atualizacao-ai-studio-9b46a63187"
ORIGIN="https://github.com/fronassor-art/FRcaixinha-22---Gest-o-Financeira-Mobile-Android-iOS-e-Multi-Cloud-OCI-GCP.git"
PGDATA="/data/data/com.termux/files/usr/var/lib/frcaixinha_aistudio_pg18"
APPROVED="$(printenv AI_STUDIO_APPROVED_SHA || true)"
MODE="$(printf "%s" "${1:-}")"
fail(){ printf "M20100_BLOQUEADO: %s\n" "$*" >&2; exit 2; }

[[ "$MODE" == audit || "$MODE" == apply || "$MODE" == verify ]] || fail "mode audit|apply|verify"
cd "$ROOT" || fail "clone AI Studio ausente"
[[ "$(git remote get-url origin)" == "$ORIGIN" ]] || fail "origin divergente"
[[ "$(git branch --show-current)" == "$BRANCH" ]] || fail "branch incorreta"
[[ "$APPROVED" =~ ^[0-9a-f]{40}$ && "$(git rev-parse HEAD)" == "$APPROVED" ]] ||
 fail "HEAD/commit aprovado incorreto"
[[ -z "$(git status --porcelain)" ]] || fail "arvore Git modificada"
[[ -f "$PGDATA/PG_VERSION" && "$(cat "$PGDATA/PG_VERSION")" == 18 ]] || fail "PG18 errado"
for tool in psql pg_dump pg_restore age sha256sum pg_isready git; do
 command -v "$tool" >/dev/null || fail "ausente: $tool"
done
pg_isready -q -h 127.0.0.1 -p 5433 || fail "PG18 5433 indisponivel"
SCRIPTS=()
for n in 034 035 036 037 038 039 040 041; do
 mapfile -t matches < <(find "$ROOT/backend/local_migrations" -maxdepth 1 \
  -type f -name "$n"'_*.sql' -print)
 [[ "${#matches[@]}" == 1 ]] || fail "arquivo local $n ausente ou duplicado"
 SCRIPTS+=(-f "${matches[0]}")
done
[[ -r /dev/tty ]] || fail "terminal interativo exigido"
read -r -s -p "Senha PostgreSQL frc_ai_owner (oculta): " DB_PASS </dev/tty ||
 fail "senha indisponivel"
printf '\n' >/dev/tty
[[ -n "$DB_PASS" ]] || fail "senha vazia"
export PGPASSWORD="$DB_PASS"
unset DB_PASS
psql_local(){
 psql -X -w -q -v ON_ERROR_STOP=1 -h 127.0.0.1 -p 5433 \
 -U frc_ai_owner -d frcaixinha_aistudio_dev "$@"
}

if [[ "$MODE" == verify ]]; then
 echo "=== M20100 VERIFICACAO POS MIGRACAO: SOMENTE LEITURA ==="
 psql_local <<'SQL'
BEGIN READ ONLY;
DO $verify$
DECLARE n int; tbl text;
BEGIN
 IF current_database()<>'frcaixinha_aistudio_dev'
 OR current_user<>'frc_ai_owner' OR session_user<>'frc_ai_owner'
 OR inet_server_port()<>5433 OR current_setting('data_directory')<>
 '/data/data/com.termux/files/usr/var/lib/frcaixinha_aistudio_pg18'
 THEN RAISE EXCEPTION 'M20100: wrong cluster'; END IF;
 SELECT count(*) INTO n FROM pg_catalog.pg_tables WHERE schemaname='public';
 IF n<>44 OR to_regclass('public.notification_inbox') IS NULL
 OR to_regclass('public.member_lifecycle_requests') IS NULL
 OR to_regclass('public.member_lifecycle_review_events') IS NULL
 THEN RAISE EXCEPTION 'M20100: expected 44 tables with M031/M19300'; END IF;
 FOREACH tbl IN ARRAY ARRAY[
 'local_m034_webhook_evidence','local_m035_pix_dryrun',
 'local_m036_orders_inbox','local_m037_order_evidence',
 'local_m038_order_reservation','local_m039_reconciliation_hold',
 'local_m040_incident_audit','local_m041_notification_outbox'
 ] LOOP
  IF to_regclass('public.'||tbl) IS NULL
  OR NOT EXISTS(SELECT 1 FROM pg_class WHERE oid=to_regclass('public.'||tbl)
   AND relrowsecurity AND relforcerowsecurity)
  OR has_table_privilege('frc_ai_app','public.'||tbl,'SELECT')
  OR has_table_privilege('frc_ai_app','public.'||tbl,'INSERT')
  OR has_table_privilege('frc_ai_auth','public.'||tbl,'SELECT')
  OR has_table_privilege('frc_ai_auth','public.'||tbl,'UPDATE')
  THEN RAISE EXCEPTION 'M20100 invalid local RLS/privileges: %',tbl; END IF;
 END LOOP;
 IF NOT EXISTS(SELECT 1 FROM pg_trigger WHERE tgname='local_m040_immutable_row'
  AND tgenabled='O')
 OR NOT EXISTS(SELECT 1 FROM pg_trigger WHERE tgname='local_m040_immutable_truncate'
  AND tgenabled='O')
 THEN RAISE EXCEPTION 'M20100: incident immutability missing'; END IF;
 RAISE NOTICE 'M20100_LOCAL_034_041_RLS_PASS: % tables',n;
END $verify$;
COMMIT;
SQL
 echo "M20100_LOCAL_034_041_POST_VERIFY=PASS"
 echo "M20100_REAL_PAYMENTS=BLOCKED"
 echo "M20100_EXTERNAL_NOTIFICATIONS=BLOCKED"
 exit 0
fi

echo "=== M20100 AUDITORIA PRE-MIGRACAO: SOMENTE LEITURA ==="
psql_local <<'SQL'
BEGIN READ ONLY;
DO $preflight$
DECLARE n int; tbl text;
BEGIN
 IF current_database()<>'frcaixinha_aistudio_dev'
 OR current_user<>'frc_ai_owner' OR session_user<>'frc_ai_owner'
 OR inet_server_port()<>5433 OR current_setting('data_directory')<>
 '/data/data/com.termux/files/usr/var/lib/frcaixinha_aistudio_pg18'
 OR current_setting('server_version_num')::int NOT BETWEEN 180000 AND 189999
 THEN RAISE EXCEPTION 'M20100: wrong PG18 cluster'; END IF;
 SELECT count(*) INTO n FROM pg_catalog.pg_tables WHERE schemaname='public';
 IF n<>36 OR to_regclass('public.notification_inbox') IS NULL
 OR to_regclass('public.member_lifecycle_requests') IS NULL
 OR to_regclass('public.member_lifecycle_review_events') IS NULL
 OR NOT EXISTS(SELECT 1 FROM pg_class WHERE oid='public.notification_inbox'::regclass
  AND relrowsecurity AND relforcerowsecurity)
 OR NOT EXISTS(SELECT 1 FROM pg_class WHERE oid='public.member_lifecycle_requests'::regclass
  AND relrowsecurity AND relforcerowsecurity)
 THEN RAISE EXCEPTION 'M20100: requires 36-table existing M19300 baseline'; END IF;
 FOREACH tbl IN ARRAY ARRAY[
 'local_m034_webhook_evidence','local_m035_pix_dryrun',
 'local_m036_orders_inbox','local_m037_order_evidence',
 'local_m038_order_reservation','local_m039_reconciliation_hold',
 'local_m040_incident_audit','local_m041_notification_outbox'
 ] LOOP
  IF to_regclass('public.'||tbl) IS NOT NULL
  THEN RAISE EXCEPTION 'M20100: local 034-041 already present: %',tbl; END IF;
 END LOOP;
 IF NOT pg_has_role('frc_ai_app','frcaixinha_app_role','member')
 OR NOT pg_has_role('frc_ai_auth','frcaixinha_auth_role','member')
 OR has_table_privilege('frc_ai_app','public.credentials','SELECT')
 THEN RAISE EXCEPTION 'M20100: auth isolation invalid'; END IF;
 RAISE NOTICE 'M20100_LOCAL_PREFLIGHT_PASS: 36 existing tables';
END $preflight$;
COMMIT;
SQL
echo "M20100_LOCAL_AUDIT=PASS"
if [[ "$MODE" == audit ]]; then
 echo "M20100_NO_MIGRATIONS_APPLIED=PASS"
 exit 0
fi

[[ "$(printenv AI_STUDIO_LOCAL_PARITY_034_041 || true)" == YES ]] ||
 fail "requires AI_STUDIO_LOCAL_PARITY_034_041=YES"
read -r -p "Digite AUTORIZO_ESQUEMA_SINTETICO_034_041: " CONFIRM
[[ "$CONFIRM" == AUTORIZO_ESQUEMA_SINTETICO_034_041 ]] || fail "confirmation denied"
DIR="$HOME/.local/share/frcaixinha-aistudio-mobile/backups"
[[ ! -L "$DIR" ]] || fail "backup directory symlink"
mkdir -p -m 700 "$DIR"
chmod 700 "$DIR"
BACKUP="$DIR/pre_local_034_041_$(date -u +%Y%m%dT%H%M%SZ)_$$.dump.age"
[[ ! -e "$BACKUP" && ! -e "$BACKUP.partial" ]] || fail "backup exists"
trap 'rm -f "$BACKUP.partial"' EXIT
echo "=== M20100 CRIPTOGRAFAR BACKUP (FRASE FORTE MANUAL, GUARDE-A) ==="
pg_dump -h 127.0.0.1 -p 5433 -U frc_ai_owner -w \
 -d frcaixinha_aistudio_dev --format=custom --no-owner --no-acl |
 age --passphrase --output "$BACKUP.partial"
[[ -s "$BACKUP.partial" ]] || fail "backup vazio"
mv -n "$BACKUP.partial" "$BACKUP"
trap - EXIT
sha256sum "$BACKUP"
age --decrypt "$BACKUP" | pg_restore --list >/dev/null
echo "M20100_BACKUP_VERIFIED=PASS"

echo "=== APLICAR 034-041 LOCAL EM UMA TRANSACAO (SEM PAGAMENTOS) ==="
psql_local --single-transaction "${SCRIPTS[@]}"
echo "M20100_LOCAL_034_041_APPLIED=PASS"
echo "M20100_POST_VERIFY=REQUIRED"
