#!/usr/bin/env bash
# FastAPI local de homologação. Nunca expor em 0.0.0.0 nem alterar bancos.
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
config_file="${FRCAIXINHA_TERMUX_ENV_FILE:-$HOME/.config/frcaixinha-2.2/api.env}"
if [[ -e "$config_file" ]]; then
  if [[ -L "$config_file" ]]; then
    echo 'BLOQUEADO: arquivo de configuração não pode ser link simbólico.' >&2
    exit 2
  fi
  permissions="$(stat -c '%a' "$config_file")"
  if [[ ! "$permissions" =~ ^[0-7]{3}$ ]] || (( (8#$permissions & 077) != 0 )); then
    echo 'BLOQUEADO: proteja api.env com chmod 600.' >&2
    exit 2
  fi
  set -a
  # O arquivo privado do operador nunca entra no repositório.
  # shellcheck disable=SC1090
  source "$config_file"
  set +a
fi
if [[ "${ENVIRONMENT:-homologation}" == 'production' ]]; then
  echo 'BLOQUEADO: servidor Termux apenas para homologação local.' >&2
  exit 2
fi
export ENVIRONMENT=homologation
export FRCAIXINHA_TERMUX_LOCAL_API=1
export PYTHONPATH="$root/backend"
cd "$root"
echo 'FastAPI homologação local: http://127.0.0.1:8000/api/health'
echo 'A verificação /api/health/ready retornará 503 até o PostgreSQL e as contas de teste estarem preparados.'
exec "${PYTHON_BIN:-python3}" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log
