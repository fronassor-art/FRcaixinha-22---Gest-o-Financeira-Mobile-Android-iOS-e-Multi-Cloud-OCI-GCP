# FR Finance — M40931: inventário fechado de rotas Master SQL (NO-GO)

**Continuidade de M40930**, sem modificar o PostgreSQL original, serviços, Termux, controles M40840 ou meios de pagamento. Este pacote cria um controle **estático de revisão de código** em CI, não uma aprovação criptográfica de operações nem proteção contra SQL arbitrário.

## Escopo observado no código FastAPI

O inspetor AST `backend/tests/test_m40931_master_route_inventory_ci.py` lê **todos os roteadores** em `backend/app/routers` e identifica rotas mutáveis (`POST, PUT, PATCH, DELETE`) cujo prefixo literal é `/master`. A matriz explícita é:

| HTTP / Master | Classificação de fonte | Proteção atual |
|---|---|---|
| `POST /master/admin-onboarding/transition-preview` | Simulação em memória | Dependência Master autenticado; nenhuma SQL de gravação identificada |
| `POST /master/admin-onboarding/preflight` | Pré-análise somente leitura | Dependência Master; `SELECT` via RLS não equivale a SQL origin atestado |
| `POST /master/license-prices` | Gravação comercial SaaS | Dependência M40930 exige HTTP 503 |
| `POST /master/support-session` | Break-glass proibido por contrato | Corpo deve **sempre** lançar proibição expressa |
| `POST /master/saas-promotions/draft` | Gravação comercial SaaS | Dependência M40930 exige HTTP 503 |
| `POST /master/saas-promotions/transition` | Gravação comercial SaaS | Dependência M40930 exige HTTP 503 |

O teste falha caso qualquer rota adicional de mutação Master apareça, desapareça, perca autenticação Master, omita M40930 nas três operações, introduza escrita SQL direta nas funções de prévia ou remova a proibição explícita de break-glass. Testes adversariais alteram a fonte apenas **em memória** e comprovam rejeição de nova rota não revisada e da remoção da dependência. Workflow específico `frfinance-m40931-master-route-inventory-ci.yml` executa via Python `unittest`, sem pip, banco, import FastAPI ou network.

**Limites importantes:** análise AST não impede execução arbitrária de SQL, manipulação por owner/superuser, funções delegadas que passem a escrever, novas rotas em módulos não registrados nem desvio direto de HTTP. Rotas de autenticação e de tenants não são certificadas por este inventário. Uma PR aprovada também não substitui proteção em runtime. No código real, as três rotas citadas já estão travadas pelo M40930. Nenhum teste positivo de autorização Master SQL independente existe na execução real.

## P0 a enfrentar em seguida

1. Identidade e autorização SQL *no PostgreSQL*: M40570 prova GUC forjável; M40730 emissor SQL legado contornável. Implementar e provar fronteira que não aceite simplesmente valores `SET LOCAL app.current_*` ou credenciais emissor em um processo compartilhado.
2. Segregação operacional de issuer/guardian/app, custódia assinada e aprovada por ator externo confiável, persistência transacional de nonce e autorização antes de qualquer alteração SaaS. M40928/M40929 continuam evidência **negativa**.
3. Homologação adversarial em PG18 descartável e depois staging isolado, com revisão independente, MFA e auditoria; somente após isso planejar substituição de M40930.
4. Manter M40840 inalterado até controle de identidade SQL e RLS aprovado e atestado. Preparação de staging/Mercado Pago sem pagamentos, tokens reais nem envio.

`PIX_REAL=OFF`, `PAGAMENTOS_REAIS=OFF`, `ATIVACAO_REAL=OFF`, `PRODUCTION=BLOCKED`. PR #2 Draft, main intacta; `ORIGINAL_PG18_CONNECTIONS=NONE`, `MIGRATIONS=NONE`, `SERVICE_RESTARTS=NONE`, `TERMUX_SYNC=NONE`.
