# FR Finance — Aditivo de engenharia M40000

Adiciona ao índice técnico `docs/FR_FINANCE_ADITIVO_M39990_INDICE.md` o
experimento de recibos de revisão com unicidade e políticas de leitura em
PostgreSQL 18 descartável.

Documento:
`docs/FR_FINANCE_M40000_RECIBOS_REVISAO_IDEMPOTENCIA_CI.md`.

**Entrega:** prova de controles transacionais em um banco descartável do
GitHub Actions, com proteção contra duplicidade de ator, sessão, nonce,
idempotência e leitura entre caixas; experimentos encerrados por
`ROLLBACK`.

**Não entregue:** autenticação real de revisores, mandato ratificado,
assinatura digital, consentimento, prova bancária, acesso ou persistência
no PostgreSQL FR Finance original, política do caixa coletivo, pagamento,
migração local ou ativação financeira.

Os documentos originais Caderno Mestre e Contrato Técnico vinculados ao
M39100 continuam SHA-locked, preservando as 330 referências e
2.310 etapas verificadas.

`M40000_ORIGINAL_DB_ACCESS=NONE`;
`M40000_LOCAL_MIGRATIONS=NONE`;
`M40000_FASTAPI_RESTART=NONE`;
`PIX_REAL=OFF`;
`PAGAMENTOS_REAIS=OFF`;
`ATIVACAO_REAL=OFF`;
`PRODUCTION=BLOCKED`.
