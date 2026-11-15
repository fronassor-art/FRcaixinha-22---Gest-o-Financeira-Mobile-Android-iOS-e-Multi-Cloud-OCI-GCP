# FR Finance — Aditivo técnico M40030

Complemento incremental de `docs/FR_FINANCE_ADITIVO_M40020_INDICE.md`.

Documento principal: `docs/FR_FINANCE_M40030_RECUPERACAO_FALHAS_CI.md`.

Evolução limitada a **testes de recuperação em PostgreSQL 18 descartável**: falha de processo antes de `COMMIT`, rollback de recibo e de proposta de revogação, retry após rollback com os mesmos identificadores, bloqueio de nonce e idempotência repetidos após confirmação e prova final RLS.

Não foi implementada autenticação humana, aprovação de revisores, mandatário real, revogação eficaz, pagamento, PIX, migrador do banco original, comunicação com provedor ou reinício do FastAPI.

Caderno Mestre e Contrato Técnico M39100 permanecem preservados, com os hashes anteriormente selados e o índice histórico de 330 requisitos/2.310 etapas.

`M40030_CI_ONLY=TRUE`; `M40030_ORIGINAL_DB_WRITES=NONE`; `M40030_LOCAL_MIGRATIONS=NONE`; `M40030_FASTAPI_RESTART=NONE`; `M40030_REAL_REVOCATION=NOT_ATTESTED`; `PIX_REAL=OFF`; `PAGAMENTOS_REAIS=OFF`; `ATIVACAO_REAL=OFF`; `PRODUCTION=BLOCKED`.
