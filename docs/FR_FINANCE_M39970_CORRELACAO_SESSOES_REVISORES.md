# FR Finance M39970 — correlação de revisores e sessões independentes

**Data:** 15/11/2026. **Branch:** `atualizacao-ai-studio-9b46a63187`. **PR #2:** Draft.

## Ponto de partida

Checkpoint Termux M39960 confirmado no commit `0a05049`:
sem novas migrações, writes, pagamentos reais ou reinício FastAPI.
A base PostgreSQL original **FR Finance 5433** e a base separada
FR Caixinha 2.2 permanecem intocadas.

M39950 comprova apenas a *forma* de duas declarações documentais.
M39960 comprova, dentro de uma requisição autenticamente atendida
pelo servidor, a prontidão de consulta de um usuário. Nenhum desses
controles implementa duas aprovações independentes.

## Entrega incremental

Biblioteca `backend/app/exclusive_cashbox_review_session_pair.py`.
Função pura `correlate_unverified_review_sessions()` combina
um diário M39920, evidência M39940, alegações de revisão M39950 e
**dois objetos de sessão M39960**. Reavalia os preflights anteriores
e exige:

- Exatamente duas sessões representadas por `AuthenticatedSession`,
  ambas apresentando o vínculo `POSTGRES_TOKEN_HASH_REFRESH`,
  UUID não zero de usuário/sessão, expiração e renovação coerentes.
- Um usuário diferente em cada sessão e identificadores de sessão
  diferentes; nenhum revisor pode ser o preparador declarado.
- A identidade de cada sessão deve coincidir **exatamente com a ordem**
  e o `reviewer_id` de sua declaração; trocas e duplicações falham.
- Papel/tenant devem ser compatíveis com **Master SaaS** ou
  **administrador do próprio tenant**, como no M39960.
  Uma sessão de Master não pode validar administração financeira
  da caixinha, e uma sessão de outro tenant não participa.
- A hora *alegada* da revisão precisa estar dentro da janela
  *alegada* de sessão, até o horário da avaliação. Não torna
  confiável um timestamp que o usuário/cliente informou.
- O domínio `TENANT_COLLECTIVE` não é aceito neste pacote:
  a política de revisores para patrimônio coletivo ainda não
  está definida e auditada separadamente.

O retorno é sempre `REVIEW_SESSION_PAIR_STRUCTURAL_ONLY`, com
`claims_cryptographically_signed=false`,
`verified_independent_reviewers=false`,
`reviewer_roles_authorized=false`,
`tenant_owner_attested=false`,
`documentary_review_authorized=false`,
`source_document_authenticated=false`,
`provider_reconciled=false`, `journal_posted=false`,
`payout_enabled=false`.

## Limites: provas que este código NÃO possui

`AuthenticatedSession` é um objeto Python instanciável em testes.
Recebê-lo como argumento de função **não prova** que houve duas
requisições HTTP autenticadas diferentes ou aprovação real.
Uma integração de produção precisará registrar cada revisão
exclusivamente no servidor a partir de seu `get_current_session`,
consultar vínculo ativo e permissão explícita *no momento do ato*,
gerar um nonce anti-replay, registrar o documento exato assinado,
persistir auditoria imutável e garantir transação/concorrência.

Há um bloqueio de produto importante: a rota atual do caixa
`TENANT_ADMIN_OWN` exige **titularidade** do administrador.
Não há política já homologada que autorize um segundo usuário
a aprovar esse patrimônio em nome do titular. **Não contornar**
este limite criando um segundo administrador fictício. É necessária
uma política de designação e responsabilidade do segundo revisor,
com prova real de consentimento e autorização.

De forma semelhante, sessões Master distintas não constituem,
por si, duas autorizações legais independentes. O caixinha
`TENANT_COLLECTIVE` requer outra política específica; Master
não pode ler fundos ou ledger coletivo.

A ausência de documento autenticado, fechamento anual validado,
rateio elegível 15%/85%, prova de despesa, conciliação do provedor,
licenças e autorização de pagamento mantém produção bloqueada.

## Entregáveis e CI

- Código puro: `backend/app/exclusive_cashbox_review_session_pair.py`.
- Testes sintéticos: `backend/tests/test_m39970_review_session_pair_ci.py`.
- Workflow: `.github/workflows/frfinance-m39970-review-session-pair-ci.yml`.
- Regressão M39950 + M39960. Sem endpoint, tabela, migração ou
  alteração de UI. O FastAPI local não é reiniciado.

## Invariantes permanentes

`M39970_TERMUX_MIGRATIONS=NONE`;
`M39970_ORIGINAL_DB_WRITES=NONE`;
`M39970_FASTAPI_RESTART=NONE`;
`PIX_REAL=OFF`;
`PAGAMENTOS_REAIS=OFF`;
`ATIVACAO_REAL=OFF`;
`PRODUCAO=BLOCKED`.

Os hashes da baseline M39100 do Caderno Mestre e do Contrato
Técnico permanecem selados; este documento é um aditivo.
