#!/usr/bin/env bash
# FR Finance M38994: additive M048 function-only migration on original PG18.
# Requires existing verified M047 and pre-M047 archive; no new DB or backup.
set -euo pipefail
umask 077
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
fail(){ printf 'M38994_BLOCKED=%s\n' "$1" >&2; exit 2; }
[[ "$ROOT" == "$HOME/fr-finance" ]] || fail WRONG_WORKTREE
[[ "$(git branch --show-current)" == "atualizacao-ai-studio-9b46a63187" ]] || fail WRONG_BRANCH
[[ -z "$(git status --porcelain)" ]] || fail DIRTY_WORKTREE
PGDATA="/data/data/com.termux/files/usr/var/lib/frcaixinha_aistudio_pg18"
[[ -f "$PGDATA/PG_VERSION" && "$(cat "$PGDATA/PG_VERSION")" == "18" ]] || fail WRONG_PGDATA
[[ ! -L "$PGDATA" ]] || fail PGDATA_LINK
export PYTHONPATH=backend PYTHONDONTWRITEBYTECODE=1
for tool in psql pg_restore pg_isready; do
  command -v "$tool" >/dev/null 2>&1 || fail "MISSING_$tool"
done
python backend/scripts/frfinance_m38794_project_isolation.py inspect
python backend/scripts/aistudio_migration_inventory.py repo-check
python backend/scripts/frfinance_m38800_existing_services_probe.py \
  local AUTHORIZE_FRFINANCE_EXISTING_SERVICES_READONLY
pg_isready -q -h 127.0.0.1 -p 5433 || fail ORIGINAL_POSTGRES_NOT_READY
# Existing M38992 backup; do not repeat creation or clone any database.
BACKUP_FOUND=NO
for archive in "$HOME"/frfinance_m047_before_*.dump; do
  if [[ -f "$archive" && ! -L "$archive" && -s "$archive" ]]; then
    if pg_restore --list "$archive" >/dev/null 2>&1; then
      BACKUP_FOUND=YES
      break
    fi
  fi
done
[[ "$BACKUP_FOUND" == YES ]] || fail ORIGINAL_PREM047_BACKUP_NOT_FOUND
echo "M38994_EXISTING_BACKUP=ARCHIVE_READABLE_NOT_RESTORABILITY_ATTESTED"
owner_psql(){
  psql -X -W -v ON_ERROR_STOP=1 -h 127.0.0.1 -p 5433 \
    -U frc_ai_owner -d frcaixinha_aistudio_dev "$@"
}
echo "=== M38994 ORIGINAL DATABASE AND M047 SCHEMA, READ ONLY ==="
preflight="$(owner_psql -At -c "
SET default_transaction_read_only=on;
SELECT CASE WHEN
 current_database()='frcaixinha_aistudio_dev'
 AND session_user='frc_ai_owner' AND current_user='frc_ai_owner'
 AND inet_server_port()=5433
 AND current_setting('data_directory')='$PGDATA'
 AND current_setting('server_version_num')::int BETWEEN 180000 AND 189999
 AND to_regclass('public.frfinance_access_delivery_outbox') IS NOT NULL
 AND to_regprocedure('public.frfinance_ack_access_mail(uuid,boolean)') IS NOT NULL
 AND to_regclass('public.password_reset_tokens') IS NOT NULL
 AND to_regclass('public.invite_email_verification') IS NOT NULL
 AND to_regprocedure('public.frfinance_redeem_reset_token(char,varchar)') IS NULL
 AND to_regprocedure('public.frfinance_verify_invite_email(char)') IS NULL
 THEN 'M048_READY' ELSE 'M048_BLOCKED' END;
" | tail -n 1)"
[[ "$preflight" == M048_READY ]] || fail M048_PRECONDITIONS
echo "M38994_READONLY_PREFLIGHT=PASS"
echo "=== M38994 EXPLICIT APPROVAL, FUNCTIONS ONLY ==="
read -r -p "Digite APLICAR_M048_FR_FINANCE para alterar apenas o banco original: " answer
[[ "$answer" == "APLICAR_M048_FR_FINANCE" ]] || fail OPERATOR_CANCELLED
echo "=== M38994 APPLY M048 IN ONE POSTGRESQL TRANSACTION ==="
owner_psql -c "SET frfinance.migration_048_approved = '1';" \
  -f backend/local_migrations/048_frfinance_access_token_redemption.sql
echo "=== M38994 CHECK FUNCTION RIGHTS, READ ONLY ==="
verified="$(owner_psql -At -c "
SET default_transaction_read_only=on;
SELECT CASE WHEN
 current_database()='frcaixinha_aistudio_dev'
 AND inet_server_port()=5433
 AND current_setting('data_directory')='$PGDATA'
 AND to_regprocedure('public.frfinance_redeem_reset_token(char,varchar)') IS NOT NULL
 AND to_regprocedure('public.frfinance_verify_invite_email(char)') IS NOT NULL
 AND has_function_privilege('frc_ai_auth',
     'public.frfinance_redeem_reset_token(char,varchar)','EXECUTE')
 AND has_function_privilege('frc_ai_auth',
     'public.frfinance_verify_invite_email(char)','EXECUTE')
 AND NOT has_function_privilege('frc_ai_app',
     'public.frfinance_redeem_reset_token(char,varchar)','EXECUTE')
 AND NOT has_function_privilege('frc_ai_app',
     'public.frfinance_verify_invite_email(char)','EXECUTE')
 THEN 'M048_FUNCTIONS_PASS' ELSE 'M048_REVIEW' END;
" | tail -n 1)"
[[ "$verified" == "M048_FUNCTIONS_PASS" ]] || fail POST_APPLY_M048_NOT_ATTESTED
echo "M38994_MIGRATION_048=FUNCTIONS_INSTALLED_IN_ORIGINAL_DB"
echo "M38994_MIGRATION_047=UNCHANGED"
echo "M38994_NEW_DATABASE=NONE"
echo "M38994_REAL_EMAIL=OFF"
echo "M38994_REAL_PIX=OFF"
echo "M38994_REAL_ACTIVATION=OFF"
echo "M38994_PRODUCTION=BLOCKED"
