#!/usr/bin/env bash
# FR Finance M39035 — APENAS Termux nativo, ÚNICO checkout /home/fr-finance.
# audit: somente leitura; sync: git fetch + merge --ff-only no ORIGINAL.
# NUNCA clona, reseta, limpa, cria outro banco, aplica SQL ou remove arquivos.
set -euo pipefail
umask 077

die() {
  printf 'M39035_ORIGINAL=BLOCKED %s\n' "$*" >&2
  exit 2
}

MODE="${1:-audit}"
[[ "$MODE" == audit || "$MODE" == sync ]] ||
  die "Modo aceito: audit ou sync"
[[ "${HOME:-}" == "/data/data/com.termux/files/home" ]] ||
  die "Execute no TERMUX NATIVO fora do Debian; HOME inesperado"
ROOT="$HOME/fr-finance"
[[ -d "$ROOT" && -d "$ROOT/.git" && ! -L "$ROOT" ]] ||
  die "Repositorio Termux original ausente ou link simbolico; NAO CLONAR"
[[ "$(git -C "$ROOT" rev-parse --show-toplevel)" == "$ROOT" ]] ||
  die "Repositorio principal nao esta na pasta exata do Termux"

BRANCH="atualizacao-ai-studio-9b46a63187"
REPO="fronassor-art/FRcaixinha-22---Gest-o-Financeira-Mobile-Android-iOS-e-Multi-Cloud-OCI-GCP"
ORIGIN="$(git -C "$ROOT" remote get-url origin)" ||
  die "Git origin indisponivel"
case "$ORIGIN" in
  "https://github.com/$REPO"|"https://github.com/$REPO.git"|
  "git@github.com:$REPO"|"git@github.com:$REPO.git"|
  "ssh://git@github.com/$REPO"|"ssh://git@github.com/$REPO.git") ;;
  *) die "Origin nao e o repositorio FR Finance autorizado" ;;
esac
[[ "$(git -C "$ROOT" branch --show-current)" == "$BRANCH" ]] ||
  die "Branch original divergente; nao fazer checkout automatico"

echo "=== FR FINANCE M39035 — DIRETORIO UNICO TERMUX ==="
echo "M39035_ENV=TERMUX_NATIVE"
echo "M39035_CANONICAL=$ROOT"
echo "M39035_REMOTE=ORIGINAL_FR_FINANCE"
echo "M39035_ORIGINAL_BEFORE=$(git -C "$ROOT" rev-parse HEAD)"
echo "M39035_TRACKED_STATUS_BEGIN"
git -C "$ROOT" status --short --untracked-files=all
echo "M39035_TRACKED_STATUS_END"

if [[ "$MODE" == audit ]]; then
  echo "M39035_MODE=AUDIT_READ_ONLY"
  echo "M39035_SYNC=NOT_EXECUTED"
  echo "M39035_DUPLICATE=NOT_TOUCHED"
  echo "M39035_PG18=NOT_TOUCHED"
  exit 0
fi

[[ "${FR_FINANCE_APPROVED_SHA:-}" =~ ^[a-f0-9]{40}$ ]] ||
  die "Defina FR_FINANCE_APPROVED_SHA com SHA exato validado"
[[ -z "$(git -C "$ROOT" status --porcelain --untracked-files=all)" ]] ||
  die "Arquivos locais alterados ou nao versionados; PRESERVADOS. Nao sobrescrever"
[[ -z "$(git -C "$ROOT" ls-files --unmerged)" ]] ||
  die "Conflitos de merge em aberto"

echo "=== SINCRONIZAR SOMENTE O ORIGINAL ==="
git -C "$ROOT" fetch --no-tags origin "$BRANCH"
[[ "$(git -C "$ROOT" rev-parse FETCH_HEAD)" == "$FR_FINANCE_APPROVED_SHA" ]] ||
  die "Remote SHA mudou; nenhuma mesclagem executada"
git -C "$ROOT" merge-base --is-ancestor HEAD FETCH_HEAD ||
  die "Historico original divergente; impossivel fast-forward seguro"
git -C "$ROOT" merge --ff-only FETCH_HEAD
[[ "$(git -C "$ROOT" rev-parse HEAD)" == "$FR_FINANCE_APPROVED_SHA" ]] ||
  die "HEAD incorreto apos atualizacao"
[[ -z "$(git -C "$ROOT" status --porcelain --untracked-files=all)" ]] ||
  die "Arvore original diferente do GitHub"
for path in \
  backend/migrations/110_fr_finance_special_credit_offline.sql \
  backend/migrations/111_frfinance_special_credit_integrity_guards.sql \
  backend/scripts/frfinance_m39032_post_migration_readonly.py \
  backend/scripts/frfinance_m39034_rls_api_offline.py
do
  [[ -f "$ROOT/$path" ]] || die "Arquivo versionado ausente: $path"
done
echo "M39035_ORIGINAL_HEAD=$(git -C "$ROOT" rev-parse HEAD)"
echo "M39035_ORIGINAL_SYNC=PASS_FAST_FORWARD"
echo "M39035_ORIGINAL_WORKTREE=CLEAN"
echo "M39035_CANONICAL_ONLY=TERMUX_NATIVE"
echo "M39035_DATABASE_MIGRATIONS=NONE"
echo "M39035_PG18=UNCHANGED"
echo "M39035_DUPLICATE=NOT_REMOVED_PENDING_INSPECTION"
