# FR Finance M40060 — API de consulta autenticada das lacunas de revisão

**Data:** 15/11/2026. **PR:** #2 Draft. **Base local comprovada pelo usuário:** M40050 sincronizado em `7036a33`.

## Novo contrato de consulta

O M40060 integra ao **FastAPI principal** um roteador separado de consulta, baseado no mesmo `get_current_session` e `verify_review_readiness` utilizado em M39960. O endpoint mostra somente bloqueios operacionais de política e mandato, e **não recebe reclamações documentais nem decisões de revisores**.

| Endpoint GET | Identidade necessária | Patrimônio |
|---|---|---|
| `/api/v1/master/exclusive-cashbox/review-policy-gaps` | Master com sessão verificada, origem de hash PostgreSQL e prazo válido | `PLATFORM_MASTER`, apenas receitas/despesas SaaS |
| `/api/v1/tenants/{tenant_id}/admin-exclusive-cashbox/review-policy-gaps` | `TENANT_ADMIN` com sessão verificável do mesmo tenant e proprietário titular ATIVO confirmado por SELECT RLS | `TENANT_ADMIN_OWN`, apenas remuneração/valores particulares |

O Master não pode consultar os gastos ou recursos da caixinha de um tenant; o membro e o administrador de outro tenant não podem ler as lacunas do titular. O domínio `TENANT_COLLECTIVE` não é autorizado. O `tenant_id` da URL só seleciona um **escopo de consulta** e jamais é aceito como prova de titularidade.

## Segurança e evidências não reivindicadas

- Apenas GET; sem POST, ações de revisão, criação de mandato, emissão de recibo ou realização de pagamentos. Não é uma segunda API.
- Sessão real obrigatoriamente validada pelo fluxo de autenticação do backend; testes de CI substituem dependências por sessões **sintéticas**, sem autenticação humana.
- A consulta do titular utiliza exatamente **um SELECT** sobre `public.tenants` na conexão `get_rls_db_connection`. Nenhum SELECT de saldo, ledger, beneficiários ou membros foi adicionado.
- Respostas sem e-mail, nomes de pessoas, sessão, token, hash, CPF ou valor disponível; HTTP `no-store`, `Pragma: no-cache` e `Vary: Authorization`.
- As categorias contábeis vêm do classificador M39900. São identificadas como **não autorizadas**, não como poderes do portador da sessão.
- M39980 permanece minuta não ratificada; M39990 não atesta revogação efetiva; recibos e HTTP idempotente do M40050 continuam apenas experimentos em CI. Não foram conectados à autenticação financeira real.
- Campos `policy_ratified`, `reviewer_grants_verified`, `two_person_approval_verified`, `effective_revocation_verified`, `real_review_approved`, `bank_reconciled`, `journal_posted`, `payout_enabled`, `payment_enabled`, `pix_enabled` e `production_authorized` permanecem todos `false`.

## Homologação e entrega

O teste específico verifica rotas registradas no `app.main`, Master versus tenant e membro, sessão antiga, falsa, expirada e futura, titularidade divergente, sem token, indisponibilidade de ações POST e ausência de código SQL mutador. Inclui regressões M39960, M39980, M39990 e M39090; **não acessa os dois bancos reais**. Até resultado positivo da CI, não sincronizar o Termux.

**Não existe nova migração SQL nem alteração nos esquemas FR Finance/FR Caixinha 2.2.** O FastAPI antigo instalado no Termux não será reiniciado por este pacote. Não instalar APK nem liberar produção. A matriz M39100 e os documentos selados permanecem inalterados.

`M40060_REVIEW_APPROVAL=FALSE`; `M40060_POLICY_RATIFIED=FALSE`; `M40060_ORIGINAL_DB_WRITES=NONE`; `M40060_MIGRATIONS=NONE`; `M40060_PIX_REAL=OFF`; `M40060_PRODUCTION=BLOCKED`.
