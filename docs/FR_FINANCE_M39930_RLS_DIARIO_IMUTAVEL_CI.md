# FR Finance M39930 — RLS e imutabilidade do diário experimental

**Data:** 15/11/2026. **Branch:** `atualizacao-ai-studio-9b46a63187`.
**PR:** #2 em rascunho. **Termux recebido:** M39920 sincronizado em
`8629281`, sem migração, escrita no banco original ou reinício da API.

## Natureza e limites

M39930 é um **ensaio de esquema contábil**, não uma migração SQL, não
um novo endpoint e não um comando para executar no celular. O código
vive apenas em `backend/tests/sql/m39930_immutable_ledger_rls_disposable_ci.sql`.
Um PostgreSQL 18 **descartável no GitHub Actions** recebe objetos
temporariamente dentro de uma transação encerrada com `ROLLBACK`.

A execução exige antes de qualquer DDL:
- `CI_M39930_DISPOSABLE` fornecido pelo workflow;
- base com nome exato `frcaixinha_ci`;
- conexão na porta `5432` do container CI;
- `session_user=postgres` e parâmetro
  `frfinance.m39930_ci=DISPOSABLE_ONLY`.

Não configurar esses gates no Termux. O PostgreSQL do FR Finance original
continua **5433**; o PostgreSQL FR Caixinha 2.2 fica isolado e não deve
ser usado no desenvolvimento desta frente.

## Invariantes testados

- **Três patrimônios distintos:** `PLATFORM_MASTER` somente SaaS e
  despesas da plataforma; `TENANT_ADMIN_OWN` exclusivamente
  remuneração/despesas do administrador; `TENANT_COLLECTIVE` para
  contribuições e lançamentos da caixinha. Chave composta de escopo
  e caixinha impede misturar os diários.
- **Partidas dobradas:** cada diário necessita ao menos duas linhas e
  soma `DR=CR`; o gatilho diferido é verificado antes de confirmar a
  transação experimental. Diário incompleto é rejeitado.
- **Append-only:** `UPDATE` e `DELETE` nas tabelas do ensaio são
  recusados por gatilhos. A política de estorno futuro deverá criar
  lançamentos inversos auditados, nunca editar o original.
- **Antirrepetição:** a referência documental é única por domínio e
  chave patrimonial, recusando replay da mesma referência.
- **Segregação por conta e tenant:** contas `PM_`, `TA_` e `TC_`
  não são intercambiáveis; FK composta impede referência de linha a
  diário de outra caixinha.
- **Permissões/RLS no banco descartável:** role de aplicação sem
  `BYPASSRLS` recebe somente `SELECT`. Políticas sintéticas
  simulam Master com acesso a registros da plataforma, Admin com
  acesso somente ao tenant escolhido e Membro sem acesso aos caixas
  exclusivos. Dois tenants independentes são verificados.
- **Sem saldos e pagamentos:** `posted=false`,
  `provider_reconciled=false`, `payout_enabled=false` e
  `available_balance_cents=null` obrigatórios nos candidatos.

## Limitações de segurança que permanecem bloqueadoras

Este esquema **não pode** ser copiado diretamente como DDL de produção.
Os valores de papel/tenant são parâmetros sintéticos de sessão para
testar as políticas. Em produção eles dependerão de autenticação
verificada server-side, usuário e titularidade ativa, transação
`SET LOCAL`, roles PostgreSQL revisadas, `FORCE RLS`, políticas que
não aceitem papel ou tenant arbitrário, auditoria de bypass pelo dono
do banco, segregação de funções e testes de corridas/conexões.

A proibição de escrita demonstrada vale para o papel de aplicação do
ensaio; **não** constitui prova de imutabilidade contra superusuário
ou operador de migração. O gatilho de balanço é uma prova de conceito;
versão real ainda exigirá prova de idempotência, competência, estorno
e conciliação do provedor, ciclo financeiro, documentos fiscais,
fechamento auditado e aprovação independente.

Em particular, a participação 15%/85% é uma **regra contratual de lucro
líquido elegível**, não um lançamento que possa ser gerado a partir da
contagem de `ledger_transactions` ou de `saas_payment_intents`.
Nenhuma tabela persistente de salário do Admin ou caixa da plataforma
foi criada no PostgreSQL original.

## Artefatos e verificações

- SQL experimental: `backend/tests/sql/m39930_immutable_ledger_rls_disposable_ci.sql`.
- Auditor de fonte: `backend/tests/test_m39930_immutable_ledger_rls_source_ci.py`.
- CI: `.github/workflows/frfinance-m39930-immutable-ledger-rls-ci.yml`.
- Documento-base de precedência: `docs/FR_FINANCE_ADITIVOS_M39900_M39920_INDICE.md`.
- Aditivos independentes não alteram a baseline selada do M39100
  (**330 itens / 2310 etapas**). Incluir M39930 em uma futura versão
  de índice formal não promove qualquer liberação de produção.

## Próximas etapas condicionais

Revisar schema em staging descartável completo com RLS do produto,
contas versionadas, periodização por ciclo, trilha imutável de correção,
validação de autenticação e titularidade, autorização de abertura/fechamento,
reconciliação do provedor e restauração de backup. Só após aprovação
documental, testes CI e autorização separada poderá ser preparado o
processo de aplicar uma migração nova no **banco original**.

`M39930_ORIGINAL_DB_ACCESS=NONE`; `M39930_MIGRATIONS=NONE`;
`PIX_REAL=OFF`; `PAGAMENTOS_REAIS=OFF`; `ATIVACAO_REAL=OFF`;
`FASTAPI_RESTART=NONE`; `PRODUCTION=BLOCKED`.
