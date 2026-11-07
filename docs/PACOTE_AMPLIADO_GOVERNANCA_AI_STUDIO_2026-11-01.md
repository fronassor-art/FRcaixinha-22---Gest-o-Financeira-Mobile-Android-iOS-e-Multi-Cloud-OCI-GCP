# AI Studio — Pacote ampliado de governança pré-migração (015–016)

**Data de referência:** 2026-11-01. **Escopo único:** aplicativo exportado do Google AI Studio,
PR #2, branch `atualizacao-ai-studio-9b46a63187`.

## Confirmação de restrições do proprietário

- Termux sincronizado até `e1e532e` **antes desta rodada**.
- PostgreSQL 18.6 do AI Studio: `frcaixinha_aistudio_dev`,
  `127.0.0.1:5433`, PGDATA próprio, **zero tabelas** segundo o último
  relatório do usuário.
- Não executar scripts `apply`, bootstrap de Master, instalar APK,
  gravar dinheiro real, ativar Pix, convocar usuários ou enviar e-mail.
- Este pacote **somente prepara código, esquema e testes**, sem criar outro
  Painel Master nem modificar outro projeto.

## Entregas do pacote (4 tarefas solicitadas + 4 adicionais)

| Frente | Evidência criada | Status |
|---|---|---|
| T1 — Identidade única | `account_governance_ci.py: link_existing_identity_ci` | Homologação CI: vincular pessoa existente a múltiplos tenants e papéis somente com aceite do tenant, sem duplicar `users` |
| T2 — Aceite contratual | `015_contract_versions_and_acceptance.sql`; `record_contract_acceptance_ci` | Versão+hash do documento, aceite imutável por usuário, escopo e tenant; prova de identidade **sintética**, não assinatura real |
| T3 — Sessões e acesso | `POST /api/v1/auth/logout-all`; teste real com AUTH role | Revogar sessões do próprio usuário em todos os perfis; não revoga de terceiros |
| T4 — Master SaaS | `016_saas_preparations_no_billing.sql`; `prepare_saas_license_ci` | Congelar a referência à versão de preço e aceite, mas **nenhuma assinatura ativa nem cobrança** |
| T5 — Consultas RBAC SaaS | `GET /master/subscription-preparations` e `GET /tenants/{id}/license-preparation` | MASTER recebe metadados comerciais; TENANT_ADMIN apenas própria caixinha; MEMBER não acessa |
| T6 — Histórico individual de contratos | `GET /tenants/{id}/my-contracts` | Pessoa vê somente seus aceites, nunca dos demais membros |
| T7 — Capacidade informativa | `saas_capacity_snapshot_ci` | Conta identidades de membros distintas e cotas ativas, sem autorizar excesso, novo vínculo ou pagamento |
| T8 — Segurança e regressão | `test_aistudio_governance_ci.py`, `test_aistudio_governance_api.py`, testes logout-all e PostgreSQL 18 | Testes de duplicidade, duas caixinhas, escopo documental, preço imutável, auditoria, RLS e isolamento |

## Regras técnicas preservadas

1. **Múltiplos papéis** não criam uma segunda identidade. Cada vínculo exige
   aceite explícito, tenant correto e auditoria. Ter `MASTER` no `users`
   não concede acesso financeiro automático.
2. `contract_documents` armazena metadados da versão e o SHA-256, não
   reproduz nem substitui as cláusulas dos PDFs originais. A criação no CI
   é **sintética**; não existe aceite real por e-mail ou assinatura digital.
   Documentos publicados e aceites são append-only (triggers bloqueiam
   update/delete). Nova versão exige outro documento.
3. `saas_subscription_preparations` restringe status aos valores
   `PENDING_PAYMENT`, `PAUSED_NO_PAYMENT`, `CANCELED`. Não existe
   `ACTIVE`; a ativação não é inferida de um registro de preparação.
   Preço referenciado à versão aprovada e periodicidade MONTHLY/ANNUAL.
   O anual comercial de 10x o mensal já está na migração 011.
4. O master vê **apenas metadados SaaS**, sem ledger ou saldo bancário de
   tenants; administradores veem somente seu vínculo contratual.
5. O papel técnico `frcaixinha_app_role` tem apenas leitura das novas
   tabelas via RLS; não pode INSERT em aceites ou preparação de licenças.
   A escrita de laboratório exige superusuário **somente em CI descartável**
   e `FRCAIXINHA_CI_ISOLATED=1`.
6. A funcionalidade real de convite/recuperação da migração 014 continua
   **503 na API pública** até implementar verificação de e-mail, provedor,
   política de consentimento e rate limit distribuído.
7. A capacidade `20/40`, `50/50` é catálogo demonstrativo até a regra
   transacional aprovada para contagem de cotas e membros; **não habilitar
   aquisição automática**.
8. Cobrança de licença com tolerância zero e reativação dependem de
   liquidação e conciliação real. Os estados do esquema 016 não representam
   essas operações e não alteram `tenants.status`.

## Aprovação de testes não equivale a operação pronta

O GitHub Actions executa testes de API/frontend, PostgreSQL 16 descartável,
PostgreSQL 18 em única transação e APK debug. A aprovação nesses testes
não representa homologação no Android real, validação de segurança independente,
integração de e-mail nem conciliação bancária.

## Pendências críticas remanescentes

- Fluxo público de cadastro/convite, comprovante de titularidade e aceite
  jurídico vinculados ao documento aprovado, sem titularidade sintética.
- Provedor de e-mail, recuperação de conta, rate limit distribuído,
  observabilidade e proteção de sessões de produção.
- Estado operacional SaaS: checkout, liquidação, expiração com tolerância zero,
  suspensão, reativação, renovação e cobranças revertidas.
- Política de aquisição de cotas e capacidade com testes de corrida real.
- Conciliação bancária, empréstimos efetivos, fechamento anual e validação
  jurídica dos módulos regulados. Nenhum desses está sendo liberado.
- Atualização individual do checkpoint de 147 cláusulas com evidência por
  requisito: os números históricos não foram reclassificados automaticamente.

**Operação seguinte autorizada:** sincronizar somente os arquivos após CI
aprovado. O banco local deve permanecer **sem migrações** até decisão
posterior e expressa do proprietário.
