# FR Caixinha AI Studio — M20800 / preparação de abertura de ciclo

O relatório do operador de 05/11/2026 confirmou que a migração 043 foi aplicada com backup AGE verificado, 45 tabelas no PG18/5433 e nenhum pagamento real.

Foi criada uma rota de prévia, administrada por sessão autenticada da própria caixinha: POST /api/v1/tenants/{tenant_id}/cycle-contribution-price/opening-preview.

O administrador deve enviar explicitamente ano, valor por cota em centavos (mínimo de 15000) e justificativa. A rota verifica responsável cadastral ativo, membership de administrador, ano já existente e fechamento dos ciclos anteriores. Todos os comandos SQL são SELECT.

A resposta contém cycle_creation_enabled=false. Portanto esta não é ainda a abertura operacional de novos ciclos. A criação transacional e auditada, com idempotência e bloqueios, é próximo módulo. Nenhum registro financeiro é criado, emitido, quitado ou modificado.

A revisão legada das 12 competências de 2027 permanece pendente, e não se deve reprecificá-las automaticamente. A regra de calendário deste projeto AI Studio é janeiro a dezembro segundo seu esquema próprio, não migrar calendários de outros projetos.

O inventário foi corrigido: o repo-check informa que prova local é necessária, e o local-readonly valida efetivamente a 043 por constraints, defaults e permissões. A CI não atesta bancos privados do operador.
