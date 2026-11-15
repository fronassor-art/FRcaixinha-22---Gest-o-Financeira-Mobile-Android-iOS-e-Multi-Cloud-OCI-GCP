# FR Finance M40040 — Resposta de confirmação incerta, consulta idempotente e isolamento documental

**Data:** 15/11/2026. **PR #2:** Draft. **Branch:** `atualizacao-ai-studio-9b46a63187`. **Checkpoint do Termux recebido:** M40030 foi aplicado por *fast-forward* de `ffd8643` até `3aa641b`; a segunda execução do verificador foi bloqueada porque já não estava no commit-base. Isso não comprova defeito no banco nem exige segunda sincronização.

## Objetivo

M40030 testou interrupções **antes** do `COMMIT` e retentativas de operações que sofreram rollback. M40040 demonstra outro caso: **a operação foi confirmada no banco descartável, mas a resposta detalhada não foi entregue ao solicitante do ensaio**.

É um teste de banco, não um servidor de produção nem uma entrega de rede real. O GitHub Actions descarta deliberadamente a saída do primeiro processo `psql` após o `COMMIT`; outra conexão faz a consulta de resultado por chave de idempotência. Não houve perda de pacote real, reenvio HTTP, reinicialização do processo servidor ou falha de conexão externa.

## Controles criados exclusivamente no PostgreSQL 18 descartável

`backend/tests/sql/m40040_disposable_ack_init_pg18_ci.sql` constrói, somente na base `frcaixinha_ci`/5432, uma tabela `m40040_ci.receipt_ack` com:
- vínculo de recibo documental anterior e identidade sintética da caixinha/revisor;
- chave de idempotência exclusiva por escopo e caixinha;
- impressão digital do conteúdo requisitado, validada no formato SHA-256;
- hora de registro emitida pelo banco e resultado imutável `CI_DOCUMENTARY_RECEIPT_UNVERIFIED`;
- campos fixos `session_authenticated=false`, `signed_human_consent=false`, `policy_approved=false`, `payout_enabled=false`, saldo disponível nulo;
- gatilho que rejeita comprovante incompatível com o recibo de origem; `BEFORE UPDATE OR DELETE` impede alteração ordinária;
- RLS com `ENABLE/FORCE ROW LEVEL SECURITY`, política `actor_db_role=current_user`, permissões `SELECT` e `INSERT` com colunas limitadas, sem concessão de `UPDATE/DELETE`.

A função `m40040_ci.inspect_uncertain_commit(key, fingerprint)` usa `SECURITY INVOKER` (não invoca privilégios adicionais) e faz **somente uma consulta** restrita ao papel do banco:
- `EXISTING_UNVERIFIED_RECEIPT_NO_NEW_WRITE`: existe a mesma chave para o mesmo revisor e conteúdo;
- `CONFLICT_DIFFERENT_REQUEST_NO_NEW_WRITE`: existe a chave, mas o conteúdo informado difere;
- `NOT_FOUND_OR_NOT_VISIBLE`: não existe um recibo visível ao papel;
- `INVALID_REQUEST_NO_EFFECT`: identificadores nulos/zerados ou hash malformado.

Nenhum resultado tem semântica de `APPROVED`, `PAID`, autenticação humana ou operação financeira.

## Sequência do experimento

1. Inicializa esquemas M40010, M40020 e M40040 num serviço PostgreSQL 18 descartável, validado por guardas sequenciais das flags `CI_M40010_DISPOSABLE`, `CI_M40020_DISPOSABLE`, `CI_M40030_DISPOSABLE` e `CI_M40040_DISPOSABLE`.
2. **Falha atômica intencional:** uma transação insere um recibo, tenta associar uma confirmação a outra chave e deve falhar com a mensagem `M40040_ACK_NOT_MATCHED_TO_COMMITTED_RECEIPT`. Um novo processo comprova que nem o recibo, nem seu comprovante ficaram gravados.
3. **Confirmação sem resposta detalhada:** outra transação grava recibo e confirmação na mesma unidade de commit. O workflow descarta a saída detalhada do `psql` e conserva apenas o estado do job, simulando uma resposta perdida do ponto de vista do chamador.
4. **Consulta posterior em nova conexão:** o mesmo papel lê o recibo pelo idempotency key e hash; mesmo conteúdo retorna o original, conteúdo diferente é conflito, chave não conhecida não retorna dado. A contagem permanece **um único** recibo.
5. **Sem vazamento:** outro revisor, administrador de outra caixinha e Master não podem ler o comprovante de um revisor diferente.
6. **Revogação somente proposta:** uma proposta marca o papel como interrompido na CI. Nova inserção é bloqueada pelo gatilho M40020; consulta do comprovante antigo permanece possível.
7. Uma auditoria independente exige contagem exata de recibos, ausência de privilégios de escrita indevidos, append-only e todas as flags de autorização/financeiras falsas.

## Limitações e cuidados

O ensaio não garante *exactly once* em pagamentos, não implementa confirmação real da API, autenticação de usuário em requisições separadas, consentimento assinado, reconciliação de provedor, saldo, liquidação, licença ou contrato ratificado. A identidade de revisor é um papel PostgreSQL `NOLOGIN` **simulado por superusuário na CI**; não é uma conta humana.

A separação dos patrimônios `PLATFORM_MASTER`, `TENANT_ADMIN_OWN` e `TENANT_COLLECTIVE` permanece. O ensaio grava apenas um documento sintético do patrimônio próprio do administrador; não transfere recursos e não autoriza revisão de patrimônio coletivo.

**Nenhuma tabela experimental deve ser aplicada ao PostgreSQL do FR Finance na porta 5433** ou ao PostgreSQL do FR Caixinha 2.2. Não foram criados endpoints, migrações, reinícios do FastAPI nem APK instalado. Os documentos selados do Caderno Mestre e Contrato Técnico M39100 permanecem intactos (330 requisitos / 2.310 etapas do catálogo).

## Arquivos

- `backend/tests/sql/m40040_disposable_guard.psql`
- `backend/tests/sql/m40040_disposable_ack_init_pg18_ci.sql`
- `backend/tests/sql/m40040_disposable_atomic_failure_pg18_ci.sql`
- `backend/tests/sql/m40040_disposable_verify_atomic_rollback_pg18_ci.sql`
- `backend/tests/sql/m40040_disposable_commit_without_ack_pg18_ci.sql`
- `backend/tests/sql/m40040_disposable_retry_resolution_pg18_ci.sql`
- `backend/tests/sql/m40040_disposable_visibility_pg18_ci.sql`
- `backend/tests/sql/m40040_disposable_stop_after_ack_pg18_ci.sql`
- `backend/tests/sql/m40040_disposable_final_audit_pg18_ci.sql`
- `backend/tests/test_m40040_uncertain_commit_source_ci.py`
- `.github/workflows/frfinance-m40040-uncertain-commit-ci.yml`

`M40040_TERMUX_ACCESS=NONE`; `M40040_ORIGINAL_DB_ACCESS=NONE`; `M40040_LOCAL_MIGRATIONS=NONE`; `M40040_FASTAPI_RESTART=NONE`; `M40040_REAL_APPROVAL=FALSE`; `PIX_REAL=OFF`; `PAGAMENTOS_REAIS=OFF`; `ATIVACAO_REAL=OFF`; `PRODUCTION=BLOCKED`.
