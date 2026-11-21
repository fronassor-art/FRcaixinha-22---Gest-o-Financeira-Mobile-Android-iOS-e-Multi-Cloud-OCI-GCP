#!/usr/bin/env bash
# FRcaixinha AI Studio: consulta somente leitura de metadados no PostgreSQL 18 local.
# Nao modifica banco, nao le linhas financeiras, nao imprime credenciais.
set -euo pipefail
umask 077

ROOT="$HOME/frcaixinha-aistudio-mobile"
BRANCH="atualizacao-ai-studio-9b46a63187"
TARGET="${1:-}"
CLUSTER="/data/data/com.termux/files/usr/var/lib/frcaixinha_aistudio_pg18"
if [[ ! "$TARGET" =~ ^[0-9a-f]{40}$ ]]; then
  echo 'BLOQUEADO: forneca o SHA completo autorizado.' >&2
  exit 2
fi
cd "$ROOT"
if [[ "$(git branch --show-current)" != "$BRANCH" ||
      "$(git rev-parse HEAD)" != "$TARGET" ||
      -n "$(git status --porcelain --untracked-files=no)" ]]; then
  echo 'BLOQUEADO: checkpoint local divergente.' >&2
  exit 2
fi
if [[ "$(git rev-parse "origin/$BRANCH")" != "$TARGET" ]]; then
  echo 'BLOQUEADO: checkpoint remoto local divergente.' >&2
  exit 2
fi
if [[ ! -f "$CLUSTER/PG_VERSION" || "$(cat "$CLUSTER/PG_VERSION")" != 18 ]]; then
  echo 'BLOQUEADO: cluster exclusivo PostgreSQL 18 ausente.' >&2
  exit 2
fi
command -v psql >/dev/null || { echo 'BLOQUEADO: psql ausente'; exit 2; }
command -v pg_isready >/dev/null || { echo 'BLOQUEADO: pg_isready ausente'; exit 2; }
pg_isready -q -h 127.0.0.1 -p 5433 || {
  echo 'BLOQUEADO: PostgreSQL AI Studio porta 5433 indisponivel'
  exit 2
}

# -W usa prompt de senha oculto, sem colocar segredo no historico ou em argumentos.
# PGOPTIONS obriga leitura e prazo; BEGIN READ ONLY tambem protege a transacao.
# Todas as consultas usam somente catalogos e verificacoes de privilegio.
result="$(PGOPTIONS='-c default_transaction_read_only=on -c statement_timeout=10000' \
  psql -X -qAt -v ON_ERROR_STOP=1 -h 127.0.0.1 -p 5433 \
  -U frc_ai_owner -d frcaixinha_aistudio_dev -W <<'SQL'
BEGIN READ ONLY;
SELECT 'CLUSTER:' || CASE WHEN
  current_database()='frcaixinha_aistudio_dev' AND
  inet_server_port()=5433 AND current_user='frc_ai_owner' AND
  current_setting('server_version_num')::integer BETWEEN 180000 AND 189999 AND
  current_setting('data_directory')=
    '/data/data/com.termux/files/usr/var/lib/frcaixinha_aistudio_pg18'
THEN 'PASS' ELSE 'BLOCKED' END;
SELECT 'ROLES:' || CASE WHEN
  (SELECT count(*) FROM pg_roles WHERE rolname IN
     ('frc_ai_app','frc_ai_auth','frc_ai_verifier')
     AND rolcanlogin AND NOT rolsuper AND NOT rolbypassrls)=3 AND
  EXISTS(SELECT 1 FROM pg_roles WHERE rolname='frc_ai_owner' AND rolcanlogin) AND
  NOT EXISTS(
    SELECT 1 FROM pg_auth_members m
    JOIN pg_roles member ON member.oid=m.member
    JOIN pg_roles granted ON granted.oid=m.roleid
    WHERE member.rolname IN ('frc_ai_app','frc_ai_auth') AND
          granted.rolname='frcaixinha_verifier_role'
  )
THEN 'PASS' ELSE 'BLOCKED' END;
SELECT 'TABLES:' || CASE WHEN
  to_regclass('public.users') IS NOT NULL AND
  to_regclass('public.sessions') IS NOT NULL AND
  to_regclass('public.credentials') IS NOT NULL AND
  to_regclass('public.tenants') IS NOT NULL AND
  to_regclass('public.memberships') IS NOT NULL AND
  to_regclass('public.ledger_accounts') IS NOT NULL AND
  to_regclass('public.audit_events') IS NOT NULL
THEN 'PASS' ELSE 'BLOCKED' END;
SELECT 'RLS:' || CASE WHEN
  EXISTS (SELECT 1 FROM pg_class
          WHERE oid=to_regclass('public.users')
          AND relrowsecurity AND relforcerowsecurity) AND
  (SELECT count(*) FROM pg_class
    WHERE oid IN (to_regclass('public.tenants'),
                  to_regclass('public.memberships'),
                  to_regclass('public.quotas'),
                  to_regclass('public.ledger_accounts'))
      AND relrowsecurity)=4
THEN 'PASS' ELSE 'BLOCKED' END;
SELECT 'GRANTS:' || CASE WHEN
  (SELECT count(*) FROM pg_roles WHERE rolname IN
    ('frcaixinha_app_role','frcaixinha_auth_role',
     'frcaixinha_verifier_role'))=3 AND
  pg_has_role('frc_ai_app','frcaixinha_app_role','member') AND
  pg_has_role('frc_ai_auth','frcaixinha_auth_role','member') AND
  NOT has_table_privilege('frc_ai_app','public.credentials','SELECT') AND
  NOT has_table_privilege('frc_ai_app','public.sessions','SELECT') AND
  NOT has_column_privilege('frc_ai_app','public.users','cpf','SELECT') AND
  NOT has_column_privilege('frc_ai_app','public.users','email','SELECT') AND
  NOT has_column_privilege('frc_ai_auth','public.credentials','password_hash','SELECT') AND
  NOT has_table_privilege('frc_ai_auth','public.sessions','INSERT') AND
  NOT has_table_privilege('frc_ai_app','public.audit_events','UPDATE') AND
  NOT has_table_privilege('frc_ai_app','public.audit_events','DELETE')
THEN 'PASS' ELSE 'BLOCKED' END;
COMMIT;
SQL
)" || {
  echo 'AI_STUDIO_M240_LOCAL_ROLES=BLOCKED (consulta nao concluida)' >&2
  exit 2
}

# Sem linhas de usuarios ou senhas. Nunca imprimir SQL ou a saida bruta.
for gate in CLUSTER ROLES TABLES RLS GRANTS; do
  if ! grep -Fqx "$gate:PASS" <<<"$result"; then
    echo "AI_STUDIO_M240_${gate}=BLOCKED"
    echo 'AI_STUDIO_M240_ROLES_RLS=BLOCKED'
    exit 2
  fi
  echo "AI_STUDIO_M240_${gate}=PASS"
done
echo 'AI_STUDIO_M240_ROLES_RLS=PASS (catalogo/privilegios; sem teste de acessos autenticados)'
echo 'AI_STUDIO_M240_NENHUMA_ESCRITA=PASS'
echo 'AI_STUDIO_M240_BACKUP_RESTORE_OPERACIONAL=PENDENTE'
