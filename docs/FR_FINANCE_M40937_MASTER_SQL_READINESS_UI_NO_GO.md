# FR Finance M40937 — bloqueios da fronteira SQL visíveis ao Master (NO-GO)

## Mudança de produto — aplicativo Android/web + FastAPI

O relatório `GET /api/v1/master/launch-readiness` já apresentava **20 gates** sem habilitar operações. M40937 mantém o total e suas categorias, mas acrescenta `sql_trust`, um conjunto separado de bloqueios P0 de SQL.

O Master visualiza, no painel de conclusão do aplicativo, **“Segurança SQL: NÃO HOMOLOGADA — NO-GO”**, com as pendências M40570 (GUC falsificável), M40730 (custódia de emissor/autorização não atestada) e M40936 (revisão de privilégios somente em PostgreSQL descartável). O painel **não** apresenta switches de ativação, concessão de privilégios, credenciais, valores financeiros nem status enganoso de recursos reais.

O backend devolve `status=NO_GO`, `evidence=SOURCE_ONLY_NOT_RUNTIME_ATTESTED` e **cinco booleanos obrigatoriamente falsos**: identidade GUC, revogação direta de INSERT SaaS atestada, aprovação Master independente, ACL de staging atestada e operação Master habilitada. A resposta não chama PostgreSQL, provedores ou rede; não lê segredos de ambiente. Flags de liberação eventualmente definidas no ambiente **não** alteram os valores.

O parser TypeScript trata uma resposta nova que tente alegar `READY`, `LIVE_ATTESTED` ou algum booleano verdadeiro como **inválida**, e rejeita ausência dos bloqueios críticos. Se o Android conversar com um FastAPI antigo que não inclui `sql_trust`, o cliente aplica um padrão **NO-GO** sem supor homologação — compatibilidade retroativa sem enfraquecimento.

## Ensaios

- `backend/tests/test_m40937_master_sql_readiness_ci.py`: status sempre bloqueado mesmo com ENVIRONMENT=production, flags reais ON ou declaração arbitrária de aprovação; resposta sem segredo; M40840 preservado.
- `src/tests/m40937_master_sql_no_go_ui_ci.test.ts`: parser, rejeição de falso status verde, valores inválidos, resposta antiga, escopo Master e texto não homologado.
- `.github/workflows/frfinance-m40937-master-sql-readiness-ui-ci.yml`: executa essas provas em GitHub Actions, sem provedor, sem PostgreSQL e sem aplicativo instalado.

**Observação de segurança:** A interface apenas informa a ausência de evidência e não atesta a existência de ACLs seguras. M40936 é ensaio de banco descartável, não uma autorização de migration. P0 M40570 e M40730 permanecem NO-GO.

`PRODUCTION=BLOCKED`; `M40840=BLOCKED`; `M40930_MASTER_WRITES=HTTP_503`; `PIX_REAL=OFF`; `PAGAMENTOS_REAIS=OFF`; `ATIVACAO_REAL=OFF`; `ORIGINAL_PG_CONNECTIONS=NONE`; `MIGRATIONS=NONE`; `SERVICE_RESTARTS=NONE`; `TERMUX_SYNC=NONE`.
