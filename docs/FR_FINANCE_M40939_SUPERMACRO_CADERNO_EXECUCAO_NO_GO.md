# FR Finance — Supermacropacote M40939: caderno único de execução, pendências e NO-GO

## Escopo e checkpoint

Este caderno preserva **um repositório GitHub**, a branch `atualizacao-ai-studio-9b46a63187`, **um PostgreSQL original já existente** no Termux e nenhum segundo serviço/projeto concorrente. Não recriar bancos, diretórios, tenants ou infraestrutura; não reiniciar processos nem tocar no FR 2.2. Nenhuma permissão de operação real é inferida de testes estáticos, CI descartável ou código de interface.

O arquivo `FR_FINANCE_M40939_SUPERMACRO_GATES.json` é a fonte máquina-legível de **20 requisitos de produção** (sincronizados por AST com `backend/app/launch_readiness.py`) e **14 tarefas transversais**, agrupadas em seis fases: P0 SQL, P1 identidade, P2 OCI/CI, P3 Android, P4 provedores/jurídico e P5 Termux/migração.

**M40939 não é uma migration**: o auditor `backend/scripts/frfinance_m40939_release_gate.py` só lê arquivos do repositório, confere todas as dependências, impede etapas ausentes, repetidas ou cíclicas e falha se qualquer requisito pretender virar aprovação. `--mode approve-production` é sempre recusado com código 2. Não lê credenciais, não abre Postgres ou rede e não modifica Git nem sistema de arquivos.

## Dependências técnicas e externas ainda impeditivas

1. **M40570 / M40730 / SQL:** substituir autoridade por GUC falsificável, credenciais de app compartilhadas e emissão Master sem custódia independente. A contenção HTTP M40930/READ ONLY M40932 não é uma correção SQL completa. M40840 permanece bloqueado.
2. **M40936:** ensaio de revogação de INSERT da role de aplicação para SQL011+SQL112+SQL113 em PostgreSQL 18 descartável; ainda exige CI dinâmica e arquitetura para leitura/SECURITY DEFINER.
3. **M40937/M40938:** painel do Master e verificação HTTP de RBAC + trava HTTP503, todos sem ativação; CI específica e homologação física Android ainda necessárias.
4. **Identidade e negócio:** MFA real, dupla autorização, integridade do cadastro e convites, recuperação, isolamento RLS, proteção contra replay, auditoria jurídica e LGPD.
5. **Infra:** staging OCI sem instância confirmada, HTTPS, isolamento, backup/restore comprovado, paridade de hashes e runtime/APK, homologação de Android.
6. **Mercado Pago:** contrato comercial e permissão do provedor, OAuth segregado, webhook, PSP_TRANSFER e conciliação não homologados, sem ativar PIX.
7. **Termux:** migrações originais exigem autorização específica, DDL revisado com rollback/backup restaurável e teste de staging. A sincronização segura já possui M40600 para *source-only fast-forward*, mas não deve ser confundida com migração, atualização de APK ou reload de serviço.

## Protocolo sequencial e retorno pelo Termux

**ETAPA A — GitHub:** completar as CIs M40936, M40937, M40938, M40939, todas as CIs relevantes no mesmo SHA e a CI geral Android (sem `cancelled`/erro). Reprovar qualquer evidência incompleta. Merge da PR #2 não está autorizado.

**ETAPA B — sincronização SOMENTE do código, quando aprovada:** usar **fora do Debian, no Termux nativo**, e apenas depois de validar SHA atual, branch, origem e FastAPI, o sincronizador M40600 *já existente* com `--expected-old` e `--target` com 40 caracteres. Ele faz fast-forward do código, **sem** migration, SQL, restart, app launch ou produção. Não publicar um comando com SHA alvo antes de a CI do mesmo SHA terminar com sucesso. Não executar em `/root/fr-finance` dentro do Debian.

**ETAPA C — diagnóstico somente leitura:** após sincronização, executar, **no Termux**, `python -B backend/scripts/frfinance_m40939_release_gate.py`, que relata `NO_GO`, total de requisitos e nenhum banco acessado. Registrar HEAD, branch e marcadores de bloqueio para retorno ao ChatGPT. Não enviar tokens ou URLs de banco nos logs.

**ETAPA D — migrar o PostgreSQL original:** **NÃO AUTOMÁTICA**. Mesmo com CI verde e código sincronizado, o próprio manifesto impede `original_database_migrations_authorized=True`. Para cada DDL posterior, será exigida **autorização específica**, validação da identidade do banco original, backup íntegro, restauração ensaiada, diff SQL, roles e rollback, e revisão P0. Nenhuma migration nova foi criada no M40939.

**ETAPA E — continuidade:** quando a saída real do Termux for enviada em nova mensagem, revisar os códigos de retorno e o SHA antes de preparar o próximo pacote. Não há trabalho em segundo plano ou execução futura sem uma nova interação.

`PRODUCTION=BLOCKED`; `PIX_REAL=OFF`; `PAGAMENTOS_REAIS=OFF`; `ATIVACAO_REAL=OFF`; `MIGRATIONS=NONE`; `TERMUX_SYNC=NONE`; `M40840=NO_GO`; `M40930_MASTER_WRITES=503`; `NO-GO`.


## M40957 — integridade do plano de liberação

O validador original exige repositório, branch e nível de evidência canônicos,
as seis fases bloqueadas e as dependências mínimas das 14 tarefas existentes.
Nenhum gate de produção pode ser apresentado como concluído por código ou CI.
Somente as quatro tarefas de engenharia enumeradas podem registrar conclusão
source-only. Dependências inválidas, remoção de controles, fases adulteradas
e falsas conclusões são rejeitadas. A validação não altera o manifesto original,
não atesta runtime e não concede autorização para migração ou pagamentos.
