# FR Finance — M40520 | Nova auditoria de prontidão para produção real

**Data:** 18/11/2026 (America/Belem). **Baseline inspecionada:** `f5ed3be1be5a22f0f9ff6230119dc45e95d39836` (M40510). **Branch:** `atualizacao-ai-studio-9b46a63187`. **PR #2:** aberta em Draft; `main` sem merge.

## Decisão

**NO-GO — NÃO PRONTO / NÃO AUTORIZADO PARA PRODUÇÃO FINANCEIRA REAL.**

Esta é uma revisão documental e estática do repositório, matrizes de evidências e GitHub Actions. Não houve nesta auditoria acesso ao PostgreSQL original, dispositivo Android, conta OCI, Mercado Pago, segredos, logs privados ou serviços em execução. Um estado não comprovado não é uma reprovação de teste; tampouco é aprovação.

**Guardas obrigatórios inalterados:** `PIX_REAL=OFF`, `PAGAMENTOS_REAIS=OFF`, `ATIVACAO_REAL=OFF`, `PRODUCTION=BLOCKED`. Nenhuma migração, DDL/DML, provisionamento OCI, reinício de FastAPI/PostgreSQL, alteração de flags, contato com provedor, envio de mensagens, merge ou deploy foi executado.

## 1. Evidências positivas atuais

| Área | Evidência verificada | O que isso comprova — e o que NÃO comprova |
|---|---|---|
| Git e sincronização | Usuário apresentou fast-forward Termux `a5c740a..f5ed3be`, HEAD `f5ed3be`, sem operações SQL ou reinícios; GitHub PR #2 ainda aponta para o mesmo SHA | Código de trabalho sincronizado conforme log do operador; não atesta versão em memória do FastAPI |
| CI geral | [Run 44308632625](https://github.com/fronassor-art/FRcaixinha-22---Gest-o-Financeira-Mobile-Android-iOS-e-Multi-Cloud-OCI-GCP/actions/runs/44308632625): 7/7 jobs SUCCESS, incluindo frontend, API sem banco configurado, PostgreSQL 18/RLS descartável, pacote e Android debug | Testes de regressão e build aprovados; não são testes financeiros de ponta a ponta |
| Android M40510 | 36/36 cenários de layout/viewport/logout na CI; correção de `LoginView.tsx`, `loginViewport.ts` e CSS | Regressões de código aprovadas; corte físico do topo após logout/teclado ainda precisa ser reavaliado no dispositivo |
| Android M40500 | Homologação física **informada pelo operador**: 4/5 PASS (monograma, biometria, fotos por conta, nomes do servidor); 1/5 FALHA do topo | As quatro funções já observadas merecem regressão no novo APK; nenhuma prova nova de M40510 no telefone |
| Autenticação e isolamento | Suítes de login/bearer, papéis e RLS de dois tenants em PG18 descartável | Proteção bem exercitada em CI; isolamento de produção e MFA Master real não certificados |
| Governança | Matriz de 330 itens, inventário de 20 gates e sete provedores, script offline CP20261117 com proteção contra promoção automática | Rastreabilidade de pendências; não confundir presença de documento com conformidade operacional |

APK atual é **debug de homologação** `com.frcaixinha.app.aistudio`, versão `1.0.3910637-AI-STUDIO-TEST`. O `android/app/build.gradle` exige assinatura release distinta e perfil de HTTPS válido; `com.frcaixinha.app` é outra identidade de instalação. A chave debug não é chave de publicação.

## 2. Medição rigorosa dos gates de produção

O [checklist CP20261114 de 330 itens](FR_FINANCE_CP20261114_CHECKLIST_INTEGRAL_330.md), [JSON canônico](FR_FINANCE_CP20261114_CHECKLIST_INTEGRAL_330.json), [auditoria CP20261117](FR_FINANCE_CP20261117_AUDITORIA_GITHUB_SEM_VM.md) e `backend/app/release_evidence_matrix.py` mantêm:

- **20 gates técnicos: 0/20 com evidência operacional independente registrada.**
- **7 gates externos: 0/7 com evidência operacional independente registrada.**
- **50 cenários AT-01–AT-50: 0/50 com aceite E2E real registrado nessa matriz.**
- **330 itens inventariados:** 57 requisitos vigentes originais + 49 aditivos vigentes + 147 cláusulas históricas sujeitas a triagem + 20 gates técnicos + 7 externos + 50 AT. Isso não significa que 330 funcionalidades estejam ausentes.
- `backend/app/launch_readiness.py` retorna `production_verified: False` por requisito. Os campos de evidência técnica `MASTER_MFA`, `OCI_PUBLIC_HTTPS`, `RUNTIME_SHA` e `PIX_OUTBOUND` aparecem como `False` na inspeção do manifesto de código. Isso é um marcador de prontidão, **não** uma conclusão de que todos os componentes de implementação inexistem.

**Regra de auditoria:** os contadores acima descrevem *provas de produção registradas*, não desempenho, percentual de funcionalidade desenvolvida ou falha de todos os cenários.

## 3. Bloqueios impeditivos (P0)

| Bloco | Estado auditável em 18/11 | Evidência exigida para sair do NO-GO |
|---|---|---|
| Android físico e publicação | M40510 sem reteste no aparelho. APK só debug | Confirmar topo completo após logout e teclado, regressão 4/4 e release assinado sob identidade comercial aprovada, HTTPS e distribuição controlada |
| Runtime e banco correto | Termux informa Git sincronizado, mas esta auditoria não leu o serviço em memória nem a base `frcaixinha_aistudio_dev:5433`. FR Caixinha 2.2 deve permanecer isolado | Comandos **somente leitura** atestando PID/versão da API, role/db/porta, catálogo SQL110–113, roles, RLS, paridade e trilhas sem credenciais; não repetir migrações |
| Infraestrutura OCI | Evidência CP20261117 registrou ausência de VM pelo operador, **não por consulta nova ao provedor**. Status OCI de hoje não foi lido | Staging operacional atestado com VM ou alternativa autorizada, domínio, TLS, firewall, IAM/Vault, deploy, observabilidade, backup e restore isolado |
| Identidade, privacidade, segurança | CI sintética robusta, mas MFA Master, dupla aprovação, contratos aceitos por pessoas, recuperação/convites e pentest reais sem prova final | E2E duas caixinhas e três perfis, auditoria de acesso, recuperação e incidentes, proteção LGPD, MFA Master, revisão independente |
| Mercado Pago / Pix | Preparação de Connect, webhook, idempotência e contabilidade; dinheiro real OFF | Integração autorizada, OAuth por administrador, segredos em Vault, webhook autenticado, consulta ao PSP, conciliação de três fontes, estornos e limites |
| Pix de saída | Capacidade Money Out não atestada por provedor | Autorização comercial documentada, controle de beneficiário, limites, segregação e dupla aprovação; jamais habilitar apenas pela presença de endpoint |
| Financeiro e rateio anual | Cotas, Price, Caixa Master/Admin e 15%/85% testados em simulação/CI | Liquidação rastreável, livro-razão autoritativo, reversão, inadimplência 90 dias, saída voluntária, capital-dias, fechamento em centavos e saldo conciliado |
| SaaS / comunicações | Testes e preparação de planos, campanhas, outbox, Brevo e push; entrega real não homologada | Licença vinculada a cobrança conciliada, expiração/estorno, opt-in/opt-out e entrega/erro verificados em contas de teste autorizadas |
| Contratos, jurídico e regulatório | Produto se descreve como plataforma de gestão e não banco, porém prevê crédito e rateio coletivo | Parecer profissional baseado no fluxo real de recursos e titularidade, enquadramento regulatório/tributário, contratos e política de privacidade; revisar 147 cláusulas históricas sem absorção automática |
| Governança do release | PR #2 Draft; nenhuma autorização formal | Resultados de AT-01–AT-50 em staging, evidências assinadas, revisão humana de segurança/jurídico e aprovação formal antes de retirar bloqueios |

**Cuidado jurídico:** a caracterização comercial “não é banco” não dispensa análise de enquadramento de atividades de pagamento/crédito. O Banco Central disciplina instituições de pagamento e SEP, incluindo autorização para atividades reguladas; o enquadramento depende de quem recebe, mantém, intermedeia e movimenta fundos. Referências oficiais: [BCB instituições de pagamento](https://www.bcb.gov.br/estabilidadefinanceira/instituicaopagamento), [Resolução CMN 5.050/2022](https://www.bcb.gov.br/estabilidadefinanceira/exibenormativo?numero=5050&tipo=RESOLU%C3%87%C3%83O+CMN), [ANPD comunicação de incidente](https://www.gov.br/anpd/pt-br/canais_atendimento/agente-de-tratamento/comunicado-de-incidente-de-seguranca-cis). Este relatório não é parecer jurídico.

## 4. Próxima execução recomendada, sem mexer no banco

1. **M40520-A:** instalar/abrir o APK M40510 já fornecido; retestar cinco itens do M40500, com prioridade à falha do topo em login, logout e teclado. Anotar PASS/FALHA e versão instalada. Não vincular essa homologação a ativação financeira.
2. **M40520-B:** verificar apenas leitura da identidade do FastAPI e PostgreSQL **FR Finance** na porta 5433, sem senha em logs, sem reinícios, sem SQL novo, sem tocar FR Caixinha 2.2; obter aprovação operacional antes de qualquer manutenção.
3. **M40520-C:** verificar no provedor OCI, por consulta somente leitura e com credenciais já configuradas, se há VM RUNNING. Ausência de nova prova significa UNKNOWN, não automaticamente NO_VM. Caso não haja VM, desenvolver ainda offline sem gastar ou mudar rede.
4. **M40520-D:** continuar testes de segurança negativa, idempotência e restauração no PG18 **descartável da CI**, registro de prova por gate; concluir review jurídico/regulatório antes de qualquer piloto com dinheiro.
5. **M40520-E:** montar homologação segregada de staging e aceite humano dos 20+7+50 gates relevantes. Somente então deliberar GO/NO-GO para produção, via processo separado.

## 5. Integridade, escopo e referências

- Baseline M40510: [commit f5ed3be](https://github.com/fronassor-art/FRcaixinha-22---Gest-o-Financeira-Mobile-Android-iOS-e-Multi-Cloud-OCI-GCP/commit/f5ed3be1be5a22f0f9ff6230119dc45e95d39836); [CI 44308632625](https://github.com/fronassor-art/FRcaixinha-22---Gest-o-Financeira-Mobile-Android-iOS-e-Multi-Cloud-OCI-GCP/actions/runs/44308632625).
- Documentação: [M40510](FR_FINANCE_M40510_ANDROID_LOGIN_FIX.md), [M40500](FR_FINANCE_M40500_AUDITORIA_PACOTE_UNICO.md), [CP20261114](FR_FINANCE_CP20261114_CHECKPOINT_PRODUCAO_NO_GO.md), [CP20261117](FR_FINANCE_CP20261117_AUDITORIA_GITHUB_SEM_VM.md), [homologação MP](MERCADO_PAGO_HOMOLOGACAO.md), [Android release](FR_FINANCE_M21700_ANDROID_RELEASE_OCI.md).
- Esta auditoria **não** altera políticas RLS, status de migrations, matriz de evidências, nenhum arquivo de aplicação, workflow ou configuração de provedor; **não** promove um teste de CI a um aceite real.

**Resultado final:** `M40520_AUDITORIA=DOCUMENTARY_READ_ONLY`; `M40520_BASELINE=f5ed3be`; `M40520_CI_BASELINE=7_OF_7_PASS`; `M40520_ANDROID_PHYSICAL_FIX=UNATTESTED`; `M40520_LIVE=0_OF_20_ATTESTED_IN_MATRIX`; `M40520_PROVIDERS=0_OF_7_ATTESTED_IN_MATRIX`; `M40520_AT=0_OF_50_ATTESTED_IN_MATRIX`; `M40520_DB_WRITES=NONE`; `M40520_RESTARTS=NONE`; `M40520_PIX_REAL=OFF`; `M40520_PRODUCTION=BLOCKED`.
