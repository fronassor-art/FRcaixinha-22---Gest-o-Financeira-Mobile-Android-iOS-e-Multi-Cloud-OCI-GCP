#!/usr/bin/env bash
# FRcaixinha AI Studio: comprova contrato carregado no FastAPI, sem modificar servicos.
set -euo pipefail
umask 077
ROOT="$HOME/frcaixinha-aistudio-mobile"
BRANCH="atualizacao-ai-studio-9b46a63187"
EXPECTED="${1:-}"
[[ "$EXPECTED" =~ ^[0-9a-f]{40}$ ]] || {
  echo 'BLOQUEADO: forneca SHA completo do Macropacote 280' >&2
  exit 2
}
cd "$ROOT"
[[ "$(git branch --show-current)" == "$BRANCH" ]] || {
  echo "AI_STUDIO_M280_BRANCH=BLOCKED"; exit 2
}
[[ "$(git rev-parse HEAD)" == "$EXPECTED" ]] || {
  echo "AI_STUDIO_M280_CHECKPOINT=BLOCKED"; exit 2
}
[[ -z "$(git status --porcelain --untracked-files=no)" ]] || {
  echo "AI_STUDIO_M280_WORKTREE=BLOCKED"; exit 2
}
[[ "$(git rev-parse "origin/$BRANCH")" == "$EXPECTED" ]] || {
  echo "AI_STUDIO_M280_REMOTE_LOCAL=BLOCKED"; exit 2
}
echo "AI_STUDIO_M280_GIT=PASS"

PGDATA="$PREFIX/var/lib/frcaixinha_aistudio_pg18"
[[ -f "$PGDATA/PG_VERSION" && "$(cat "$PGDATA/PG_VERSION")" == "18" ]] || {
  echo "AI_STUDIO_M280_CLUSTER=BLOCKED"; exit 2
}
pg_isready -q -h 127.0.0.1 -p 5433 || {
  echo "AI_STUDIO_M280_PG5433=BLOCKED"; exit 2
}
echo "AI_STUDIO_M280_PG5433=PASS"

ready="$(curl -s --max-time 10 -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/api/health/ready || true)"
[[ "$ready" == "200" ]] || {
  echo "AI_STUDIO_M280_FASTAPI_READY=BLOCKED_HTTP_$ready"; exit 2
}
echo "AI_STUDIO_M280_FASTAPI_READY=PASS"

# Resposta curta de metadados publicos; nunca imprimir resposta completa ou segredos.
runtime="$(curl -fsS --max-time 10 http://127.0.0.1:8000/api/health/runtime)" || {
  echo 'AI_STUDIO_M280_RUNTIME=BLOCKED (servidor ainda usa versao anterior?)'; exit 2
}
if ! printf '%s' "$runtime" | python3 -c '
import json,sys
try:
 d=json.load(sys.stdin)
 assert type(d) is dict and set(d)=={
  "project","runtime_contract","ledger_account_limit",
  "ledger_transaction_limit","ledger_entry_limit",
  "financial_closing_authorized","bank_reconciled","runtime_git_sha_verified"}
 assert d["project"]=="FRCAIXINHA_AI_STUDIO_MOBILE"
 assert d["runtime_contract"]=="AI_STUDIO_M280_RUNTIME_V1"
 assert [d["ledger_account_limit"],d["ledger_transaction_limit"],d["ledger_entry_limit"]]==[500,500,100]
 assert all(d[k] is False for k in
   ("financial_closing_authorized","bank_reconciled","runtime_git_sha_verified"))
except (ValueError,AssertionError,TypeError,KeyError):
 sys.exit(2)
'; then
  echo 'AI_STUDIO_M280_RUNTIME=BLOCKED (contrato nao corresponde ao pacote)'
  exit 2
fi
echo 'AI_STUDIO_M280_RUNTIME_CARREGADO=PASS'
echo 'AI_STUDIO_M280_GIT_SHA_NO_RUNTIME=NAO_COMPROVADO'
echo 'AI_STUDIO_M280_FECHAMENTO_REAL=BLOCKED'
echo 'AI_STUDIO_M280_CONSULTA_SOMENTE_LEITURA=PASS'
echo 'AI_STUDIO_M280_BANCO_MODIFICADO=NAO'
