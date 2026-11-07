#!/usr/bin/env bash
# M25700 — one safe audit for AI Studio: never runs any migration.
set -euo pipefail
umask 077
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BRANCH="atualizacao-ai-studio-9b46a63187"
MODE="${1:-}"
fail(){ printf 'M25700_BLOQUEADO: %s\n' "$*" >&2; exit 2; }

[[ "$MODE" == repo-only || "$MODE" == local-proof ]] ||
  fail "modo obrigatorio: repo-only | local-proof"
[[ "$(git -C "$ROOT" branch --show-current)" == "$BRANCH" ]] ||
  fail "branch diferente da frente AI Studio"
[[ -z "$(git -C "$ROOT" status --porcelain --untracked-files=no)" ]] ||
  fail "arquivos locais modificados"
if [[ "$MODE" == local-proof ]]; then
  [[ "$ROOT" == "$HOME/frcaixinha-aistudio-mobile" ]] ||
    fail "diretorio Termux incorreto"
  [[ "${AI_STUDIO_APPROVED_SHA:-}" =~ ^[0-9a-f]{40}$ ]] ||
    fail "informe AI_STUDIO_APPROVED_SHA exato, manualmente aprovado"
  [[ "$(git -C "$ROOT" rev-parse HEAD)" == "$AI_STUDIO_APPROVED_SHA" ]] ||
    fail "SHA diferente do checkpoint aprovado"
fi
cd "$ROOT"
echo "=== M25700 REPOSITORIO ==="
git rev-parse --short HEAD
python3 backend/scripts/aistudio_migration_inventory.py repo-check
if [[ "$MODE" == local-proof ]]; then
  echo "=== M25700 POSTGRESQL LOCAL: SOMENTE LEITURA ==="
  # Existing guard checks exact Termux path, DB name/port/data dir/PG18,
  # roles, RLS, tables and migration 028–044 structures.
  # Password entered by getpass without echo; no DB writes.
  python3 backend/scripts/aistudio_migration_inventory.py local-readonly
  echo "M25700_LOCAL_DATABASE_ATTESTATION=PASS"
else
  echo "M25700_REPOSITORY_ONLY=PASS"
fi
echo "M25700_NO_MIGRATIONS_APPLIED=PASS"
