# FR Finance — Aditivo técnico M39960

Complementa `docs/FR_FINANCE_ADITIVO_M39950_INDICE.md`.
A baseline de 330 requisitos / 2310 passos e os SHA do Caderno
Mestre e Contrato Técnico M39100 permanecem intactos.

- M39960 adiciona somente GET de prontidão para observadores
  financeiros Master e Administrador titular, vinculado a sessão
  PostgreSQL gerada pelo servidor.
- A sessão precisa ter hash/token verificado, renovação válida
  e role/tenant compatíveis; no administrador exige também
  SELECT de titularidade ativa via conexão RLS.
- As seis rotas atuais de caixas devem retornar `no-store`.
- Não autentica comprovantes M39940, não converte revisões
  alegadas M39950 em aprovações, não autoriza saques,
  transferências, lançamentos ou conciliação.
- Endpoints e testes: ver
  `docs/FR_FINANCE_M39960_PRONTIDAO_SESSAO_CAIXAS.md`.

`M39960_TERMUX_MIGRATIONS=NONE`;
`M39960_ORIGINAL_DATABASE_WRITES=NONE`;
`FASTAPI_RESTART=NONE`;
`PIX_REAL=OFF`;
`PAGAMENTOS_REAIS=OFF`;
`ATIVACAO_REAL=OFF`;
`PRODUCAO=BLOCKED`.
