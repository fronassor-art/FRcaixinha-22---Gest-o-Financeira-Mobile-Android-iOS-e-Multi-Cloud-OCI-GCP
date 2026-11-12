#!/usr/bin/env bash
# FR Finance AI Studio M39020 — PREPARAÇÃO SOMENTE LEITURA.
# NUNCA sincroniza Git, aplica migração, ativa push ou movimenta Pix.
set -euo pipefail
umask 077

die() { printf 'M39020_PREFLIGHT=BLOCKED %s\n' "$*" >&2; exit 2; }
EXPECTED="/data/data/com.termux/files/home/fr-finance"
BRANCH="atualizacao-ai-studio-9b46a63187"
SQL110="backend/migrations/110_fr_finance_special_credit_offline.sql"
SQL111="backend/migrations/111_frfinance_special_credit_integrity_guards.sql"

[[ -n "${AI_STUDIO_APPROVED_SHA:-}" && "${AI_STUDIO_APPROVED_SHA}" =~ ^[0-9a-f]{40}$ ]] ||
  die "Defina AI_STUDIO_APPROVED_SHA com o commit previamente aprovado no GitHub."
cd "$EXPECTED" || die "Repositório único Termux não encontrado; NÃO crie clone no Debian"
[[ "$(git branch --show-current)" == "$BRANCH" ]] || die "Branch errada"
[[ "$(git rev-parse HEAD)" == "$AI_STUDIO_APPROVED_SHA" ]] || die "HEAD difere do commit aprovado"
[[ -z "$(git status --porcelain --untracked-files=no)" ]] || die "Alterações locais rastreadas"
[[ -f "$SQL110" && -f "$SQL111" ]] || die "Duas migrations ausentes"
PYTHON="/root/.venvs/frcaixinha-aistudio/bin/python"
[[ -x "$PYTHON" ]] || die "Python validado do projeto não encontrado; não reinstale bibliotecas"
command -v psql >/dev/null || die "psql indisponível"
command -v pg_dump >/dev/null || die "pg_dump indisponível"
command -v pg_restore >/dev/null || die "pg_restore indisponível"
# M39026: mesma biblioteca psycopg validada nas migrações anteriores.
# Não executar local-readonly genérico: ele avalia requisitos históricos
# fora do escopo de crédito especial; seu erro não exige reaplicar migrações.
"$PYTHON" backend/scripts/frfinance_m39026_credit_only_preflight.py

echo 'M39020_PREFLIGHT=PASS_CREDIT_ONLY_READ_ONLY'
echo "M39020_APPROVED_SHA=$AI_STUDIO_APPROVED_SHA"
echo 'M39020_SQL_110_111=VERSIONED_NOT_APPLIED_BY_PREFLIGHT'
echo 'M39020_TERMUX_GIT_MUTATIONS=NONE'
echo 'M39020_DATABASE_MIGRATIONS=NONE'
echo 'M39020_PUSH_EMAIL_WHATSAPP_SMS_REAL=OFF'
echo 'M39020_PIX_REAL=OFF'
echo 'M39020_NEXT_STEP=REQUIRES_SEPARATE_LOCAL_APPLY_APPROVAL'
