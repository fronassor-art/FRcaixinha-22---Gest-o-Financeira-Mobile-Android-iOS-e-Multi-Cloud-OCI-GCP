#!/usr/bin/env bash
# Exclusivo: exportação AI Studio (repo FRcaixinha-22---Gest-o...).
# Jamais usar a base/credenciais/cluster do projeto independente FRcaixinha-2.2.
set -euo pipefail
umask 077
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

# M38801: this is the EXISTING FR Finance FastAPI launcher, not a new server.
# Android may close Termux/PG at any time; check the original services first.
# Never create a PostgreSQL cluster, new worktree, config directory, or port.
export PYTHONDONTWRITEBYTECODE=1
PYTHON_BIN="${PYTHON_BIN:-python3}"
if [[ "$root" != "$HOME/fr-finance" ]]; then
  echo 'M38801_BLOCKED=WRONG_PROJECT_WORKTREE' >&2
  exit 2
fi
if ! "$PYTHON_BIN" "$root/backend/scripts/frfinance_m38794_project_isolation.py" inspect >/dev/null; then
  echo 'M38801_BLOCKED=PROJECT_ISOLATION_FAILED' >&2
  exit 2
fi
PGDATA="/data/data/com.termux/files/usr/var/lib/frcaixinha_aistudio_pg18"
if ! pg_ctl -D "$PGDATA" status >/dev/null 2>&1; then
  echo 'M38801_BLOCKED=EXISTING_FR_FINANCE_POSTGRES_NOT_RUNNING' >&2
  echo 'Reativar somente o cluster original PG18 na porta 5433; nao criar outro.' >&2
  exit 2
fi
if ! pg_isready -q -h 127.0.0.1 -p 5433 -U frc_ai_owner -d frcaixinha_aistudio_dev; then
  echo 'M38801_BLOCKED=EXISTING_PG_5433_NOT_READY' >&2
  exit 2
fi
# A listener on 8000 (even an unrelated process) must never be replaced.
# M40180: only positive ECONNREFUSED means safe to attempt a bind.
# Timeouts, Android restrictions and other failures are NOT a free port.
if ! "$PYTHON_BIN" -B - <<'PY'
import errno
import socket
import sys
try:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(1.5)
        result = sock.connect_ex(("127.0.0.1", 8000))
except (OSError, ValueError):
    result = None
sys.exit(0 if result == errno.ECONNREFUSED else 2)
PY
then
  echo 'M40180_FASTAPI_START=BLOCKED_PORT_8000_OCCUPIED_OR_UNVERIFIED'
  echo 'Nao criar segundo FastAPI; identificar listener sem matar processos.'
  exit 2
fi
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

"$PYTHON_BIN" "$root/backend/scripts/validate_aistudio_database.py"

# M40180: enforce the frozen financial / external delivery gates AFTER
# sourcing private api.env. The guard reads only non-secret flag names and
# values; no password, URL or DSN is displayed.
if ! "$PYTHON_BIN" -B "$root/backend/scripts/frfinance_m40180_launch_sandbox_guard.py"; then
  echo 'M40180_FASTAPI_START=BLOCKED_SANDBOX_FLAGS'
  exit 2
fi
export PIX_REAL=OFF
export PAGAMENTOS_REAIS=OFF
export ATIVACAO_REAL=OFF
export FR_FINANCE_ACCESS_MAIL_ENABLE=OFF
export FR_FINANCE_ACCESS_MAIL_WORKER=OFF
export FRCAIXINHA_CI_ISOLATED=0
export AI_STUDIO_M2040_CI_EVIDENCE_READS=0
export ENVIRONMENT=homologation
export FRCAIXINHA_TERMUX_LOCAL_API=1
export PYTHONPATH="$root/backend"
cd "$root"
echo 'FastAPI existente FR Finance: http://127.0.0.1:8000/api/health'
echo 'Sem banco próprio AI Studio configurado, /api/health/ready deve retornar 503.'
exec "$PYTHON_BIN" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log
