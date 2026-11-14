#!/usr/bin/env bash
set -euo pipefail

# Restauração só no banco efêmero nomeado para CI, nunca no banco do celular.
: "$PGDATABASE"
: "${AGE_IDENTITY_FILE:?Informe a identidade age temporária}"
: "${BACKUP_INPUT:?Informe o backup age}"
if [[ "$PGDATABASE" != "frcaixinha_restore_ci" || ( "$PGHOST" != "127.0.0.1" && "$PGHOST" != "localhost" ) ]]; then
  echo "Restauração recusada fora do banco local frcaixinha_restore_ci" >&2
  exit 2
fi
command -v age >/dev/null
command -v pg_restore >/dev/null
age --decrypt --identity "$AGE_IDENTITY_FILE" "$BACKUP_INPUT" |
  pg_restore --exit-on-error --no-owner --no-acl --dbname="$PGDATABASE"
echo "Restauração descartável concluída; reconciliação externa permanece necessária."
