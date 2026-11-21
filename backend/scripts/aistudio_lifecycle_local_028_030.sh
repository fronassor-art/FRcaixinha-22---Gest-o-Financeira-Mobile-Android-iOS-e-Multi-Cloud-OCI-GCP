#!/usr/bin/env bash
# AI Studio M19300: incremental 028-030 ONLY, never 001-027/031 or real finances.
set -euo pipefail
umask 077
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
MODE="$1"
BRANCH="atualizacao-ai-studio-9b46a63187"
ORIGIN="https://github.com/fronassor-art/FRcaixinha-22---Gest-o-Financeira-Mobile-Android-iOS-e-Multi-Cloud-OCI-GCP.git"
SHA="$(printenv AI_STUDIO_APPROVED_SHA || true)"
PGDATA="/data/data/com.termux/files/usr/var/lib/frcaixinha_aistudio_pg18"
fail(){ printf "M19300_BLOQUEADO: %s\n" "$*" >&2; exit 2; }
test "$MODE" = audit || test "$MODE" = apply || test "$MODE" = verify || fail "use audit|apply|verify"
test "$ROOT" = "$HOME/frcaixinha-aistudio-mobile" || fail "projeto inesperado"
test "$(git -C "$ROOT" remote get-url origin)" = "$ORIGIN" || fail "origin incorreto"
test "$(git -C "$ROOT" branch --show-current)" = "$BRANCH" || fail "branch incorreta"
[[ "$SHA" =~ ^[0-9a-f]{40}$ ]] || fail "SHA aprovado ausente"
test "$(git -C "$ROOT" rev-parse HEAD)" = "$SHA" || fail "SHA divergente"
test -z "$(git -C "$ROOT" status --porcelain)" || fail "arquivos modificados"
test -f "$PGDATA/PG_VERSION" && test "$(cat "$PGDATA/PG_VERSION")" = 18 || fail "PG18 indisponivel"
for tool in psql pg_dump pg_restore age sha256sum git pg_isready; do command -v "$tool" >/dev/null || fail "falta $tool"; done
pg_isready -q -h 127.0.0.1 -p 5433 || fail "banco 5433 inativo"
for n in 028 029 030; do
 test "$(find "$ROOT/backend/local_migrations" -maxdepth 1 -type f -name "$n"'_*.sql' | wc -l)" -eq 1 ||
   fail "arquivo local $n ausente ou duplicado"
done
test -r /dev/tty || fail "terminal interativo exigido"
read -r -s -p "Senha frc_ai_owner (oculta): " PW </dev/tty || fail "erro ao ler senha"
printf '\n' >/dev/tty
test -n "$PW" || fail "senha vazia"
export PGPASSWORD="$PW"
unset PW
sql(){ psql -X -v ON_ERROR_STOP=1 -q -w -h 127.0.0.1 -p 5433 -U frc_ai_owner -d frcaixinha_aistudio_dev "$@"; }

if test "$MODE" = verify; then
 echo "=== M19300 VERIFICACAO POS MIGRACAO: SOMENTE LEITURA ==="
 sql <<'SQL'
BEGIN READ ONLY;
DO $verify$
DECLARE n integer;
BEGIN
 IF current_database()<>'frcaixinha_aistudio_dev' OR inet_server_port()<>5433
 OR current_user<>'frc_ai_owner'
 OR current_setting('data_directory')<>
 '/data/data/com.termux/files/usr/var/lib/frcaixinha_aistudio_pg18'
 THEN RAISE EXCEPTION 'wrong cluster'; END IF;
 SELECT count(*) INTO n FROM pg_catalog.pg_tables WHERE schemaname='public';
 IF n<>36 OR to_regclass('public.notification_inbox') IS NULL
 OR to_regclass('public.member_lifecycle_requests') IS NULL
 OR to_regclass('public.member_lifecycle_review_events') IS NULL
 OR to_regprocedure('public.lifecycle_submit_request_sandbox(uuid,uuid,uuid,character varying,uuid,character varying)') IS NULL
 OR to_regprocedure('public.lifecycle_append_review_event_sandbox(uuid,uuid,character varying,uuid,character varying)') IS NULL
 OR EXISTS (SELECT 1 FROM pg_indexes WHERE schemaname='public'
  AND indexname='member_lifecycle_one_pending_per_cycle_kind')
 OR NOT EXISTS (SELECT 1 FROM pg_indexes WHERE schemaname='public'
  AND indexname='member_lifecycle_case_round_lookup')
 OR EXISTS (SELECT 1 FROM pg_class WHERE oid IN
  ('public.member_lifecycle_requests'::regclass,'public.member_lifecycle_review_events'::regclass)
  AND NOT(relrowsecurity AND relforcerowsecurity))
 OR NOT has_table_privilege('frc_ai_app','public.member_lifecycle_requests','SELECT')
 OR NOT has_table_privilege('frc_ai_app','public.member_lifecycle_review_events','SELECT')
 OR has_table_privilege('frc_ai_app','public.member_lifecycle_requests','INSERT')
 OR has_table_privilege('frc_ai_app','public.member_lifecycle_review_events','INSERT')
 OR has_table_privilege('frc_ai_app','public.member_lifecycle_requests','UPDATE')
 OR has_table_privilege('frc_ai_app','public.member_lifecycle_review_events','UPDATE')
 OR has_table_privilege('frc_ai_auth','public.member_lifecycle_requests','SELECT')
 OR has_table_privilege('frc_ai_auth','public.member_lifecycle_review_events','SELECT')
 THEN RAISE EXCEPTION 'schema/RLS/grants invalid'; END IF;
 RAISE NOTICE 'M19300_LIFECYCLE_RLS=PASS, public tables=%',n;
END $verify$;
COMMIT;
SQL
 echo "M19300_POST_VERIFY=PASS"
 echo "M19300_FINANCIAL_ACTIONS=BLOCKED"
 exit 0
fi

echo "=== M19300 AUDITORIA PRE-MIGRACAO: SOMENTE LEITURA ==="
sql <<'SQL'
BEGIN READ ONLY;
DO $guard$
DECLARE n integer;
BEGIN
 IF current_database()<>'frcaixinha_aistudio_dev' OR current_user<>'frc_ai_owner'
 OR session_user<>'frc_ai_owner' OR inet_server_port()<>5433
 OR current_setting('data_directory')<>
 '/data/data/com.termux/files/usr/var/lib/frcaixinha_aistudio_pg18'
 OR current_setting('server_version_num')::int NOT BETWEEN 180000 AND 189999
 THEN RAISE EXCEPTION 'not exclusive AI Studio PG18'; END IF;
 SELECT count(*) INTO n FROM pg_catalog.pg_tables WHERE schemaname='public';
 IF n<>34 OR to_regclass('public.notification_inbox') IS NULL
 OR to_regclass('public.member_lifecycle_requests') IS NOT NULL
 OR to_regclass('public.member_lifecycle_review_events') IS NOT NULL
 OR to_regclass('public.cycles') IS NULL OR to_regclass('public.memberships') IS NULL
 OR to_regprocedure('public.rls_is_tenant_admin(uuid,uuid)') IS NULL
 OR to_regprocedure('public.rls_user_membership_ids(uuid,uuid)') IS NULL
 OR NOT EXISTS(SELECT 1 FROM pg_class WHERE oid='public.notification_inbox'::regclass
  AND relrowsecurity AND relforcerowsecurity)
 OR NOT pg_has_role('frc_ai_app','frcaixinha_app_role','member')
 OR NOT pg_has_role('frc_ai_auth','frcaixinha_auth_role','member')
 THEN RAISE EXCEPTION 'expected M031-only populated baseline (34 tables)'; END IF;
 RAISE NOTICE 'M19300_PREFLIGHT=PASS, local tables=%',n;
END $guard$;
COMMIT;
SQL
echo "M19300_AUDIT_ONLY=PASS"
if test "$MODE" = audit; then echo "M19300_LOCAL_028_030=NOT_APPLIED";exit 0;fi
test "$(printenv AI_STUDIO_APPLY_LIFECYCLE_028_030 || true)" = YES ||
 fail "requer AI_STUDIO_APPLY_LIFECYCLE_028_030=YES"
read -r -p "Digite AUTORIZO_CICLO_SINTETICO_028_030: " CONFIRM
test "$CONFIRM" = AUTORIZO_CICLO_SINTETICO_028_030 || fail "confirmacao invalida"

DIR="$HOME/.local/share/frcaixinha-aistudio-mobile/backups"
test ! -L "$DIR" || fail "pasta backup symlink"
mkdir -p -m 700 "$DIR"
chmod 700 "$DIR"
BACKUP="$DIR/antes_ciclo_028_030_$(date -u +%Y%m%dT%H%M%SZ)_$$.dump.age"
test ! -e "$BACKUP" && test ! -e "$BACKUP.partial" || fail "backup existente"
trap 'rm -f "$BACKUP.partial"' EXIT
echo "=== BACKUP AGE: CRIE FRASE FORTE MANUAL E GUARDE-A ==="
pg_dump -h 127.0.0.1 -p 5433 -U frc_ai_owner -w \
 -d frcaixinha_aistudio_dev --format=custom --no-owner --no-acl |
 age --passphrase --output "$BACKUP.partial"
test -s "$BACKUP.partial" || fail "backup vazio"
mv -n "$BACKUP.partial" "$BACKUP"
trap - EXIT
sha256sum "$BACKUP"
age --decrypt "$BACKUP" | pg_restore --list >/dev/null
echo "M19300_BACKUP_VERIFIED=PASS"
echo "=== APLICAR LOCAL 028-030 EM TRANSACAO UNICA ==="
sql --single-transaction \
 -f "$ROOT/backend/local_migrations/028_member_lifecycle_sandbox_requests.sql" \
 -f "$ROOT/backend/local_migrations/029_member_lifecycle_review_events.sql" \
 -f "$ROOT/backend/local_migrations/030_member_lifecycle_case_rounds.sql"
echo "M19300_MIGRATIONS_028_030_APPLIED=PASS"
echo "EXECUTE_VERIFY_SEPARATELY=REQUIRED"
