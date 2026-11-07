#!/usr/bin/env bash
# Exclusivo: exportação AI Studio (repo FRcaixinha-22---Gest-o...).
# Jamais usar a base/credenciais/cluster do projeto independente FRcaixinha-2.2.
set -euo pipefail
umask 077
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
config_file="$HOME/.config/frcaixinha-aistudio-mobile/api.env"

# Caminho fixo, exclusivo do projeto AI Studio: sem override para arquivo legado.
if [[ -L "$config_file" ]]; then
  echo 'BLOQUEADO: api.env do AI Studio não pode ser link simbólico.' >&2
  exit 2
fi
if [[ -e "$config_file" ]]; then
  if [[ ! -f "$config_file" ]]; then
    echo 'BLOQUEADO: api.env não é arquivo regular.' >&2
    exit 2
  fi
  permissions="$(stat -c '%a' "$config_file")"
  if [[ ! "$permissions" =~ ^[0-7]{3}$ ]] || (( (8#$permissions & 077) != 0 )); then
    echo 'BLOQUEADO: proteja api.env do AI Studio com chmod 600.' >&2
    exit 2
  fi
  set -a
  # O operador mantém este arquivo fora do Git. Não imprimir variáveis.
  # shellcheck disable=SC1090
  source "$config_file"
  set +a
fi

if [[ "${ENVIRONMENT:-homologation}" == 'production' ]]; then
  echo 'BLOQUEADO: servidor AI Studio no Termux é somente homologação.' >&2
  exit 2
fi

PYTHON_BIN="${PYTHON_BIN:-python3}"
"$PYTHON_BIN" "$root/backend/scripts/validate_aistudio_database.py"
export ENVIRONMENT=homologation
export FRCAIXINHA_TERMUX_LOCAL_API=1
export PYTHONPATH="$root/backend"
cd "$root"
echo 'FastAPI AI Studio: http://127.0.0.1:8000/api/health'
echo 'Sem banco próprio AI Studio configurado, /api/health/ready deve retornar 503.'
exec "$PYTHON_BIN" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log
