# Auditoria geral M4800 — FR Caixinha AI Studio

**Data da fotografia:** 04/11/2026. **Repositório:** `fronassor-art/FRcaixinha-22---Gest-o-Financeira-Mobile-Android-iOS-e-Multi-Cloud-OCI-GCP`. **Branch:** `atualizacao-ai-studio-9b46a63187`. **Implementação auditada:** `b48baaae522bd20e9fe712668452769cf3ac6403`.

**Escopo desta auditoria:** revisão estática de arquitetura/repositório, 147 requisitos documentados e resultados de CI em GitHub. **Não representa auditoria regulatória, pentest, revisão individual de cada linha, prova de banco real ou aceite completo AT-01–AT-50.** A matriz de cláusulas foi extraída de `docs/CHECKPOINT_CONTRATO_2026-11-01.md` e anotada conservadoramente com evidências atuais. Os PDFs incorporados à frente AI Studio são documentos históricos identificados como 2.2; **não** autoriza alterar o repositório 2.2 nem misturar os bancos.

## Resultado executivo

- **FR Caixinha:** aplicativo SaaS de gestão financeira automatizada, **não é banco, custodiante ou instituição de pagamento**; dinheiro só é movimentado externamente por provedor autorizado.
- **Código CI:** 6/6 GitHub Actions SUCCESS em [run 41944881200](https://github.com/fronassor-art/FRcaixinha-22---Gest-o-Financeira-Mobile-Android-iOS-e-Multi-Cloud-OCI-GCP/actions/runs/41944881200): frontend, API, PostgreSQL 16 e 18 descartáveis, ZIP fonte, APK debug. Isto não significa operação real homologada ou APK instalado pelo usuário neste commit.
- **GitHub:** PR #2 Draft, sem merge; manter Issue #3 aberta para bloqueios financeiros/comerciais.
- **Termux:** último checkpoint informado: `673e870` (M4000), FastAPI PID 6655, PG5433 respondendo; M4800 **ainda não sincronizado** até prova do usuário.
- **Migrações:** 30 arquivos SQL locais no repo; staging 034/035/036/037 não aplicadas. Nenhuma instrução deste pacote executou migração local.
- **Dinheiro:** Pix IN/OUT real, desembolso, conciliação com banco, baixa em contabilidade e fechamento **inativos e não testados de ponta a ponta**.

## Inventário de código e evidências

Fotografia no commit de implementação: **558 arquivos** (incluindo artefatos), **73 módulos Python backend**, **99 arquivos de teste backend**, **38 componentes React**, **49 arquivos de teste/frontend**, **30 migrações locais** e **4 scripts de staging**. Existência de arquivos não é prova de execução de cada funcionalidade.

## Baixas técnicas verificadas (código + testes automatizados; não homologação financeira)

- [x] Autenticação segregada e contextos Master/Administrador/Membro com testes de sessão e isolamento RLS.
- [x] Catálogo/visualizações de SaaS Master, inventário administrativo, onboarding/aceites em estados de preparação; sem cobrança real.
- [x] Componentes de consulta de membros, cotas e contribuição mensal por competência.
- [x] Consulta administrativa de Livro-Razão, prévia de integridade e paginação por cursor.
- [x] Simulação Price exata em Decimal, período inicial proporcional e ajuste da última parcela em testes.
- [x] Solicitação e aprovação documental de empréstimo no backend, sob restrições (desembolso real permanece 503).
- [x] Motor de imputação parcial juros→mora→multa→principal em testes sintéticos.
- [x] Pix mensal por obrigação com operação econômica e idempotência estáveis; interface de QR oficial condicionada ao provedor.
- [x] Novo adaptador brasileiro Orders `POST /v1/orders` e `GET /v1/orders/{id}`, IDs ORD/PAY e status de espera.
- [x] Isolamento de conta conectada, valor BRL e referência sem CPF/PII no identificador técnico.
- [x] OAuth Connect em pré-autorização PKCE, renovação/rotação por tenant e revogação como contratos de backend.
- [x] HMAC Webhook Orders, escopo de conta, limite de corpo, replay e inbox durável desenhada para OCI staging.
- [x] Money Out bloqueado em produção sem assinatura e autorização comercial específica.
- [x] Esquemas 034–037 separados do PostgreSQL Termux; gatilhos/provas externas permanecem não aplicados.
- [x] Orquestração de Pix Orders com reserva, anti-retry, verificação de extrato e interface para commit atômico, em mock.
- [x] Frontend distingue QR Orders real da prévia ilustrativa, reconhece ORD/PAY e não confirma Pix sem recibo.
- [x] Limpeza dos dados Pix ao alternar caixinha ou perfil e descarte de resposta de sessão anterior.
- [x] Ausência de instalação de OCI, acesso bancário, movimentação financeira e merge de PR neste pacote.

## Pendências P0 — impedem conclusão do produto financeiro

- [ ] **P0-01** Autorizar e provisionar OCI de homologação (TLS, DNS, IAM, Vault, roles mínimas, observabilidade e custos aprovados); sem produção.
- [ ] **P0-02** Auditar divergência de roles/names em SQL staging 034 e validar cadeia de migrações 034–037 em banco descartável equivalente; aplicar somente depois de autorização/backup.
- [ ] **P0-03** Vincular OAuth Connect real de cada administrador ao cofre, com PKCE, offline_access, refresh, revogação, auditoria e reconexão.
- [ ] **P0-04** Adaptar runtime de cobrança para `OrdersCollectionAutomation` e telas Pix, com conexão de cada tenant e recuperação após timeout.
- [ ] **P0-05** Executar Webhooks Orders assinados em servidor HTTPS confiável; armazenar eventos e consultar GET Orders por conta vinculada.
- [ ] **P0-06** Criar serviço independente de extrato/liquidação bancária com autenticação do relatório, saldo, comprovante e taxas por transação.
- [ ] **P0-07** Implementar commits financeiros transacionais (SERIALIZABLE/locks), RLS tenant e ledger de partidas dobradas, centavos e chave única por pagamento.
- [ ] **P0-08** Implementar baixa definitiva de cota mensal/competência após conciliação, status parcial/vencimento, reversão e comprovante.
- [ ] **P0-09** Implementar pagamento de parcela de crédito, mora/multa única, regras Price, juros/receita e abatimento do principal somente após prova bancária.
- [ ] **P0-10** Corrigir geração antecipada de `loan_installments` na rota legada de aprovação, com cronograma definitivo a partir do Pix OUT confirmado.
- [ ] **P0-11** Implementar cadastro/alteração/revogação e verificação do destinatário Pix do membro, minimização de CPF e Vault seguro.
- [ ] **P0-12** Implementar reserva atômica de caixa para empréstimos, concorrência, consentimentos, limites e idempotência de um desembolso por crédito.
- [ ] **P0-13** Solicitar aprovação comercial Money Out para contas conectadas e finalidade específica de concessão/repasse de empréstimos, com assinatura de requests em produção.
- [ ] **P0-14** Implementar consulta de status de saída no PSP, liquidação final e reversão/falha sem reenvio duplicado.
- [ ] **P0-15** Concluir telas do Administrador (aprovação/rejeição/reserva/destino/ordem Pix), Membro (parcelas e comprovantes) e Master (exclusivamente governança SaaS).
- [ ] **P0-16** Efetivar fechamentos anuais e distribuição de resultados com conciliação, capital-dias, recibos e autorização legítima; hoje bloqueado.
- [ ] **P0-17** Executar backup cifrado e restauração real de staging e indicadores RPO/RTO; atualizar diagnóstico após evidência operacional.
- [ ] **P0-18** Avaliação jurídica/tributária/regulatória do modelo de caixinha e crédito internos, LGPD, condições de uso e enquadramento das contas.
- [ ] **P0-19** Testes integrados de 3 perfis, 2+ tenants, webhooks duplicados/invertidos, perdas de rede, reconciliação, reversão, estornos e invasão de contexto.
- [ ] **P0-20** Executar e registrar todos os cenários AT-01–AT-50; homologar APK instalado, pagamentos fictícios, contas de teste e aceite dos administradores.

## Pendências P1/P2 — produto e expansão

- [ ] **P1-01** Revisar plano Essencial/Intermediário/Ampliado, limite do Ampliado ainda não contratado, checkout SaaS só após decisão.
- [ ] **P1-02** Operacionalizar convites e confirmação de e-mail/membro, cadastro único e proteção contra duplicação de identidade.
- [ ] **P1-03** Concluir lifecycle, expulsão, inadimplência, transições e trilha de consentimento por tenant e ciclo.
- [ ] **P1-04** Revisar rigorosamente políticas parametrizáveis (até 12 parcelas clientes vs seis na caixinha do proprietário) e taxas/limites distintos.
- [ ] **P1-05** Testar integralmente ciclo anual 2027, renovação, encerramento, restituições e devoluções.
- [ ] **P1-06** Testar suporte/monitoramento, alertas, logs protegidos, LGPD, hardening TLS e custos.
- [ ] **P1-07** Publicação/assinatura Android/iOS, atualização segura, observabilidade, documentação operacional e recuperação de desastre.
- [ ] **P2-01** Rifa/bolão continuam demonstrativos: não habilitar transação real sem novo escopo e aprovação legal/comercial.

## Divergências documentais não resolvidas por código

1. **Cl. 1.6:** demonstradores de rifa/bolão vs restrições comerciais do contrato; sem dinheiro.
2. **Cl. 1.8:** contrato histórico cita Flutter; o AI Studio atual usa React/Capacitor por decisão do proprietário. Formalizar versão AI Studio sem misturar projetos.
3. **Cl. 4.1:** regras de política por tenant vs seeds/parametrização atual; exigir revisão do backend.
4. **Cl. 5.3:** gatilhos de suporte previstos vs instrumentação operacional real.
5. **Cl. 8.2:** até 12 parcelas em outros tenants e máximo de 6 na caixinha do proprietário; limite no motor ainda não é plenamente parametrizado.

## Matriz documental — 147 cláusulas

**Leitura:** `Base 01/11` é a conclusão do checkpoint histórico; `Leitura M4800` atualiza somente quando existe novo arquivo pertinente e CI para o código. `BLOQUEADO (integração)` quer dizer **código parcial novo, funcionalidade real ainda bloqueada**. `PARCIAL (código)` não significa regra cumprida integralmente. **Nenhuma cláusula financeira foi declarada operacional ou homologada apenas com testes simulados.**

| Cláusula | Requisito | Base 01/11 | Leitura M4800 | Evidência nova / restrição |
|---|---|---|---|---|
| 1.1 | Visão — DEFINIDO. | PARCIAL | PARCIAL | Sem prova adicional individual neste macropacote |
| 1.2 | Público e modelo. | PARCIAL | PARCIAL | Sem prova adicional individual neste macropacote |
| 1.3 | Princípios não negociáveis — DEFINIDO. | PARCIAL | PARCIAL | Sem prova adicional individual neste macropacote |
| 1.4 | Diferença essencial entre software e operação. | PARCIAL | PARCIAL | backend/app/mp_money_out_policy.py — FR Caixinha como software de gestão, sem custódia. |
| 1.5 | Primeira entrega — DEFINIDO. | BLOQUEADO | BLOQUEADO | Sem prova adicional individual neste macropacote |
| 1.6 | Escopo por prontidão, sem circularidade — APROVADO COMO REQUISITO DOCUMENTAL. | DIVERGENTE | DIVERGENTE | Sem prova adicional individual neste macropacote |
| 1.7 | Dinheiro real e fronteira de responsabilidade — DEFINIDO. | BLOQUEADO | BLOQUEADO | Sem prova adicional individual neste macropacote |
| 1.8 | Ambiente técnico oficialmente escolhido — DEFINIDO. | DIVERGENTE | DIVERGENTE | Sem prova adicional individual neste macropacote |
| 1.9 | Desenvolvimento independente e orçamento inicial — DEFINIDO. | NÃO VERIFICADO | NÃO VERIFICADO | Sem prova adicional individual neste macropacote |
| 1.10 | Titularidade e estratégia comercial. | NÃO VERIFICADO | NÃO VERIFICADO | Sem prova adicional individual neste macropacote |
| 1.11 | Documentos empresariais por estágio. | NÃO VERIFICADO | NÃO VERIFICADO | Sem prova adicional individual neste macropacote |
| 1.12 | Plano econômico enxuto. | NÃO VERIFICADO | NÃO VERIFICADO | Sem prova adicional individual neste macropacote |
| 2.1 | Perfis funcionais — DEFINIDO. | PARCIAL | PARCIAL | Sem prova adicional individual neste macropacote |
| 2.2 | Direitos do administrador contratante — DEFINIDO. | PARCIAL | PARCIAL | Sem prova adicional individual neste macropacote |
| 2.3 | Papéis simultâneos e troca de contexto. | PARCIAL | PARCIAL | backend/app/dependencies.py — Master/Admin/Membro e isolamento de escopo. |
| 2.4 | Administrador também é membro — DEFINIDO. | PARCIAL | PARCIAL | Sem prova adicional individual neste macropacote |
| 2.5 | Autorização coletiva anual para crédito próprio — DEFINIDO COMO MODELO CONTRATUAL. | BLOQUEADO | BLOQUEADO | Sem prova adicional individual neste macropacote |
| 2.6 | Ausência de outros membros ou falta de unanimidade. | BLOQUEADO | BLOQUEADO | Sem prova adicional individual neste macropacote |
| 2.7 | Transparência aos membros. | PARCIAL | PARCIAL | Sem prova adicional individual neste macropacote |
| 2.8 | Acesso de Master. | PARCIAL | PARCIAL | Sem prova adicional individual neste macropacote |
| 2.9 | Matriz básica de permissões. | PARCIAL | PARCIAL | Sem prova adicional individual neste macropacote |
| 3.1 | Início da contratação e tenant preliminar — APROVADO COMO REQUISITO DOCUMENTAL. | BLOQUEADO | BLOQUEADO | Sem prova adicional individual neste macropacote |
| 3.1-A | Cadastro e identificação do Administrador Contratante — DEFINIDO E APROVADO em 16/10/2026. | BLOQUEADO | BLOQUEADO | Sem prova adicional individual neste macropacote |
| 3.1-A.1 | Verificação e segurança. | BLOQUEADO | BLOQUEADO | Sem prova adicional individual neste macropacote |
| 3.1-A.2 | Aceite, identidade e privacidade. | BLOQUEADO | BLOQUEADO | Sem prova adicional individual neste macropacote |
| 3.2 | Tabela comercial — DEFINIDA E APROVADA. | PARCIAL | PARCIAL | Sem prova adicional individual neste macropacote |
| 3.2-A | Preço comercial dinâmico e anual automático — DEFINIDO. | PARCIAL | PARCIAL | Sem prova adicional individual neste macropacote |
| 3.2-B | Cobrança por resultado das caixinhas — EM ESTUDO, não aprovada. | NÃO VERIFICADO | NÃO VERIFICADO | Sem prova adicional individual neste macropacote |
| 3.3 | Enquadramento sem lacunas. | PARCIAL | PARCIAL | Sem prova adicional individual neste macropacote |
| 3.4 | Contagem de capacidade — APROVADO COMO REQUISITO DOCUMENTAL. | PARCIAL | PARCIAL | Sem prova adicional individual neste macropacote |
| 3.5 | Aceite de licença. | BLOQUEADO | BLOQUEADO | Sem prova adicional individual neste macropacote |
| 3.6 | Pagamento de licença. | BLOQUEADO | BLOQUEADO | Sem prova adicional individual neste macropacote |
| 3.7 | Vigência mensal/anual — APROVADO COMO REQUISITO DOCUMENTAL. | BLOQUEADO | BLOQUEADO | Sem prova adicional individual neste macropacote |
| 3.8 | Tolerância = ZERO DIAS — DEFINIDO. | BLOQUEADO | BLOQUEADO | Sem prova adicional individual neste macropacote |
| 3.9 | Reativação e cobranças revertidas. | BLOQUEADO | BLOQUEADO | Sem prova adicional individual neste macropacote |
| 3.10 | Alteração, cancelamento e reembolso — APROVADO COMO REQUISITO DOCUMENTAL. | PARCIAL | PARCIAL | Sem prova adicional individual neste macropacote |
| 3.11 | Separação de receitas. | BLOQUEADO | BLOQUEADO | Sem prova adicional individual neste macropacote |
| 4.1 | Política financeira por tenant — DEFINIDO. | DIVERGENTE | DIVERGENTE | Sem prova adicional individual neste macropacote |
| 4.2 | Configuração inaugural da caixinha do proprietário — DEFINIDO. | PARCIAL | PARCIAL | Sem prova adicional individual neste macropacote |
| 4.3 | Percentual administrativo — DEFINIDO. | PARCIAL | PARCIAL | Sem prova adicional individual neste macropacote |
| 4.4 | Vigência das políticas e dos percentuais — DEFINIDO. | BLOQUEADO | BLOQUEADO | Sem prova adicional individual neste macropacote |
| 4.5 | CALENDÁRIO FINANCEIRO CENTRAL — DEFINIDO E NÃO EDITÁVEL PELO TENANT. | PARCIAL | PARCIAL | Sem prova adicional individual neste macropacote |
| 4.6 | Fases do fechamento sem mudar datas. | BLOQUEADO | BLOQUEADO | Sem prova adicional individual neste macropacote |
| 4.7 | Entrada após 01/01 e lançamento futuro. | BLOQUEADO | BLOQUEADO | Sem prova adicional individual neste macropacote |
| 4.8 | Separação do ciclo e da licença. | PARCIAL | PARCIAL | Sem prova adicional individual neste macropacote |
| 5.1 | Atendimento normal. | PARCIAL | PARCIAL | Sem prova adicional individual neste macropacote |
| 5.2 | Acesso excepcional consentido. | BLOQUEADO | BLOQUEADO | Sem prova adicional individual neste macropacote |
| 5.3 | Prazo e gatilhos de suporte — APROVADO COMO REQUISITO DOCUMENTAL. | DIVERGENTE | DIVERGENTE | Sem prova adicional individual neste macropacote |
| 5.4 | Vedações invariáveis. | PARCIAL | PARCIAL | Sem prova adicional individual neste macropacote |
| 5.5 | Operação da manutenção. | BLOQUEADO | BLOQUEADO | Sem prova adicional individual neste macropacote |
| 6.1 | Adesão. | BLOQUEADO | BLOQUEADO | Sem prova adicional individual neste macropacote |
| 6.1-A | Cadastro e identificação do Membro — DEFINIDO E APROVADO em 16/10/2026. | BLOQUEADO | BLOQUEADO | Sem prova adicional individual neste macropacote |
| 6.1-A.1 | Aceite e liberação de acesso. | BLOQUEADO | BLOQUEADO | Sem prova adicional individual neste macropacote |
| 6.1-A.2 | Identidade única, cotas, privacidade e isolamento. | PARCIAL | PARCIAL | Sem prova adicional individual neste macropacote |
| 6.2 | Capital e cotas. | PARCIAL | PARCIAL | backend/app/pix_automation_contract.py — Capital somente após confirmação externa. |
| 6.3 | Contribuições. | PARCIAL | PARCIAL | backend/app/mp_orders_api.py — Orders Pix por obrigação/competência; baixa real pendente. |
| 6.4 | Estados. | PARCIAL | PARCIAL | backend/app/mp_orders_workflow.py — Estados e reversões devem preservar histórico. |
| 6.5 | Regra específica da caixinha do proprietário — DEFINIDO, sujeita à validação jurídica antes da execução real. | BLOQUEADO | BLOQUEADO | Sem prova adicional individual neste macropacote |
| 6.6 | Proibição de confisco e exclusão indevida. | BLOQUEADO | BLOQUEADO | Sem prova adicional individual neste macropacote |
| 7.1 | Segregação. | PARCIAL | PARCIAL | backend/app/mp_oauth_rotation.py — Conta conectada por tenant. |
| 7.2 | Ledger autoritativo. | PARCIAL | PARCIAL | backend/app/mp_orders_workflow.py — Porta de ledger, não commit real. |
| 7.3 | Diferenciar saldos e evitar dupla dedução. | BLOQUEADO | BLOQUEADO (integração) | backend/app/pix_automation_contract.py — Separação dívida, capital, receita e saldo lógico. |
| 7.4 | Concorrência. | BLOQUEADO | BLOQUEADO (integração) | backend/app/mp_orders_workflow.py — Idempotência modelada; corrida DB real pendente. |
| 7.5 | Controle de integridade. | PARCIAL | PARCIAL | backend/app/financial_three_source_preflight.py — Conciliação sintética 3 fontes não é saldo bancário. |
| 7.6 | Fronteira regulatória entre livro e custódia — CONSOLIDADO. | PARCIAL | PARCIAL | backend/app/mp_money_out_policy.py — Fronteira software vs serviço financeiro. |
| 8.1 | Exclusividade interna. | PARCIAL | PARCIAL | Sem prova adicional individual neste macropacote |
| 8.2 | Parametrização financeira na primeira entrega — APROVADO COMO REQUISITO DOCUMENTAL. | DIVERGENTE | DIVERGENTE | backend/app/routers/loans.py — Limite 6 local x até 12 por tenant: divergência. |
| 8.3 | Elegibilidade e limites verificáveis. | PARCIAL | PARCIAL | backend/app/pix_automation_contract.py — Pré-condições de crédito sem saldo real. |
| 8.4 | Simulação obrigatória e datas. | PARCIAL | PARCIAL | backend/app/routers/loans.py — Price proporcional; data real no workflow sem DB integrado. |
| 8.5 | Price com primeiro período irregular — DEFINIDO. | PARCIAL | PARCIAL | backend/app/routers/loans.py — Decimal e primeiro período irregular testados. |
| 8.6 | Atrasos, imputação parcial e quitação — DEFINIDO. | BLOQUEADO | BLOQUEADO (integração) | backend/app/pix_automation_contract.py — Juros/mora/multa/principal em cálculo; baixa real bloqueada. |
| 8.7 | Aprovação. | BLOQUEADO | BLOQUEADO (integração) | backend/app/pix_automation_workflows.py — Aprovação/reserva/saída somente portas, runtime pendente. |
| 8.8 | Empréstimo do administrador-membro. | BLOQUEADO | BLOQUEADO (integração) | backend/app/routers/loans.py — Autoempréstimo permanece bloqueado sem unanimidade. |
| 8.9 | Proibição de fechamento indevido. | BLOQUEADO | BLOQUEADO (integração) | backend/app/pix_automation_workflows.py — Fechamento real bloqueado. |
| 9.1 | Contas e finalidade. | BLOQUEADO | BLOQUEADO (integração) | backend/app/mp_oauth_rotation.py — OAuth por conta de cada administrador. |
| 9.2 | Integração escolhida. | BLOQUEADO | BLOQUEADO (integração) | backend/app/mp_orders_api.py — Orders API substitui Payments para novas cobranças. |
| 9.3 | Recebimento. | BLOQUEADO | BLOQUEADO (integração) | backend/app/mp_orders_api.py — QR/Copia e Cola; cobrança real ainda HTTP 503. |
| 9.4 | Saída, autorização e idempotência. | BLOQUEADO | BLOQUEADO (integração) | backend/app/mp_money_out_policy.py — Money Out exige assinatura e habilitação. |
| 9.5 | Reversão ou falha. | BLOQUEADO | BLOQUEADO (integração) | backend/app/mp_orders_workflow.py — Timeout/reversões ainda sem worker transacional. |
| 9.6 | Fechamento. | BLOQUEADO | BLOQUEADO (integração) | backend/app/routers/closings.py — Fechamento depende de autorização e provedor. |
| 9.7 | Bolões. | BLOQUEADO | BLOQUEADO (integração) | src/components/RaffleModuleView.tsx — Bolões/rifas não habilitados para dinheiro real. |
| 9.8 | Verificações mínimas. | BLOQUEADO | BLOQUEADO (integração) | backend/app/mp_orders_webhook.py — Webhook HMAC e GET; falta extrato autenticado e posting. |
| 9.8-A | Interfaces estáveis de integração para futura migração — CONSOLIDADO. | PARCIAL | PARCIAL | backend/app/mp_orders_workflow.py — Portas de provedor e journal separadas. |
| 9.9 | Ambientes e liberação por finalidade — APROVADO COMO REQUISITO DOCUMENTAL. | BLOQUEADO | BLOQUEADO (integração) | backend/app/mp_money_out_policy.py — Teste/staging vs produção; sem ativação automática. |
| 10.1 | Formação da base e corte de realização. | BLOQUEADO | BLOQUEADO | Sem prova adicional individual neste macropacote |
| 10.2 | Percentuais por caixinha — DEFINIDO. | BLOQUEADO | BLOQUEADO | Sem prova adicional individual neste macropacote |
| 10.3 | Rateio Capital-Dias V2 — motor comum, com corte diário aprovado. | BLOQUEADO | BLOQUEADO | Sem prova adicional individual neste macropacote |
| 10.4 | Rateio, precisão e destino definitivo dos centavos — DEFINIDO. | PARCIAL | PARCIAL | Sem prova adicional individual neste macropacote |
| 10.5 | Distinguir administrador como beneficiário duplo. | PARCIAL | PARCIAL | Sem prova adicional individual neste macropacote |
| 10.6 | Fechamento anual e obrigações remanescentes. | BLOQUEADO | BLOQUEADO | Sem prova adicional individual neste macropacote |
| 10.7 | Documentos e conferência. | BLOQUEADO | BLOQUEADO | Sem prova adicional individual neste macropacote |
| 10.8 | Imutabilidade e versões de resultado — DEFINIDO. | BLOQUEADO | BLOQUEADO | Sem prova adicional individual neste macropacote |
| 11.0-A | Telas de demonstrador regulatório e evolução — CONSOLIDADO. | PARCIAL | PARCIAL | Sem prova adicional individual neste macropacote |
| 11.1 | Design simples. | PARCIAL | PARCIAL | Sem prova adicional individual neste macropacote |
| 11.2 | Estados visuais. | PARCIAL | PARCIAL | Sem prova adicional individual neste macropacote |
| 11.3 | Textos de transparência. | PARCIAL | PARCIAL | Sem prova adicional individual neste macropacote |
| 11.4 | Manual oficial para administradores — ENTREGÁVEL DO MVP. | PARCIAL | PARCIAL | Sem prova adicional individual neste macropacote |
| 11.5 | Apoio comercial e demonstração — ENTREGÁVEL NÃO TRANSACIONAL. | PARCIAL | PARCIAL | Sem prova adicional individual neste macropacote |
| 12.1 | Padrões de todas as tabelas. | PARCIAL | PARCIAL | Sem prova adicional individual neste macropacote |
| 12.2 | Entidades fundamentais (tabelas e colunas mínimas). | PARCIAL | PARCIAL | backend/staging_migrations/037_orders_payment_link_staging_only.sql — Schema ORD/PAY staging não aplicado. |
| 12.2-B | Vínculos semânticos obrigatórios identificados na auditoria. | PARCIAL | PARCIAL | Sem prova adicional individual neste macropacote |
| 12.2-A | Campos de preparação para novos provedores, sem código bancário — CONSOLIDADO. | NÃO VERIFICADO | PARCIAL (código) | backend/app/mp_oauth_rotation.py — Referência de segredo/token por tenant, CAS port. |
| 12.3 | Regras de chaves e índices. | PARCIAL | PARCIAL | backend/staging_migrations/036_signed_orders_inbox_staging_only.sql — Índices e RLS staging não aplicados. |
| 12.4 | Relações de negócio. | PARCIAL | PARCIAL | Sem prova adicional individual neste macropacote |
| 12.5 | Entidades futuras de bolões — não migrar na primeira entrega. | NÃO VERIFICADO | NÃO VERIFICADO | Sem prova adicional individual neste macropacote |
| 13.1 | Defesa em camadas. | PARCIAL | PARCIAL | backend/app/mp_orders_webhook.py — Assinatura, conta vinculada, limite 16KiB, TLS. |
| 13.2 | LGPD e minimização. | PARCIAL | PARCIAL | backend/app/mp_oauth_rotation.py — Sem expor tokens/segredos, proteção de contexto. |
| 13.3 | Controle fiscal e conformidade da plataforma. | BLOQUEADO | BLOQUEADO | Sem prova adicional individual neste macropacote |
| 13.4 | Política mínima de backup e recuperação — APROVADO COMO REQUISITO DOCUMENTAL. | PARCIAL | PARCIAL | backend/app/oci_recovery_policy.py — Recuperação OCI só preflight, nenhum backup real. |
| 13.5 | Monitoramento enxuto. | BLOQUEADO | BLOQUEADO | Sem prova adicional individual neste macropacote |
| 13.6 | Homologação. | PARCIAL | PARCIAL | backend/app/mp_orders_webhook.py — CI/mocks não substituem teste provedor. |
| 13.7 | Projeto preparado para evolução institucional — CONSOLIDADO. | NÃO VERIFICADO | NÃO VERIFICADO | Sem prova adicional individual neste macropacote |
| 13.8 | Possível instituição financeira ou de pagamento no futuro — CONDICIONADO. | NÃO VERIFICADO | NÃO VERIFICADO | Sem prova adicional individual neste macropacote |
| 13.9 | Linha de licenciamento/homologação — CONSOLIDADO. | NÃO VERIFICADO | NÃO VERIFICADO | Sem prova adicional individual neste macropacote |
| 13.10 | Formalização empresarial digital — ROTEIRO PARA O PROPRIETÁRIO. | NÃO VERIFICADO | NÃO VERIFICADO | Sem prova adicional individual neste macropacote |
| 13.11 | Propriedade intelectual e documentos de titularidade. | NÃO VERIFICADO | NÃO VERIFICADO | Sem prova adicional individual neste macropacote |
| 13.12 | Assistência gratuita e autonomia nos requerimentos. | NÃO VERIFICADO | NÃO VERIFICADO | Sem prova adicional individual neste macropacote |
| 13.13 | Matriz documental de conformidade por função — PARA CONSTRUÇÃO E AUDITORIA. | NÃO VERIFICADO | NÃO VERIFICADO | Sem prova adicional individual neste macropacote |
| 13.14 | Regra de licenciamento sem impasse circular. | NÃO VERIFICADO | NÃO VERIFICADO | Sem prova adicional individual neste macropacote |
| 14.1 | Modelo escolhido — CONDICIONADO. | BLOQUEADO | BLOQUEADO | Sem prova adicional individual neste macropacote |
| 14.2 | Preço final e margem — DEFINIDO COMO MODELO ECONÔMICO. | PARCIAL | PARCIAL | Sem prova adicional individual neste macropacote |
| 14.3 | Destinação e risco. | BLOQUEADO | BLOQUEADO | Sem prova adicional individual neste macropacote |
| 14.4 | Fluxo de demonstrador completo e futura operação condicionada. | PARCIAL | PARCIAL | Sem prova adicional individual neste macropacote |
| 14.5 | Barreiras de operação, NÃO de desenvolvimento demonstrável. | PARCIAL | PARCIAL | Sem prova adicional individual neste macropacote |
| 14.6 | Demonstração e prova regulatória. | PARCIAL | PARCIAL | Sem prova adicional individual neste macropacote |
| 15.1 | Ordem de trabalho. | NÃO VERIFICADO | NÃO VERIFICADO | Sem prova adicional individual neste macropacote |
| 15.2 | Estimativa inicial, sem promessa de entrega. | NÃO VERIFICADO | NÃO VERIFICADO | Sem prova adicional individual neste macropacote |
| 15.2-A | Condição de prontidão do escopo. | NÃO VERIFICADO | NÃO VERIFICADO | Sem prova adicional individual neste macropacote |
| 15.2-B | Pacotes independentes, sem circularidade. | NÃO VERIFICADO | NÃO VERIFICADO | Sem prova adicional individual neste macropacote |
| 15.2-C | Prazo e conclusão honesta. | NÃO VERIFICADO | NÃO VERIFICADO | Sem prova adicional individual neste macropacote |
| 15.3 | Gestão do cronograma por etapa. | NÃO VERIFICADO | NÃO VERIFICADO | Sem prova adicional individual neste macropacote |
| 15.3-A | Evidências técnicas obrigatórias para apresentar a terceiros. | NÃO VERIFICADO | NÃO VERIFICADO | Sem prova adicional individual neste macropacote |
| 15.4 | Gates independentes. | NÃO VERIFICADO | NÃO VERIFICADO | Sem prova adicional individual neste macropacote |
| 15.5 | Execução técnica. | NÃO VERIFICADO | NÃO VERIFICADO | Sem prova adicional individual neste macropacote |
| 15.6 | Plano de negócios e chegada ao mercado — FORA DOS 60 DIAS DE CODIFICAÇÃO. | NÃO VERIFICADO | NÃO VERIFICADO | Sem prova adicional individual neste macropacote |
| 15.7 | Autonomia de produção de documentos. | NÃO VERIFICADO | NÃO VERIFICADO | Sem prova adicional individual neste macropacote |
| 16.1 | Itens definidos que NÃO devem voltar como perguntas. | NÃO VERIFICADO | NÃO VERIFICADO | Sem prova adicional individual neste macropacote |
| 16.2 | Quatro convenções financeiras complementares — DEFINIDAS E APROVADAS PELO PROPRIETÁRIO em 16/10/2026. | PARCIAL | PARCIAL | backend/app/pix_automation_contract.py — Imputação, centavos, Price; sem aceite financeiro ponta a ponta. |
| 16.2-A | Limites externos e recursos não liberados pelo aceite documental. | NÃO VERIFICADO | NÃO VERIFICADO | Sem prova adicional individual neste macropacote |
| 16.3 | Condições de ativação real, não bloqueios de codificação ou demonstração. | NÃO VERIFICADO | PARCIAL (código) | backend/app/mp_money_out_policy.py — Gates sem dinheiro real, homologação pendente. |
| 16.3-A | Limite de decisões não documentadas pelo tenant. | NÃO VERIFICADO | PARCIAL (código) | backend/app/pix_automation_contract.py — Sem criar parâmetros financeiros não aceitos. |
| 16.4 | Cenários de auditoria documental e posterior teste — AT-01 a AT-23, complementados até AT-50. | BLOQUEADO | BLOQUEADO (integração) | backend/tests/test_m4100_orders_pix_ci.py — AT-01 a AT-50 ainda não foram executados integralmente. |
| 16.4-A | Testes adicionais da auditoria de evolução e licenciamento (AT-24 a AT-31). | NÃO VERIFICADO | NÃO VERIFICADO | Sem prova adicional individual neste macropacote |
| 16.4-C | Testes de aceite acrescidos nesta versão (AT-32 a AT-44), após futura programação. | NÃO VERIFICADO | NÃO VERIFICADO | Sem prova adicional individual neste macropacote |
| 16.4-E | Testes de cadastro e vínculos incorporados após aprovação dos itens 3.1-A e 6.1-A (AT-45 a AT-50). | NÃO VERIFICADO | NÃO VERIFICADO | Sem prova adicional individual neste macropacote |
| 16.4-D | Auditoria do código efetivamente existente. | PARCIAL | PARCIAL | backend/tests/test_m4600_orders_workflow_ci.py — Auditoria estática e regressão synthetic. |
| 16.5 | Estado deste documento — APROVADO PARA DESENVOLVIMENTO, NÃO PARA EXECUÇÃO AUTOMÁTICA. | NÃO VERIFICADO | NÃO VERIFICADO | Sem prova adicional individual neste macropacote |

## Totais da revisão conservadora

**Linha de base:** 58 PARCIAL; 50 BLOQUEADO; 5 DIVERGENTE; 34 NÃO VERIFICADO; total 147. **Cláusulas com evidência complementar deste pacote:** 41. As demais exigem revisão individual adicional ou estão fora dos macropacotes Pix/identidade. Esta revisão é um checklist de rastreabilidade e **não** substitui homologação 147/147.

**Distribuição textual M4800:** PARCIAL: 58; BLOQUEADO: 34; DIVERGENTE: 5; NÃO VERIFICADO: 31; BLOQUEADO (integração): 16; PARCIAL (código): 3.

## Decisões de governança

- Preservar PR #2 como Draft e Issue #3 aberta; não promover para produção.
- Jamais usar contas da plataforma Master para Pix/cotas/empréstimos de tenants.
- Contratos 6.3, 8.4–8.8 e 9.1–9.9 são regras de implementação; não inventar prazo, juros, split ou saldos.
- Confirmar junto a Mercado Pago a capacidade técnica, comercial e o enquadramento legal de Pix OUT. Nenhum webhook isolado dá baixa contábil.
- No Termux, sincronizar somente Git; sem autoaplicar staging, sem dinheiro real; validar commit e health M4800 antes da próxima etapa.
