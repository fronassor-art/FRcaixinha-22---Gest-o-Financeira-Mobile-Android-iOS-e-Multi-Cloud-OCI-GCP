#!/usr/bin/env bash
# FR Finance M38992: additive SQL 047 on ONE original PG18, after private archive.
# No initdb, new DB, new directory, pg_ctl, other repository or real email.
set -euo pipefail
umask 077
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
fail(){ echo "M38992_BLOCKED=$1" >&2; exit 2; }
[[ "$ROOT" == "$HOME/fr-finance" ]] || fail WRONG_WORKTREE
[[ "$(git branch --show-current)" == "atualizacao-ai-studio-9b46a63187" ]] || fail WRONG_BRANCH
[[ -z "$(git status --porcelain)" ]] || fail WORKTREE_MODIFIED
PGDATA="/data/data/com.termux/files/usr/var/lib/frcaixinha_aistudio_pg18"
[[ ! -L "$PGDATA" ]] || fail PGDATA_LINK
[[ "$(cat "$PGDATA/PG_VERSION" 2>/dev/null)" == "18" ]] || fail WRONG_CLUSTER
export PYTHONPATH=backend PYTHONDONTWRITEBYTECODE=1
for tool in psql pg_dump pg_restore sha256sum df; do
  command -v "$tool" >/dev/null 2>&1 || fail TOOL_UNAVAILABLE
done
python backend/scripts/frfinance_m38794_project_isolation.py inspect
python backend/scripts/aistudio_migration_inventory.py repo-check
python backend/scripts/frfinance_m38800_existing_services_probe.py \
  local AUTHORIZE_FRFINANCE_EXISTING_SERVICES_READONLY
pg_isready -q -h 127.0.0.1 -p 5433 || fail POSTGRES_OFFLINE
DB="frcaixinha_aistudio_dev"
USER="frc_ai_owner"
psql_original(){ psql -X -W -v ON_ERROR_STOP=1 -h 127.0.0.1 -p 5433 -U "$USER" -d "$DB" "$@"; }
echo "=== M38992 CONFERENCIA DB ORIGINAL, READ ONLY ==="
proof="$(psql_original -At -c "
SET default_transaction_read_only=on;
SELECT CASE WHEN current_database()='$DB'
 AND current_user='$USER' AND session_user='$USER'
 AND inet_server_port()=5433
 AND current_setting('data_directory')='$PGDATA'
 AND current_setting('server_version_num')::int BETWEEN 180000 AND 189999
 AND to_regclass('public.frfinance_access_delivery_outbox') IS NULL
 AND NOT EXISTS(
  SELECT 1 FROM (VALUES ('frc_ai_owner'),('frc_ai_auth'),
   ('frc_ai_app'),('frcaixinha_app_role'),
   ('frcaixinha_auth_role'),('frcaixinha_verifier_role')) AS x(role_name)
  WHERE NOT EXISTS (SELECT 1 FROM pg_roles r WHERE r.rolname=x.role_name))
 AND EXISTS(SELECT 1 FROM pg_roles WHERE rolname='frc_ai_auth'
  AND NOT rolsuper AND NOT rolbypassrls AND NOT rolcreatedb AND NOT rolcreaterole)
 AND (SELECT count(*) FROM (VALUES
  ('invitations'),('password_reset_tokens'),('invite_email_verification'),
  ('contract_documents'),('saas_license_entitlements'),('sessions'),
  ('users'),('memberships'),('tenants')) AS x(name)
  WHERE to_regclass('public.'||x.name) IS NOT NULL)=9
 THEN 'M047_READY' ELSE 'M047_BLOCKED' END;
" | tail -n 1)"
[[ "$proof" == "M047_READY" ]] || fail ORIGINAL_SCHEMA_NOT_READY
echo "M38992_SCHEMA_PRECHECK=PASS"
echo "=== M38992 ESPACO PARA PRESERVACAO ==="
DB_BYTES="$(psql_original -At -c "SELECT pg_database_size(current_database())" | tail -n 1)"
FREE_KIB="$(df -Pk "$HOME" | awk 'NR==2{print $4}')"
[[ "$DB_BYTES" =~ ^[0-9]+$ && "$FREE_KIB" =~ ^[0-9]+$ ]] || fail SPACE_UNKNOWN
(( FREE_KIB * 1024 > DB_BYTES + 1073741824 )) || fail SPACE_INSUFFICIENT
BACKUP="$HOME/frfinance_m047_before_$(date -u +%Y%m%dT%H%M%SZ).dump"
[[ ! -e "$BACKUP" ]] || fail BACKUP_FILE_EXISTS
echo "=== M38992 PRESERVAR DADOS EM ARQUIVO LOCAL (NAO NOVO BANCO) ==="
if ! pg_dump -W -h 127.0.0.1 -p 5433 -U "$USER" -d "$DB" \
  --format=custom --file="$BACKUP"; then
  rm -f -- "$BACKUP"
  fail BACKUP_FAILED
fi
chmod 600 "$BACKUP"
[[ -s "$BACKUP" ]] || fail BACKUP_EMPTY
pg_restore --list "$BACKUP" >/dev/null || fail BACKUP_ARCHIVE_INVALID
sha256sum "$BACKUP"
echo "M38992_BACKUP_ARCHIVE=VALID_LIST_ONLY_NOT_RESTORABILITY_ATTESTED"
echo "M38992_BACKUP_FILE=$BACKUP"
echo "=== M38992 CONFIRMACAO EXPLICITA ==="
read -r -p "Digite APLICAR_M047_FR_FINANCE para aplicar no banco original: " APPROVAL
[[ "$APPROVAL" == "APLICAR_M047_FR_FINANCE" ]] || fail USER_CANCELLED
echo "=== M38992 MIGRACAO ADITIVA 047, TRANSACAO SQL ==="
# -c and -f run in the SAME psql session. SQL wraps changes in BEGIN/COMMIT.
psql_original \
  -c "SET frfinance.migration_047_approved = '1';" \
  -f backend/local_migrations/047_frfinance_access_delivery_outbox.sql
echo "=== M38992 ESTRUTURA POS-APLICACAO, READ ONLY ==="
result="$(psql_original -At -c "
SET default_transaction_read_only=on;
SELECT CASE WHEN current_database()='$DB'
 AND inet_server_port()=5433
 AND current_setting('data_directory')='$PGDATA'
 AND EXISTS(SELECT 1 FROM pg_class
  WHERE oid=to_regclass('public.frfinance_access_delivery_outbox')
   AND relrowsecurity AND relforcerowsecurity)
 AND NOT has_table_privilege('frc_ai_auth',
  'public.frfinance_access_delivery_outbox','SELECT')
 AND NOT has_table_privilege('frc_ai_app',
  'public.frfinance_access_delivery_outbox','INSERT')
 AND to_regprocedure('public.frfinance_enqueue_member_invite(uuid,uuid,uuid,uuid,varchar,char,char,char,bytea)') IS NOT NULL
 AND to_regprocedure('public.frfinance_enqueue_password_reset(uuid,varchar,char,char,char,bytea)') IS NOT NULL
 AND to_regprocedure('public.frfinance_claim_access_mail()') IS NOT NULL
 AND to_regprocedure('public.frfinance_ack_access_mail(uuid,boolean)') IS NOT NULL
 THEN 'M047_SCHEMA_PASS' ELSE 'M047_SCHEMA_REVIEW' END;
" | tail -n 1)"
[[ "$result" == "M047_SCHEMA_PASS" ]] || fail POST_APPLY_REVIEW
echo "M38992_ORIGINAL_DATABASE=frcaixinha_aistudio_dev"
echo "M38992_MIGRATION_047=SCHEMA_APPLIED"
echo "M38992_NEW_DATABASE=NONE"
echo "M38992_NEW_DIRECTORY=NONE"
echo "M38992_NEW_API=NONE"
echo "M38992_REAL_EMAIL=OFF"
echo "M38992_REAL_PIX=OFF"
echo "M38992_PRODUCTION=BLOCKED"
