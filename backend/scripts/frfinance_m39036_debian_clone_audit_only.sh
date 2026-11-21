#!/usr/bin/env bash
# FR Finance M39036 — diagnostico somente leitura no Debian PRoot.
# Confere se /root/fr-finance é secundario e lista pendencias ANTES de eliminar.
# NUNCA apaga, move, limpa, clona, faz checkout, fetch nem toca no PostgreSQL.
set -euo pipefail
CANON="/data/data/com.termux/files/home/fr-finance"
EXTRA="/root/fr-finance"
die() { printf 'M39036_STATUS=BLOCKED %s\n' "$*" >&2; exit 2; }
[[ "${HOME:-}" == /root ]] || die "Execute somente no Debian, root@localhost"
[[ -d "$CANON/.git" ]] || die "Diretorio ORIGINAL Termux nao visivel pelo Debian"
[[ -d "$EXTRA/.git" ]] || die "Clone secundario nao presente: nada a excluir"
[[ ! -L "$CANON" && ! -L "$EXTRA" ]] || die "Caminho e link simbolico"
[[ "$(stat -Lc '%d:%i' "$CANON")" != "$(stat -Lc '%d:%i' "$EXTRA")" ]] ||
  die "Mesma pasta fisica; nao excluir"

BRANCH="atualizacao-ai-studio-9b46a63187"
CHEAD="$(git -C "$CANON" rev-parse HEAD)"
EHEAD="$(git -C "$EXTRA" rev-parse HEAD)"
CSTATUS="$(git -C "$CANON" status --porcelain --untracked-files=all)"
ESTATUS="$(git -C "$EXTRA" status --porcelain --untracked-files=all)"
# git ls-files -o -i inclui qualquer conteudo ignorado, mesmo que a
# arvore Git pareca limpa: e.g. .env, builds, APKs, logs ou segredos.
IGNORED="$(git -C "$EXTRA" ls-files --others --ignored --exclude-standard | wc -l | tr -d ' ')"
STASHES="$(git -C "$EXTRA" stash list | wc -l | tr -d ' ')"
LOCAL_COMMITS="$(git -C "$EXTRA" rev-list --count --all --not --remotes)"
echo "=== FR FINANCE M39036 — AUDITORIA CLONES ==="
echo "M39036_ENV=DEBIAN"
echo "M39036_ORIGINAL_TERMUX=$CANON"
echo "M39036_EXTRA_DEBIAN=$EXTRA"
echo "M39036_SAME_PHYSICAL_DIRECTORY=FALSE"
echo "M39036_ORIGINAL_HEAD=$CHEAD"
echo "M39036_EXTRA_HEAD=$EHEAD"
echo "M39036_ORIGINAL_BRANCH=$(git -C "$CANON" branch --show-current)"
echo "M39036_EXTRA_BRANCH=$(git -C "$EXTRA" branch --show-current)"
echo "M39036_ORIGINAL_WORKTREE_CLEAN=$([[ -z "$CSTATUS" ]] && echo TRUE || echo FALSE)"
echo "M39036_EXTRA_WORKTREE_CLEAN=$([[ -z "$ESTATUS" ]] && echo TRUE || echo FALSE)"
echo "M39036_EXTRA_IGNORED_FILE_COUNT=$IGNORED"
echo "M39036_EXTRA_STASH_COUNT=$STASHES"
echo "M39036_EXTRA_LOCAL_ONLY_COMMITS=$LOCAL_COMMITS"
if [[ "$CHEAD" == "$EHEAD" ]]; then
  echo "M39036_TRACKED_REVISIONS_IDENTICAL=TRUE"
else
  echo "M39036_TRACKED_REVISIONS_IDENTICAL=FALSE"
fi
if [[ "$IGNORED" -gt 0 || -n "$ESTATUS" || "$STASHES" -gt 0 ||
      "$LOCAL_COMMITS" -gt 0 || "$CHEAD" != "$EHEAD" ||
      "$(git -C "$CANON" branch --show-current)" != "$BRANCH" ||
      "$(git -C "$EXTRA" branch --show-current)" != "$BRANCH" ]]; then
  echo "M39036_DELETE_PERMISSION=BLOCKED_REQUIRES_RECONCILIATION"
else
  echo "M39036_DELETE_PERMISSION=ELIGIBLE_FOR_SEPARATE_VERIFIED_DELETE"
fi
echo "M39036_DATABASE_WRITES=NONE"
echo "M39036_FILES_DELETED=NONE"
