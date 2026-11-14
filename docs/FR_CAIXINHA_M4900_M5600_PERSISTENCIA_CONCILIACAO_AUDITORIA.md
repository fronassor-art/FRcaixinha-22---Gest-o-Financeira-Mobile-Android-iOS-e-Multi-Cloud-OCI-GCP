# FR Caixinha AI Studio — Macropacote M4900–M5600 e auditoria incremental

**Projeto exclusivo:** FR Caixinha AI Studio, SaaS de gestão financeira automatizada, **não banco, instituição de pagamento, nem custodiante**. Nada deste pacote altera o projeto separado FRcaixinha 2.2.

**Baseline Termux informado:** `48e084678fadf6fbc583e2cb3f0f2b759ffd827c` (M4800), FastAPI PID `9436`, PostgreSQL local `127.0.0.1:5433`, dinheiro real inativo. Este pacote **não** aplica migrações nem instala servidor.

**Commits de implementação:** `2b09d39e6c4bc2224fc231512a68c9b27d662a66` e correção de testes `80ab252638853fc283762276fda334ec8b025643`. Branch `atualizacao-ai-studio-9b46a63187`; PR #2 Draft e não mesclada.

**Método de auditoria:** inventário atual de 572 arquivos versionados, 77 módulos backend, 106 testes backend, 38 componentes React e 49 testes frontend, 30 migrações locais e 5 scripts de staging. Conferência dos caminhos e CI automatizada, sem declarar testes reais de provedor, análise regulatória ou aplicação de migrações. Checklist contratual de 147 cláusulas mantido em `docs/AUDITORIA_GERAL_M4800_CHECKLIST_147_2026-11-04.md`.

## Tarefas com implementação entregue (M4900–M5600)

- [x] **M4900.01** Aprovação de empréstimo separada da operação de desembolso.
- [x] **M4900.02** Eliminar geração antecipada de `loan_installments` da rota de aprovação administrativa.
- [x] **M4900.03** Não permitir a aprovação quando já existam parcelas indevidas para empréstimo ainda solicitado; exigir revisão.
- [x] **M4900.04** Preservar bloqueio de autoempréstimo do administrador sem unanimidade/aceite anual.
- [x] **M4900.05** Registrar evento de auditoria para aprovação sem movimentação financeira.
- [x] **M4900.06** Testar que Master, Membro, tenant diverso e estado inválido não aprovam crédito.
- [x] **M5000.01** Criar migração 038 exclusiva de OCI staging, condicionada ao DBA e à cadeia M034–M037.
- [x] **M5000.02** Corrigir campos de ID da transação Pix Orders `PAY...` de `varchar(40)` para `varchar(80)`.
- [x] **M5000.03** Vincular tenant + operação por FKs compostas entre cobrança, prova, recibo e consulta Orders.
- [x] **M5000.04** Adicionar função de reserva transacional com `pg_advisory_xact_lock` e única tentativa ativa por obrigação.
- [x] **M5000.05** Na função, comparar valor ainda devido em `contributions` ou `loan_installments` e status do empréstimo efetivamente desembolsado.
- [x] **M5000.06** Exigir vínculo ativo do seller Mercado Pago, membro ativo e ciclo aberto.
- [x] **M5000.07** Preservar idempotência de operação e impedir colisões econômicas de outra cobrança.
- [x] **M5000.08** Função restrita para salvar Order, PAY e QR apenas uma vez; repetição idêntica retorna replay.
- [x] **M5000.09** Preservar timeout ambíguo `PENDENTE_CONCILIACAO`; não gerar reenvio automático.
- [x] **M5000.10** Impedir que reserva em conciliação seja exibida como QR novamente.
- [x] **M5000.11** Revogar execução das funções do público e conceder apenas ao login de worker financeiro de staging.
- [x] **M5100.01** Implementar adaptador PostgreSQL server-only para reserva, leitura, gravação e estado incerto.
- [x] **M5100.02** Exigir `frcaixinha_staging`, conta `frcaixinha_mp_financial_worker` e função SQL presente.
- [x] **M5100.03** Recusar tenant/seller divergente ou produção antes de abrir transação.
- [x] **M5100.04** Não executar chamadas externas dentro da transação de banco.
- [x] **M5100.05** Negar `atomic_post_once` enquanto repositório financeiro de conciliação não existir.
- [x] **M5200.01** Validar três origens de prova: obrigação, GET Order autenticado e declaração de liquidação externa autenticada.
- [x] **M5200.02** Conferir tenant, seller, Order, PAY, referência, moeda BRL e centavos exatos.
- [x] **M5200.03** Conferir `gross - fee = net`, status de liquidação, hash e data com fuso.
- [x] **M5200.04** Rejeitar CSV enviado pelo usuário, webhook isolado, status `approved` ou divergência de identidade como prova conclusiva.
- [x] **M5200.05** Definir porta de leitura de extrato externo injetada por worker de confiança; não conectada a banco real.
- [x] **M5300.01** Classificar estado de cobrança e ação de recuperação sem efeito financeiro.
- [x] **M5300.02** Se timeout ocorreu sem Order ID, solicitar rastreio do provedor; proibir novo POST automático.
- [x] **M5300.03** Quando Order ID existe, permitir apenas GET autenticado e consulta de extrato, não baixa/repasse.
- [x] **M5300.04** Proibir recuperação sob vínculo revogado ou contexto de tenant inválido.
- [x] **M5300.05** Preservar estados finais e recibos existentes sem mutação/reprocessamento.
- [x] **M5400.01** Converter `effective_at` confirmado para o fuso IANA da caixinha antes de calcular a Tabela Price.
- [x] **M5400.02** Exigir horário com timezone, prazo no ciclo, principal idêntico ao desembolso e amortização integral.
- [x] **M5400.03** Atualizar `PayoutAutomation.reconcile_disbursement` para exigir `tenant_timezone` explícito do contexto do servidor.
- [x] **M5400.04** Testar cenários de horário de Belém e Manaus, limites de ciclo e valor divergente.
- [x] **M5500.01** Registrar endpoint de saúde M5600 mostrando todas as funcionalidades financeiras reais desativadas.
- [x] **M5500.02** Garantir webhook Orders não exposto no FastAPI local.
- [x] **M5500.03** Adicionar grupos de testes M4900–M5500 à CI existente, preservando os seis jobs originais.
- [x] **M5600.01** Preparar checklist incremental de execução e pendências com bloqueios sem mascarar falta de homologação.
- [x] **M5600.02** Preservar linha de base das 147 cláusulas e 5 divergências documentais; nenhuma baixa integral sem prova contratual.

**Critério do [x]:** implementação versionada e verificação automatizada associada ao pacote. A marca NÃO diz que a ferramenta está conectada a contas bancárias, pronta para produção ou que a migração 038 foi aplicada.

## Atualização pontual da matriz contratual (sem inventar estado integral)

| Cláusula | Evidência nova | Estado conservador |
|---|---|---|
| 1.4 e 7.6 | Separação de software de gestão e PSP externo | PARCIAL: parecer jurídico ainda pendente |
| 7.1–7.4 | SQL staging 038 com tenant+operação e advisory lock | PARCIAL / BLOQUEADO: staging não aplicado |
| 8.4–8.5 | Aprovação sem parcelas e datas pelo desembolso comprovado+fuso | PARCIAL: worker de posting e prova bancária faltam |
| 8.6 | Preflight de recebimento, imputação testada em motor existente | BLOQUEADO: journal real não implementado |
| 8.7–8.9 | Desembolso protegido, cronograma posterior, bloqueio de fechamento | BLOQUEADO: Money Out e contabilidade efetiva inativos |
| 9.2–9.3 | Orders Pix + reserva idempotente, repositório staging | BLOQUEADO: app runtime não ligado ao provedor |
| 9.4–9.5 | Anti-reenvio, recuperação de timeout e replay | BLOQUEADO: aprovação comercial Money Out e reversões faltam |
| 9.8–9.9 | Validação três fontes, gates de ambiente e webhook | BLOQUEADO: extrato autenticado real e worker faltam |
| 12.3–12.4 | FKs compostas e constraints no SQL staging | PARCIAL: execução/rolamento real ausentes |
| 13.1–13.6 | Testes e proibições de escopo financeiro | PARCIAL: recuperação operacional e pentest faltam |
| 16.4 | CI de contratos adicionais | BLOQUEADO: cenários AT-01 a AT-50 não homologados integralmente |

## Checklist ainda P0 para finalizar a automação

- [ ] **P0-01 — OCI:** provisionar staging autorizado com IAM, TLS, Vault, banco isolado e backup comprovado.
- [ ] **P0-02 — Migrações:** executar ensaio de aplicação e rollback 034–038 em PostgreSQL descartável equivalente, auditar nomes reais de roles, FKs e SECURITY DEFINER antes de qualquer aplicação OCI.
- [ ] **P0-03 — Identidade:** onboarding real OAuth Connect por tenant com PKCE, `offline_access`, refresh Vault e revogação.
- [ ] **P0-04 — Runtime:** injetar o adaptador Orders com identidade validada no `app.state.pix_automation_runtime` sob autorização expressa, não com flags do cliente.
- [ ] **P0-05 — Webhooks:** montar a entrada HTTPS assinada Orders no staging com inbox, replay, recuperação e status autenticado.
- [ ] **P0-06 — Banco de prova:** implementar fonte independente autenticada de extrato e conciliação de taxas do PSP, não arquivo CSV isolado.
- [ ] **P0-07 — Journal:** criar worker transacional real com RLS, idempotência econômica, ledger equilibrado e recibo único, reversões e tolerância a crash.
- [ ] **P0-08 — Obrigações:** dar baixa contábil e mensalidades/parcelas apenas após prova externa e atomicidade no journal.
- [ ] **P0-09 — Crédito:** implementar disponibilidade de caixa, reserva, limites, consentimentos, aprovação, recusas, auditoria e registro de beneficiário Pix com titularidade comprovada.
- [ ] **P0-10 — Money Out:** obter aprovação comercial para empréstimos e por conta de administrador, homologar assinatura do body, consulta final de status e saída Pix em teste autorizado.
- [ ] **P0-11 — Price:** persistir parcelas definitivas e atualizar os totais simulados do empréstimo após prova real de desembolso, transacionalmente com ledger; reconciliar timezone da política.
- [ ] **P0-12 — Segurança:** testar concorrência entre tenants, tokens revogados, dados Pix, incidentes, segredo Vault, RLS e histórico não destrutivo.
- [ ] **P0-13 — Fechamento:** validar distribuição, restituição, ciclo e encerramento só após conciliação e aceite de todos os casos.
- [ ] **P0-14 — LGPD/Jurídico:** avaliação profissional do modelo operacional de empréstimo e de eventuais exigências fiscais/regulatórias de crédito.
- [ ] **P0-15 — Homologação:** testes E2E realistas sem dinheiro, ataque, falhas, replays, rollback, Android instalado, Admin/Membro/Master e AT-01 a AT-50.
- [ ] **P0-16 — Observabilidade:** backup real e restauração com RPO/RTO, monitoração, controles de custo, manual de incidentes e operação.
- [ ] **P0-17 — Documental:** manter 5 divergências históricas abertas: 1.6, 1.8, 4.1, 5.3, 8.2, até aditivo para a frente AI Studio.

## Bloqueios não negociáveis

- Nenhum endpoint pode marcar pago, desembolsado ou liquidado com clique do usuário, webhook isolado ou GET do provedor sem extrato autenticado e commit atômico.
- Nenhuma migração 034–038 pode ser aplicada no Termux local ou na produção por este pacote.
- Não enviar dinheiro real, nem cadastrar token/CPF/chave Pix de produção nos arquivos Git, CI ou Termux compartilhado.
- O Master não acessa saldos financeiros das caixinhas nem mistura contas bancárias de administradores diferentes.
- PR #2 permanece Draft, Issue #3 aberta.
