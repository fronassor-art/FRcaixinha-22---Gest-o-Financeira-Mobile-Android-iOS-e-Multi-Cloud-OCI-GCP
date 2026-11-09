#!/usr/bin/env bash
# M29810 — renomeação local de diretório, sem clone, Git write ou SQL.
set -euo pipefail
OLD="$HOME/frcaixinha-aistudio-mobile"
NEW="$HOME/fr-finance"
BRANCH="atualizacao-ai-studio-9b46a63187"
REPO="https://github.com/fronassor-art/FRcaixinha-22---Gest-o-Financeira-Mobile-Android-iOS-e-Multi-Cloud-OCI-GCP.git"

validate() {
  local dir="$1" origin
  test -d "$dir" && git -C "$dir" rev-parse --is-inside-work-tree | grep -qx true || {
    echo "BLOQUEADO=NAO_E_REPOSITORIO_FR_FINANCE"; return 2;
  }
  origin="$(git -C "$dir" remote get-url origin)"
  if [[ "$origin" != "$REPO" && "$origin" != "${REPO%.git}" ]]; then
    echo "BLOQUEADO=ORIGEM_GIT_INCORRETA"; return 3
  fi
  if [[ "$(git -C "$dir" branch --show-current)" != "$BRANCH" ]]; then
    echo "BLOQUEADO=BRANCH_INCORRETA"; return 4
  fi
}
echo "=== FR FINANCE — RENOMEACAO LOCAL SEGURA ==="
if [[ -d "$NEW" && ! -e "$OLD" ]]; then
  validate "$NEW"
  echo "DIRETORIO=JA_RENOMEADO"; echo "FR_FINANCE_TERMUX_PATH=PASS"
  exit 0
fi
if [[ -e "$NEW" || ! -d "$OLD" || -L "$OLD" ]]; then
  echo "BLOQUEADO=PASTAS_COLIDENTES_OU_ORIGEM_AUSENTE"; exit 5
fi
validate "$OLD"
before="$(git -C "$OLD" rev-parse HEAD)"
cd "$HOME"
mv -- "$OLD" "$NEW"
validate "$NEW"
test "$(git -C "$NEW" rev-parse HEAD)" = "$before"
echo "DIRETORIO_ANTIGO=$OLD"
echo "DIRETORIO_NOVO=$NEW"
echo "HEAD=${before:0:12}"
echo "GIT_REMOTE=INALTERADO"
echo "BANCO_LOCAL=NAO_MODIFICADO"
echo "OCI_DEBIAN=NAO_MODIFICADO"
echo "FR_FINANCE_TERMUX_PATH=PASS"
echo "PROXIMO_COMANDO=cd \"\$HOME/fr-finance\""
