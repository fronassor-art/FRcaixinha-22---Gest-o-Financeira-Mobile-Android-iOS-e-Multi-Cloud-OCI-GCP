#!/usr/bin/env bash
# FR Finance M39030 — backup do PG18 original com CLIENTES TERMUX 18.6.
# Executar NO DEBIAN (root@localhost). NAO aplica SQL 110/111.
set -euo pipefail
umask 077
die() { echo "M39030_STATUS=BLOCKED $*" >&2; exit 2; }

BRANCH="atualizacao-ai-studio-9b46a63187"
EXPECTED="${AI_STUDIO_APPROVED_SHA:-}"
ROOT="$HOME/fr-finance"
PG18="/data/data/com.termux/files/usr/bin"
DUMP="$PG18/pg_dump"
RESTORE="$PG18/pg_restore"
CREATE="$PG18/createdb"
DROP="$PG18/dropdb"

echo "=== FR FINANCE M39030 — PG18 ORIGINAL BACKUP + RESTORE ==="
[[ "$HOME" == /root ]] || die "Execute no Debian como root@localhost"
[[ "$EXPECTED" =~ ^[0-9a-f]{40}$ ]] || die "SHA aprovado ausente"
cd "$ROOT" || die "Repositorio Debian ausente"
[[ "$(git branch --show-current)" == "$BRANCH" ]] || die "Branch divergente"
[[ "$(git rev-parse HEAD)" == "$EXPECTED" ]] || die "HEAD divergente"
[[ "$(git rev-parse "refs/remotes/origin/$BRANCH")" == "$EXPECTED" ]] ||
  die "Referencia origin divergente"
[[ -z "$(git status --porcelain --untracked-files=no)" ]] ||
  die "Alteracoes locais rastreadas"
for tool in "$DUMP" "$RESTORE" "$CREATE" "$DROP"; do
  [[ -x "$tool" ]] || die "Cliente PG18 Termux indisponivel: $tool"
  version="$("$tool" --version)" || die "Nao foi possivel verificar versao: $tool"
  [[ "$version" == *"(PostgreSQL) 18."* ]] ||
    die "Cliente PostgreSQL incompativel: $version"
  echo "M39030_CLIENT=$version"
done
command -v psql >/dev/null || die "psql indisponivel"
command -v sha256sum >/dev/null || die "sha256sum indisponivel"
[[ -z "${PGOPTIONS:-}${PGSERVICE:-}${PGHOSTADDR:-}${PGPASSFILE:-}" ]] ||
  die "Ambiente libpq herdado nao autorizado"
[[ -t 0 ]] || die "Execucao interativa exigida"

export PGHOST=127.0.0.1
export PGPORT=5433
export PGUSER=frc_ai_owner
export PGDATABASE=frcaixinha_aistudio_dev
read -rs -p 'Senha local frc_ai_owner (oculta): ' PGPASSWORD
printf '\n'
[[ -n "$PGPASSWORD" ]] || die "Senha vazia"
export PGPASSWORD
TEMP_CREATED=0
TEMP_DB=""
cleanup() {
  if [[ "$TEMP_CREATED" == 1 ]]; then
    echo "M39030_CLEANUP=REMOVING_TEMP_DATABASE"
    "$DROP" --if-exists -w -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" "$TEMP_DB" ||
      echo "M39030_WARNING=TEMP_DB_CLEANUP_FAILED:$TEMP_DB" >&2
  fi
  unset PGPASSWORD
}
trap cleanup EXIT

echo "=== VALIDAR A IDENTIDADE DO SERVIDOR ORIGINAL ==="
identity="$(psql -X -w -v ON_ERROR_STOP=1 -Atc \
  "SELECT current_database()='frcaixinha_aistudio_dev'
     AND current_user='frc_ai_owner' AND session_user='frc_ai_owner'
     AND inet_server_port()=5433
     AND host(inet_server_addr())='127.0.0.1'
     AND current_setting('data_directory')=
       '/data/data/com.termux/files/usr/var/lib/frcaixinha_aistudio_pg18'
     AND current_setting('server_version_num')::int BETWEEN 180000 AND 189999")" ||
  die "Consulta de identidade falhou"
[[ "$identity" == t ]] || die "Identidade do PostgreSQL original divergente"
table_count="$(psql -X -w -v ON_ERROR_STOP=1 -Atc \
  "SELECT count(*) FROM pg_catalog.pg_tables WHERE schemaname='public'")" ||
  die "Inventario de tabelas indisponivel"
[[ "$table_count" == 47 ]] || die "Tabelas originais inesperadas: $table_count"
missing="$(psql -X -w -v ON_ERROR_STOP=1 -Atc \
  "SELECT count(*) FROM unnest(ARRAY[
     'special_credit_grants','special_credit_campaigns',
     'special_credit_recipients','special_credit_preferences',
     'special_credit_outbox','special_credit_audit'
   ]) AS t(name) WHERE to_regclass('public.'||name) IS NOT NULL")" ||
  die "Verificacao das SQL110/111 indisponivel"
[[ "$missing" == 0 ]] || die "Migração 110/111 existente ou parcial: interromper"

BACKUP_DIR="$HOME/frfinance-backups/m39030"
[[ ! -L "$BACKUP_DIR" ]] || die "Diretorio de backup nao pode ser symlink"
mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP="$BACKUP_DIR/frfinance_original_$stamp.$$.dump"
TEMP_DB="fr_m39030_restore_$(date -u +%H%M%S)_$$"
[[ ! -e "$BACKUP" ]] || die "Arquivo de backup ja existe"

echo "=== BACKUP PG18 — NOVO ARQUIVO PRIVADO ==="
"$DUMP" -w -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE" \
  --format=custom --file="$BACKUP" ||
  die "Backup falhou; SQL110/111 NAO aplicadas"
[[ -s "$BACKUP" ]] || die "Backup vazio"
chmod 600 "$BACKUP"
"$RESTORE" --list "$BACKUP" >/dev/null || die "Formato de backup invalido"
sha256sum "$BACKUP" > "$BACKUP.sha256"
chmod 600 "$BACKUP.sha256"
sha256sum --check --status "$BACKUP.sha256" ||
  die "Hash do backup invalido"
echo "M39030_BACKUP=PASS"

echo "=== PROVA DE RESTAURACAO EM BANCO DESCARTAVEL ==="
"$CREATE" -w -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" \
  --template=template0 "$TEMP_DB" ||
  die "Nao foi possivel criar banco de RESTAURO DESCARTAVEL"
TEMP_CREATED=1
"$RESTORE" -w -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" \
  --exit-on-error --no-owner --no-acl -d "$TEMP_DB" "$BACKUP" ||
  die "Restauro descartavel falhou; banco original preservado"
restored="$(psql -X -w -v ON_ERROR_STOP=1 -d "$TEMP_DB" -Atc \
  "SELECT count(*) FROM pg_catalog.pg_tables WHERE schemaname='public'")" ||
  die "Contagem da restauracao falhou"
[[ "$restored" == 47 ]] ||
  die "Restauro inesperado: $restored tabelas (esperadas 47)"
objects="$(psql -X -w -v ON_ERROR_STOP=1 -d "$TEMP_DB" -Atc \
  "SELECT count(*) FROM unnest(ARRAY[
    'users','tenants','memberships','cycles','credentials','sessions'
  ]) AS t(name) WHERE to_regclass('public.'||name) IS NOT NULL")" ||
  die "Verificacao das tabelas essenciais falhou"
[[ "$objects" == 6 ]] || die "Restauro sem as seis tabelas essenciais"
"$DROP" -w -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" "$TEMP_DB" ||
  die "Falha na limpeza do banco temporario"
TEMP_CREATED=0

echo "=== CHECKPOINT FINAL ==="
echo "M39030_BACKUP=PASS"
echo "M39030_RESTORE_TEST=PASS"
echo "M39030_PUBLIC_TABLES=47"
echo "M39030_ORIGINAL_DB=UNCHANGED"
echo "M39030_SQL110_111=NOT_APPLIED"
echo "M39030_BACKUP_PRIVATE_UNENCRYPTED=TRUE"
echo "M39030_BACKUP_PATH=$BACKUP"
echo "M39030_PIX_REAL=OFF"
