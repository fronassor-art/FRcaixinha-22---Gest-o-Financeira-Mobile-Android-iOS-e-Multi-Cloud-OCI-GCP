# FR Finance M40610 — exigir sessão PostgreSQL validada antes da conexão RLS

**Data:** 18/11/2026. **Base:** M40600 `f37002db5fe5e18a775749081b719d8c4a67d988`. **PR #2:** Draft; **NO-GO**.

## Defesa adicionada ao código

A dependência `get_rls_db_connection` agora falha com HTTP 401, **antes de obter a pool**, quando a sessão não traz `verified_session_id` UUID válido e não-nulo, origem `POSTGRES_TOKEN_HASH_REFRESH`, timestamps de verificação/expiração conscientes de timezone e vigentes, `user_id` UUID válido, papel conhecido e coerência entre MASTER/tenant. O código de `get_current_session` continua sendo a autoridade que produz as evidências após consulta de hash de bearer, checagem de revogação, expiração, membership e refresh no PostgreSQL. Nenhum cabeçalho ou payload passa a definir papel.

Não há migração; o controle é **código-fonte** e só será aplicado pelo processo de FastAPI após deploy/reload ou restart formalmente autorizados. Não se infere alteração do FastAPI atualmente em memória. Testes unitários só com objetos sintéticos não são prova de autenticação real nem de disponibilidade de staging.

## Risco importante ainda aberto

Esse guard evita que uma sessão legada/não comprovada chegue à pool, mas **não** torna o contexto `app.current_*` imutável dentro do PostgreSQL. A exposição M40570, em que um cliente SQL com a role financeira é capaz de alterar GUCs em comandos arbitrários, **permanece**; não reivindicar mitigação completa, nem aprovação de produção. Um modelo com funções/roles protegidas de contexto e SQL origin auditado será necessário para uma defesa independente robusta, sujeito a revisão, teste em banco descartável e autorização explícita antes de qualquer migração do PostgreSQL original.

Os dois PostgreSQL existentes são mantidos intocados. Sem gravação local, sem SQL aplicado, sem reinício FastAPI/PostgreSQL, sem mensagens, push, Pix, pagamentos ou ativação reais.

`M40610_GUC_SPOOF_EXPOSURE=NOT_REMEDIATED`; `PIX_REAL=OFF`; `PAGAMENTOS_REAIS=OFF`; `ATIVACAO_REAL=OFF`; `PRODUCTION=BLOCKED`.
