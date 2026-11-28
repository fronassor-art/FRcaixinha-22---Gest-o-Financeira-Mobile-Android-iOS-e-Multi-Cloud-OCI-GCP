# FR Finance M41140 — serialização entre revogação e escrita (NO-GO)

Base M41130: 1626cc379ea0e1d7977c53387f501f3543d89f7f. Rastreabilidade CP26-0061 / CTM-07 e CP26-0062 / CTM-08. Os 330 IDs e as 2.310 etapas permanecem estáveis; nenhuma regra contratual foi alterada.

No fixture PostgreSQL 18 descartável já usado pelos workflows M41050/M41060, a função de autorização da escrita bloqueia, em ordem determinística, as contas, os vínculos ativo-admin e ativo-membro, a sessão e a capability. Revalida estado, vínculo, escopo e expiração após obter os bloqueios e mantém os bloqueios até o fim da transação. O teste mede bloqueadores com pg_blocking_pids e usa chaves de idempotência únicas.

Ensaios exigidos no SHA: ACCOUNT_REVOKE_FIRST e ACCOUNT_WRITE_FIRST; ADMIN_MEMBERSHIP_REVOKE_FIRST e ADMIN_MEMBERSHIP_WRITE_FIRST; MEMBER_MEMBERSHIP_REVOKE_FIRST e MEMBER_MEMBERSHIP_WRITE_FIRST. Quando a revogação obtém o bloqueio primeiro, a escrita aguarda e é negada depois do commit da revogação. Quando a escrita obtém os bloqueios primeiro, a revogação aguarda; a escrita válida conclui, e então a revogação é aplicada. A capability do administrador suspenso permanece inválida após reativação. Cada cenário verifica a contagem final da chave de idempotência.

Evidência limitada ao fixture e às transações de CI. Não prova FastAPI/runtime financeiro, isolamento entre processos reais, comportamento sob todas as configurações de isolamento, ledger autoritativo, PSP, custódia independente de chaves ou homologação em staging. Não substitui M40840/M40930 nem fecha a Issue #5. Os 330 requisitos não foram reclassificados como concluídos; CP26-0061/0062 continuam PENDING_INDEPENDENT_EVIDENCE. A prontidão de produção segue NO-GO.

ORIGINAL_DATABASE=NOT_ACCESSED; MIGRATIONS=NONE; DB_WRITES=NONE; SERVICE_RESTARTS=NONE; RUNTIME_RELOAD=NONE; PIX_REAL=OFF; PAGAMENTOS_REAIS=OFF; ATIVACAO_REAL=OFF; PRODUCTION=BLOCKED.
