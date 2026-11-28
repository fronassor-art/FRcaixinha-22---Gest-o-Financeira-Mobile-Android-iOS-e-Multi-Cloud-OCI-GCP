# FR Finance — Aditivo técnico M40040

Complementa o índice incremental `docs/FR_FINANCE_ADITIVO_M40030_INDICE.md` preservando integralmente os documentos selados do Caderno Mestre e Contrato Técnico M39100.

Documento técnico: `docs/FR_FINANCE_M40040_CONFIRMACAO_INCERTA_IDEMPOTENCIA_CI.md`.

**Objetivo:** comprovar em PostgreSQL 18 descartável que uma resposta detalhada omitida **após COMMIT** não precisa produzir um segundo recibo e que uma consulta por idempotência pode recuperar o estado documental original. O teste ainda rejeita anexos inconsistentes, payload diferente, acesso entre caixinhas e novos recibos após uma **proposta de revogação** de teste.

Não são assinaturas reais, não há prova jurídica de designação/revogação, autorização de crédito, liquidação, saldo, saque ou ativação de pagamentos.

**Termux local:** M40030 já foi sincronizado no commit `3aa641b`; uma segunda execução do script originalmente esperado foi bloqueada por checagem de commit antigo, o que não é falha de sincronização.

`M40040_CI_ONLY=TRUE`; `M40040_ORIGINAL_DB_WRITES=NONE`; `M40040_LOCAL_MIGRATIONS=NONE`; `M40040_FASTAPI_RESTART=NONE`; `M40040_REAL_REVIEW_APPROVAL=FALSE`; `PIX_REAL=OFF`; `PAGAMENTOS_REAIS=OFF`; `ATIVACAO_REAL=OFF`; `PRODUCTION=BLOCKED`.
