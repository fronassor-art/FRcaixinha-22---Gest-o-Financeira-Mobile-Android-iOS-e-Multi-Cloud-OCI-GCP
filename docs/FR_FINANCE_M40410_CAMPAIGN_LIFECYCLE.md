# FR Finance M40410 — campanhas e respostas em CI descartável

Este pacote dá continuidade à homologação após M40400 (sincronizado no Termux).
Executa **a API FastAPI original**, login com senha sintética, seis tabelas SQL110
e as regras SQL111 no PostgreSQL 18 descartável do GitHub (`frfinance_ci_credit:5432`).

Para testar a lógica positiva, o script M40410 faz um `patch.object` **somente
na memória do processo CI** do predicado `_enabled`. O ambiente e a configuração
seguem `FR_FINANCE_SPECIAL_CREDIT_SANDBOX=NO`, `PIX_REAL=OFF` e produção bloqueada.
Isso não é uma autorização de ativação local, de staging nem de produção.

Valida: campanhas por caixinha, visibilidade individual dos membros A/A2/B,
respostas INTERESTED e DECLINED, duplicidade e alteração tardia negadas,
preferência de PUSH desativada, recusa de validade vencida e além do ciclo,
publicação idempotente, cancelamento, revogação, outbox sempre BLOCKED_EXTERNAL,
nenhum empréstimo ou lançamento contábil produzido.

**Limites:** ambiente CI descartável; sem teste físico da escrita no APK, sem
alteração real do PostgreSQL do celular, sem despacho por push/e-mail/SMS/WhatsApp.
PR #2 Draft. Não rodar o script M40410 no Termux ou no Debian.
Banco original frcaixinha_aistudio_dev:5433 preservado. Sem migrations locais.