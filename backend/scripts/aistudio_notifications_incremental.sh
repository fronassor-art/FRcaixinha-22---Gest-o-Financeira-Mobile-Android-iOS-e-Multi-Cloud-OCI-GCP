#!/usr/bin/env bash
# Somente AI Studio em Termux; backup age para somente 031 incremental sobre 001-027 existentes.
set -euo pipefail
umask 077
root="$(cd "$(dirname "$0")/../.." && pwd)"
branch="atualizacao-ai-studio-9b46a63187"
origin="https://github.com/fronassor-art/FRcaixinha-22---Gest-o-Financeira-Mobile-Android-iOS-e-Multi-Cloud-OCI-GCP.git"
mode="$(printf '%s' "$1")"
approved="$(printenv AI_STUDIO_APPROVED_SHA || true)"
fail() { echo "BLOQUEADO: $*" >&2; exit 2; }

[[ "$mode" == audit || "$mode" == apply ]] || fail "modo valido: audit|apply"
[[ "$root" == "$HOME/frcaixinha-aistudio-mobile" ]] || fail "clone errado"
[[ "$(git -C "$root" remote get-url origin)" == "$origin" ]] || fail "origin errado"
[[ "$(git -C "$root" branch --show-current)" == "$branch" ]] || fail "branch errada"
[[ -z "$(git -C "$root" status --porcelain)" ]] || fail "arquivos modificados"
[[ "$approved" =~ ^[0-9a-f]{40}$ ]] || fail "informe SHA40 aprovado"
[[ "$(git -C "$root" rev-parse HEAD)" == "$approved" ]] || fail "HEAD diferente"
test -f "$root/backend/migrations/027_shared_login_attempt_limits.sql" || fail "falta 027"
for tool in psql pg_dump pg_restore age sha256sum git; do
  command -v "$tool" >/dev/null || fail "utilitario ausente: $tool"
done

echo "=== INVENTARIO DO BANCO EXISTENTE: SEM ALTERACOES ==="
bash "$root/backend/scripts/aistudio_db_local.sh" check
psql -X -v ON_ERROR_STOP=1 -W -h 127.0.0.1 -p 5433 -U frc_ai_owner \
 -d frcaixinha_aistudio_dev \
 -f "$root/backend/scripts/aistudio_notifications_existing_base_guard.sql"
if [[ "$mode" == audit ]]; then
 echo "M19100_INCREMENTAL_AUDIT=PASS"
 echo "MIGRACAO_031_LOCAL=NAO_EXECUTADA"
 exit 0
fi

[[ "$(printenv AI_STUDIO_INCREMENTAL_M031 || true)" == YES ]] ||
  fail "requer AI_STUDIO_INCREMENTAL_M031=YES"
read -r -p "Digite AUTORIZO_SOMENTE_NOTIFICACOES_031 para continuar: " confirm
[[ "$confirm" == AUTORIZO_SOMENTE_NOTIFICACOES_031 ]] || fail "sem confirmacao"

dir="$HOME/.local/share/frcaixinha-aistudio-mobile/backups"
[[ ! -L "$dir" ]] || fail "pasta backup e symlink"
mkdir -p -m 700 "$dir"
chmod 700 "$dir"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup="$dir/pre_migracao_$stamp.$$.dump.age"
[[ ! -e "$backup" && ! -e "$backup.partial" ]] || fail "backup ja existe"
trap 'rm -f "$backup.partial"' EXIT
echo "BACKUP=START: solicitar senha PostgreSQL antes de iniciar o age."
[[ -r /dev/tty ]] || fail "terminal interativo indisponivel"
db_password=""
IFS= read -r -s -p "Senha do PostgreSQL (entrada oculta): " db_password </dev/tty ||
  fail "nao foi possivel ler senha de modo oculto"
printf '\n' >/dev/tty
[[ -n "$db_password" ]] || fail "senha PostgreSQL vazia"
# pg_dump -w NAO faz nova pergunta: age fica sozinho com o terminal.
(
  export PGPASSWORD="$db_password"
  pg_dump -h 127.0.0.1 -p 5433 -U frc_ai_owner -w \
    -d frcaixinha_aistudio_dev --format=custom --no-owner --no-acl
) | age --passphrase --output "$backup.partial"
unset db_password
[[ -s "$backup.partial" ]] || fail "backup vazio"
mv -n "$backup.partial" "$backup"
trap - EXIT
sha256sum "$backup"
age --decrypt "$backup" | pg_restore --list >/dev/null
echo "BACKUP_ENCRYPTED_VERIFIED=PASS; $backup"
echo "=== MIGRAR APENAS 031 EM TRANSACAO UNICA ==="
psql -X -v ON_ERROR_STOP=1 -W --single-transaction \
 -h 127.0.0.1 -p 5433 -U frc_ai_owner -d frcaixinha_aistudio_dev \
 -f "$root/backend/migrations/031_notification_inbox_local_sandbox.sql" \
 -f "$root/backend/scripts/aistudio_post_migration_roles.sql"
echo "=== VALIDACAO POS MIGRACAO: LEITURA ==="
bash "$root/backend/scripts/aistudio_db_local.sh" verify
echo "M19100_MIGRACAO_031_INCREMENTAL=PASS; verificar API e APK em etapa separada."
