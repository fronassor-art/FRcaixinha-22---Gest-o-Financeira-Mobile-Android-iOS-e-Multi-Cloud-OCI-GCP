# FR Finance — CP20261117 | Auditoria ampla do desenvolvimento no GitHub — SEM VM

**Data:** 17/11/2026. **Projeto:** FR Finance AI Studio, separado do FR Caixinha 2.2. **Branch:** atualizacao-ai-studio-9b46a63187. **PR #2:** aberta em Draft, sem merge. **Baseline inspecionado:** 0d7276be61e185b4ad8acd74d94738ee3cc9da40. **Correção posterior:** 0f96e888a079582ffb2133851360eae40462eff0.

## Decisão operacional

O operador **interrompeu o Termux** e informou **não haver VM OCI criada**. Esta auditoria **não chamou a OCI** e não verificou contador de instâncias no provedor: o estado de ausência da VM vem do operador. **Nenhuma VM foi criada, nenhuma migração ou alteração no banco foi executada.** Permanecem PRODUCTION=BLOCKED, PIX_REAL=OFF, PAGAMENTOS_REAIS=OFF e ATIVACAO_REAL=OFF.

A auditoria M40240 ficou interrompida **antes da consulta ao banco**. Primeiro, o commit esperado se tornou antigo porque a branch recebeu 13 commits de OCI; segundo, uma constante SHA incorreta no comando do chat causou bloqueio, embora os blobs reais estivessem idênticos. Script SHA correto 59d141a067b979f30300288d94ceda9f82da8229; SQL SHA 4cfa98e3536ad539bba969236f1e3ef8bfe9c5e6. A última sincronização comprovada no Termux foi M40230 28b16e9. O teste de catálogo live M40240 continua NOT_EXECUTED. Não pedir senha, não reiniciar PG/FastAPI e não sincronizar o telefone durante este checkpoint.

## Auditoria de escopo do repositório

Árvore Git completa, sem truncamento: **1.753 arquivos**, incluindo **401 docs**, **202 arquivos backend/app**, **467 testes backend**, **161 scripts backend**, **200 arquivos src, dos quais 89 testes**, **69 arquivos Android**, **97 workflows GitHub Actions** e **6 arquivos infra**. Inspeção de estrutura, contratos e arquivos prioritários; não equivale a revisão individual de todas as linhas de código nem a pentest.

Matriz atual **330 itens com IDs estáveis**:
- 57 exigências atuais originais, sendo 29 Caderno e 28 Contrato Técnico.
- 49 aditivos atuais, sendo 25 Caderno e 24 Contrato: **106 exigências vigentes**.
- 147 cláusulas históricas da frente 2.2; não se tornam vigentes automaticamente.
- 20 gates técnicos; 7 gates externos; 50 cenários AT-01 a AT-50.

**Evidência independente de produção declarada na matriz:** 0/20 gates técnicos, 0/7 externos, 0/50 cenários AT. Esses índices medem a aprovação operacional documentada, não o percentual de código pronto. O script CP20261117 impede promoção silenciosa.

## Resultado por frente

| Frente | Evidências | Pendências não resolvidas |
|---|---|---|
| Governança/Git | PR #2 Draft, branch ativa, histórico fast-forward sem perda | Não fazer merge ou release; atualização da matriz exige revisão humana |
| CI | No baseline 0d7276b: workflow geral AI Studio **7/7 jobs SUCCESS** (frontend, API, PG18 descartável, RLS, APK debug) | Testes sintéticos não comprovam dispositivos e provedores reais |
| M38701 | Três runs do mesmo workflow falharam no baseline por assert textual antigo M38801 | **CORRIGIDO M40250** commit 0f96e88: launcher inalterado; **321 testes PASS**, run 44071249698 |
| Identidade e RBAC | M40220 12/12 respostas HTTP 401 anônimas no Android; M40230 testes sintéticos intertenant | MFA Master, aprovação independente, usuários autenticados/RLS real, revogação E2E e testes de conta faltam |
| Banco FR Finance | PostgreSQL 18 exclusivo 127.0.0.1:5433/frcaixinha_aistudio_dev; CI SQL e 6 tabelas crédito / 16 políticas | M40240 catálogo live pausado, paridade SQL110–113, backup/restauração e RLS de duas caixinhas sem reatestação |
| Crédito Especial/Extraordinário | Rotas FastAPI, campanhas, preferência de push, recusa/interesse, UI e CI sandbox | Campanhas e restrições de ciclo em sessão real, revisão jurídica e push efetivo ainda sem E2E |
| SaaS Master | Preços mensal/anual independentes, promoções e rascunhos | Assinatura, checkout, fatura, expiração, estorno e conciliação do provedor não provados |
| Caixas segregados | Componentes/rotas Master e administrador, rotas ocultas M40060 | Saldos e extratos reconciliados, autorizações de revisores e pagamentos reais não existem como prova |
| Cotas/Price/rateio | Regras de mínimo R$150 definido por ciclo, Price com Decimal e rateio 15%/85% em testes | Fechamento com lucro líquido elegível, capital-dias, inadimplência, perdas e estornos finais não homologados |
| Mercado Pago/Pix | Preparação Connect, webhook, idempotência, CI sem dinheiro real | OAuth real, Vault, HTTPS, 3 fontes, Money Out e consentimentos do provedor ausentes |
| Notificações | Código de canais; diagnóstico FCM voluntário sem guardar token; SMTP/DNS em CI | Entrega e retorno reais, consentimentos e opt-out auditado, callbacks autorizados |
| Android e iOS | React/TypeScript, Capacitor 8, APK debug CI, pacote debug .aistudio; Gradle exige assinatura release separada e HTTPS | Teste de upgrade e três perfis no aparelho, release AAB/APK, Play e iOS não atestados |
| OCI | Scripts observador e criador A1 com guard persistente; testes offline; região alvo sa-saopaulo-1 | **VM AINDA NÃO CRIADA**, sem staging, TLS, Vault, backup OCI, logs e monitoramento comprovados |
| LGPD/segurança/jurídico | Sessões, RLS e guards no código, múltiplas regressões CI; Caderno e Contrato mestres versionados | Consentimentos, revisão de 147 históricas, pentest, RIPD, parecer regulatório/tributário pendentes |

### Achados e divergências confirmados

1. Falha CI M38701 era incompatibilidade entre teste legado e inicializador M40180, não prova de falha no runtime. A atualização M40250 preservou a regra segura de iniciar FastAPI somente se o socket der ECONNREFUSED.
2. Bloqueio M40240 foi erro de SHA literal e checkpoint desatualizado; blobs não foram modificados, SQL live não executado.
3. Documento CP20261114 registrava ausência de prova de rotas/404. Depois houve M39700/M40190/M40210/M40220 no aparelho: seis rotas GET, 33 combinações visíveis, duas rotas intencionalmente ocultas na fonte, 12 recusas anônimas comprovadas. Fluxo autenticado e publicação de campanha **ainda não comprovados**.
4. Auditoria antiga M37693 cobre 57 requisitos originais. Para validade atual, utilizar a matriz de 330; não reduzir a 281 ou marcar anexos aprovados.
5. Scripts de OCI/CI não criam VM só por estarem no GitHub; agendamento criador usa variáveis de habilitação explícitas. Esta auditoria não ligou nenhuma variável ou credencial.
6. Produto é software de gestão, não banco; o rótulo não substitui avaliação jurídica se crédito, intermediação ou operações financeiras vierem a ser lançados.

## Pendências P0 e ordem de continuidade, sem VM

**Concluído agora, GitHub:** corrigir M38701 com CI verde; registrar versão e limites da auditoria; adicionar gate offline de 330 itens, requisitos de fonte e bloqueio de produção.

**Prosseguir em GitHub sem VM:** a) regressões RBAC com sessões sintéticas de duas caixinhas; b) campanha individual / validade / opt-out / pressão de notificações em CI, sem envio; c) Price, auditoria financeira, cancelamento, reexecução e idempotência com dados fictícios; d) revisão de UI/UX Android e falhas de rede com testes simulados; e) documentação do SQL local versus migrações e contrato; f) backup/restauração em PostgreSQL descartável; g) conformidade LGPD e gestão de segredos em fonte.

**Bloqueado pela ausência de VM e infraestrutura:** implantação backend pública, DNS/HTTPS válido, ingress TLS/webhook, Vault de tokens, banco staging independente, restauração OCI, testes de carga e disponibilidade, autenticação real em staging, observabilidade/alertas e E2E com provedores.

**Bloqueado por autorização externa/usuário:** mercado pago Connect e Money Out, recebimento Pix, envio FCM/SMTP/WhatsApp/SMS efetivo, contas reais, documentos assinados, revisão jurídica, testes físicos e aceites AT-01–AT-50.

**Pendente no Termux, mas expressamente pausado:** M40240 read-only no PG18 original; identidade de processo Android sem atestação completa; qualquer novo teste de banco deve ser retomado separadamente, sem migrações implícitas.

## Checkpoint final

GITHUB_HEAD_BEFORE_AUDIT=0d7276be; M40250_CI=321_PASS; PR2=DRAFT; MAIN=NO_MERGE; M40240_LIVE_SQL=NOT_RUN; OCI_VM=NOT_CREATED_PER_OPERATOR_NOT_CLOUD_ATTESTED; 330_ITEM_MATRIX=UNPROMOTED; LIVE_GATES=0/20; EXTERNAL_GATES=0/7; AT_E2E=0/50; PRODUCTION=BLOCKED.

**Fontes detalhadas:** o arquivo CP20261114_CHECKLIST_INTEGRAL_330.json lista os 330 IDs e seus critérios; o relatório CP20261114_CHECKPOINT_PRODUCAO_NO_GO.md organiza P0-01 a P0-20 com provas de saída. Este novo checkpoint é um complemento de evidências e decisões, não substituição das exigências nem aceite jurídico.
