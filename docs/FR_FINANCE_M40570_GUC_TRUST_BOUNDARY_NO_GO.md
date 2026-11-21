# FR Finance M40570 — fronteira de confiança SQL GUC (NO-GO)

**Data:** 18/11/2026. **Base:** M40560 `cae64077b863d17beeb1391921c0303d87394486`. **Natureza:** teste adversarial fictício, exclusivamente GitHub Actions/PostgreSQL 18 descartável. **Sem alteração do banco original.**

## Evidência M40560 no aparelho

O operador confirmou `M40560_TERMUX=SYNCED` e HEAD `cae6407`, sem DB writes, migrações, reinícios ou operações reais. Os testes M40560 de permissões no PG18 descartável haviam passado, mas eles **injetavam GUCs como owner sintético**. Não comprovaram procedência de contexto diante de SQL arbitrário sob a role app.

## Confiança atual

O FastAPI `get_current_session` verifica bearer por hash de token no PostgreSQL, revogação, expiração, vínculo ativo e renovação. `get_rls_db_connection` toma os valores de `AuthenticatedSession`, os define com `set_config(..., true)` numa transação e limpa a conexão. **Não há prova nesta auditoria de que um usuário HTTP consiga escolher esses valores.**

O SQL113, porém, exige `app.current_role='MASTER'` e `rls_is_master(app.current_user_id)`. Valores `app.current_*` são **custom GUCs configuráveis em uma sessão SQL comum**. Portanto, se um invasor conseguir executar SQL arbitrário como `frcaixinha_app_role` e souber um UUID de Master, poderá forjar o contexto RLS nessa sessão. O cadastro Master consultado pela função não autentica a origem do UUID. Essa hipótese de ameaça deve ser tratada como **fronteira de confiança**, não como alegação de ataque HTTP comprovado.

## O que o M40570 verifica

O teste reproduz em um banco descartável, com UUIDs aleatórios e tabela sintética, um papel app sem contexto Master que não vê linhas; após mudar `app.current_role` e `app.current_user_id` por SQL **sob o próprio papel app**, a visibilidade muda. A execução não altera SQL112/113, FastAPI, dados locais, OCI ou prove dores. Um teste verde significa **exposição documentada**, não correção.

**Critério técnico de desbloqueio:** auditoria de ausência de SQL arbitrário na API, restrição de credenciais e papéis no runtime, desenho de ligação não falsificável ao contexto de sessão (por exemplo, papel protegido de contexto, ou outro mecanismo validado por especialista), testes adversariais da mitigação em PostgreSQL descartável, e teste de sessão autenticada real em staging com MFA, sem tokens/segredos nos relatórios. Não alterar PGDATA ou migrar tabelas sem aprovação e rollback ensaiado.

**Gates:** `M40570_GUC_SPOOFING=EXPOSURE_REPRODUCED_DISPOSABLE`; `M40570_RLS_NOT_INDEPENDENT_AUTHENTICATOR=CONFIRMED`; `M40570_HTTP_BEARER_BYPASS=NOT_TESTED`; `PRODUCTION=BLOCKED`.
