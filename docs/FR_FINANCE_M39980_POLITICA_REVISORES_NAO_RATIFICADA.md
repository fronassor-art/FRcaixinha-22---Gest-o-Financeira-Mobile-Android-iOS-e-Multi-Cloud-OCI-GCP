# FR Finance M39980 — Política de revisores: rascunho auditável, autoridade negada

**Data:** 15/11/2026. **PR #2:** Draft na branch `atualizacao-ai-studio-9b46a63187`.
**Último checkpoint recebido no celular:** M39970 sincronizado no commit `5c0d78e`, sem novas migrações,
operações em bancos originais ou reinício do FastAPI.

## Fronteira de política

Os pacotes M39950/M39970 aceitaram duas alegações de revisão associadas a dois
objetos de sessão estruturalmente coerentes. Isso **não** autentica duas assinaturas
nem configura poderes para aprovar gastos, pagamentos ou rateios. A política
de designação de um segundo revisor para patrimônio particular do administrador
ainda não foi pactuada nem homologada.

M39980 cria `backend/app/exclusive_cashbox_review_policy_draft.py`, que
aceita **somente** um `ReviewPolicyDraft` imutável e declara:
- UUID de política e referência digest SHA-256 em minúsculas (formato, não prova).
- Escopo financeiro, tenant, evento vinculado ao mesmo diário e documento M39940.
- Autor da minuta (distinto de preparador e dos revisores), papel compatível e
  janela proposta com horário ciente do fuso.
- Duas `ReviewerGrantDraft` distintas, com os mesmos IDs, escopos,
  tenant e papéis dos revisores M39970; somente `DRAFT_NOT_ATTESTED`.
- `status=PROPOSED_ONLY` como **único** estado aceito. Qualquer cliente tentando
  alegar `APPROVED`, `RATIFIED`, `SIGNED` ou `ACTIVE` falha.
- Declarações dentro da janela proposta, sem transformar horários informados
  pelo cliente em horários atestados.
- Recomputação do M39970 e seus pré-controles documentais e de sessão.

**Por domínio:**
- `PLATFORM_MASTER`: exige rascunho de papel Master para dois revisores
  distintos, mas mantém `MASTER_INDEPENDENT_REVIEWER_MANDATE_UNRATIFIED`.
  Dois IDs de Master não significam que haja dois responsáveis autorizados.
- `TENANT_ADMIN_OWN`: exige papéis e tenant coerentes, mantendo
  `TENANT_ADMIN_OWN_SECOND_REVIEWER_DESIGNATION_UNRATIFIED`.
  O titular não pode simplesmente inventar um segundo administrador
  autorizado ou desconsiderar a regra de titularidade existente.
- `TENANT_COLLECTIVE`: bloqueado neste pacote. Direitos e deveres de
  revisores de recursos coletivos precisam de política própria, separada
  do Master e da remuneração pessoal do administrador.

Há ainda uma **matriz fixa no código** para os sete eventos contábeis:
`SAAS_SETTLEMENT`, `PLATFORM_OPERATING_EXPENSE`,
`ADMIN_CLOSING_REMUNERATION`, `ADMIN_OWN_EXPENSE`,
`MEMBER_CONTRIBUTION`, `TENANT_LOAN_REPAYMENT`,
`TENANT_OPERATING_EXPENSE`. O evento precisa ser do caixa correspondente;
cada tipo exige evidências futuras específicas de provedor, fiscal,
contrato ou fechamento. Nenhuma dessas provas é atestada por esta etapa.

## Invariantes que permanecem falsas

O retorno é sempre `POLICY_DRAFT_NO_AUTHORITY`.
`reviewer_grant_shapes_aligned=true` significa apenas **igualdade de
campos** e nunca autorização concedida.

`policy_approved=false`,
`policy_source_authenticated=false`,
`roles_and_tenant_authorized=false`,
`independent_reviewer_appointment_verified=false`,
`two_person_approval_verified=false`,
`event_evidence_reconciled=false`,
`journal_posted=false`,
`payment_enabled=false`,
`payout_enabled=false`.

Ficam pendentes assinatura/consentimento jurídico da política,
autenticação independente em duas requisições, designação legal do
segundo revisor, titularidade no instante do ato, nonce e idempotência
persistida, reconciliação com provedor e auditoria contábil/fechamento
de 15%/85%. O hash do rascunho **não** é prova criptográfica de assinatura,
aprovação ou versão registrada no banco.

## Execução e testes

A CI `.github/workflows/frfinance-m39980-review-policy-draft-ci.yml`
testa a nova matriz e as regressões M39970/M39950 em Python sem conexões
com PostgreSQL, FastAPI real, Mercado Pago ou OCI. Os testes rejeitam
cross-tenant, evento de outro caixa, período inválido, preparação
e autoaprovação, duplicidade, origem de designação forjada, política
alegadamente ratificada e domínio coletivo sem regra homologada.

**Não foram introduzidos endpoints novos, migrações SQL, alterações no
banco, payloads de pagamento ou de autorização real.** O PostgreSQL original
FR Finance na porta 5433 e o PostgreSQL legado FR Caixinha 2.2 são
independentes e permanecem preservados.

## Passos pendentes para implementar autorização real

A próxima evolução técnica deverá discutir e fixar a política jurídica
do revisor independente, incluindo quem pode nomeá-lo, a separação
entre Master/administrador/membro, seu alcance, prazo, revogação,
registro versionado e assinaturas individualizadas com trilhas de auditoria.
Mesmo após a política, a execução no servidor exigirá leitura autenticada
da identidade/tenant, revisão anti-replay em transação RLS e bloqueio
de lançamento/saque até prova de liquidação e conciliação.

A baseline M39100 de 330 requisitos e 2.310 etapas, o Caderno Mestre
e o Contrato Técnico selados por SHA permanecem intactos; esta é uma
extensão documental separada.

`M39980_TERMUX_ACCESS=NONE`;
`M39980_LOCAL_MIGRATIONS=NONE`;
`M39980_DB_WRITES_ORIGINAL=NONE`;
`M39980_FASTAPI_RESTART=NONE`;
`PIX_REAL=OFF`;
`PAGAMENTOS_REAIS=OFF`;
`ATIVACAO_REAL=OFF`;
`PRODUCTION=BLOCKED`.
