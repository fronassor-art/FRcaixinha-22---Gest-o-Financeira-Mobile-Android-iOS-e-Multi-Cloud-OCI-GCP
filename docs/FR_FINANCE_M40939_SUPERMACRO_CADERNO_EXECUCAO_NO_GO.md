# FR Finance — Supermacropacote M40939: caderno único de execução, pendências e NO-GO

## Escopo e checkpoint

Este caderno preserva **um repositório GitHub**, a branch `atualizacao-ai-studio-9b46a63187`, **um PostgreSQL original já existente** no Termux e nenhum segundo serviço/projeto concorrente. Não recriar bancos, diretórios, tenants ou infraestrutura; não reiniciar processos nem tocar no FR 2.2. Nenhuma permissão de operação real é inferida de testes estáticos, CI descartável ou código de interface.

O arquivo `FR_FINANCE_M40939_SUPERMACRO_GATES.json` é a fonte máquina-legível de **20 requisitos de produção** (sincronizados por AST com `backend/app/launch_readiness.py`) e **14 tarefas transversais**, agrupadas em seis fases: P0 SQL, P1 identidade, P2 OCI/CI, P3 Android, P4 provedores/jurídico e P5 Termux/migração.

**M40939 não é uma migration**: o auditor `backend/scripts/frfinance_m40939_release_gate.py` só lê arquivos do repositório, confere todas as dependências, impede etapas ausentes, repetidas ou cíclicas e falha se qualquer requisito pretender virar aprovação. `--mode approve-production` é sempre recusado com código 2. Não lê credenciais, não abre Postgres ou rede e não modifica Git nem sistema de arquivos.

## Dependências técnicas e externas ainda impeditivas

1. **M40570 / M40730 / SQL:** substituir autoridade por GUC falsificável, credenciais de app compartilhadas e emissão Master sem custódia independente. A contenção HTTP M40930/READ ONLY M40932 não é uma correção SQL completa. M40840 permanece bloqueado.
2. **M40936 — concluído source-only:** ensaio adversarial de revogação de INSERT SQL011/112/113 no PostgreSQL 18 descartável e CI passaram no SHA `ae4021d696a1`. Isso comprova somente o ensaio isolado; leitura por GUC falsificável e SECURITY DEFINER continuam bloqueadores.
3. **M40937/M40938 — concluídos source-only:** painel Master NO-GO e contrato HTTP read-only/RBAC passaram em CI no SHA `ae4021d696a1`; M40938: [workflow](https://github.com/fronassor-art/FRcaixinha-22---Gest-o-Financeira-Mobile-Android-iOS-e-Multi-Cloud-OCI-GCP/actions/runs/45650933241). Reteste Android físico continua pendente. Nenhuma destas provas resolve identidade SQL, custódia ou liberação real.
4. **Identidade e negócio:** MFA real, dupla autorização, integridade do cadastro e convites, recuperação, isolamento RLS, proteção contra replay, auditoria jurídica e LGPD.
5. **Infra:** staging OCI sem instância confirmada, HTTPS, isolamento, backup/restore comprovado, paridade de hashes e runtime/APK, homologação de Android.
6. **Mercado Pago:** contrato comercial e permissão do provedor, OAuth segregado, webhook, PSP_TRANSFER e conciliação não homologados, sem ativar PIX.
7. **Termux:** migrações originais exigem autorização específica, DDL revisado com rollback/backup restaurável e teste de staging. A sincronização segura já possui M40600 para *source-only fast-forward*, mas não deve ser confundida com migração, atualização de APK ou reload de serviço.

## Protocolo sequencial e retorno pelo Termux

**ETAPA A — GitHub:** no SHA base `ae4021d696a1`, M40936–M40940 e a CI geral foram validados; a CI principal [M40978](https://github.com/fronassor-art/FRcaixinha-22---Gest-o-Financeira-Mobile-Android-iOS-e-Multi-Cloud-OCI-GCP/actions/runs/45650929347) fechou 7/7. Este ajuste de rastreabilidade cria novo SHA e exige CI integral nesse SHA antes de sincronizar. PR #2 continua Draft, sem merge.

**ETAPA B — sincronização SOMENTE do código, quando aprovada:** usar **fora do Debian, no Termux nativo**, e apenas depois de validar SHA atual, branch, origem e FastAPI, o sincronizador M40600 *já existente* com `--expected-old` e `--target` com 40 caracteres. Ele faz fast-forward do código, **sem** migration, SQL, restart, app launch ou produção. Não publicar um comando com SHA alvo antes de a CI do mesmo SHA terminar com sucesso. Não executar em `/root/fr-finance` dentro do Debian.

**ETAPA C — diagnóstico somente leitura:** o operador já executou M40941 após M40600 no Termux nativo: SHA `ae4021d696a1`, branch/repositório pinados, árvore limpa, plano `VALIDATED_NO_GO`, runtime sem reload/atestado e nenhum acesso/escrita no DB. Essa é a última sincronização confirmada; um novo SHA deste pacote exigirá novo M40600 e M40941 somente após CI integral.

**ETAPA D — migrar o PostgreSQL original:** **NÃO AUTOMÁTICA**. Mesmo com CI verde e código sincronizado, o próprio manifesto impede `original_database_migrations_authorized=True`. Para cada DDL posterior, será exigida **autorização específica**, validação da identidade do banco original, backup íntegro, restauração ensaiada, diff SQL, roles e rollback, e revisão P0. Nenhuma migration nova foi criada no M40939.

**ETAPA E — continuidade:** quando a saída real do Termux for enviada em nova mensagem, revisar os códigos de retorno e o SHA antes de preparar o próximo pacote. Não há trabalho em segundo plano ou execução futura sem uma nova interação.

`PRODUCTION=BLOCKED`; `PIX_REAL=OFF`; `PAGAMENTOS_REAIS=OFF`; `ATIVACAO_REAL=OFF`; `MIGRATIONS=NONE`; `TERMUX_LAST_CONFIRMED=M40600_SOURCE_ONLY_SYNCED_AT_ae4021d696a1`; `RUNTIME=NOT_ATTESTED`; `M40840=NO_GO`; `M40930_MASTER_WRITES=503`; `NO-GO`.


## M40957 — integridade do plano de liberação

O validador original exige repositório, branch e nível de evidência canônicos,
as seis fases bloqueadas e as dependências mínimas das 14 tarefas existentes.
Nenhum gate de produção pode ser apresentado como concluído por código ou CI.
Somente as quatro tarefas de engenharia enumeradas podem registrar conclusão
source-only. Dependências inválidas, remoção de controles, fases adulteradas
e falsas conclusões são rejeitadas. A validação não altera o manifesto original,
não atesta runtime e não concede autorização para migração ou pagamentos.
