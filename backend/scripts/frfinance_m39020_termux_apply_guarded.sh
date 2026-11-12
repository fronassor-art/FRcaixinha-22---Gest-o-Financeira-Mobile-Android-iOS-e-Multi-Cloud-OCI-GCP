#!/usr/bin/env bash
# FR Finance M39020 — aplica SQL 110 e 111 SOMENTE após aprovação separada.
# ESTE SCRIPT É VERSIONADO MAS NÃO É EXECUTADO PELO GITHUB.
set -euo pipefail
umask 077

die(){ printf 'M39020_APPLY=BLOCKED %s\n' "$*" >&2; exit 2; }
[[ "${FR_FINANCE_M39020_APPLY_APPROVED:-}" == "YES_AFTER_INDEPENDENT_REVIEW" ]] ||
  die "Falta autorização expressa independente para migrar o banco original"
[[ "${FR_FINANCE_M39020_RESTORE_TEST:-}" == "YES" ]] ||
  die "Restauro ensaiado é obrigatório antes de qualquer aplicação"
[[ -t 0 ]] || die "Use terminal interativo; proibido execução desassistida"
[[ "${AI_STUDIO_APPROVED_SHA:-}" =~ ^[0-9a-f]{40}$ ]] ||
  die "SHA do commit GitHub aprovado ausente"

cd "$HOME/fr-finance" || die "Diretório canônico ausente"
[[ "$(git branch --show-current)" == "atualizacao-ai-studio-9b46a63187" ]] ||
  die "Branch de trabalho errada"
[[ "$(git rev-parse HEAD)" == "$AI_STUDIO_APPROVED_SHA" ]] ||
  die "HEAD difere do SHA aprovado"
[[ -z "$(git status --porcelain --untracked-files=no)" ]] ||
  die "Arquivos rastreados estão alterados"
python3 backend/scripts/aistudio_migration_inventory.py repo-check ||
  die "Inventário SQL/hash incongruente"

SQL110="backend/migrations/110_fr_finance_special_credit_offline.sql"
SQL111="backend/migrations/111_frfinance_special_credit_integrity_guards.sql"
[[ -r "$SQL110" && -r "$SQL111" ]] || die "Migrations não encontradas"

for prog in psql pg_dump pg_restore createdb dropdb sha256sum; do
  command -v "$prog" >/dev/null || die "Dependência ausente: $prog"
done
# O servidor original é PostgreSQL 18. Cliente de dump/restore de versão
# anterior (ex.: pg_dump 17 do Debian) interrompe o processo antes do backup.
# O operador deve escolher clientes 18 já instalados no Termux ou Debian;
# este script NUNCA instala outro PostgreSQL e NUNCA cria outro cluster.
for prog in pg_dump pg_restore; do
  detected="$("$prog" --version 2>/dev/null)" ||
    die "Não foi possível identificar a versão de $prog"
  [[ "$detected" == "$prog (PostgreSQL) 18."* ]] ||
    die "$prog incompatível com servidor 18: $detected. Selecione cliente PostgreSQL 18 antes de aplicar SQL."
done
# Não permitir opções de libpq herdadas ou arquivos de serviço.
[[ -z "${PGOPTIONS:-}${PGSERVICE:-}${PGHOSTADDR:-}${PGPASSFILE:-}" ]] ||
  die "Substituições libpq externas não são permitidas"

read -rs -p 'Senha PostgreSQL frc_ai_owner (oculta): ' LOCAL_DB_PASSWORD
printf '\n'
[[ -n "$LOCAL_DB_PASSWORD" ]] || die "Senha vazia"
export PGPASSWORD="$LOCAL_DB_PASSWORD"
unset LOCAL_DB_PASSWORD
PGHOST=127.0.0.1
PGPORT=5433
PGUSER=frc_ai_owner
PGDATABASE=frcaixinha_aistudio_dev
export PGHOST PGPORT PGUSER PGDATABASE
# A conexão deve identificar o PostgreSQL 18 original, via TCP em 5433.
IDENTITY="$(psql -X -v ON_ERROR_STOP=1 -Atc \
  "SELECT current_database()||'|'||current_user||'|'||inet_server_port()||'|'||current_setting('server_version_num')")" ||
  die "Identidade PostgreSQL não verificável"
[[ "$IDENTITY" =~ ^frcaixinha_aistudio_dev\|frc_ai_owner\|5433\|18[0-9]{4}$ ]] ||
  die "Banco/usuário/porta/versão divergentes"

# Só iniciar quando as duas migrations estiverem AUSENTES.
existing="$(psql -X -v ON_ERROR_STOP=1 -Atc \
  "SELECT count(*) FROM pg_class WHERE oid IN (to_regclass('public.special_credit_grants'),to_regclass('public.special_credit_campaigns'),to_regclass('public.special_credit_recipients'),to_regclass('public.special_credit_preferences'),to_regclass('public.special_credit_outbox'),to_regclass('public.special_credit_audit'))")" ||
  die "Não foi possível conferir tabelas"
[[ "$existing" == "0" ]] || die "Migração previamente aplicada ou parcial: não reaplicar"

BACKUP_DIR="$HOME/frfinance-backups/m39020"
mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP="$BACKUP_DIR/frfinance_original_pre_m39020_$STAMP.dump"
RESTORE_DB="fr_m39020_verify_$(date -u +%H%M%S)"
RESTORE_CREATED=0
cleanup(){
  if [[ "$RESTORE_CREATED" == "1" ]]; then
    dropdb --if-exists "$RESTORE_DB" >/dev/null 2>&1 || true
  fi
  unset PGPASSWORD
}
trap cleanup EXIT

echo 'M39020_BACKUP=START'
pg_dump --format=custom --no-password -f "$BACKUP" ||
  die "Backup original falhou; nenhuma migração executada"
[[ -s "$BACKUP" ]] || die "Backup vazio"
pg_restore --list "$BACKUP" >/dev/null ||
  die "Backup inválido no formato PostgreSQL custom"
sha256sum "$BACKUP" > "$BACKUP.sha256"
sha256sum --check --status "$BACKUP.sha256" ||
  die "Hash do backup inconsistente"

echo 'M39020_RESTORE_PROOF=START'
createdb "$RESTORE_DB" || die "Não foi possível criar banco descartável de restauro"
RESTORE_CREATED=1
pg_restore --exit-on-error --no-owner --no-acl -d "$RESTORE_DB" "$BACKUP" ||
  die "Restauro em banco descartável falhou; original intocado"
[[ "$(psql -d "$RESTORE_DB" -X -Atc \
  "SELECT count(*) FROM information_schema.tables WHERE table_schema='public'")" -ge 27 ]] ||
  die "Restauro não apresentou estrutura básica"
dropdb "$RESTORE_DB" || die "Falha ao limpar banco de restauro; parar"
RESTORE_CREATED=0
echo 'M39020_BACKUP_RESTORE_DISPOSABLE=PASS'

# -1: atomicidade global. Os dois SQLs não contêm BEGIN nem COMMIT próprios.
# Falha em qualquer etapa cancela toda a transação e preserva o backup.
psql -X -v ON_ERROR_STOP=1 --single-transaction \
  -c "SET frfinance.m39020_migration_mode='LOCAL_AUTHORIZED'" \
  -f "$SQL110" \
  -f "$SQL111" ||
  die "Falha atomicamente; nenhum checkpoint de aplicação foi declarado"

CHECK="$(psql -X -At -v ON_ERROR_STOP=1 -c \
  "SELECT count(*) FROM pg_class WHERE oid IN (
   'public.special_credit_grants'::regclass,
   'public.special_credit_campaigns'::regclass,
   'public.special_credit_recipients'::regclass,
   'public.special_credit_preferences'::regclass,
   'public.special_credit_outbox'::regclass,
   'public.special_credit_audit'::regclass)
   AND relrowsecurity AND relforcerowsecurity")" ||
  die "Aplicação ocorreu, mas evidência RLS falhou: bloquear homologação"
[[ "$CHECK" == "6" ]] ||
  die "RLS insuficiente; bloquear o aplicativo"
TRIGGERS="$(psql -X -At -v ON_ERROR_STOP=1 -c \
  "SELECT count(*) FROM pg_trigger WHERE tgname LIKE 'sc_m39020_%'
   AND tgenabled='O' AND NOT tgisinternal")" ||
  die "Falha ao conferir triggers"
[[ "$TRIGGERS" == "5" ]] || die "Guardas SQL 111 ausentes; bloquear aplicativo"

echo 'M39020_LOCAL_SQL110_111=APPLIED_ATOMICALLY'
echo 'M39020_LOCAL_FORCE_RLS=6_OF_6'
echo 'M39020_LOCAL_INTEGRITY_TRIGGERS=5_OF_5'
echo "M39020_BACKUP_PATH=$BACKUP"
echo 'M39020_PIX_REAL=OFF'
echo 'M39020_EXTERNAL_MARKETING=OFF'
echo 'M39020_ANDROID_APK_TEST=REQUIRES_SEPARATE_HOMOLOGATION'
