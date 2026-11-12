#!/usr/bin/env bash
# FR Finance AI Studio M39020 — PREPARAÇÃO SOMENTE LEITURA.
# NUNCA sincroniza Git, aplica migração, ativa push ou movimenta Pix.
set -euo pipefail
umask 077

die() { printf 'M39020_PREFLIGHT=BLOCKED %s\n' "$*" >&2; exit 2; }
EXPECTED="$HOME/fr-finance"
BRANCH="atualizacao-ai-studio-9b46a63187"
SQL110="backend/migrations/110_fr_finance_special_credit_offline.sql"
SQL111="backend/migrations/111_frfinance_special_credit_integrity_guards.sql"

[[ -n "${AI_STUDIO_APPROVED_SHA:-}" && "${AI_STUDIO_APPROVED_SHA}" =~ ^[0-9a-f]{40}$ ]] ||
  die "Defina AI_STUDIO_APPROVED_SHA com o commit previamente aprovado no GitHub."
cd "$EXPECTED" || die "Repositório canônico nao encontrado"
[[ "$(git branch --show-current)" == "$BRANCH" ]] || die "Branch errada"
[[ "$(git rev-parse HEAD)" == "$AI_STUDIO_APPROVED_SHA" ]] || die "HEAD difere do commit aprovado"
[[ -z "$(git status --porcelain --untracked-files=no)" ]] || die "Alterações locais rastreadas"
[[ -f "$SQL110" && -f "$SQL111" ]] || die "Duas migrations ausentes"
command -v python3 >/dev/null || die "Python indisponível"
command -v psql >/dev/null || die "psql indisponível"
command -v pg_dump >/dev/null || die "pg_dump indisponível"
command -v pg_restore >/dev/null || die "pg_restore indisponível"
python3 backend/scripts/aistudio_migration_inventory.py repo-check
python3 backend/scripts/aistudio_migration_inventory.py local-readonly

echo 'M39020_PREFLIGHT=PASS_READ_ONLY'
echo "M39020_APPROVED_SHA=$AI_STUDIO_APPROVED_SHA"
echo 'M39020_SQL_110_111=VERSIONED_NOT_APPLIED_BY_PREFLIGHT'
echo 'M39020_TERMUX_GIT_MUTATIONS=NONE'
echo 'M39020_DATABASE_MIGRATIONS=NONE'
echo 'M39020_PUSH_EMAIL_WHATSAPP_SMS_REAL=OFF'
echo 'M39020_PIX_REAL=OFF'
echo 'M39020_NEXT_STEP=REQUIRES_SEPARATE_LOCAL_APPLY_APPROVAL'
