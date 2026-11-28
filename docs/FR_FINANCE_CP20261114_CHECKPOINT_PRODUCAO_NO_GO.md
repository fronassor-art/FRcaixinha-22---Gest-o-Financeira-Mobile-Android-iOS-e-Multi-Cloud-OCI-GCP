# FR Finance — CP20261114 | Checkpoint executivo de desenvolvimento e homologação para produção

**Data da revisão:** 14/11/2026  
**Produto:** FR Finance AI Studio (não FR Caixinha 2.2)  
**HEAD do código auditado:** \`af4d73b38e2a0687be1ae22fdc7364cf008efb84\`  
**PR:** #2, em rascunho; branch \`atualizacao-ai-studio-9b46a63187\`.  
**Decisão de produção:** **NO-GO / PRODUCTION_NOT_AUTHORIZED**.  
**Natureza da evidência:** análise de documentos normativos versionados, código selecionado, regressões CI/artefatos GitHub e checkpoints operacionais anteriores. Não houve acesso remoto direto ao Android, PostgreSQL original, provedor de pagamento, e-mail ou OCI nesta auditoria; não confundir ausência de nova prova com teste físico negativo.

## 1. Escopo documental completo e reconciliação do inventário

| Bloco documental | Itens rastreados | Estado de homologação |
|---|---:|---|
| Caderno Mestre vigente, seis seções originais | 29 | Pendente de atestação item a item |
| Contrato Técnico vigente, sete seções originais | 28 | Pendente de atestação item a item |
| **Subtotal da base vigente original** | **57** | Código/CI existentes não homologam produção |
| Anexos vigentes do Caderno: Crédito Especial, SaaS, Caixas | 8 + 10 + 7 = 25 | Pendente de aceite E2E |
| Anexos vigentes do Contrato: Crédito Especial, SaaS, Caixas | 8 + 9 + 7 = 24 | Pendente de aceite E2E |
| **Total vigente, incluindo anexos** | **106** | Todos registrados individualmente |
| 147 cláusulas históricas (FR Caixinha 2.2 de origem) | 147 | Revalidar aplicabilidade; não são automaticamente contrato atual |
| 20 gates técnicos reais | 20 | **0/20** com prova operacional independente atestada pelo avaliador versionado |
| 7 gates externos | 7 | **0/7** com autorização operacional independente atestada pelo avaliador versionado |
| AT-01 a AT-50 | 50 | **0/50** com aceites E2E reais demonstrados integralmente no avaliador |
| **Matriz original** | **281** | 57 + 147 + 20 + 7 + 50 |
| **Matriz atual ampliada CP20261114** | **330** | 281 + 49 anexos posteriores |

**Artefatos canônicos de trabalho:** [checklist humano de 330 itens](FR_FINANCE_CP20261114_CHECKLIST_INTEGRAL_330.md) e [registro estruturado dos 330 itens com IDs estáveis e fontes](FR_FINANCE_CP20261114_CHECKLIST_INTEGRAL_330.json). Nenhum item foi silenciosamente marcado como concluído. Os 147 itens históricos contam com 58 PARCIAL, 50 BLOQUEADO, 34 NÃO VERIFICADO e 5 DIVERGENTE na fotografia de origem; não tomar esses estados como diagnóstico corrente do aplicativo.

## 2. Fotografia técnica verificada no GitHub e no histórico operacional

| Componente | Evidência atual | Situação para produção |
|---|---|---|
| GitHub/CI | Commit \`af4d73b\`, PR #2 Draft, **29/29 workflows SUCCESS**; workflow geral run \`43604286730\`, **7/7 jobs SUCCESS** em 14/11/2026 | Engenharia CI aprovada; **não é homologação real** |
| Android APK | Artifact \`14117567210\`, pacote \`com.frcaixinha.app.aistudio\`, \`versionCode 3910382\`, assinatura v2 e certificado persistente SHA-256 \`ab003bfd9a496e211370ff4dfcc5044ec19e1151b69ad488d7ec1b0f34ce31c7\` | APK **debug** assinado; APK/AAB release, lojas e instalação E2E M39091 ainda sem prova |
| FastAPI local | O operador sincronizou Git até \`af4d73b\` e iniciou Uvicorn PID \`27796\` em 127.0.0.1:8000; primeiro diagnóstico ocorreu com servidor desligado | Rota após reinício e fluxo físico de Crédito Especial **não reatestados**; não concluir 404 resolvido por inferência |
| PostgreSQL FR Finance | PostgreSQL 18 \`127.0.0.1:5433/frcaixinha_aistudio_dev\`, independente do FR Caixinha 2.2 em 5432; fontes operacionais anteriores confirmaram SQL110/111 e SQL112/113 aplicadas com verificações posteriores | **Rever prova live no mesmo banco, migratory ledger, integridade/backup restaurável e paridade** antes de alterações; não reaplicar versões |
| OCI | VCN/Subnet/rota e compartimento \`fr-finance-staging\` criados; últimos relatos indicam tentativas A1 Always Free sem capacidade, nenhuma VM comprovada RUNNING | Infra operacional pública, HTTPS, Vault, IAM, database staging, observabilidade e restauração: **não homologados** |
| Caixas exclusivos | \`backend/app/routers/exclusive_cashboxes.py\` + \`src/components/ExclusiveCashboxView.tsx\`, UI por papel, testes M39090 | **Somente leitura**; não existem extratos/saldos conciliados transferíveis nem liquidação do Master/Admin comprovada |
| Crédito Especial | API \`special_credit.py\`, UI, ciclo, concessões e campanhas com testes de sandbox, ações externas e financeiras desativadas | 404 físico ainda sem prova de desaparecimento; último inventário local registrou **nenhum ciclo aberto**, sem campanhas; não há envio FCM/Brevo/WhatsApp/SMS real homologado |
| SaaS Master | SQL112/113, preços mensal/anual independentes e promoções de novos administradores; código e CI versionados | Aceite de oferta congelada, faturamento conciliado, licença ativa após pagamento e ciclo de vida real não homologados |
| Cotas/ciclos | Mínimo **R$150 por membro/ciclo**, escolhido explicitamente pelo administrador, regras/CI de price/cycle | Testar transações reais, concorrência, histórico de versão, competência e ciclo anual fim a fim |
| Motor de crédito | Price/Decimal, simulações, idempotência, aprovação e contratos operacionais parciais | Comprovar limites por tenant, cronograma após desembolso, inadimplência, garantias/risco, Money Out e revisões jurídicas |
| Financeiro e Ledger | Livro-Razão, contabilidade sintética, RLS e fronteiras de reconciliação em código | Sem liquidação financeira real/conciliada PSP ↔ sistema ↔ ledger, reversão, estorno, reserva atômica e fechamento autorizado |
| Rateio anual | Teste do rateio de **15% admin/85% membros** por Capital-Dias e conservação de centavos | Cálculo demonstrativo **não é** lucro líquido realizado nem autorização de crédito/transferência |
| Identidade | RBAC, sessões e teste de dois tenants no CI; trilha de convites/aceites em preparação | MFA Master, aprovação independente, confirmação real de e-mail, consentimento jurídico definitivo e recuperação completa E2E pendentes |
| E-mail e push | DNS/SMTP Brevo e módulos de push/FCM documentados, preferências e gates de no-send | Entrega, rejeição, opt-out, credenciais Vault e callbacks não atestados em staging autorizado |
| Segurança/privacidade | Guards de API, RLS/roles, políticas de logs e testes adversariais sintéticos | Pentest, LGPD/gestão de incidentes, backup restaurado, monitoração, segregação operacional e revisão de permissões Android faltam |
| iOS e publicação | Tecnologia Capacitor está presente | Versão iOS distribuível, assinatura/certificados, políticas de loja e teste em dispositivo iOS não demonstrados |
| Juridico/regulatorio | Escopo descrito como software de gestão, não banco; contratos históricos e técnicos versionados | Parecer jurídico sobre estrutura de crédito, titularidade, remuneração e modelos comerciais/tributários ausente |

**Conceito de status:** \`CÓDIGO/CI\` ≠ \`TESTE_FÍSICO\` ≠ \`STAGING_E2E\` ≠ \`PROVEDOR_AUTORIZADO\` ≠ \`PRODUÇÃO_AUTORIZADA\`. Para dinheiro real, todos os últimos quatro precisam ter provas pertinentes.

## 3. Divergências documentais e impedimentos que não podem ser ocultados

- **DR-01 — SQL110/111:** Caderno Mestre §7 e documento anterior descrevem SQL110 como não aplicada, mas o operador demonstrou aplicação controlada em 12/11/2026 (pós-check M39032). **A redação documental está desatualizada**; conferir estado persistente, hash/DDL, histórico e backup original. Não reaplicar.
- **DR-02 — SQL112/113:** §8 do Caderno e Contrato Técnico §G indicam migração pendente/nenhuma migração local; registros operacionais de 13/11/2026 e M39068/M39069 reportaram ambas **já aplicadas**. Corrigir o status documental após novo atestado somente leitura, sem reexecutar SQL.
- **DR-03 — Android package (RESOLVIDO EM AUDITORIA DE CÓDIGO M39100):** não há conflito de IDs: o Contrato Técnico §B e `capacitor.config.ts` identificam o **applicationId-base** `com.frcaixinha.app`; o Gradle acrescenta intencionalmente `applicationIdSuffix '.aistudio'` **apenas na variante debug principal**, originando o APK instalado `com.frcaixinha.app.aistudio`. A variante diagnóstica usa `.aistudio.diag` e o release tem identidade-base separada. **Não renomear pacotes nem reaproveitar a chave debug no release.** Ainda falta homologar o lançamento da variante release, que não é equivalente à atualização debug.
- **DR-04 — 147 cláusulas históricas:** 1.6 (rifas/bolões), 1.8 (Flutter histórico vs React/Capacitor atual), 4.1 (parametrização de políticas por tenant), 5.3 (SLA/suporte), 8.2 (até 12 parcelas vs seis no caso específico) ainda exigem decisão individual. Não transplantar implementação FR Caixinha 2.2.
- **DR-05 — Anuidade antiga:** fórmula histórica \`10×mensal\` foi **substituída** pela decisão contratual de 12/11/2026 de preço mensal/anual independente. Formalizar substituição para AT-25/cláusula 3.2-A sem mudar contratos pretéritos.
- **DR-06 — Tamanho da matriz:** contador M37693–M37973 inspeciona **apenas 57 itens originais** e interrompe a leitura nos anexos; o inventário atual requer **106 itens vigentes**; a matriz total aumenta de **281 para 330**. Não declarar “todos auditados” com o relatório antigo sozinho.
- **DR-07 — Código ≠ dinheiro do administrador:** telas M39090 mostram \`settled_balance_cents=null\`; contagens de intents/lançamentos não são saldo, receita recebida nem comissão realizada. Requer modelagem/registro/fechamento/conciliador e prova financeira real.
- **DR-08 — Arquivos de instrução antigos:** existem documentos com nomenclatura/pastas anteriores a \`$HOME/fr-finance\`; validar versões e rotular legado para não reiniciar outra instância, criar outro banco ou confundir FR Finance com FR Caixinha 2.2.
- **DR-09 — Crédito Especial 404:** código e rota existem no GitHub; mesmo com FastAPI reiniciado, é necessária resposta real após reinício e verificação de sessão/ciclo/sandbox. 404 não deve causar migração nem fallback de banco.
- **DR-10 — Regulatory/Store:** “não é banco” é descrição do produto e **não substitui análise regulatória** se houver intermediação, oferta de crédito ou fluxo monetário entre pessoas. Revisar modelo com profissional habilitado antes de venda/marketing/ativação.

## 4. Fila priorizada de homologação — gates de entrega

| Ordem | Bloco | Implementação/ação necessária | Evidência de saída para encerramento |
|---:|---|---|---|
| **P0-01** | **Rastreabilidade e contratos** | Resolver DR-01…DR-10, decidir aplicabilidade das 147 cláusulas, atualizar versões jurídicas e anexos, manter catálogo de 330 itens | Matriz de decisões assinada, hashes de contratos, textos definitivos e responsáveis |
| **P0-02** | **Runtime original e banco** | Provar que FastAPI em execução carrega SHA correto e módulos; auditar PostgreSQL 18 original, SQL110–113 e diferenças de catálogo, sem escrever | Inventário read-only de API, schema, roles, RLS, migrations, hashes, conexões e logs sem segredos |
| **P0-03** | **Infra staging** | OCI VM ou alternativa de homologação tecnicamente equivalente aprovada, VPN/SSH mínimo, DNS/HTTPS, IAM, Vault, logs, alarmes e custo | Evidência de instância RUNNING, TLS público válido, segredo isolado, rede auditada e API implantada |
| **P0-04** | **Segurança, recuperação e DR** | Testes adversariais, hardening do PostgreSQL, RLS real de dois tenants, backups cifrados, restore isolado, RPO/RTO, monitoramento, incidentes | Logs saneados, restauração completa, pentest/correções e teste de recuperação |
| **P0-05** | **Master e contas** | MFA real, dupla aprovação, identidade única/roles simultâneos, limites, autenticação em produção, sessões revogáveis | E2E de 3 perfis, 2+ tenants, revogação, reset e tentativas inválidas; auditoria |
| **P0-06** | **Convites e contrato** | Convites single-use, e-mail verificado, texto contratual final byte a byte, aceite expresso e versionado do destinatário | Prova do destinatário, concorrência, consumo único, cancelamento e recuperação |
| **P0-07** | **Comunicações** | Brevo SMTP/outbox, DKIM/SPF/DMARC, FCM push, SMS/WhatsApp opt-in e provider callbacks isolados | Entrega e falhas comprovadas em caixas/dispositivos de teste autorizados; opt-out auditado |
| **P0-08** | **SaaS da plataforma** | Preços flexíveis/versionados, ofertas/promoções congeladas, checkout do plano e conciliação SaaS, renovação, expiração, estorno e reativação | Ciclo completo de assinatura de teste, sem confundir taxa SaaS com capital de tenant |
| **P0-09** | **Caixa Master** | Tesouraria SaaS operacional com lançamentos auditáveis, receitas/despesas, relatórios, conciliação e acesso Master | Valor exibido somente a partir de dinheiro conciliado; reconciliação e negativação |
| **P0-10** | **Caixa do administrador** | Remuneração 15% apurada após lucro anual elegível, conta beneficiário, histórico/tributação, garantias e trilha de pagamento | Sem apropriar cotas, principal ou 85% dos membros; aprovação e liquidação autenticadas |
| **P0-11** | **Cotas e ciclo** | Abertura explícita do ciclo com piso R$150, capital separado de receita, competências, pagamentos parciais, inadimplência 90 dias ≠ 3 competências | Teste ciclo atual/futuro e atravessamento anual, reversão de competência e dois tenants |
| **P0-12** | **Crédito ordinário/extraordinário** | Políticas por tenant, limites/parcelas, Price, análise/consentimento/garantias, campanha pontual, expiração, interesses/recusas, cronograma | E2E sem criação automática de dívida; simulações e testes de autorização por membro/ciclo |
| **P0-13** | **Mercado Pago Connect** | Redirect HTTPS, OAuth PKCE/state, Vault, refresh/revogar credenciais, cada conta tenant com autorização real | Dois sellers autorizados isolados, tokens rotacionáveis e falha fechada |
| **P0-14** | **Pix inbound e ledger** | Orders, x-signature, idempotência, provider GET, PSP↔app↔ledger, dupla contabilização, estorno, tarifa e parcial | Transação de teste conciliada sem confirmar por webhook isolado; prova de não duplicação |
| **P0-15** | **Pix outbound / Money Out** | Verificar habilitação comercial por escrito do provedor; reservas atômicas, beneficiário, limites, autorização independente, consulta/recuperação | Aprovação externa e ensaios de pagamento, perda de rede, reembolso e sem duplicidade |
| **P0-16** | **Fechamento / saída** | Inadimplência, devolução voluntária sem confisco, contagem Capital-Dias, lucro líquido e 15/85, imutabilidade e regras de elegibilidade | Fechamento íntegro e reexecução audível com centavos conservados e evidências de 2 tenants |
| **P0-17** | **Android/iOS e UX** | Testar APK debug M39091 no telefone, correção real do 404, caixas na navegação, backup local; preparar APK/AAB release e iOS se escopo incluir | Matriz visual + funcional em aparelhos reais, upgrade sem perda, assinatura válida e requisitos das lojas |
| **P0-18** | **LGPD e conformidade** | Finalizar contratos, privacidade, classificação de dados, minimização, exercício de direitos, registro de tratamento, política de incidentes e enquadramento do crédito | Parecer independente jurídico/regulatório/fiscal, revisão política Google Play e evidência de controles |
| **P0-19** | **Aceite integral** | Executar AT-01–AT-50 caso a caso com dados sintéticos e reais somente quando autorizados; integrar testes adversariais e de provedor | 50 evidências aprovadas e rastreáveis; nenhum item condicionado sem justificativa formal |
| **P0-20** | **GO/NO-GO final** | Review por produto, jurídico, segurança, operação e responsável técnico, com rollback ensaiado e suporte preparado | Decisão formal assinada, checklist sem P0 aberto, rollout limitado e monitoramento |

### P1 — completar antes do lançamento comercial se o escopo incluir

- Suporte com SLA verificável, incidentes, solicitação de acesso excepcional consentido e evidências de revogação.
- Regras contratuais de administrador como membro, crédito próprio e unanimidade coletiva; cenários sem membros/contrato não homologado.
- Plano Ampliado com limite de capacidade **somente após definição contratual**; não ativar por preço configurável.
- Relatórios e documentação fiscal/contábil, trilha do beneficiário, estornos, comprovantes, política de devolução de assinaturas.
- Conformidade acessibilidade/usabilidade, operações offline/reconexão, notificações/campanhas e atualização do aplicativo.
- iOS/distribuição se parte da primeira oferta. Qualquer exclusão de escopo exige decisão registrada, nunca omissão silenciosa.

### P2 — explicitamente fora do go-live enquanto não houver escopo e permissões

- Rifa, bolão, jogos, intermediações de terceiros e outras operações sujeitas a regras próprias **não devem receber ativação automática** por existirem telas demonstrativas; decidir seu tratamento legal e versão futura.

## 5. Gates oficiais que permanecem abertos por falta de prova operacional

**Identidade (4):** AUTH_PRODUCTION; MASTER_MFA; DUAL_CONTROL; TENANT_RLS.  
**Cadastro (6):** INVITE_TRANSACTION; VERIFIED_EMAIL; CANONICAL_CONTRACT; CONTRACT_CONSENT; MAIL_OUTBOX; PASSWORD_RECOVERY.  
**Infraestrutura (5):** OCI_PUBLIC_HTTPS; OCI_BACKUP_RESTORE; MIGRATION_PARITY; RUNTIME_SHA; ANDROID_RELEASE.  
**Pagamentos e fechamento (5):** MP_CONNECT; PIX_INBOUND; PIX_OUTBOUND; FINANCIAL_RECONCILIATION; ANNUAL_CLOSING.  
**Provedores (7):** OCI_HOSTING; OCI_VAULT_IAM; MAIL_PROVIDER; USER_ACTIVATION; MP_CONNECT; PIX_INBOUND; PIX_OUTBOUND.

As provas estão nomeadas individualmente no arquivo JSON do checkpoint e em \`backend/app/release_evidence_matrix.py\`. Não modificar a medição 0/20 ou 0/7 enquanto não houver evidência independente de cada gate. Nenhuma infraestrutura provisionada ou CI bem-sucedida preenche automaticamente essas provas.

## 6. Ressalva jurídica e de distribuição a conferir

Os requisitos atuais do produto exigem **parecer jurídico específico** sobre a atuação da plataforma nas operações de crédito e patrimônio coletivo. O BCB descreve regras aplicáveis a SCD e SEP e ressalta restrições à intermediação de empréstimos entre pessoas por plataforma; o enquadramento depende do **fluxo jurídico e financeiro efetivo**, não só do nome “gestão”. A Google Play exige declarações financeiras para aplicativos com recursos de crédito/pagamento, e mantém restrições de permissões sensíveis para serviços associados a empréstimos. Isso é alerta de conformidade, **não conclusão de que o FR Finance já opera ilegalmente**.

Fontes de revisão: [BCB Resolução CMN 5050/2022](https://www.bcb.gov.br/estabilidadefinanceira/exibenormativo?numero=5050&tipo=RESOLU%C3%87%C3%83O+CMN), [BCB FAQ SCD/SEP](https://bcb.gov.br/meubc/faqs/p/operacoes-e-servicos-prestados-pela-scd-e-sep), [Google Play serviços financeiros](https://support.google.com/googleplay/android-developer/answer/9876821?hl=pt-br), [Google Play declaração financeira](https://support.google.com/googleplay/android-developer/answer/13849271?hl=pt-BR), [ANPD RIPD](https://www.gov.br/anpd/pt-br/canais_atendimento/agente-de-tratamento/relatorio-de-impacto-a-protecao-de-dados-pessoais-ripd).

## 7. Próximo ponto de retomada

**M39100 correção DR-03:** divergência aparente explicada pela variável de buildType do Gradle; evidência estática, não representa homologação Android release. As outras divergências seguem abertas até prova específica.

**Primeiro pacote pontual a fechar: P0-01 + P0-02.** Validar uma só API e um só banco originais FR Finance, levantar prova pós-reinício sobre o 404, cruzar SQL110–113 já aplicadas com a documentação, resolver incompatibilidade de appId e registrar as cinco divergências históricas sem alterar contratos ou esquema automaticamente. Só depois avançar para homologação OCI/identidade/comunicações e, por fim, provedores e transações financeiras.

**Última decisão formal:** nenhum GO; \`PIX_REAL=OFF\`, \`PAGAMENTOS_REAIS=OFF\`, \`ATIVACAO_REAL=OFF\`, \`PRODUCTION_RELEASE=BLOCKED\`. O PR continua draft. Esta auditoria não aplicou SQL, não reiniciou Uvicorn, não tocou OCI nem movimentou dinheiro.
