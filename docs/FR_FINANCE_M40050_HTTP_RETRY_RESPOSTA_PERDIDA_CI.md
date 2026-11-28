# FR Finance M40050 — Falha de comunicação HTTP, confirmação e retentativa idempotente

**Data:** 15/11/2026. **Branch:** `atualizacao-ai-studio-9b46a63187`, PR #2 Draft. **Checkpoint local confirmado:** M40040 sincronizado por *fast-forward* no commit `9ba74c3`. Nenhuma migração, escrita local, instalação ou reinício foi executado.

## Objetivo

M40030 demonstrou rollback após interrupção antes do `COMMIT`; M40040 demonstrou confirmação seguida de descarte simulado da resposta de um processo `psql`. O **M40050** adiciona uma camada HTTP de laboratório: o cliente realiza uma requisição para `127.0.0.1`, o servidor sintético grava o recibo no PostgreSQL descartável, **confirma a transação** e fecha a conexão HTTP **sem enviar a primeira resposta**.

A próxima requisição HTTP, com a mesma chave e o mesmo conteúdo, deve recuperar o recibo existente sem inserir outra linha. Uma requisição com a mesma chave, mas conteúdo diferente, deve retornar conflito.

**Não há simulação de pagamento, nem garantia de exatamente uma vez em provedor real.** A perda da resposta ocorre entre processos HTTP de ensaio na própria CI; não há implantação da API FastAPI, teste pela internet pública, Mercado Pago, PIX ou comunicação com usuário real.

## Arquivos

- `backend/tests/m40050_loopback_http_retry_pg18_ci.py`: cliente e servidor HTTP de teste usando biblioteca padrão Python e `psycopg`;
- `backend/tests/test_m40050_loopback_http_source_ci.py`: verificações estáticas de segurança, papéis simulados, porta e ausência de ações financeiras;
- `.github/workflows/frfinance-m40050-loopback-http-retry-ci.yml`: serviço PostgreSQL 18 descartável, inicialização de esquemas sintéticos M40010/M40020/M40040, teste de conexão e descarte da primeira resposta, nova requisição e auditoria final.

## Cenários comprováveis

1. **Pedido inicial:** o servidor HTTP de CI recebe um pedido documental com um token de laboratório; este é mapeado no próprio servidor para um papel PostgreSQL de teste `NOLOGIN`. O banco confirma, em uma transação, um recibo documental e seu comprovante sintético.
2. **Resposta perdida:** depois do fechamento da transação, o servidor encerra a conexão sem enviar cabeçalhos ou corpo HTTP. O cliente detecta a interrupção. Isso ocorre **exatamente uma vez** por execução de teste.
3. **Retentativa idêntica:** o cliente usa mesma chave, mesma ação e mesmo conteúdo. A consulta documental retorna `EXISTING_UNVERIFIED_RECEIPT_NO_NEW_WRITE` com HTTP 200, sem segundo recibo.
4. **Requisição alterada:** a chave anterior, com novo conteúdo, retorna HTTP 409 e `CONFLICT_DIFFERENT_REQUEST_NO_NEW_WRITE`. O hash é calculado no servidor de teste a partir de JSON canônico, não aceito diretamente como um atestado do cliente.
5. **Visibilidade e acesso:** o segundo revisor, um revisor de outra caixinha e o papel Master recebem `NOT_FOUND_OR_NOT_VISIBLE` ao consultar o recibo de A; ausência de token e tentativa de escrita por papel não designado são bloqueadas.
6. **Auditoria final:** consulta separada exige exatamente um recibo e um comprovante, IDs/nonce/idempotência originais, impressão digital correta e todos os campos de aprovação e pagamento falsos.

## Segurança e limitações

O fluxo HTTP é **exclusivamente loopback**; o código é um utilitário em `backend/tests`, não é importado pela API, não cria endpoint em produção e verifica `GITHUB_ACTIONS=true`, `PGHOST=127.0.0.1`, banco `frcaixinha_ci`, porta 5432, usuário `postgres` e cinco flags `DISPOSABLE_ONLY` antes da conexão. Se não estiver no ambiente previsto, falha de modo fechado.

Os tokens sintéticos `ci-actor-a`, `ci-actor-b`, `ci-tenant-b` e `ci-master` **não são credenciais reais**, não possuem autenticação criptográfica, não provam existência de usuários e não devem ser copiados para a aplicação. São apenas um modo determinístico de diferenciar os papéis `NOLOGIN` no ensaio. O acesso ao PostgreSQL usa credenciais exclusivas de serviço CI descartável, e não as do FR Finance original.

A garantia de não duplicação é restrita ao recibo sintético de uma requisição de laboratório. Não cobre múltiplos serviços, failover, reinicialização simultânea de servidores, balanceadores, entrega de notificações, conciliação com provedores ou conflitos de política financeira real. A implementação real exigiria autenticação por token-hash por solicitação, vínculos RLS server-side, política de revisores ratificada, proteção de concorrência, auditoria imutável e revisão de riscos.

**Patrimônios separados:** `PLATFORM_MASTER` permanece limitado ao SaaS; `TENANT_ADMIN_OWN` à remuneração própria do administrador; `TENANT_COLLECTIVE` não recebe nenhum poder de revisão neste ensaio. O rateio 15%/85% não é executado.

**Nenhum banco original foi acessado**, incluindo o PostgreSQL FR Finance porta 5433 e o FR Caixinha 2.2. Nenhuma migração foi aplicada. O FastAPI antigo, o APK instalado, os e-mails, mensagens e PIX real continuam inalterados. O Caderno Mestre e o Contrato Técnico M39100 permanecem selados.

`M40050_LOOPBACK_HTTP=CI_ONLY`; `M40050_ORIGINAL_DB_ACCESS=NONE`; `M40050_LOCAL_MIGRATIONS=NONE`; `M40050_FASTAPI_RESTART=NONE`; `M40050_HUMAN_AUTH=NOT_ATTESTED`; `M40050_REAL_REVIEW_APPROVAL=FALSE`; `PIX_REAL=OFF`; `PAGAMENTOS_REAIS=OFF`; `ATIVACAO_REAL=OFF`; `PRODUCTION=BLOCKED`.
