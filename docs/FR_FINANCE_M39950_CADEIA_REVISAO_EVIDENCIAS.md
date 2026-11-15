# FR Finance M39950 — Cadeia de revisão e catálogo de evidências

**Data:** 15/11/2026. **Branch:** `atualizacao-ai-studio-9b46a63187`. **PR #2:** Draft.

## Confirmações anteriores

O usuário confirmou a sincronização M39930 em `4c47109` no Termux:
`M39930_TERMUX=SYNCED`, `MIGRATIONS=NONE`,
`DB_WRITES=NONE`, `FASTAPI_RESTART=NONE`.
O M39940 foi aprovado em 38/38 workflows GitHub no commit `deb84bc`.
**Esta etapa não acessa o Termux.**

## Entrega

O pacote M39950 aprofunda a preparação de rastreabilidade dos
três caixas sem sequer pretender autenticar documentos ou
lançar saldos. Dois módulos independentes são desenvolvidos:

1. `backend/app/exclusive_cashbox_documentary_review.py`:
   avalia a **forma** de duas alegações de revisão documental.
   Exige dois identificadores distintos do preparador e
   um do outro, um dos revisores deve corresponder ao revisor
   proposto no rascunho M39940, e todos devem referenciar
   o mesmo escopo, tenant, fingerprint e hash documental.
   Datas precisam ser timezone-aware e não regressivas.
   Apenas os códigos `DOCUMENTARY_CHECK_PROPOSED` e
   `REQUEST_MORE_EVIDENCE` são admitidos. `APPROVED`,
   `PAY`, `SETTLED` ou `TRANSFER` são proibidos.
   Um hash canônico de cadeia é **identificador sintético**,
   não assinatura digital ou prova de identidade.
2. `backend/tests/sql/m39950_documentary_review_catalog_disposable_ci.sql`:
   ensaio de **catalogação em PostgreSQL 18 descartável**.
   Cria tabelas e funções somente em uma transação da base
   `frcaixinha_ci`, obriga RLS/FORCE, concede apenas
   `SELECT` ao papel sintético, FK composta para
   `document_id + scope + cashbox_key + fingerprint + digest`,
   regras anti-replay, anti-autorrevisão, sem escrita à
   conta sintética e triggers de apêndice imutável.
   Executa `ROLLBACK` integral ao final.

O resultado puro é sempre
`DOCUMENTARY_REVIEW_CLAIMS_UNVERIFIED` e mantém:
`document_authenticated=false`,
`reviewer_identities_verified=false`,
`two_person_approval_verified=false`,
`independent_authorization_verified=false`,
`provider_reconciled=false`, `journal_posted=false`,
`payout_enabled=false`.

## Provas específicas

- Duas identidades de revisores alegadas, distintas do
  preparador; sem duplicação, rejeição de par e quantidade
  errados.
- Correspondência exata do documento original com diário,
  escopo financeiro, tenant e hash; troca de caixinha
  falha antes de qualquer autorização.
- Horários UTC normalizados, sem exigir que um horário
  fornecido por cliente seja considerado confiável.
- Controle numérico documental M39940 permanece
  somente prévia dos 15%/85% contratuais, **sem
  fechamento financeiro, remuneração reconhecida, saque
  ou apuração real**.
- PostgreSQL experimental verifica Master separado do
  tenant, dois tenants segregados, membros sem acesso,
  role de leitura sem INSERT/UPDATE/DELETE,
  documento imutável e impossibilidade de aprovação
  ou balanço positivo fictício.
- Arquivos com nome `m39950_` sob `backend/tests/sql`
  **não são** novas migrations, nem migração SQL 114/115.
  O ensaio exige flag CI, banco `frcaixinha_ci`,
  PostgreSQL container porta 5432, usuário `postgres`
  e `frfinance.m39950_ci=DISPOSABLE_ONLY`.
  Não copiar essas variáveis ou scripts para Termux.

## Limites essenciais

Os IDs de revisores e o papel/tenant de sessão utilizados
pelo experimento são **alegações e valores sintéticos**.
Não há verificação de RG/CPF, autenticação por backend,
controle de titularidade do tenant, assinaturas independentes,
vínculo legal da autorização, checagem em Mercado Pago,
conciliação bancária, conferência de notas fiscais, estorno,
saldo, saída de caixa, posting ou pagamento.

O ensaio com `SET LOCAL ROLE` não constitui política
de produção: a sessão real precisa derivar identidade e
permissões autenticadas no servidor, não de parâmetros
arbitrários fornecidos por app/cliente. Imutabilidade
contra superusuário, restrições de migração, ciclo,
idempotência real e backup ainda requerem auditoria.

O FR Finance PostgreSQL 18 original (porta **5433**) e o
FR Caixinha 2.2 legado seguem isolados; nenhuma consulta
ou escrita foi realizada neles. O Caderno Mestre e o
Contrato Técnico selados pelo M39100 permanecem
**imutáveis**, com aditivos em documentação separada.

## Arquivos

- Biblioteca: `backend/app/exclusive_cashbox_documentary_review.py`
- Testes: `backend/tests/test_m39950_documentary_review_chain_ci.py`
  e `backend/tests/test_m39950_documentary_catalog_source_ci.py`
- SQL de CI descartável:
  `backend/tests/sql/m39950_documentary_review_catalog_disposable_ci.sql`
- Workflow GitHub:
  `.github/workflows/frfinance-m39950-documentary-review-catalog-ci.yml`

**Checkpoint:** `M39950_MIGRATIONS_LOCAL=NONE`;
`M39950_DB_WRITES_ORIGINAL=NONE`;
`M39950_FASTAPI_RESTART=NONE`; `PIX_REAL=OFF`;
`PAGAMENTOS_REAIS=OFF`; `ATIVACAO_REAL=OFF`;
`PRODUCAO=BLOCKED`.

A etapa seguinte, antes de qualquer plano real de migração,
exige autorização de atores ancorada no servidor,
fonte de prova autenticada, orçamento/resultado auditado,
registros idempotentes e revisão independente verificável.
