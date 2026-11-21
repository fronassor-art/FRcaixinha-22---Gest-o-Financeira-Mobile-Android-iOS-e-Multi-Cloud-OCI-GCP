#!/data/data/com.termux/files/usr/bin/bash
# M40540: original FR Finance SQL112/113 catalog classifier; never applies migrations.
set -eu
umask 077
echo "=== FR FINANCE M40540 — READ ONLY ==="
if [ "$PREFIX" != "/data/data/com.termux/files/usr" ] ||
   [ "$HOME" != "/data/data/com.termux/files/home" ] || [ ! -t 0 ]; then
  echo "M40540_STATUS=BLOCKED_NOT_NATIVE_TERMUX_INTERACTIVE"
  exit 2
fi
cd "$HOME/fr-finance"
test "$(git branch --show-current)" = "atualizacao-ai-studio-9b46a63187" || {
  echo "M40540_STATUS=BLOCKED_WRONG_BRANCH"; exit 2;
}
REPO="fronassor-art/FRcaixinha-22---Gest-o-Financeira-Mobile-Android-iOS-e-Multi-Cloud-OCI-GCP"
case "$(git remote get-url origin)" in
  "https://github.com/$REPO" | "https://github.com/$REPO.git" | \
  "git@github.com:$REPO" | "git@github.com:$REPO.git") ;;
  *) echo "M40540_STATUS=BLOCKED_WRONG_REMOTE"; exit 2 ;;
esac
if ! EVIDENCE="$(python -B backend/scripts/frfinance_m38794_project_isolation.py inspect)"; then
  echo "M40540_STATUS=BLOCKED_ORIGINAL_IDENTITY"; exit 2
fi
if ! printf '%s\n' "$EVIDENCE" | grep -Fxq 'M38794_PROJECT_SEPARATION=PASS_STATIC'; then
  echo "M40540_STATUS=BLOCKED_ORIGINAL_IDENTITY"; exit 2
fi
unset EVIDENCE
SQL="backend/scripts/frfinance_m40540_sql112_113_catalog_readonly.sql"
test -f "$SQL" && test ! -L "$SQL" || {
 echo "M40540_STATUS=BLOCKED_SQL_FILE"; exit 2
}
echo "M40540_CONNECTION=FR_FINANCE_127_0_0_1_PORT_5433_ONLY"
echo "M40540_PASSWORD=HIDDEN_LOCAL_PROMPT"
if env -i HOME="$HOME" PATH="$PREFIX/bin" LANG=C TMPDIR="$PREFIX/tmp" \
 PGOPTIONS="-c default_transaction_read_only=on -c statement_timeout=10000 -c lock_timeout=2000" \
 "$PREFIX/bin/psql" -X -W -q -t -A -v ON_ERROR_STOP=1 \
 -h 127.0.0.1 -p 5433 -U frc_ai_owner -d frcaixinha_aistudio_dev -f "$SQL"; then
 echo "M40540_STATUS=PASS_CLASSIFICATION_ONLY"
else
 echo "M40540_STATUS=BLOCKED_CATALOG_OR_CONNECTION"
 echo "M40540_AUTOMATIC_REPAIR=OFF"
 exit 2
fi
echo "M40540_FR_CAIXINHA_2_2=NOT_ACCESSED"
echo "M40540_MIGRATIONS=NONE"
echo "M40540_DB_WRITES=NONE"
echo "M40540_SERVICE_RESTARTS=NONE"
echo "M40540_PIX_REAL=OFF"
echo "M40540_PAGAMENTOS_REAIS=OFF"
echo "M40540_ATIVACAO_REAL=OFF"
echo "M40540_PRODUCTION=BLOCKED"