# FR Finance — Aditivo M39970 de revisão por sessões

Este aditivo estende o índice
`docs/FR_FINANCE_ADITIVO_M39960_INDICE.md` sem modificar o
Caderno Mestre nem o Contrato Técnico selados pelo M39100
(330 requisitos e 2.310 etapas).

**M39970:** `docs/FR_FINANCE_M39970_CORRELACAO_SESSOES_REVISORES.md`.

Verifica apenas estrutura e correspondência entre duas declarações
documentais e dois objetos de sessão com metadados
`POSTGRES_TOKEN_HASH_REFRESH`. Rejeita sessão duplicada, ator
diferente do revisor alegado, preparador na dupla, falta de papel,
troca de tenant, expiração e timestamp fora de janela.
Não reconhece identidade/assinatura de dois usuários independentes,
não verifica titularidade do segundo revisor e não autoriza
movimentação de caixa.

A política real de designação de revisor do Admin e a política
do caixa coletivo permanecem abertas; não improvisar permissões.
Sem endpoint novo, SQL, migração, alteração no Termux, reinício
de FastAPI, pagamento ou liberação de produção.

`M39970_ORIGINAL_DB_WRITES=NONE`;
`PIX_REAL=OFF`; `PAGAMENTOS_REAIS=OFF`;
`ATIVACAO_REAL=OFF`; `PRODUCTION=BLOCKED`.
