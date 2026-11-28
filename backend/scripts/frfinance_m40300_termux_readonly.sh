#!/data/data/com.termux/files/usr/bin/bash
# M40300 — observer only, native Termux; cannot connect to SQL or create VM.
set -euo pipefail
umask 077

echo "=== FR FINANCE M40300 — SERVICES READ ONLY ==="
if [[ "${PREFIX:-}" != "/data/data/com.termux/files/usr" ]] ||
   [[ "${HOME:-}" != "/data/data/com.termux/files/home" ]]; then
  echo "M40300_STATUS=BLOCKED_NOT_TERMUX_NATIVE"
  exit 2
fi
cd "$HOME/fr-finance"
BRANCH="atualizacao-ai-studio-9b46a63187"
[[ "$(git branch --show-current)" == "$BRANCH" ]] || {
  echo "M40300_STATUS=BLOCKED_WRONG_BRANCH"
  exit 2
}
REPO="fronassor-art/FRcaixinha-22---Gest-o-Financeira-Mobile-Android-iOS-e-Multi-Cloud-OCI-GCP"
case "$(git remote get-url origin)" in
  "https://github.com/$REPO" | \
  "https://github.com/$REPO.git" | \
  "git@github.com:$REPO" | \
  "git@github.com:$REPO.git") ;;
  *)
    echo "M40300_STATUS=BLOCKED_WRONG_REPO"
    exit 2 ;;
esac

echo "M40300_HEAD=$(git rev-parse --short HEAD)"
echo "M40300_PG_TARGET=127_0_0_1_5433_FR_FINANCE_ONLY"
echo "M40300_DB_NAME=frcaixinha_aistudio_dev"
echo "M40300_DB_IDENTITY=NOT_ATTESTED_BY_PROCESS_PROBE"
PGDATA="/data/data/com.termux/files/usr/var/lib/frcaixinha_aistudio_pg18"
PG_STATUS="NOT_RUNNING_OR_NOT_VISIBLE"
PG_READY="NOT_READY_OR_NOT_REACHABLE"
API="NOT_RUNNING_OR_NOT_FR_FINANCE_HEALTH"

if [[ -d "$PGDATA" && ! -L "$PGDATA" ]]; then
  echo "M40300_PGDATA_PATH=PRESENT_NOT_CORRUPTION_PROOF"
  if command -v pg_ctl >/dev/null 2>&1 &&
     pg_ctl -D "$PGDATA" status >/dev/null 2>&1; then
    PG_STATUS="RUNNING_ORIGINAL_PGDATA"
  fi
  if command -v pg_isready >/dev/null 2>&1 &&
     pg_isready -q -h 127.0.0.1 -p 5433 -U frc_ai_owner -d frcaixinha_aistudio_dev; then
    PG_READY="ACCEPTING_CONNECTIONS_PORT_5433"
  fi
else
  echo "M40300_PGDATA_PATH=NOT_AT_EXPECTED_PATH_REVIEW_ONLY"
fi

if command -v curl >/dev/null 2>&1 && command -v python >/dev/null 2>&1; then
  if curl --silent --show-error --fail --max-time 4 \
    http://127.0.0.1:8000/api/health 2>/dev/null |
     python -B -c 'import json,sys
try:
 d=json.load(sys.stdin)
 good=d.get("app")=="FR Finance" and d.get("status")=="ONLINE"
except (ValueError,TypeError,AttributeError): good=False
sys.exit(0 if good else 2)' >/dev/null 2>&1; then
    API="FR_FINANCE_HEALTH_ONLINE"
  fi
fi

echo "M40300_PG_PROCESS=$PG_STATUS"
echo "M40300_PG_READINESS=$PG_READY"
echo "M40300_FASTAPI=$API"
if [[ "$PG_STATUS" == "RUNNING_ORIGINAL_PGDATA" &&
      "$PG_READY" == "ACCEPTING_CONNECTIONS_PORT_5433" &&
      "$API" == "FR_FINANCE_HEALTH_ONLINE" ]]; then
  echo "M40300_STATUS=PASS_EXISTING_SERVICES_OBSERVED"
else
  echo "M40300_STATUS=SERVICES_INACTIVE_OR_UNVERIFIED_NOT_DATABASE_LOSS"
  echo "M40300_EXPLANATION=ANDROID_TERMUX_TERMINATION_CAN_STOP_BOTH_SERVICES"
  echo "M40300_RECOVERY=MANUAL_IDENTITY_PREFLIGHT_REQUIRED_NO_AUTOMATIC_RESTART"
fi

echo "M40300_DB_ROWS_READ=NONE"
echo "M40300_SQL_CONNECTIONS=NONE"
echo "M40300_DATABASE_WRITES=NONE"
echo "M40300_NEW_DIRECTORIES=NONE"
echo "M40300_NEW_DATABASES=NONE"
echo "M40300_FASTAPI_RESTART=NONE"
echo "M40300_POSTGRESQL_RESTART=NONE"
echo "M40300_MIGRATIONS=NONE"
echo "M40300_PIX_REAL=OFF"
echo "M40300_PAGAMENTOS_REAIS=OFF"
echo "M40300_ATIVACAO_REAL=OFF"
echo "M40300_PRODUCTION=BLOCKED"
