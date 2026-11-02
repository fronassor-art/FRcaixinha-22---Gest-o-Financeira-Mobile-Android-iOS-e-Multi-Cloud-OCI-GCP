# CHECKPOINT EXECUTIVO — AI STUDIO: ESTADO ATUAL E TUDO O QUE FALTA

**Data de referência:** 01/11/2026 (America/Belem)  
**Escopo exclusivo:** exportação AI Studio em `fronassor-art/FRcaixinha-22---Gest-o-Financeira-Mobile-Android-iOS-e-Multi-Cloud-OCI-GCP`.  
**PR:** [#2](https://github.com/fronassor-art/FRcaixinha-22---Gest-o-Financeira-Mobile-Android-iOS-e-Multi-Cloud-OCI-GCP/pull/2), aberta, **DRAFT**, sem merge na `main`.  
**Checkpoint auditado:** `dfb5978c998cc79cafce070c7d1029e18fc74d8d`, sincronizado em Termux pelo operador.  
**Última CI verificada:** [run 41378843831](https://github.com/fronassor-art/FRcaixinha-22---Gest-o-Financeira-Mobile-Android-iOS-e-Multi-Cloud-OCI-GCP/actions/runs/41378843831), **5/5 PASS**: frontend, FastAPI, PG16 descartável, PG18 transação única descartável, APK debug. APK gerado no CI; **não instalado, não homologado em dispositivo e não assinado para release**.  
**Estado local informado:** PostgreSQL 18.6, `127.0.0.1:5433/frcaixinha_aistudio_dev`, `$PREFIX/var/lib/frcaixinha_aistudio_pg18`, papéis `frc_ai_owner` (administrativo), `frc_ai_app` e `frc_ai_auth` (sem SUPERUSER/BYPASSRLS), **0 tabelas e 0 migrações aplicadas**. Esse estado vem da saída do Termux enviada pelo operador; o GitHub não inspeciona o banco do celular.

## 1. Limites da prova e fontes

Este checkpoint foi elaborado por inspeção dos arquivos no **commit acima**, do relatório das 147 cláusulas e do resultado real da CI. **Não foi executada nova leitura integral comparativa dos dois PDFs neste turno**; o [checkpoint contratual preservado](CHECKPOINT_CONTRATO_2026-11-01.md) relata 38 páginas do Contrato Técnico Mestre (SHA-256 `7b28d5d5cf773fb5c35194bce64ebfdfec4d67422bafac4595a6662b4f45f468`) e 57 do Caderno Mestre (SHA-256 `94d2a15c54d3f5982c09fe78762ae0f1c76e03fa644cb05a6404f5c7b2feb0f6`), disponíveis em `public/assets/aistudio`.

O [anexo integral das 147 cláusulas](MATRIZ_147_PENDENCIAS_AI_STUDIO_2026-11-01.md) conserva suas pendências documentais e acrescenta evidências recentes por item, **sem alterar automaticamente os rótulos**. A fotografia anterior soma: **58 PARCIAL, 50 BLOQUEADO, 34 NÃO VERIFICADO, 5 DIVERGENTE, 0 CONCLUÍDO E TESTADO**, total 147. **Esses números NÃO são índices atuais de entrega.** Testes localizados, compilar APK, ter tabela SQL ou possuir adaptador sem integração não provam cláusula integral. O conjunto AT-01 a AT-50 ainda não tem execução abrangente e rastreável.

### Legenda operacional

- **CI VERIFICADO:** testes automatizados executados no commit, em cenário sintético, não produção.
- **PREPARADO:** código, interface ou SQL escritos, mas falta caminho real integrado ou validação essencial.
- **BLOQUEADO PARA USO REAL:** não habilitar antes de autorização/infraestrutura/documentação/segurança.
- **SEM PROVA INTEGRAL:** não é possível declarar cumprimento do módulo todo.
- **DIVERGÊNCIA HISTÓRICA:** conflito levantado no contrato, a ser resolvido documentalmente sem descartar escolha expressa do proprietário.

## 2. Visão operacional por domínio

| Domínio | O que existe no commit `dfb5978` | O que ainda falta / limite atual | Estado |
|---|---|---|---|
| GitHub, CI e versão | PR #2 draft; CI 5/5; APK debug disponível como artefato | Merge somente após aprovação; release assinado; teste físico, telemetria | CI VERIFICADO / release PENDENTE |
| Banco AI Studio | Migrações **001–019** e ensaios PG16/PG18 em CI | **Não aplicadas no Termux**; preflight local sob autorização futura, plano de rollback e backup | PREPARADO; operação local BLOQUEADA |
| PostgreSQL/RLS | Papéis app/auth segregados, RLS em domínios selecionados, testes com 2–3 tenants | Auditoria CRUD completa, concorrência, hardening de SECURITY DEFINER, conflitos de permissão | PARCIAL |
| Login e senha | Sessões persistentes/hashes, login de homologação, logout, revogação global | Autenticação produtiva, políticas anti-abuso distribuídas, sessão TLS/cookies, prova externa | BLOQUEADO REAL |
| Acesso único multi-caixinha | `/auth/contexts`, `switch-context`, nomes na migração 019, painel de sessões, testes | Homologação em Android real, ciclo completo de onboarding, autorizações por todos os recursos | CI VERIFICADO / ponta a ponta PENDENTE |
| Convites para conta existente | Token/aceite CI com papel/vínculo/contrato validado | Rota pública permanece **503**, entrega real, titularidade, antifraude e rate-limit | PREPARADO, BLOQUEADO REAL |
| Novo cadastro por convite | `invite_registration_ci.py` com CPF, senha hash e vínculo/auditoria transacionais | Serviços privilegiados mínimos e interface pública verificada, tenant preliminar e email de confirmação | CI VERIFICADO / REAL BLOQUEADO |
| Recuperação de senha | Tokens hash e revogação CI; caminho frontend alinhado | `POST /auth/forgot-password` **503**, envio e confirmação por e-mail, proteção anti-enumeração e abuso | BLOQUEADO REAL |
| Contratos/aceites | Migrações 015–016: versões/hash e aceites auditáveis, RLS, imutabilidade | Documento efetivo aprovado + prova de consentimento real vinculada ao fluxo e retenção LGPD | PREPARADO CI |
| Provisionamento | Scripts CI de Master/tenant; conta por tenant do banco | Master humano não provisionado; tenant preliminar → contratação → licença → ativação; evitar duplicar identidades existentes | BLOQUEADO LOCAL/REAL |
| Catálogo e preço Master | Migração 011, versões de preço, anual 10× mensal, endpoints Master, testes | Publicação de oferta/aceite efetivo, governança de alteração, compatibilidade para renovação | PARCIAL |
| Capacidade dos planos | `saas_capacity_snapshot_ci` informa membros/cotas; catálogo no SQL | Aplicar limite em transação de aquisição de cotas e adesão, concorrência e upgrades/downgrades | PREPARADO CI |
| Pagamentos SaaS | Adapter Mercado Pago, assinatura HMAC e GET autoritativo, tabelas 017, estados CI | Conta MP **da plataforma**, webhook público validado, segredo segregado, serviço de cobrança, conciliação operacional | BLOQUEADO REAL |
| Licença e vencimento | Entitlement CI, `effective_status` computado em leitura, suspensão/retomada/estorno CI | Job de ciclo e recuperação, política de cobrança real, reembolso parcial, renovação, tolerância zero aplicados em **todas** as rotas | PARCIAL CI |
| Dashboard Master | Visões de licenciamento e estado SaaS sem ledger de tenants | Gestão operacional de contratos, inadimplência SaaS, faturas, incidentes, suporte consentido | PARCIAL |
| Membros, cotas e contribuições | GET via API/RLS; entidades e demonstradores | Adesão real, aquisição de cota, cobrança Pix, baixa por conciliação, inadimplência e estorno | BLOQUEADO REAL |
| Pix das caixinhas | Roteiros e contratos de adaptação de provedor | **OAuth por tenant**, escopo/conta recebedora, idempotência, webhook, reconciliação, estorno e Pix de saída | BLOQUEADO REAL |
| Ledger financeiro | Migração 010, DR=CR/FK/referências, RLS parcial, testes sintéticos | Serviço autoritativo de postagem, lock/reserva, idempotência e reconciliação pós-provedor | SEM PROVA INTEGRAL |
| Empréstimos internos | Simulador Price com política ACTIVE do ciclo, recusa taxa informada pelo cliente; cálculos CI | Elegibilidade integral, consentimento anual persistente, mora, parcelas, desembolso/baixa/quitação reais | PARCIAL / REAL BLOQUEADO |
| Autoempréstimo do administrador | Motor puro de unanimidade e testes | Assinaturas persistidas, membros elegíveis, revogação/revalidação em todas as etapas; autorização anual | BLOQUEADO |
| Fechamento anual e lucro | Cálculos/demonstradores, algumas entidades no SQL | `POST /closings` **503**, Capital-Dias V2 autoritativo, maiores restos, saldos residuais, auditoria e liquidação confirmada | BLOQUEADO |
| Bolões e rifas | Demonstradores React com aviso de dados fictícios | Não executar sorteio/aposta real; análise jurídica e especificação de operação futura separada | DEMO SOMENTE |
| Nuvem, deploy e observabilidade | Telas/arquitetura OCI/GCP e documentação preparatória | Recursos produtivos, HTTPS, domínio, secrets manager, logs, alertas, SLO, disaster recovery real | NÃO HOMOLOGADO |
| Segurança e LGPD | Segregação de papéis, minimizar dados, hash de tokens, testes CI; backup age sintético | LGPD operacional, DPIA/LIA quando aplicável, exclusão/exportação, pentest, retenção e trilha de incidentes | PARCIAL |
| Backup e restauração | Backup criptografado + restauração efêmera na CI | Simulado com falha de rede, RPO/RTO e reconciliação após restauração, ensaio autorizado no ambiente próprio | CI VERIFICADO / REAL PENDENTE |
| Android/iOS | React + Capacitor; APK debug buildado | Assinatura release, teste real Android, upgrade, publicação; validação iOS e distribuição ainda não demonstradas | PARCIAL |

## 3. Divergências documentais que exigem resolução rastreável

1. **1.6 — rifa privada:** restrição documental versus preservação do **demonstrador** solicitada pelo proprietário. A decisão de manter DEMO já está dada; proibir operação real e formalizar sua exceção de escopo, sem perguntar novamente.
2. **1.8 — Flutter vs React + Capacitor:** a escolha de React + Capacitor já foi expressa; registrar o aditivo/decisão e não reintroduzir Flutter.
3. **4.1 — política financeira por tenant:** código novo passou a ler política do ciclo em simulações; ainda falta verificar todos os campos, versões e fluxos financeiros.
4. **5.3 — suporte excepcional:** o endpoint break-glass segue 403; regras de consentimento e prazos carecem de conciliação documental e jurídica. **Não habilitar suporte invasivo.**
5. **8.2 — parametrização/Price:** o `loans/simulate` agora **rejeita `monthly_rate` externo** e lê política ativa, corrigindo parte da divergência histórica. Reauditar todo o requisito, sem declará-lo resolvido integralmente.

Outras decisões reconhecidas pela documentação: início do ciclo de referência em **01/01/2027**, encerramento **31/12/2027**, liquidação prevista **10/01/2028**; não alongar Capital-Dias pelo prazo de liquidação. Se PDFs diferirem, registrar decisão individual, nunca escolher redação por inferência. **Não confundir esta exportação AI Studio com qualquer outro ambiente, cluster ou projeto.**

## 4. Prioridades de execução: backlog completo por lotes

As etiquetas **P0** a **P4** são prioridades técnicas propostas neste checkpoint, **não** renomeiam estados contratuais. "Executável agora" significa desenvolver/testar **apenas no GitHub e em dados sintéticos**, não efetuar operações reais.

| ID | Prioridade | Trabalho restante | Critério de aceite / prova | Dependência |
|---|---|---|---|---|
| A01 | P0 | Confrontar os dois PDFs e consolidar o texto aplicável dos 147 requisitos e cenários AT-01…AT-50 | Matriz com texto prevalecente, divergências e commit de evidência por cláusula | Análise documental, sem produção |
| A02 | P0 | Revisar SECURITY DEFINER/RLS da migração 019; impedir consulta de vínculos de identidade arbitrária com credencial de serviço | Testes de tentativa cross-user/cross-tenant e privilégios mínimos | CI |
| A03 | P0 | Auditoria negativa em todos endpoints de MASTER/ADMIN/MEMBER e 2+ tenants | Testes CRUD, papéis simultâneos, login/logout/troca, acesso e consultas financeiras negadas | CI |
| A04 | P0 | Reconciliar docs desatualizados e rotas reais | Arquitetura/Termux/README/Mercado Pago apontam para caminhos atuais, não versões antigas | Repositório |
| A05 | P0 | Validar política Price em pedido, simulação, aprovação, parcelas e mudanças de versão | Mesma política/ciclo em todas as etapas; teste taxa cliente proibida e datas | CI |
| A06 | P0 | Revisar contrato de privilégio da API e separar serviço autenticador, financeiro, contratos e provedor | Matriz de GRANT/REVOKE/SQL + testes de abuso e concorrência | CI |
| A07 | P0 | Construir mapa de dados reais versus `SEED_*` em cada tela | Conta autenticada jamais apresenta saldo/cota/aprovação demonstrativa como real | CI, testes UI |
| A08 | P0 | Pré-migração do AI Studio: checklist de backup, hash e rollback, inventário real read-only | Plano reproduzível, testes em PG18 efêmero, sem tocar banco local | CI, operador aprova depois |
| B01 | P1 | Onboarding de admin com convite preliminar (tenant ainda não contratado) | Fluxo registrado com identidade única, consentimento e tenant não ativado sem pagamento | CI, jurídico para real |
| B02 | P1 | Convites/aceites de novo usuário e usuário existente por API de homologação | Estado, entrega, expiração, reutilização, endereço validado, aceite e auditoria transacionais | CI, SMTP fake |
| B03 | P1 | Recuperação de senha e prova de posse do e-mail com rate-limit distribuído | Token single-use, reset e revogação de sessões, antifraude/anti-enumeração | CI, SMTP fake |
| B04 | P1 | Contratos/documentos versionados, revogação de consentimento e histórico | Versão e hash exibidos, aceite específico por usuário/tenant, retenção auditável | CI, revisão jurídica |
| B05 | P1 | Serviço SaaS dedicado para criar intenção e conciliar pagamento sem conceder superuser à API | Idempotência, collector/currency/mode, falhas/reembolso/race testados, sem transferência real | CI, MP fake |
| B06 | P1 | Máquina de estados SaaS: pendente, cancelada, liquidada, expirada, suspensa, reativada, estornada | Nenhum status falso, expiração tolerância zero, retry/replay, job offline no CI | CI |
| B07 | P1 | Limites de membros e cotas concorrentes por plano; upgrade/downgrade | Constraints/locks, diferentes tenants, preço versionado e regressões de capacidade | CI |
| B08 | P1 | Implementar consentimento anual de autoempréstimo com persistência e revalidação | Unanimidade dos demais, entrada/saída/revogação, bloqueio sem outros membros | CI; operação real ainda proibida |
| B09 | P1 | Serviço de ledger com idempotência por operação e reserva atômica | Partidas equilibradas, recuperação de falhas, sem dupla baixa/débito nem escrita cross-tenant | CI, provedor fake |
| B10 | P1 | Protocolo de eventos Pix/contribuição com estados de conciliação e outbox | Webhook não confirma sozinho; consulta autenticada simulada precede lançamento | CI, provedor fake |
| B11 | P1 | Cálculo autoritativo de Capital-Dias, maiores restos, centavos e fechamento | PostgreSQL, datas/ciclos, auditoria, 15%/85% quando aplicável, pagamentos apenas sintéticos | CI |
| B12 | P1 | Separação de contas SaaS plataforma versus contas de cada tenant | Testes de tenant, contas, destinatário, fluxos e política financeira, sem mistura de receitas | CI |
| B13 | P1 | Cobertura de inadimplência, bloqueio, quitação, mora, descontos e ressarcimentos | Testes negativos e invariantes sem confisco/saldo negativo indevido | CI |
| B14 | P1 | Sessão de suporte consentida com escopo mínimo e trilha de auditoria | Acesso continua bloqueado até decisão jurídica e testes de consentimento | CI + parecer |
| C01 | P2 | Ambiente seguro homologado: HTTPS, domínio, TLS, e-mail verificado, secrets manager | Verificação real de infra em sandbox sem divulgar segredos | Infra aprovada |
| C02 | P2 | Conta Mercado Pago **exclusiva da plataforma** para SaaS, sem usar recursos dos tenants | Credencial segregada, collector correto, callbacks validados | Aprovação MP/operador |
| C03 | P2 | OAuth por tenant, instalação/renovação de tokens e escopos necessários | OAuth revogável por empresa, isolado, finalidade e consentimento | Aprovação MP/operador/jurídica |
| C04 | P2 | Webhook público com assinatura, consulta GET, inbox/outbox, replay e auditoria | Delivery repetida/fora de ordem, contestações e estornos reconciliados | Infra, provedor |
| C05 | P2 | Observabilidade: erros, alertas, backups cifrados, disaster recovery e RPO/RTO | Simulações de falhas e restauração reconciliada | Infra/homologação |
| C06 | P2 | Proteção jurídica, termos e fiscalidade da plataforma e operação financeira | Parecer e autorização por finalidade; LGPD e documentação por módulo | Jurídico/empresarial |
| D01 | P3 | Teste de migração em cópia descartável com PG18.6 e dados sintéticos | Verificação schema/GRANT/RLS/rollback, comparação hash, sem tocar banco reservado | Gate técnico |
| D02 | P3 | Migração **ao banco AI Studio no Termux** somente mediante autorização expressa | Plano aprovado, backup, execução única com evidências e rollback, sem outro cluster | Aprovação escrita específica |
| D03 | P3 | Bootstrap Master humano e contas de homologação no banco AI Studio | Primeiro somente dados sintéticos; configuração adequada e auditoria | Depende D02 + nova aprovação |
| D04 | P3 | Homologação Android física, conectividade FastAPI, mudanças de contexto, offline e acessibilidade | Teste em aparelho, logs filtrados e UX, sem transações reais | APK debug sem instalação automática |
| D05 | P3 | Assinatura release, atualização do app, distribuição controlada e testes iOS | Certificado seguro, update reproducível e distribuição aprovada | Infra e proprietário |
| E01 | P4 | Ativação real dos fluxos de convite e cadastro | E-mail entregue, identidade verificada, aceite jurídico, logs e suporte | C01, C06, D02/D03, aprovação |
| E02 | P4 | Cobrança/ativação SaaS real | Pagamento conciliado, licença ativa só com provedor, políticas e cobrança autorizadas | C01–C04, C06, aprovação |
| E03 | P4 | Movimentação real, Pix saída, empréstimos e fechamento | Autorização legal/financeira específica, controles, conciliação e auditoria | Todos gates anteriores |
| E04 | P4 | Bolão/rifa real, se um dia permitido | Nova decisão jurídica e desenvolvimento separado; **não** está aprovado | Fora do escopo atual |

## 5. Condições técnicas mínimas para marcar módulos como concluídos

**Acesso único:** uma pessoa entra em duas caixinhas com múltiplos papéis; cada troca invalida dados de contexto anterior; RLS impede qualquer leitura cruzada; cliente e backend sobrevivem a logout concorrente; teste no Android autorizado.  
**Convite e senha:** convite e token entregues por provedor, link único, confirmação de titularidade, aceite versionado, auditoria e tentativas abusivas bloqueadas; nenhum novo Master implícito.  
**SaaS:** oferta correta e congelada, conta da plataforma identificada, pagamento real validado pela API, evento idempotente, licença com prazo/estado efetivo, suspensão/restituição/expiração e reversão sem cobrança duplicada.  
**Financeiro:** contas por tenant, autorização/saldo/ledger únicos, transação idempotente, conciliação bancária, empréstimos sem autoaprovação e fechamento anual por banco autoritativo, com extratos auditáveis.  
**Produção:** legalidade demonstrada por finalidade, segurança externa e testes de desastre; dispositivos assinados/homologados; revisão do operador e ativação explícita.

## 6. Diferenças entre infraestrutura de código e a operação real

- `backend/app/account_lifecycle.py`, `invite_registration_ci.py`, `saas_billing_ci.py` e `account_governance_ci.py` estão protegidos pelo gate `_ci_only`, com exigência de `FRCAIXINHA_CI_ISOLATED=1`, banco `frcaixinha_ci`, papel `postgres`, porta `5432`. **Esses serviços não são produção.**
- `backend/app/platform_provider_adapters.py` tem chamadas SMTP/MP capazes de comunicação real, mas exigem flags de autorização; não estão conectadas a fluxo público de cobrança/cadastro. **Não configurar flags reais por antecipação.**
- `backend/app/routers/invitations.py` permanece HTTP **503**, `/auth/forgot-password` permanece **503**; débito Pix de contribuição, desembolso, quitação e fechamento seguem bloqueados em seus endpoints. A presença de código após um `raise 503` não autoriza tratá-lo como funcionalidade operacional.
- `src/services/store.ts` ainda contém muitos `SEED_*`, inclusive financiamentos, membros e licenças. Eles podem dar percepção visual de completude; auditar se as telas os exibem somente como demo e nunca como confirmação de estado financeiro real.
- `docs/TERMUX_FASTAPI_ANDROID_DEBUG.md` contém texto antigo dizendo que o banco AI Studio ainda não havia sido criado, **desatualizado ante a prova mais recente do operador**. `docs/ARQUITETURA_FASTAPI_POSTGRES.md` inclui rotas `/api/auth/me` antigas, enquanto o backend usa `/api/v1/auth/me`. `docs/CHECKPOINT_CONTRATO_2026-11-01.md` inclui exemplos históricos de `routers/pix.py`, não presente na árvore atual, e pendências anteriores ao trabalho 011–019. Corrigir essas referências sem apagar histórico/hashes.
- `backend/migrations/019_named_contexts_and_session_inventory.sql` contém função `SECURITY DEFINER(p_user_id)`. O serviço chama com identidade autorizada, mas uma auditoria de **quem pode executar e com qual UUID** é necessária para minimizar enumeração caso a credencial técnica seja comprometida; esse é **risco a testar**, não invasão constatada.

## 7. Ordem recomendada sem circularidade

`A01–A08` (reconciliação documental e segurança) → `B01–B07` (identidade/contratos/SaaS no laboratório) em paralelo com `B08–B14` (motor financeiro isolado) → `C01–C06` (infraestrutura/jurídico/provedores) → `D01–D05` (migração autorizada, Master e QA real) → `E01–E04` (operações reais, somente com autorização por finalidade).

Não é necessário aguardar validação jurídica para escrever e testar **lógica desativada** que não move dinheiro. Tampouco se deve alegar que a obtenção de uma credencial autoriza operação real.

## 8. Próximo pacote grande de código seguro

**Proposta técnica, ainda não executada neste checkpoint:** juntar A02, A03, A04, A05, A07 e B07 em uma PR incremental testada: revisão de privilégios SECURITY DEFINER e RLS, mapa de telas SEED versus servidor, padronização da política financeira, teste multi-tenant amplo, testes de concorrência de cotas/licenças e atualização da documentação técnica. **Nenhuma mudança no banco local, pagamento ou cadastro real.**

## 9. Controles irrevogáveis sem nova autorização

1. Não executar `backend/scripts/aistudio_db_local.sh apply`, migrations 001–019 ou bootstrap humano em Termux. `check` read-only continua permitido.
2. Não instalar APK, assinar release, criar recursos pagos, efetuar Pix, mover saldos, enviar e-mails de convite, cobrar licença, criar usuário real ou ligar flags reais sem aprovação.
3. Não mesclar a PR #2 na `main`; mudanças documentais e de código permanecem revisáveis na branch.
4. Não custodiar dinheiro dos membros nem transferir saldos entre tenants; Master só possui metadados SaaS, jamais acesso financeiro por esse papel.
5. Rifa e bolão exclusivamente demonstrativos; autoempréstimos exigem consentimento anual válido, não autoaprovação.

**Resultado deste checkpoint:** inventário e plano completos para orientar novas rodadas de desenvolvimento, sem concluir por inferência as 147 cláusulas e sem alterar qualquer banco do celular. A lista integral ID a ID está no [anexo de 147 cláusulas](MATRIZ_147_PENDENCIAS_AI_STUDIO_2026-11-01.md).
