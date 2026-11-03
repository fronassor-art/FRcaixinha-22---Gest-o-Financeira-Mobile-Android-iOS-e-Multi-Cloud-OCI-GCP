#!/usr/bin/env bash
# Diagnóstico somente leitura. Não habilita ciclo, política nem empréstimos.
set -euo pipefail
umask 077
cd "$HOME/frcaixinha-aistudio-mobile"
test "$(git branch --show-current)" = "atualizacao-ai-studio-9b46a63187" || {
 echo "BLOQUEADO: branch não corresponde ao AI Studio" >&2
 exit 2
}
echo "DIAGNOSTICO_PRICE_SOMENTE_LEITURA=INICIADO"
echo "O psql poderá solicitar a senha do usuário técnico sem exibir caracteres."
psql -X -v ON_ERROR_STOP=1 -h 127.0.0.1 -p 5433 \
 -U frc_ai_owner -d frcaixinha_aistudio_dev -W <<'SQL'
BEGIN READ ONLY;
SELECT CASE WHEN current_database()='frcaixinha_aistudio_dev'
 AND inet_server_port()=5433
 AND current_user='frc_ai_owner'
 AND current_setting('data_directory')=
 '/data/data/com.termux/files/usr/var/lib/frcaixinha_aistudio_pg18'
 THEN 'AI_STUDIO_CLUSTER=PASS'
 ELSE (1/0)::text END AS isolamento;
SELECT 'CICLOS_ABERTOS='||count(*)::text
 FROM public.cycles WHERE status='ABERTO';
SELECT 'POLITICAS_ACTIVE='||count(*)::text
 FROM public.policies WHERE status='ACTIVE';
SELECT 'CICLOS_COM_POLITICA_ACTIVE='||count(*)::text
 FROM public.cycles c
 JOIN public.policies p ON p.tenant_id=c.tenant_id AND p.cycle_id=c.id
 WHERE c.status='ABERTO' AND p.status='ACTIVE';
SELECT 'CICLOS_CADASTRADOS='||count(*)::text FROM public.cycles;
SELECT 'POLITICAS_CADASTRADAS='||count(*)::text FROM public.policies;
ROLLBACK;
SQL
echo "DIAGNOSTICO_PRICE_SOMENTE_LEITURA=CONCLUIDO"
