#!/usr/bin/env bash
# M19100 - read-only inventory of existing AI Studio PostgreSQL.
set -euo pipefail
cd "$HOME/frcaixinha-aistudio-mobile"
[[ "$(git branch --show-current)" == "atualizacao-ai-studio-9b46a63187" ]]
[[ -z "$(git status --porcelain)" ]]
echo "=== M19100 READ ONLY DATABASE INVENTORY ==="
psql -X -v ON_ERROR_STOP=1 -W -h 127.0.0.1 -p 5433 -U frc_ai_owner -d frcaixinha_aistudio_dev <<'SQL'
BEGIN READ ONLY;
SELECT current_database(),current_user,inet_server_port(),current_setting('data_directory');
SELECT count(*) AS public_tables FROM pg_catalog.pg_tables WHERE schemaname='public';
SELECT to_regclass('public.notification_inbox') AS existing_inbox;
SELECT to_regclass('public.sessions') AS sessions;
SELECT to_regclass('public.auth_login_proofs') AS login_proofs;
SELECT to_regprocedure('public.auth_active_memberships(text)') AS memberships_auth;
SELECT to_regprocedure('public.auth_issue_pending_session(uuid,text,text)') AS session_issuer;
SELECT has_table_privilege('frc_ai_app','public.credentials','SELECT') AS app_credentials_exposed;
COMMIT;
SQL
echo "M19100_INVENTORY_ONLY=PASS"
