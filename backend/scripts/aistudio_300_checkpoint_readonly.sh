#!/usr/bin/env bash
# FR Caixinha M300: diagnostico somente leitura, frente AI Studio.
set -euo pipefail
umask 077
ROOT="$HOME/frcaixinha-aistudio-mobile"
BRANCH="atualizacao-ai-studio-9b46a63187"
TARGET="${1:-}"
[[ "$TARGET" =~ ^[a-f0-9]{40}$ ]] || {
  echo 'BLOQUEADO: forneça o SHA completo do pacote.' >&2; exit 2;
}
cd "$ROOT"
[[ "$(git branch --show-current)" == "$BRANCH" &&
   "$(git rev-parse HEAD)" == "$TARGET" &&
   "$(git rev-parse "origin/$BRANCH")" == "$TARGET" &&
   -z "$(git status --porcelain --untracked-files=no)" ]] || {
  echo 'FR_CAIXINHA_M300_GIT=BLOCKED'; exit 2;
}
echo 'FR_CAIXINHA_M300_GIT=PASS'

PGDATA="$PREFIX/var/lib/frcaixinha_aistudio_pg18"
[[ -f "$PGDATA/PG_VERSION" && "$(cat "$PGDATA/PG_VERSION")" == 18 ]] || {
  echo 'FR_CAIXINHA_M300_PG18_EXCLUSIVO=BLOCKED'; exit 2;
}
pg_isready -q -h 127.0.0.1 -p 5433 || {
  echo 'FR_CAIXINHA_M300_PG5433=BLOCKED'; exit 2;
}
echo 'FR_CAIXINHA_M300_PG5433=PASS'

ready="$(curl -s --max-time 10 -o /dev/null -w '%{http_code}' \
  http://127.0.0.1:8000/api/health/ready || true)"
[[ "$ready" == 200 ]] || {
  echo "FR_CAIXINHA_M300_READY=BLOCKED_HTTP_$ready"; exit 2;
}
echo 'FR_CAIXINHA_M300_READY=PASS'

feature="$(curl -fsS --max-time 10 http://127.0.0.1:8000/api/health/features)" || {
  echo 'FR_CAIXINHA_M300_RUNTIME=BLOCKED (FastAPI antigo?)'; exit 2;
}
if ! printf '%s' "$feature" | python3 -c '
import json,sys
try:
 d=json.load(sys.stdin)
 assert type(d) is dict and set(d)=={
  "product","workstream","feature_contract","ledger_account_journal_page_max",
  "bank_reconciled","financial_closing_authorized","real_payments_enabled",
  "master_tenant_ledger_allowed","runtime_git_sha_verified"}
 assert d["product"]=="FR Caixinha" and d["workstream"]=="AI_STUDIO"
 assert d["feature_contract"]=="FR_CAIXINHA_M300_RUNTIME_V1"
 assert d["ledger_account_journal_page_max"]==50
 assert all(d[k] is False for k in (
  "bank_reconciled","financial_closing_authorized","real_payments_enabled",
  "master_tenant_ledger_allowed","runtime_git_sha_verified"))
except (TypeError,KeyError,ValueError,AssertionError):
 sys.exit(2)
';then
  echo 'FR_CAIXINHA_M300_RUNTIME=BLOCKED'; exit 2;
fi
echo 'FR_CAIXINHA_M300_RUNTIME_CARREGADO=PASS'
echo 'FR_CAIXINHA_M300_SHA_EXECUCAO=NAO_COMPROVADO'
echo 'FR_CAIXINHA_M300_OPERACOES_REAIS=BLOCKED'
echo 'FR_CAIXINHA_M300_SEM_MIGRACAO=PASS'
echo 'FR_CAIXINHA_M300_BANCO_MODIFICADO=NAO'
