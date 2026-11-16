#!/data/data/com.termux/files/usr/bin/bash
# FR Finance M40240 — fixed original cluster; catalogue queries only.
# Password is prompted by psql, never read from environment, repo or argv.
set -eu
umask 077

echo "=== FR FINANCE M40240 — POSTGRESQL RLS CATALOG READ ONLY ==="
if [ "${PREFIX:-}" != "/data/data/com.termux/files/usr" ] ||
   [ "${HOME:-}" != "/data/data/com.termux/files/home" ]; then
  echo "M40240_STATUS=BLOCKED_NOT_NATIVE_TERMUX"
  exit 2
fi
if [ ! -t 0 ]; then
  echo "M40240_STATUS=BLOCKED_NO_INTERACTIVE_PASSWORD_TTY"
  exit 2
fi

cd "$HOME/fr-finance"
test "$(git branch --show-current)" = "atualizacao-ai-studio-9b46a63187" || {
  echo "M40240_STATUS=BLOCKED_WRONG_BRANCH"
  exit 2
}
test "$(git remote get-url origin)" =   "https://github.com/fronassor-art/FRcaixinha-22---Gest-o-Financeira-Mobile-Android-iOS-e-Multi-Cloud-OCI-GCP" || {
  echo "M40240_STATUS=BLOCKED_WRONG_REMOTE"
  exit 2
}

if ! python -B backend/scripts/frfinance_m38794_project_isolation.py inspect     | grep -q '^M38794_PROJECT_SEPARATION=PASS_STATIC$'; then
  echo "M40240_STATUS=BLOCKED_FR_FINANCE_IDENTITY"
  exit 2
fi

SQL="backend/scripts/frfinance_m40240_pg18_rls_catalog_readonly.sql"
test -f "$SQL" && test ! -L "$SQL" || {
  echo "M40240_STATUS=BLOCKED_SQL_SCRIPT"
  exit 2
}

echo "M40240_CONNECTION=FR_FINANCE_127_0_0_1_PORT_5433_ONLY"
echo "M40240_PASSWORD=PROMPTED_HIDDEN_NOT_STORED"
echo "M40240_SCOPE=CATALOG_ONLY_NO_MEMBER_DATA"
echo "M40240_TRANSACTION=DEFAULT_READ_ONLY"
if env -i    HOME="$HOME"    PATH="$PREFIX/bin"    LANG=C    TMPDIR="${TMPDIR:-$PREFIX/tmp}"    PGOPTIONS="-c default_transaction_read_only=on -c statement_timeout=10000 -c lock_timeout=2000"    "$PREFIX/bin/psql"      -X -W -q -t -A -v ON_ERROR_STOP=1      -h 127.0.0.1 -p 5433      -U frc_ai_owner      -d frcaixinha_aistudio_dev      -f "$SQL"
then
  echo "M40240_STATUS=PASS_LIVE_RLS_CATALOG_ONLY"
else
  echo "M40240_STATUS=BLOCKED_LIVE_RLS_CATALOG_OR_CONNECTION"
  echo "M40240_WARNING=DO_NOT_EDIT_DB_OR_RUN_MIGRATIONS"
  exit 2
fi

echo "M40240_POSTGRESQL_START_STOP=NONE"
echo "M40240_FASTAPI_START_STOP=NONE"
echo "M40240_FR_CAIXINHA_2_2=NOT_ACCESSED"
echo "M40240_REAL_SESSIONS=NONE"
echo "M40240_PIX_REAL=OFF"
echo "M40240_PAGAMENTOS_REAIS=OFF"
echo "M40240_ATIVACAO_REAL=OFF"
echo "M40240_PRODUCTION=BLOCKED"
