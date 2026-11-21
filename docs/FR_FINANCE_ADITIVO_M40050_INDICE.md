# FR Finance — Aditivo técnico M40050

Complementa `docs/FR_FINANCE_ADITIVO_M40040_INDICE.md`, mantendo intactos o Caderno Mestre e o Contrato Técnico selados na auditoria M39100.

**Referência de M40050:** `docs/FR_FINANCE_M40050_HTTP_RETRY_RESPOSTA_PERDIDA_CI.md`.

O pacote testa, somente em **GitHub Actions com servidor HTTP loopback e PostgreSQL 18 descartável**, a confirmação de recibo documental sintético seguida de perda da resposta HTTP e retentativa com a mesma chave de idempotência. Testa também conteúdo alterado, ausência de token sintético, leitor de outra caixinha e bloqueio de escrita por papel não designado.

Não autentica pessoas reais, não cria mandatos, não altera o saldo de membro, não ratifica revisores e não ativa aprovação, PIX ou pagamentos. A PR #2 permanece Draft.

Termux: checkpoint M40040 `9ba74c3` sincronizado. Sem migrações ou acesso ao banco original FR Finance 5433 e ao banco independente FR Caixinha 2.2; sem reinício do FastAPI ou instalação de APK.

`M40050_ORIGINAL_DB_WRITES=NONE`; `M40050_LOCAL_MIGRATIONS=NONE`; `M40050_FASTAPI_RESTART=NONE`; `M40050_REAL_REVOCATION=NOT_ATTESTED`; `PIX_REAL=OFF`; `PAGAMENTOS_REAIS=OFF`; `ATIVACAO_REAL=OFF`; `PRODUCTION=BLOCKED`.
