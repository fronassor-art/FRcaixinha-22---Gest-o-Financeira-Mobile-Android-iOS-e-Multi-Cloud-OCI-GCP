# FR Finance M40550 — auditoria aprofundada de permissões SaaS

**Data:** 18/11/2026. **Base:** `ca37501` (M40540). **Produção:** NO-GO.

## Evidência física já recebida

M40540 executou no Termux original contra FR Finance 127.0.0.1:5433, com senha oculta; `M40540_SQL112=STRUCTURE_PRESENT_NOT_PROVENANCE` e `M40540_SQL113=STRUCTURE_PRESENT_NOT_PROVENANCE`, `ROLLBACK_READ_ONLY`, zero writes/restarts. Esse resultado não prova o histórico de migração nem RLS data-plane.

## M40550

Novos SQL, launcher Termux, testes e CI estritamente de metadados para confirmar proteção de preços e campanhas:

- SQL112: preços anuais independentes, coluna não gerada e obrigatória, CHECK positivo validado, RLS e proibição de alterações históricas por papéis de app/autenticação.
- SQL113: duas políticas Master sem políticas adicionais, FORCE RLS, INSERT limitado a campos permitidos, sem UPDATE/DELETE e sem leitura pela role de autenticação.
- Funções SQL113: SECURITY DEFINER, `search_path` restrito, somente role app com EXECUTE na função de leitura, trigger de inserção e guardas de campanha indicados na definição.

Mesmo que passe no banco original, este é **teste de catálogo**, não execução dos controles com contas reais, nem verificação semântica formal das funções, histórico SQL, segurança de produção ou governança financeira.

A execução no **Termux fora do Debian** só ocorre depois de aprovação de CI e sincronização estrita. Destino PostgreSQL 18 FR Finance fixo em 127.0.0.1:5433, banco `frcaixinha_aistudio_dev`, owner com senha digitada localmente e oculta. Transação `BEGIN READ ONLY ... ROLLBACK`; nenhuma leitura de registros de usuário, funções de negócio não são chamadas. Em caso de falha, interromper sem reparar.

**Sem migrações, escritas, restart, pagamentos, Pix ou ativação financeira real.** PR #2 continua Draft; não fazer merge nem ativar flags.