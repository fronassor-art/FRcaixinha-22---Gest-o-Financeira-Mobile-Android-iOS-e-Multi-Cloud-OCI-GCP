#!/usr/bin/env bash
# FR Finance M39037 — LIMPEZA DA CÓPIA REDUNDANTE, exclusivamente no Debian.
# SÓ APÓS M39035 sync e M39036 audit + análise de artefatos.
# NÃO EXCLUI a pasta original Termux nem os backups nem o PostgreSQL.
set -euo pipefail
umask 077
die(){ echo "M39037_DELETE=BLOCKED $*" >&2; exit 2; }
[[ "${HOME:-}" == /root ]] || die "EXECUTE SOMENTE NO DEBIAN"
[[ -t 0 ]] || die "CONFIRMACAO INTERATIVA OBRIGATORIA"
[[ "${FR_FINANCE_APPROVED_SHA:-}" =~ ^[0-9a-f]{40}$ ]] ||
  die "SHA APROVADO OBRIGATORIO"
CANON="/data/data/com.termux/files/home/fr-finance"
EXTRA="/root/fr-finance"
EXPECTED="$FR_FINANCE_APPROVED_SHA"
BRANCH="atualizacao-ai-studio-9b46a63187"

# Dir efetivo, não link, não mount do mesmo checkout.
[[ -d "$CANON/.git" && -d "$EXTRA/.git" ]] ||
  die "Faltando copia original ou secundaria"
[[ ! -L "$CANON" && ! -L "$EXTRA" ]] ||
  die "Link simbolico nao pode ser removido aqui"
[[ "$(realpath -e "$CANON")" == "$CANON" ]] ||
  die "Original nao e diretorio fisico exato esperado"
[[ "$(realpath -e "$EXTRA")" == "$EXTRA" ]] ||
  die "Clone nao e diretorio fisico exato esperado"
[[ "$(stat -Lc '%d:%i' "$CANON")" != "$(stat -Lc '%d:%i' "$EXTRA")" ]] ||
  die "Original e clone apontam para a MESMA pasta"
# Clones precisam compartilhar MESMO remoto, não apenas o mesmo SHA.
[[ "$(git -C "$CANON" remote get-url origin)" == \
   "$(git -C "$EXTRA" remote get-url origin)" ]] ||
  die "Remotos dos dois checkouts divergentes"
# Não remover código em uso por processo cujo diretório de trabalho
# seja o clone secundário. Parar serviços antigos explicitamente antes.
for proc in /proc/[0-9]*; do
  [[ -d "$proc" ]] || continue
  cwd="$(readlink -e "$proc/cwd" 2>/dev/null || true)"
  case "$cwd" in
    "$EXTRA"|"$EXTRA"/*)
      die "Processo ainda usa o clone: PID=${proc##*/}" ;;
  esac
done
[[ "$(git -C "$CANON" rev-parse --show-toplevel)" == "$CANON" ]] ||
  die "Original nao coincide com raiz Git"
[[ "$(git -C "$EXTRA" rev-parse --show-toplevel)" == "$EXTRA" ]] ||
  die "Clone nao coincide com raiz Git"
for path in "$CANON" "$EXTRA"; do
  [[ "$(git -C "$path" branch --show-current)" == "$BRANCH" ]] ||
    die "Branch incorreta em $path"
  [[ "$(git -C "$path" rev-parse HEAD)" == "$EXPECTED" ]] ||
    die "SHA diferente do aprovado em $path"
  [[ -z "$(git -C "$path" status --porcelain --untracked-files=all)" ]] ||
    die "Mudancas versionadas/untracked em $path; preservar"
done
[[ -z "$(git -C "$EXTRA" ls-files --others --ignored --exclude-standard)" ]] ||
  die "Arquivos IGNORADOS no clone podem conter .env, APK, logs ou segredos; PRESERVAR"
[[ -z "$(git -C "$EXTRA" stash list)" ]] ||
  die "Clone tem stash: preservar antes da exclusao"
[[ "$(git -C "$EXTRA" rev-list --count --all --not --remotes)" == 0 ]] ||
  die "Clone contem commits locais exclusivos; preservar"
[[ -z "$(git -C "$CANON" ls-files --unmerged)" ]] ||
  die "Conflito de merge no original"
# Não apagar mountpoint ou qualquer submount conhecido.
if command -v findmnt >/dev/null 2>&1; then
  if findmnt --kernel --submounts --target "$EXTRA" -rn -o TARGET 2>/dev/null |
      grep -E "^$EXTRA(/|$)" >/dev/null; then
    die "Mount point sob clone; preservar"
  fi
fi
# Backups anteriores devem permanecer inteiros e fora da arvore Git.
for file in \
  /root/frfinance-backups/m39030/frfinance_original_20261112T054938Z.29689.dump \
  /root/frfinance-backups/m39020/frfinance_original_pre_m39020_20261112T055640Z.dump
do
  [[ -s "$file" && -s "$file.sha256" ]] ||
    die "Backup validado ausente: $file"
  sha256sum --check --status "$file.sha256" ||
    die "SHA256 do backup invalido: $file"
done

echo "=== FR FINANCE M39037 — PROVA ANTES DA EXCLUSAO ==="
echo "M39037_ORIGINAL_CANONICAL=$CANON"
echo "M39037_SECONDARY_TO_DELETE=$EXTRA"
echo "M39037_IDENTICAL_HEAD=$EXPECTED"
echo "M39037_NO_CHANGES=PASS"
echo "M39037_NO_UNTRACKED_OR_IGNORED=PASS"
echo "M39037_NO_STASH_OR_PRIVATE_COMMITS=PASS"
echo "M39037_DB_BACKUPS=VERIFIED"
echo "M39037_DATABASE_WRITES=NONE"
echo "=== ATENCAO: SERA EXCLUIDO SOMENTE /root/fr-finance ==="
read -r -p "Digite EXCLUIR_SOMENTE_CLONE_DEBIAN para remover a copia redundante: " CONFIRM
[[ "$CONFIRM" == "EXCLUIR_SOMENTE_CLONE_DEBIAN" ]] ||
  die "Operacao cancelada; arquivos preservados"
# Não pode executar com cwd dentro do clone.
cd /root
rm --one-file-system -rf -- /root/fr-finance
[[ ! -e /root/fr-finance ]] || die "Limpeza nao finalizada"
echo "M39037_SECONDARY_CLONE_DELETED=PASS"
echo "M39037_ORIGINAL_TERMUX=UNTOUCHED"
echo "M39037_DATABASE_WRITES=NONE"
echo "M39037_DB_BACKUPS=RETAINED"
