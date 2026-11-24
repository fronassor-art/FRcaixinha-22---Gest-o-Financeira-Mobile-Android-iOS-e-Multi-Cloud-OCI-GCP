# FR Finance M40938 — ensaio HTTP real do painel Master e proteção SQL NO-GO

## Desenvolvimento realizado

Enquanto M40936 prova o cenário de SQL adversarial num PostgreSQL 18 descartável e M40937 apresenta os bloqueios à pessoa que administra a plataforma, **M40938 testa a integração real do FastAPI**, sem iniciar rede nem usar o PostgreSQL original:

- Requisita `GET /api/v1/master/launch-readiness` pela aplicação FastAPI realmente montada (`app.main.app`).
- Substitui **apenas a consulta do token** por uma sessão sintética. O guard `require_master` continua real: Master verdadeiro recebe relatório; Tenant Admin, membro, Master com `is_master=False` e Master com tenant vinculado recebem **403**.
- Garante `status=BLOCKED`, `sql_trust.status=NO_GO`, três pendências M40570/M40730/M40936 e `master_write_operations_enabled=False`.
- Intercepta `asyncpg.connect` e `get_db_pool` para causar falha se o endpoint tentar usar banco. Garante que DSN e segredos sintéticos não aparecem na resposta.
- Confere `Cache-Control: no-store` e mantém `POST /api/v1/master/license-prices` protegido por **503** sem override da dependência M40930, mesmo com sessão Master sintética.
- Confirma que M40840 rejeita `ENVIRONMENT=production` mesmo com PIX, pagamentos e ativação em OFF.

O teste não comprova o verificador de token de uma sessão real, não atesta ACL original, não substitui a verificação de RLS por papéis independentes, não testa a custódia de emissão de comandos nem integra Mercado Pago.

**Não há uma nova migration** nem modificação do código do banco: M40938 é cobertura de integração da aplicação já existente e das mudanças M40937, para prevenir regressões. É executado no GitHub Actions com dependências do backend, sem servidor FastAPI permanente, sem OCI e sem SQL real.

`PRODUCTION=BLOCKED`; `PIX_REAL=OFF`; `PAGAMENTOS_REAIS=OFF`; `ATIVACAO_REAL=OFF`; `M40840=NO_GO`; `M40930_MASTER_WRITES=503`; `ORIGINAL_PG_CONNECTIONS=NONE`; `MIGRATIONS=NONE`; `SERVICE_RESTARTS=NONE`; `TERMUX_SYNC=NONE`.
