#!/usr/bin/env bash
set -euo pipefail
umask 077

# Credenciais ficam exclusivamente no ambiente do operador, nunca no repositório.
: "$PGDATABASE" # libpq lê PGHOST, PGUSER e PGPASSWORD do ambiente
: "${AGE_RECIPIENT:?Informe o destinatário age público}"
: "${BACKUP_OUTPUT:?Informe o arquivo de backup fora do repositório}"
command -v pg_dump >/dev/null
command -v age >/dev/null

case "$BACKUP_OUTPUT" in
  *.age) ;;
  *) echo "Saída deve terminar em .age" >&2; exit 2 ;;
esac
if [[ -e "$BACKUP_OUTPUT" ]]; then
  echo "Arquivo já existe; backup não sobrescrito" >&2
  exit 2
fi
tmp_file="${BACKUP_OUTPUT}.partial"
trap 'rm -f "$tmp_file"' EXIT
pg_dump --format=custom --no-owner --no-acl |
  age --recipient "$AGE_RECIPIENT" --output "$tmp_file"
mv "$tmp_file" "$BACKUP_OUTPUT"
trap - EXIT
echo "Backup age criado; teste de restauração ainda é obrigatório."
