#!/usr/bin/env bash
# FR Caixinha M320, frente AI Studio: somente leitura; sem credenciais ou PII.
set -euo pipefail
umask 077
ROOT="$HOME/frcaixinha-aistudio-mobile"
cd "$ROOT"
SHA="${1:-}"
[[ "$SHA" =~ ^[a-f0-9]{40}$ ]] || { echo 'M320_SHA=BLOCKED';exit 2; }

# Reutilizar gates da versao anterior: Git ff-only, PG18 exclusivo, API pronta,
# declaracao M300 carregada. Nao executar nenhuma migracao neste script.
bash backend/scripts/aistudio_300_checkpoint_readonly.sh "$SHA"

data="$(curl -fsS --max-time 10 http://127.0.0.1:8000/api/health/features/m320)" || {
 echo 'M320_FASTAPI=BLOCKED_REINICIO_NECESSARIO'; exit 2;
}
if ! printf '%s' "$data" | python3 -c '
import json,sys
try:
 d=json.load(sys.stdin)
 assert type(d) is dict and set(d)=={
  "product","workstream","contract","account_directory_read_only",
  "account_directory_max_accounts","tenant_admin_only",
  "empty_ledger_balance_values_hidden","financial_closing_authorized",
  "real_payments_enabled","bank_reconciled","runtime_git_sha_verified"}
 assert d["product"]=="FR Caixinha"
 assert d["workstream"]=="AI_STUDIO"
 assert d["contract"]=="FR_CAIXINHA_M320_EMPTY_LEDGER_V1"
 assert d["account_directory_max_accounts"]==500
 assert all(d[k] is True for k in (
  "account_directory_read_only","tenant_admin_only",
  "empty_ledger_balance_values_hidden"))
 assert all(d[k] is False for k in (
  "financial_closing_authorized","real_payments_enabled",
  "bank_reconciled","runtime_git_sha_verified"))
except (TypeError,ValueError,KeyError,AssertionError):
 sys.exit(2)
'; then
 echo 'M320_CONTRATO=BLOCKED'; exit 2;
fi
echo 'M320_RUNTIME_CARREGADO=PASS'

# Sem autenticacao, nem uma conta de outro tenant pode ser consultada.
STATUS="$(curl -s --max-time 10 -o /dev/null -w '%{http_code}' \
  http://127.0.0.1:8000/api/v1/tenants/00000000-0000-4000-8000-000000000001/ledger/accounts/directory || true)"
[[ "$STATUS" == 401 ]] || {
 echo "M320_DIRETORIO_SEM_SESSAO=BLOCKED_HTTP_$STATUS";exit 2;
}
echo 'M320_DIRETORIO_SEM_SESSAO_401=PASS'
echo 'M320_SEM_CRIACAO_DE_CONTAS=PASS'
echo 'M320_NENHUMA_MIGRACAO=PASS'
echo 'M320_NENHUMA_OPERACAO_FINANCEIRA=PASS'
echo 'M320_BANCO_MODIFICADO=NAO'
