#!/usr/bin/env bash
# Diagnostico de integridade de arquivo .age; NAO descriptografa e NAO restaura.
set -euo pipefail
umask 077
INPUT="${1:-}"
EXPECTED="${2:-}"
if [[ -z "$INPUT" || ! "$EXPECTED" =~ ^[[:xdigit:]]{64}$ ]]; then
  echo 'Uso: bash script CAMINHO_BACKUP.age SHA256_ESPERADO_64_HEX' >&2
  exit 2
fi
if [[ "$INPUT" != *.age || -L "$INPUT" || ! -f "$INPUT" ]]; then
  echo 'AI_STUDIO_M240_BACKUP_FORMAT=BLOCKED (arquivo .age regular exigido)'
  exit 2
fi
case "$(basename "$INPUT")" in
  *FRcaixinha_2_2*|*FRcaixinha-2.2*)
    echo 'BLOQUEADO: backup do projeto independente FRcaixinha 2.2' >&2
    exit 2
    ;;
esac
command -v sha256sum >/dev/null || { echo 'BLOQUEADO: sha256sum ausente' >&2;exit 2; }
command -v stat >/dev/null || { echo 'BLOQUEADO: stat ausente' >&2;exit 2; }
if (( $(stat -c %s "$INPUT") < 80 )); then
  echo 'AI_STUDIO_M240_BACKUP_SIZE=BLOCKED'
  exit 2
fi
header="$(head -c 21 "$INPUT")"
if [[ "$header" != 'age-encryption.org/v1' ]]; then
  echo 'AI_STUDIO_M240_AGE_HEADER=BLOCKED'
  exit 2
fi
actual="$(sha256sum -- "$INPUT")"
actual="${actual:0:64}"
if [[ "${actual,,}" != "${EXPECTED,,}" ]]; then
  echo 'AI_STUDIO_M240_BACKUP_HASH=BLOCKED'
  exit 2
fi
echo 'AI_STUDIO_M240_AGE_HEADER=PASS (somente identificacao sintatica)'
echo 'AI_STUDIO_M240_BACKUP_HASH=PASS (integridade contra SHA recebido)'
echo 'AI_STUDIO_M240_BACKUP_DECRYPTION=NOT_TESTED'
echo 'AI_STUDIO_M240_BACKUP_RESTORE=NOT_TESTED'
echo 'AI_STUDIO_M240_DADOS_DO_BANCO_ALTERADOS=NAO'
