# FR Finance M40070 — HTTP real do FastAPI e isolamento RLS em PG18 descartável

**Data:** 15/11/2026. **PR #2:** Draft. **Checkpoint confirmado pelo usuário:** M40060 sincronizado no Termux, commit `73da599`, `FAST_FORWARD`, sem migrações, SQL local ou reinício da API.

## Avanço sobre M40060

M40060 testava as rotas novas por `TestClient`, substituindo `get_current_session` e a conexão PostgreSQL por objetos sintéticos. M40070 acrescenta integração HTTP do **FastAPI original não modificado** com **duas conexões PostgreSQL reais dentro de um serviço PostgreSQL 18 descartável no GitHub Actions**.

O pacote possui um fixture SQL em `backend/tests/sql/m40070_disposable_auth_policy_pg18_ci.sql` que cria somente na base efêmera `frcaixinha_ci`: usuários, tenants, sessões, papéis mínimos e uma RLS de titularidade. As funções de vínculo e renovação de sessão do fixture reproduzem apenas suas **interfaces**, e não afirmam ser cópias de produção.

O driver `backend/tests/m40070_pg18_policy_runtime_ci.py` chama rotas por requisições HTTP internas do `TestClient`, **sem dependency overrides**. Exercita o fluxo real de código `get_current_session`, a conferência de hash do bearer no PostgreSQL, `auth_active_memberships`, `auth_refresh_session` e `get_rls_db_connection` com `set_config(..., true)` e RLS real da tabela `tenants`.

## Casos e proteção

- Master consulta apenas pendências do SaaS; administradores e membros não acessam sua rota.
- Titulares A e B consultam a própria caixinha; cross-tenant e Master no patrimônio alheio são rejeitados.
- Um portador de sessão TENANT_ADMIN sem titularidade comprovada é negado pela RLS, mesmo quando seu tenant declarado coincide.
- Token desconhecido, token expirado, token revogado e acesso sem bearer falham.
- Parâmetros falsos (`policy_ratified=true`, `pix_enabled=true`) não alteram bloqueios; POST de aprovação retorna 405.
- Dados sintéticos de tenants permanecem iguais; o único UPDATE funcional previsto é a renovação de prazo de sessão *dentro da base efêmera de CI*; nenhuma escrita financeira ou banco original.
- Resposta sempre mantém política não ratificada e aprovações, conciliação, lançamentos e PIX como `false`.

## Limites comprovados

**Isso é uma integração com PostgreSQL real, mas de dados e funções de autenticação simulados.** Não equivale a um teste com os esquemas reais FR Finance 5433, à identidade de uma pessoa, à revogação real entre sistemas, à assinatura de revisores, à conciliação com Mercado Pago ou à prontidão de produção.

Guardas exigem `GITHUB_ACTIONS=true`, `PGHOST=127.0.0.1`, porta `5432`, usuário inicial `postgres`, banco `frcaixinha_ci`, DSNs fixos de papéis CI, `CI_M40070_DISPOSABLE=1` e GUC `frfinance.m40070_ci=DISPOSABLE_ONLY`. Fora desse contexto, o driver recusa antes de abrir conexão. A fixture SQL também recusa outro banco, sessão sem privilégio e contexto sem GUC. Sem instalação local do fixture.

**Nenhuma migration em `backend/migrations`, `backend/local_migrations` ou banco do Termux**. Nenhum reinício do FastAPI, instalação APK, comunicação externa ou habilitação financeira. M39100 permanece intocado.

`M40070_AUTH_INTEGRATION=DISPOSABLE_CI_ONLY`; `M40070_ORIGINAL_DB_ACCESS=NONE`; `M40070_LOCAL_MIGRATIONS=NONE`; `M40070_REAL_REVIEW_APPROVAL=FALSE`; `PIX_REAL=OFF`; `PAGAMENTOS_REAIS=OFF`; `ATIVACAO_REAL=OFF`; `PRODUCTION=BLOCKED`.

## Ajuste de compatibilidade identificado pelo teste M40070

A primeira execução da integração revelou HTTP 403 para um proprietário válido, embora uma consulta de controle confirmasse que a RLS do PostgreSQL 18 permitia a leitura do registro. O driver `asyncpg` entrega o identificador PostgreSQL em um tipo UUID compatível, mas a rota M40060 usava `type(owner) is UUID`, exigindo a classe exata. O controle foi ajustado para `isinstance(owner, UUID)` **mantendo a igualdade obrigatória com o UUID do ator de sessão**. Strings, valores nulos e proprietários divergentes continuam proibidos. Um teste de regressão com subtipo de UUID complementa a integração PostgreSQL real. Nenhum poder financeiro foi adicionado.
