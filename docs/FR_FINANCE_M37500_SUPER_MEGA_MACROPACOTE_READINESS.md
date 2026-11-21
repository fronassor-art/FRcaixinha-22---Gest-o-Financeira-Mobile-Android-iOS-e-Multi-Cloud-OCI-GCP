# FR Finance AI Studio — M37500–M37692 | Super Mega Macropacote

**Projeto exclusivo:** AI Studio; branch `atualizacao-ai-studio-9b46a63187`. PR #2 permanece draft. Não alterar a `main`, não confundir com FR 2.2.

## Situação operacional de referência (10/11/2026)

A auditoria autenticada M37472 concluiu `M37470_OCI_READONLY=PASS` na região `sa-saopaulo-1`, com **0 VMs de staging em RUNNING**, **0 em PROVISIONING**, **0 Vaults ativos**, 0 dynamic groups do projeto, VCN/subnet/IGW/rota disponíveis, TCP 443 público não preparado. Leitura pontual, não monitoramento permanente.

O relatório offline continua com **0/20 provas reais de lançamento** e **0/7 provas de provedores**: código/CI não equivalem a comprovação operacional. Pix real, pagamentos reais, emissão de licenças reais e ativação de membros/administradores reais permanecem OFF.

## Macropacote desenvolvido no código

1. `backend/app/m37500_release_safety.py`: verificações determinísticas e somente locais de identidade, convite, tenant, contrato versionado, consentimento afirmativo, dupla aprovação, MFA, valor mínimo de **R$150 por membro/ciclo**, inadimplência 90 dias, e-mail, quarentena da outbox, conciliação em três fontes, proteção contra estorno/replay e cálculo anual **15% para administrador / 85% para membros** em centavos. Retorna apenas **candidato sintético de sandbox**, jamais autorização real.
2. `backend/app/m37500_release_workplan.py`: **192 etapas** com IDs estáveis `M37501`–`M37692`, distribuídas em **16 frentes**, com dependências dentro de cada frente. Todas começam `PLANNED_NOT_REAL_VERIFIED` e não assumem conclusão.
3. `backend/scripts/aistudio_m37500_megapack_offline.py`: visão resumida ou JSON, sem rede, banco ou credencial.
4. `backend/tests/test_m37500_release_safety_ci.py`: validações adversariais e regressões de isolamento e segurança.
5. `backend/tests/test_m37500_release_workplan_ci.py` e `test_m37500_offline_cli_ci.py`: consistência das 192 etapas, paridade com os 20/7 gates existentes e bloqueio contra aprovações falsas.

Esses novos módulos são **bibliotecas e preflights isolados**. Não estão ligados à API operacional ou ao fluxo Android; integração, UI, autenticação e provedor E2E continuam tarefas futuras, sujeitas a testes próprios. Não confundir etapa planejada com implementação concluída.

## Frentes — cada uma tem 12 tarefas rastreáveis

| Frente | Foco |
|---|---|
| OCI_CAPACITY | capacidade gratuita, instâncias e observador |
| OCI_NETWORK | VCN, HTTPS, DNS, portas, NSG, firewall |
| OCI_IAM_VAULT | Vault, dynamic groups, Instance Principal |
| POSTGRES_STAGE | migrações, backup, restore, TLS, RLS |
| AUTH_SESSIONS | sessões, login, expiração, revogação |
| ACCESS_MASTER_ADMIN_MEMBER | acesso único e permissões por perfil |
| CONTRACTS | hash, identidade, consentimento versionado |
| INVITATIONS | e-mail, prova de posse, uso único, concorrência |
| BREVO_NOTIFICATIONS | SPF/DKIM/DMARC, outbox, bounce, callback |
| MP_OAUTH | PKCE, state, refresh e contas independentes |
| PIX_INBOUND | Orders, assinatura, idempotência, Livro-Razão |
| PIX_OUTBOUND | habilitação comercial, limites, aprovações |
| RECONCILIATION | três fontes, reversões, tarifas, incidentes |
| FINANCIAL_RULES | R$150 mínimo, 90 dias, 15%/85% e saída |
| ANDROID_DELIVERY | APK release, HTTPS, SHA, testes no aparelho |
| RELEASE_CONTROL | 20 gates, 7 provedores, go/no-go independente |

Consulta da lista integral: `PYTHONPATH=backend python backend/scripts/aistudio_m37500_megapack_offline.py json`.

## Migração versionada: SQL 066, 067 e 068

Foram **criadas e registradas** no `migration_catalog_ai_studio.json` três migrações de **quarentena sintética CI-only**, levando o catálogo de 106 para **109** arquivos SQL. Todos possuem classificação `STAGING_ONLY_NEEDS_PORT`, `do_not_apply_source_to_termux=true`, SHA do blob Git, guarda de banco `frcaixinha_staging`, usuário `postgres`, superuser e flag local de sessão `frfinance.m37500_ci=1`. RLS `ENABLE/FORCE`, revogação pública, registros append-only e flags impossíveis de habilitar por CHECK.

- `066_release_gate_evidence_quarantine_ci_only.sql`: snapshot não atestado dos gates (sem promover conclusão).
- `067_mail_delivery_quarantine_ci_only.sql`: evidências sintéticas de entrega, sem envio.
- `068_payment_reconciliation_hold_ci_only.sql`: hold sintético, sem conciliação real ou crédito.

O novo job `m37500-sql-disposable` aplica **somente esses três SQL** a um PostgreSQL 18 **descartável do GitHub Actions** e confere três tabelas, FORCE RLS, seis triggers e zero linhas. Isto não é implantação na OCI nem migração do banco do aparelho. Toda mudança futura no banco financeiro real exige backup, aprovação, compatibilidade, plano de rollback e homologação independente. Nunca executar SQL `staging_migrations` ou `ci_migrations` no banco Termux 5433.

## Sequência de execução

**A. GitHub:** subir os fontes e testes, rodar 7 jobs, incluindo PostgreSQL 18 descartável, API, frontend e Android. Corrigir falhas antes da sincronização.

**B. Termux:** sincronizar por fast-forward, validar o SHA informado, conferir árvore limpa e executar apenas testes Python, diagnóstico offline, preflight do catálogo 109 SQL e `/api/health`. Nenhuma migração local. Se algum teste falhar, interromper e devolver o log.

**C. Próxima rodada após retorno:** usar o relatório Termux para priorizar a integração real das bibliotecas com FastAPI/mobile, o fluxo de recuperação de senha, os trabalhadores outbox Brevo, a preparação de OCI staging e os cenários de provedor sandbox. Os 192 itens são um plano de trabalho, não 192 implementações integradas neste commit.

**D. Produção:** somente quando houver as provas independentes reais de identidade, contrato, consentimento, infraestrutura, backups, segurança, provedor e autorização do operador. Nenhuma CI dá autorização automática para movimentar dinheiro ou ativar pessoas.

## Limites inegociáveis

- Não criar VM, não alterar OCI, IAM, VCN, DNS ou regras de firewall automaticamente.
- Não enviar e-mails reais, não ativar OAuth Mercado Pago real, não enviar Pix.
- Não consultar ou alterar banco financeiro original em tarefas offline.
- Não armazenar chaves, tokens, senhas, CPF, e-mails de destinatários ou OCIDs privados em logs de CI.
- Não interpretar estado RUNNING como DNS/HTTPS, aprovação de produção ou consentimento.
- Não aplicar migrações do catálogo apenas por existirem no repositório.

**Critério de aceitação deste pacote:** testes e registro de código aprovados, execução SQL CI descartável aprovada, sincronização Termux comprovada. A produção **continua bloqueada** até provas reais.
