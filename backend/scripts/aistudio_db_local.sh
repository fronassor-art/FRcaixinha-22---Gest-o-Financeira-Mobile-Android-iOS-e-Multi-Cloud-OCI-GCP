#!/usr/bin/env bash
# Execucao somente no Termux, para o cluster exclusivo do aplicativo AI Studio.
set -euo pipefail
umask 077
root="$(cd "$(dirname "$0")/../.." && pwd)"
mode="${1:-check}"
host="127.0.0.1"
port="5433"
user="frc_ai_owner"
db="frcaixinha_aistudio_dev"
pgdata="/data/data/com.termux/files/usr/var/lib/frcaixinha_aistudio_pg18"

if [[ "$mode" != check && "$mode" != apply && "$mode" != verify ]]; then
  echo "Uso: bash backend/scripts/aistudio_db_local.sh check|apply|verify" >&2
  exit 2
fi
if [[ "$root" != "$HOME/frcaixinha-aistudio-mobile" ]]; then
  echo "BLOQUEADO: clone AI Studio inesperado" >&2
  exit 2
fi
origin="$(git -C "$root" remote get-url origin)"
if [[ "$origin" != "https://github.com/fronassor-art/FRcaixinha-22---Gest-o-Financeira-Mobile-Android-iOS-e-Multi-Cloud-OCI-GCP.git" ]]; then
  echo "BLOQUEADO: repositorio origin nao e o AI Studio aprovado" >&2
  exit 2
fi
if [[ ! -f "$pgdata/PG_VERSION" ]] || [[ "$(cat "$pgdata/PG_VERSION")" != 18 ]]; then
  echo "BLOQUEADO: cluster AI Studio PostgreSQL 18 ausente" >&2
  exit 2
fi
if ! pg_isready -q -h "$host" -p "$port"; then
  echo "BLOQUEADO: PostgreSQL AI Studio nao ativo na porta 5433" >&2
  exit 2
fi
psql_base=(psql -X -v ON_ERROR_STOP=1 -h "$host" -p "$port" -U "$user" -d "$db" -W)

case "$mode" in
check)
  "${psql_base[@]}" <<'SQL'
BEGIN READ ONLY;
SELECT current_database() AS banco,current_user AS usuario,
       inet_server_port() AS porta,current_setting('data_directory') AS cluster,
       current_setting('server_version') AS versao;
SELECT count(*) AS tabelas_public FROM pg_catalog.pg_tables WHERE schemaname='public';
SELECT rolname,rolcanlogin,rolsuper,rolbypassrls
 FROM pg_roles WHERE rolname IN ('frc_ai_owner','frc_ai_app','frc_ai_auth')
 ORDER BY rolname;
COMMIT;
SQL
  ;;
apply)
  if [[ "${AI_STUDIO_APPLY_MIGRATIONS:-}" != YES ]]; then
    echo "BLOQUEADO: somente com AI_STUDIO_APPLY_MIGRATIONS=YES e autorizacao expressa" >&2
    exit 2
  fi
  if [[ "$(git -C "$root" branch --show-current)" != "atualizacao-ai-studio-9b46a63187" ]]; then
    echo "BLOQUEADO: branch atual nao e a PR do AI Studio" >&2
    exit 2
  fi
  if [[ -n "$(git -C "$root" status --porcelain)" ]]; then
    echo "BLOQUEADO: clone contem modificacoes locais; revisar antes" >&2
    exit 2
  fi
  read -r -p "Digite MIGRAR_SOMENTE_AI_STUDIO para confirmar: " confirm
  if [[ "$confirm" != MIGRAR_SOMENTE_AI_STUDIO ]]; then
    echo "Cancelado sem alteracoes."
    exit 2
  fi

  args=(-f "$root/backend/scripts/aistudio_migration_guard.sql")
  for n in 001 002 003 004 005 006 007 008 009 010 011 012 013 014 015 016 017 018 019 020; do
    files=("$root"/backend/migrations/"$n"_*.sql)
    if [[ "${#files[@]}" != 1 ]] || [[ ! -f "${files[0]}" ]]; then
      echo "BLOQUEADO: arquivo da migracao $n ausente ou duplicado" >&2
      exit 2
    fi
    args+=(-f "${files[0]}")
  done
  args+=(-f "$root/backend/scripts/aistudio_post_migration_roles.sql")
  echo "Aplicando 001-020 + papeis na MESMA transacao PostgreSQL; falhas causam ROLLBACK."
  "${psql_base[@]}" --single-transaction "${args[@]}"
  echo "AI_STUDIO_MIGRATIONS=APPLIED (execute verify antes do login)"
  ;;
verify)
  "${psql_base[@]}" <<'SQL'
BEGIN READ ONLY;
SELECT current_database(),current_user,inet_server_port(),current_setting('data_directory');
SELECT count(*) AS tabelas_public FROM pg_catalog.pg_tables WHERE schemaname='public';
SELECT to_regclass('public.users') AS users,
       to_regclass('public.credentials') AS credentials,
       to_regclass('public.sessions') AS sessions,
       to_regprocedure('public.auth_active_memberships(uuid)') AS vinculos;
SELECT pg_has_role('frc_ai_app','frcaixinha_app_role','member') AS app_role,
       pg_has_role('frc_ai_auth','frcaixinha_auth_role','member') AS auth_role;
SELECT c.relname,c.relrowsecurity,c.relforcerowsecurity
 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
 WHERE n.nspname='public'
   AND c.relname IN ('tenants','memberships','quotas','loans','ledger_accounts')
 ORDER BY c.relname;
SELECT count(*) AS total_master FROM public.users WHERE is_master;
COMMIT;
SQL
  ;;
esac
