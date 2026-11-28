# FR Caixinha — Macropacote consolidado M300 | Inventário vivo

Data: 04/11/2026. Frente de trabalho: **AI Studio Mobile**. Produto único: **FR Caixinha**. As regras funcionais têm por fontes o **Documento Mestre** e o **Contrato Técnico Mestre**, comuns à implementação original (pausada) e à atual. Os ambientes de código, banco, credenciais, backup e operações permanecem segregados.

## Fonte e status verificados antes da implementação
- Baseline GitHub: `49da46b8449ef9c484e40b78ca04d6043883376c` (PR #2 Draft, sem merge).
- GitHub Actions #210: **6/6 PASS**. APK 210: **7/7 PASS de homologação física informados pelo operador**.
- Termux M280: código sincronizado, PostgreSQL exclusivo 5433, FastAPI ready e runtime M280 PASS segundo logs enviados; **SHA completo executado em memória permanece não comprovado**.
- Backup age de AI Studio com SHA e restauração estrutural isolada PASS anteriormente reportados. **Guarda off-device, RPO/RTO e recuperação total permanecem pendentes**.
- [Matriz contratual das 147 cláusulas](MATRIZ_147_PENDENCIAS_AI_STUDIO_2026-11-01.md) e [checkpoint executivo de 01/11](CHECKPOINT_EXECUTIVO_PENDENCIAS_AI_STUDIO_2026-11-01.md) são fotografias históricas, NÃO reclassificadas por este pacote. A contagem histórica era 58 parciais, 50 bloqueadas, 34 não verificadas, 5 divergentes.

## Entregas de código do M300
Implementações propostas e testes vinculados: `backend/app/routers/ledger.py`, `backend/app/models.py`, `src/services/ledgerAccountJournalBoundary.ts`, `src/services/financialApiService.ts`, `src/components/LedgerAccountEntries.tsx`, `src/components/LedgerView.tsx`, `backend/app/main.py`, `backend/app/config.py`, `README.md`, `index.html`, `capacitor.config.ts`, `android/app/src/main/res/values/strings.xml`, `public/manifest.webmanifest`, `src/App.tsx`, `src/components/LoginView.tsx`, testes e workflow CI. **Cada entrega só é declarada CI PASS após conclusão integral dos seis jobs, e operacional PASS somente após Termux + APK no aparelho.**

### Etapa A — implementações incluídas (verificar CI, Termux e Android separadamente)
| ID | Controle/deliverable | Estado inicial do pacote |
|---|---|---|
| M300-001 | Conservar PR #2 Draft e main sem merge | CÓDIGO PREPARADO; CI/Termux/APK a homologar |
| M300-002 | Preservar SHA-base e avanço somente fast-forward | CÓDIGO PREPARADO; CI/Termux/APK a homologar |
| M300-003 | Reconhecer a homologação do APK 210 (7/7 relatados) | CÓDIGO PREPARADO; CI/Termux/APK a homologar |
| M300-004 | Conferir CI 210 6/6 PASS | CÓDIGO PREPARADO; CI/Termux/APK a homologar |
| M300-005 | Reconhecer runtime M280 validado no Termux | CÓDIGO PREPARADO; CI/Termux/APK a homologar |
| M300-006 | Distinguir produto FR Caixinha da frente AI Studio | CÓDIGO PREPARADO; CI/Termux/APK a homologar |
| M300-007 | Manter Documento Mestre e Contrato Técnico Mestre comuns | CÓDIGO PREPARADO; CI/Termux/APK a homologar |
| M300-008 | Separar repositórios/PG/contas/chaves das duas frentes | CÓDIGO PREPARADO; CI/Termux/APK a homologar |
| M300-009 | Corrigir identificação pública em README | CÓDIGO PREPARADO; CI/Termux/APK a homologar |
| M300-010 | Corrigir nome da API FastAPI | CÓDIGO PREPARADO; CI/Termux/APK a homologar |
| M300-011 | Corrigir projeto no settings backend | CÓDIGO PREPARADO; CI/Termux/APK a homologar |
| M300-012 | Corrigir título HTML e Open Graph | CÓDIGO PREPARADO; CI/Termux/APK a homologar |
| M300-013 | Corrigir nome no Capacitor sem mudar appId | CÓDIGO PREPARADO; CI/Termux/APK a homologar |
| M300-014 | Corrigir nome nas strings Android | CÓDIGO PREPARADO; CI/Termux/APK a homologar |
| M300-015 | Corrigir nome no manifesto web | CÓDIGO PREPARADO; CI/Termux/APK a homologar |
| M300-016 | Corrigir rótulos de login e acessibilidade | CÓDIGO PREPARADO; CI/Termux/APK a homologar |
| M300-017 | Corrigir identificação do preview mobile | CÓDIGO PREPARADO; CI/Termux/APK a homologar |
| M300-018 | Retirar alegação enganosa OCI/GCP ativos | CÓDIGO PREPARADO; CI/Termux/APK a homologar |
| M300-019 | Preservar teste prévio M280 do runtime | CÓDIGO PREPARADO; CI/Termux/APK a homologar |
| M300-020 | Adicionar página read-only por conta contábil | CÓDIGO PREPARADO; CI/Termux/APK a homologar |
| M300-021 | Restringir endpoint ao TENANT_ADMIN do tenant | CÓDIGO PREPARADO; CI/Termux/APK a homologar |
| M300-022 | Recusar Master/Membro/outro tenant antes do SQL | CÓDIGO PREPARADO; CI/Termux/APK a homologar |
| M300-023 | Validar UUID de tenant e conta | CÓDIGO PREPARADO; CI/Termux/APK a homologar |
| M300-024 | Exigir existência da conta dentro do tenant | CÓDIGO PREPARADO; CI/Termux/APK a homologar |
| M300-025 | Paginação limitada 1–1000 e 1–50 itens | CÓDIGO PREPARADO; CI/Termux/APK a homologar |
| M300-026 | Aplicar ORDER determinístico e LIMIT+1 | CÓDIGO PREPARADO; CI/Termux/APK a homologar |
| M300-027 | Adicionar JOIN de transação com tenant correspondente | CÓDIGO PREPARADO; CI/Termux/APK a homologar |
| M300-028 | Recusar valores/entradas malformados | CÓDIGO PREPARADO; CI/Termux/APK a homologar |
| M300-029 | Conservar contrato de não conciliação/fechamento | CÓDIGO PREPARADO; CI/Termux/APK a homologar |
| M300-030 | Adicionar parser TypeScript estrito contra campos extras | CÓDIGO PREPARADO; CI/Termux/APK a homologar |
| M300-031 | Recusar valores não inteiros, negativos e divergentes | CÓDIGO PREPARADO; CI/Termux/APK a homologar |
| M300-032 | Recusar paginação forjada e tenant cruzado na resposta | CÓDIGO PREPARADO; CI/Termux/APK a homologar |
| M300-033 | Descartar resposta obsoleta após troca de sessão | CÓDIGO PREPARADO; CI/Termux/APK a homologar |
| M300-034 | Adicionar UI extrato de conta Anterior/Próxima | CÓDIGO PREPARADO; CI/Termux/APK a homologar |
| M300-035 | Manter Livro-Razão só em prévia equilibrada | CÓDIGO PREPARADO; CI/Termux/APK a homologar |
| M300-036 | Não gravar lançamentos ao consultar página | CÓDIGO PREPARADO; CI/Termux/APK a homologar |
| M300-037 | Adicionar marcador de runtime M300 em memória | CÓDIGO PREPARADO; CI/Termux/APK a homologar |
| M300-038 | Verificar runtime sem imprimir tokens ou URLs SQL | CÓDIGO PREPARADO; CI/Termux/APK a homologar |
| M300-039 | Criar diagnóstico somente leitura de Git, PG5433, FastAPI | CÓDIGO PREPARADO; CI/Termux/APK a homologar |
| M300-040 | Ampliar testes backend, UI, segurança e CI | CÓDIGO PREPARADO; CI/Termux/APK a homologar |

### Etapa B — backlog preservado e priorizado (não marcar como concluído)
| ID | Pendência | Situação |
|---|---|---|
| P-001 | Reauditar todas as 147 cláusulas confrontando PDFs mestres | PENDENTE / requer controle específico |
| P-002 | Executar cenários de aceitação AT-01 a AT-50 com evidência integral | PENDENTE / requer controle específico |
| P-003 | Resolver divergência 1.6: rifa apenas demonstração | PENDENTE / requer controle específico |
| P-004 | Registrar aditivo 1.8: React/Capacitor versus Flutter | PENDENTE / requer controle específico |
| P-005 | Validar política Price em cada etapa de crédito | PENDENTE / requer controle específico |
| P-006 | Auditar funções SECURITY DEFINER e grants mínimos | PENDENTE / requer controle específico |
| P-007 | Cobrir CRUD de papéis simultâneos em dois tenants | PENDENTE / requer controle específico |
| P-008 | Concluir mapa de seeds e dados autoritativos por tela | PENDENTE / requer controle específico |
| P-009 | Testar roles app/auth/verifier autenticadas no PG local | PENDENTE / requer controle específico |
| P-010 | Validar RLS com dados sintéticos e autorização específica | PENDENTE / requer controle específico |
| P-011 | Criar paginação global confiável de contas e transações | PENDENTE / requer controle específico |
| P-012 | Substituir OFFSET por cursor/snapshot para extratos grandes | PENDENTE / requer controle específico |
| P-013 | Implementar filtros de competência e datas com isolamento | PENDENTE / requer controle específico |
| P-014 | Provar completude e consistência temporal do Livro-Razão | PENDENTE / requer controle específico |
| P-015 | Criar trilha de auditoria imutável autenticada | PENDENTE / requer controle específico |
| P-016 | Validar idempotência de lançamentos e reservas sintéticas | PENDENTE / requer controle específico |
| P-017 | Ligar contrato/aceite persistente aos fluxos de ingresso | PENDENTE / requer controle específico |
| P-018 | Completar onboarding seguro de administradores | PENDENTE / requer controle específico |
| P-019 | Completar convites e validação externa de e-mail | PENDENTE / requer controle específico |
| P-020 | Completar recuperação de senha anti-enumeração | PENDENTE / requer controle específico |
| P-021 | Validar expiração e revogação de sessões em ambiente real | PENDENTE / requer controle específico |
| P-022 | Validar histórico multi-role sem elevação indevida | PENDENTE / requer controle específico |
| P-023 | Homologar titularidade, consentimento e suporte consentido | PENDENTE / requer controle específico |
| P-024 | Garantir versão e limites por plano SaaS sob concorrência | PENDENTE / requer controle específico |
| P-025 | Homologar cobrança SaaS com provedor fake e recebedor correto | PENDENTE / requer controle específico |
| P-026 | Homologar estados de licença, suspensão e reembolso | PENDENTE / requer controle específico |
| P-027 | Homologar OAuth Mercado Pago por tenant em sandbox | PENDENTE / requer controle específico |
| P-028 | Webhook assinado, idempotência, replay e estorno fake | PENDENTE / requer controle específico |
| P-029 | Conciliação bancária independente antes de baixa real | PENDENTE / requer controle específico |
| P-030 | Crédito interno: elegibilidade, mora, quitação e contratos | PENDENTE / requer controle específico |
| P-031 | Autoempréstimo: unanimidade anual auditável e revalidada | PENDENTE / requer controle específico |
| P-032 | Crédito externo: parecer e elegibilidade jurídica | PENDENTE / requer controle específico |
| P-033 | Capital-dias e rateio 15/85 com dados reais conciliados | PENDENTE / requer controle específico |
| P-034 | Resíduos de centavos segregados e trilha auditável | PENDENTE / requer controle específico |
| P-035 | Fechamento anual e liquidação financeira permanecem 503 | PENDENTE / requer controle específico |
| P-036 | Backup cifrado off-device em guarda segura | PENDENTE / requer controle específico |
| P-037 | Cópia independente da chave age e plano de recuperação | PENDENTE / requer controle específico |
| P-038 | Restaurar funcionalmente com RPO/RTO aferidos | PENDENTE / requer controle específico |
| P-039 | Simular perda do aparelho/erro de rede e restauração | PENDENTE / requer controle específico |
| P-040 | LGPD: consentimento, exportação, exclusão e retenção | PENDENTE / requer controle específico |
| P-041 | Auditoria de dependências, dados sensíveis e incidentes | PENDENTE / requer controle específico |
| P-042 | OCI/GCP: TLS, secrets, deploy e monitoramento reais | PENDENTE / requer controle específico |
| P-043 | Estratégia de iOS, assinatura release e distribuição | PENDENTE / requer controle específico |
| P-044 | Revisão independente de PR e merge somente autorizado | PENDENTE / requer controle específico |
| P-045 | Comparação posterior com código do Google AI Studio | PENDENTE / requer controle específico |
| P-046 | Teste físico APK do macropacote novo no celular | PENDENTE / requer controle específico |

### Etapa C — proibições e gates de alto risco
| ID | Operação | Situação |
|---|---|---|
| B-001 | Liberar dinheiro real ou disparar Pix | BLOQUEADO sem aprovação expressa |
| B-002 | Registrar pagamento como conciliado sem instituição | BLOQUEADO sem aprovação expressa |
| B-003 | Cobrança/estorno SaaS produtivo sem sandbox e jurídico | BLOQUEADO sem aprovação expressa |
| B-004 | Efetuar desembolso de empréstimo | BLOQUEADO sem aprovação expressa |
| B-005 | Liquidar ciclo ou distribuir lucros | BLOQUEADO sem aprovação expressa |
| B-006 | Criar usuário Master adicional no ambiente atual | BLOQUEADO sem aprovação expressa |
| B-007 | Aplicar migração operacional sem aprovação específica | BLOQUEADO sem aprovação expressa |
| B-008 | Misturar PostgreSQL 5433 com ambiente da outra frente | BLOQUEADO sem aprovação expressa |
| B-009 | Publicar ou fundir a PR #2 na main sem autorização | BLOQUEADO sem aprovação expressa |
| B-010 | Ativar rifas/bolões reais | BLOQUEADO sem aprovação expressa |
| B-011 | Ativar suporte break-glass sem consentimento | BLOQUEADO sem aprovação expressa |
| B-012 | Enviar ZIP para AI Studio sem solicitação expressa | BLOQUEADO sem aprovação expressa |

## Limites da implementação paginada
- Nova rota `GET /api/v1/tenants/{tenant_id}/ledger/accounts/{account_id}/entries?page=1&page_size=25`, `page_size` máximo 50; retorna apenas uma janela por conta autorizada. Paginação OFFSET 1..1000, ordenação estável com IDs, não snapshot transacional entre requisições.
- A rota antiga `/ledger/accounts`, `/ledger/transactions` e `integrity-preview` permanece com gate global de 500 registros. O novo extrato por conta **NÃO resolve paginação global, saldos, integralidade histórica, nem banco conciliado**.
- Identidade do produto apresentada como **FR Caixinha**; `AI_STUDIO` permanece identificador técnico da frente. `appId`, package e certificado Android são preservados.
- Sem criação/alteração de tabelas, role Master, migrações, cron, operações financeiras ou acesso externo a provedores.

## Liberação em etapas obrigatórias
1. GitHub: CI **6/6 PASS** no SHA publicado, PR Draft, sem merge.
2. Termux: branch esperada, worktree limpa, SHA origem previsto, `fetch` e `merge --ff-only` para HEAD exato.
3. Reinício manual **somente do FastAPI** após alteração Python, `Ctrl+C` no terminal da API e `bash backend/scripts/run_termux_fastapi.sh`; **não reiniciar PostgreSQL**.
4. Segunda sessão Termux: `bash backend/scripts/aistudio_300_checkpoint_readonly.sh SHA_COMPLETO` para CI e runtime.
5. APK Android sobre versão anterior, sem desinstalar nem limpar dados. Testar versão, login, Livro-Razão, extrato por conta, Master e Membro negados, navegação, bloqueios financeiros, erros e paginação.
6. Se qualquer gate FAIL/BLOCKED: não liberar módulo, investigar no mesmo branch com novo commit e CI. Só mudar status após evidência.

## Registro de backlog por prioridade contratual
Prioridade P0: requisitos mestres, RLS/SECURITY DEFINER, identidade/roles, seeds, backup e trilha. P1: convites, contratos, SaaS, crédito, ledger autoritativo, Pix simulado e fechamento sintético. P2: OCI/GCP, OAuth MP em sandbox, observabilidade e jurídico. P3: PG18 descartável, atualizações físicas Android/iOS e backup/restauração. P4: produção real, que permanece bloqueada. Consultar tarefas A01–E04 do checkpoint executivo para preservar todas as 37 pendências históricas.

**Regra central:** o Documento Mestre e o Contrato Técnico Mestre pertencem ao produto FR Caixinha e não a um repositório. Implementar sem confundir ambientes, sem resultados financeiros fictícios em telas autenticadas, e sem equiparar CI com autorização operacional.

## Adendo de continuidade M320 — sem reclassificação da matriz

Após o M300, o operador informou **4/7 PASS no APK 211** (commit `e33bae7`): Livro-Razão do Admin, prévia, Master/Membro segregados e bloqueio de operações reais. Os três testes restantes ficaram pendentes pela ausência de transações registradas na prévia. Esta falta de dados **não é PASS para paginação, nem FAIL do Android**.

O [Macropacote M320](FR_CAIXINHA_MACROPACOTE_320_LEDGER_EMPTY_GATES.md) prepara diretório **sem saldo** para contas existentes mesmo quando o razão não tem transações, com guardas de tenant e papéis, parser estrito, máquina de estados e testes sintéticos. Se não existirem contas, a tela exibe ausência sem criar dados. As 40 entregas, 46 pendências e 12 bloqueios acima são fotografias do inventário M300, não contagens atualizadas automaticamente.

**Guarda:** CI do M320, sincronização ff-only, reinício somente do FastAPI, diagnóstico runtime, APK físico e revisão independente são gates posteriores e específicos. O Documento Mestre e o Contrato Técnico Mestre seguem aplicáveis a ambas as frentes, com infra isolada.
