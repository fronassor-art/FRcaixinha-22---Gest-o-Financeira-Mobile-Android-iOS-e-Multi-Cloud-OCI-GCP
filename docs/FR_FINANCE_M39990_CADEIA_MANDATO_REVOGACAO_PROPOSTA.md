# FR Finance M39990 — Sequência documental de designação, desistência e revogação

**Data:** 15/11/2026. **Branch:** `atualizacao-ai-studio-9b46a63187`.
**PR #2:** Draft. **Checkpoint local recebido:** M39980 `adc7510` sincronizado
no Termux, por fast-forward, com `MIGRATIONS=NONE`,
`DB_WRITES=NONE`, `FASTAPI_RESTART=NONE`.

## Contexto

M39950: dupla de alegações documentais.
M39960: sessão do observador ancorada no mecanismo de autenticação do servidor,
somente leitura.
M39970: correlação estrutural de dois objetos de sessão a revisores alegados.
M39980: rascunho de política não ratificada e sem autoridade.

**M39990 não finge que esses dados já criam mandatos legais ou autorização de
pagamentos.** Ele constrói o ensaio puro de sequências de eventos declarados,
incluindo revogação e desistência *propostas*, para expor requisitos técnicos
antes de implementar um fluxo autenticado.

## Entrega

`backend/app/exclusive_cashbox_mandate_lifecycle_draft.py` contém
`inspect_untrusted_mandate_lifecycle` e os tipos imutáveis
`MandateEventDraft` / `MandateLifecyclePreview`.

Entrada obrigatória: diário candidato, documento proposto, duas alegações de
revisão, duas sessões declaradas, rascunho de política M39980, sequência de
eventos e horário de observação.

Cada evento exige:
- UUID distinto, fingerprint exato da política proposta, escopo e tenant
  idênticos aos do rascunho;
- revisor integrante de um dos dois vínculos da política;
- ator alegado e ação estritamente compatíveis com a **forma** do pedido:
  `APPOINTMENT_PROPOSED` pelo autor da minuta, `WITHDRAWAL_PROPOSED`
  pelo próprio revisor, `REVOCATION_PROPOSED` pelo autor da minuta;
- digest SHA-256 estrutural distinto por evento, horário com fuso
  dentro da janela proposta e nunca posterior à observação;
- cronologia estritamente crescente, UUID e digest sem duplicação.

A sequência começa com **exatamente duas propostas de designação**, uma para
cada revisor; após elas, permite no máximo uma desistência ou revogação
proposta por revisor. Não admite reativação, novo mandato após uma
terminação proposta ou mudança de papel/tenant no meio da sequência.
O número de eventos permitidos é 2–4. O hash de cadeia canônico inclui
a versão do formato, fingerprint anterior, política, ator alegado, evento,
revisor, documento e horário em UTC.

**Esses controles são estruturais, não autenticação nem auditoria
persistida**: um cliente pode criar todos os campos, inclusive UUIDs, horários
e digests. O hash de cadeia não é assinatura digital, timestamp confiável,
prova de consentimento, prova de não repúdio, proteção durável contra replay
ou garantia contra concorrência. O histórico só existe na memória do ensaio.

## Patrimônios e responsabilidades

- `PLATFORM_MASTER`: a política de quem pode designar e revogar
  revisores do caixa de receitas/despesas SaaS não está ratificada.
- `TENANT_ADMIN_OWN`: o segundo revisor da remuneração própria do
  administrador não está designado nem autorizado juridicamente.
  Nenhum membro ou funcionário recebe privilégios por este ensaio.
- `TENANT_COLLECTIVE`: permanece fora da prévia de mandato; nenhuma
  autorização Master sobre o patrimônio coletivo é criada.

O estado de retorno é sempre `MANDATE_LIFECYCLE_DRAFT_ONLY`.
São sempre **falsos**:
`source_events_authenticated`,
`durable_audit_events_recorded`,
`reviewer_appointment_verified`,
`consent_signatures_verified`,
`effective_revocation_recorded`,
`reviewer_grants_authorized`,
`independent_review_approved`,
`journal_posted`,
`payment_enabled`,
`payout_enabled`.

As contagens `nonterminal_proposal_count` e
`terminal_proposal_count` contam **somente alegações**; não equivalem
a cargos ativos, mandatos vigentes ou revogações legalmente eficazes.

## Testes

`backend/tests/test_m39990_mandate_lifecycle_draft_ci.py` e workflow
`.github/workflows/frfinance-m39990-mandate-lifecycle-ci.yml`:
- propostas iniciais exigidas, cadeia determinística e normalização UTC;
- desistência e revogação apenas como eventos propostos;
- rejeição de UUID repetido, digest repetido, sequência regressiva,
  eventos fora da janela, ressurreição de mandato alegado;
- rejeição de ator diferente, escopo/tenant de outra caixinha,
  revisor ausente, enum `APPROVED` / `ACTIVE` / `PAID`;
- regressão M39980, M39970 e M39950; tudo offline, sem SQL.

## Para futura implementação real

Serão necessários: decisão contratual sobre poderes de nomeação/revogação,
identidade ancorada na sessão em **requisições diferentes**, consentimento
assinado, notificações adequadas, documento original autenticado, linha
de auditoria append-only transacional, chave de idempotência durável,
controle de concorrência, RLS real com tenant e papéis provados pelo
servidor, expiração/revogação efetivas e revisão de responsabilidades.
Esses requisitos não são preenchidos aqui.

O PostgreSQL original FR Finance (porta 5433) e o banco FR Caixinha 2.2
permanecem segregados. O M39990 não cria endpoints, tabelas, migrações,
notificações, pagamentos, lançamentos, controles de produção ou reinícios.

Caderno Mestre e Contrato Técnico SHA-locked M39100 intocados.
`M39990_ORIGINAL_DB_ACCESS=NONE`;
`M39990_LOCAL_MIGRATIONS=NONE`;
`M39990_FASTAPI_RESTART=NONE`;
`PIX_REAL=OFF`;
`PAGAMENTOS_REAIS=OFF`;
`ATIVACAO_REAL=OFF`;
`PRODUCAO=BLOCKED`.
