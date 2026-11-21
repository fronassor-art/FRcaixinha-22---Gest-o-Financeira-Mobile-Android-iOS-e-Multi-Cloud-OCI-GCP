#!/usr/bin/env bash
# FR Caixinha M360: somente leitura. Sem SQL, sem credenciais, sem escrita.
set -euo pipefail
umask 077
ROOT="$HOME/frcaixinha-aistudio-mobile"
cd "$ROOT"
SHA="${1:-}"
[[ "$SHA" =~ ^[a-f0-9]{40}$ ]] || { echo 'M360_SHA=BLOCKED';exit 2; }

bash backend/scripts/aistudio_320_checkpoint_readonly.sh "$SHA"

data="$(curl -fsS --max-time 10 http://127.0.0.1:8000/api/health/features/m360)" || {
 echo 'M360_FASTAPI=BLOCKED_REINICIO_NECESSARIO'; exit 2;
}
if ! printf '%s' "$data" | python3 -c '
import hashlib,json,sys
from pathlib import Path
try:
 d=json.load(sys.stdin)
 assert type(d) is dict and set(d)=={
  "product","workstream","contract","keyset_read_only","page_max",
  "tenant_admin_only","financial_closing_authorized","real_payments_enabled",
  "bank_reconciled","source_fingerprints_at_import","runtime_git_sha_verified"}
 assert d["product"]=="FR Caixinha" and d["workstream"]=="AI_STUDIO"
 assert d["contract"]=="FR_CAIXINHA_M360_KEYSET_V1"
 assert d["page_max"]==50 and d["keyset_read_only"] is True
 assert d["tenant_admin_only"] is True
 assert all(d[k] is False for k in ("financial_closing_authorized",
  "real_payments_enabled","bank_reconciled","runtime_git_sha_verified"))
 paths={"main_py":"backend/app/main.py",
  "ledger_py":"backend/app/routers/ledger.py",
  "ledger_keyset_py":"backend/app/ledger_keyset.py"}
 assert d["source_fingerprints_at_import"]=={
  key:hashlib.sha256(Path(path).read_bytes()).hexdigest()
  for key,path in paths.items()}
except (TypeError,KeyError,ValueError,AssertionError,OSError):
 sys.exit(2)
';then
 echo 'M360_SOURCE_FINGERPRINTS=BLOCKED';exit 2;
fi
echo 'M360_SOURCE_FINGERPRINTS_MATCH=PASS'

STATUS="$(curl -s --max-time 10 -o /dev/null -w '%{http_code}' \
 http://127.0.0.1:8000/api/v1/tenants/00000000-0000-4000-8000-000000000001/ledger/accounts/00000000-0000-4000-8000-000000000002/entries/keyset || true)"
[[ "$STATUS" == 401 ]] || {
 echo "M360_KEYSET_SEM_SESSAO=BLOCKED_HTTP_$STATUS";exit 2;
}
echo 'M360_KEYSET_SEM_SESSAO_401=PASS'
echo 'M360_RUNTIME_FULL_GIT_SHA=NAO_COMPROVADO'
echo 'M360_SEM_MIGRACAO=PASS'
echo 'M360_SEM_OPERACAO_FINANCEIRA=PASS'
echo 'M360_BANCO_MODIFICADO=NAO'
