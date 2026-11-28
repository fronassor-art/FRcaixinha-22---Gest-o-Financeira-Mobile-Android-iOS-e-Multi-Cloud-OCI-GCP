# FR Finance — Aditivo técnico M40020

Este registro complementa `docs/FR_FINANCE_ADITIVO_M40010_INDICE.md` e mantém intactos o Caderno Mestre e Contrato Técnico M39100 (330 referências / 2.310 etapas).

**M40020:** `docs/FR_FINANCE_M40020_CONCORRENCIA_REVOGACAO_CI.md`.

O pacote acrescenta testes de concorrência em duas conexões reais com banco PostgreSQL 18 **descartável da CI**, cobrindo colisão de dois recibos e bloqueio de registro após **proposta** de revogação. Nenhum poder jurídico, cargo real, consentimento assinado, identidade humana ou direito de pagamento é criado.

O banco original FR Finance, porta 5433, permanece preservado, bem como o banco independente FR Caixinha 2.2. Não há SQL executado localmente, migração de aplicação, reinício do FastAPI antigo, instalação de APK nem alteração na PR #2 Draft.

`M40020_CI_ONLY=TRUE`;
`M40020_LOCAL_MIGRATIONS=NONE`;
`M40020_ORIGINAL_DB_WRITES=NONE`;
`M40020_REAL_REVOCATION=NOT_ATTESTED`;
`PIX_REAL=OFF`;
`PAGAMENTOS_REAIS=OFF`;
`ATIVACAO_REAL=OFF`;
`PRODUCTION=BLOCKED`.
