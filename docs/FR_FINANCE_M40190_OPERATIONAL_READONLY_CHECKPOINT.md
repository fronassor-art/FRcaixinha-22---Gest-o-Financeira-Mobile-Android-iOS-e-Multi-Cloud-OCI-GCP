# FR Finance M40190 — checkpoint operacional após recuperação dos serviços

Data: 15/11/2026; continuação de M40180, commit 429e77a.

## Evidências reais comunicadas pelo operador (Termux)

- PostgreSQL original PG18 FR Finance 5433 foi iniciado e identificado com SQL `BEGIN READ ONLY`, `FR_FINANCE_PG18=PASS`.
- Uvicorn FastAPI 127.0.0.1:8000 iniciou, `/api/health` respondeu `FR Finance / ONLINE`.
- M39700: `M39700_STATUS=PASS_READ_ONLY_RUNTIME_AND_TEST_AUTH`; seis rotas GET presentes; autenticação local de homologação pronta.
- M40080: import fingerprints batem com arquivos locais, mas `M40080_PROCESS_ORIGIN=NOT_ATTESTED_ANDROID_OR_UNKNOWN`; logo diagnóstico M40080 não pode fornecer prova completa do dono do processo. Essa lacuna não equivale a problema no banco, divergência de código ou falha das rotas.
- Zero migrações, produção e operações reais OFF.

## M40190 — desacoplar prontidão operacional e atestação do processo

O novo script GET-only combina apenas `/api/health`, `/api/health/checkpoint`, `/api/health/features/m40080`, `/openapi.json` e `/api/health/ready`. Revalida app e contrato em memória, as seis rotas GET esperadas, hashes locais versus snapshot importado e readiness de autenticação de homologação. A última verificação health evita afirmar prontidão se a resposta mudou durante o diagnóstico.

O diagnóstico de processo via `/proc`/Android é separado: `M40190_PROCESS_OWNER=NOT_ATTESTED_ANDROID_OR_UNKNOWN` e `M40190_GIT_SHA_IN_RUNNING_PROCESS=NOT_ATTESTED` mesmo quando o status operacional for `PASS_LOCAL_READONLY_FUNCTIONAL_SMOKE`.

Uma aprovação M40190 **não prova** permissão para login real, créditos, campanhas, revogação, envios, pagamentos, reconciliação, produção, publicação de APK ou mudanças contratuais. Nenhum endpoint protegido de membro/caixinha é requisitado; apenas o catálogo documenta as seis rotas GET.

Sem token, cookie, senha, POST, sessões de login, processo PID, DB SQL direta, reinício ou alteração de banco. O endpoint `/api/health/ready` possui checagens internas de metadados em leitura e só será consultado se a API, o checkpoint, o snapshot e as rotas corresponderem ao FR Finance.

## Uso

Após sincronizar M40190 na branch do AI Studio, **sem parar FastAPI**:

`python -B backend/scripts/frfinance_m40190_operational_readonly_checkpoint.py`

Execução apenas no Termux nativo `~/fr-finance`, sem Debian. O código retorna `0` para prontidão de smoke GET-only confirmada, `2` para bloqueio. Nenhum dos resultados muda gates financeiros: `PIX_REAL=OFF`, `PAGAMENTOS_REAIS=OFF`, `ATIVACAO_REAL=OFF`, `PRODUCTION=BLOCKED`.

No futuro, testes funcionais que criem sessões ou executem POST precisarão de escopo e autorização separados.
