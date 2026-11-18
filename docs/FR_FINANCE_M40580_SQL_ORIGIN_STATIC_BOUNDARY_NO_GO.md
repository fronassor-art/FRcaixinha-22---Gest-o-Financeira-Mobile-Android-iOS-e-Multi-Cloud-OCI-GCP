# FR Finance M40580 — guarda de SQL estático e origem de sessão (defesa parcial)

**Data:** 18/11/2026. **Base:** M40570 `814bc31`. **Produção:** NO-GO.

## Motivação

O M40570 reproduziu, exclusivamente no banco PG18 descartável, a possibilidade de um cliente SQL que já executa comandos arbitrários como `frcaixinha_app_role` modificar os custom GUCs `app.current_*` e então assumir contexto sintético de Master conhecido. **Não foi encontrado/demonstrado bypass de autenticação HTTP.** O risco comprova que os GUCs não são uma autenticação criptográfica independente.

## Proteção adicionada

O M40580 verifica via AST de Python que os **primeiros argumentos de SQL** das chamadas `conn.execute/fetch/fetchrow/fetchval/executemany` nos três módulos críticos `database.py`, `dependencies.py` e `routers/saas_promotions.py` sejam literais estáticos; rejeita strings formatadas, interpolação de f-string, concatenação de dados e nome de variável. Os testes verificam ainda hash do bearer, expiração/revogação, vínculo ativo, uso do `AuthenticatedSession` para definir `set_config(..., true)`, transação/rollback e reset da conexão. Trata-se de **guarda de regressão fonte**, não de auditoria dinâmica de SQL injection, análise de todos os módulos, comprovação de integridade da sessão ou bloqueio da falsificação GUC sob acesso SQL arbitrário.

Esta proteção **não altera o código operacional** de autenticação, banco, migrações ou Android. A CI é puramente offline sem qualquer conexão PostgreSQL.

**Controles ainda necessários antes de GO:** revisão integral de rotas com variáveis em SQL e privilégios efetivos, verificação de segredos DB, desenho independente de atestação da sessão e testes de staging com bearer real, MFA, RLS negativo e pen test. Não alterar PG18 original nem reiniciar serviços por conta desta auditoria.

`M40580_GUC_SPOOF_EXPOSURE=NOT_REMEDIATED`; `M40580_ORIGINAL_DB=NOT_ACCESSED`; `PIX_REAL=OFF`; `PAGAMENTOS_REAIS=OFF`; `ATIVACAO_REAL=OFF`; `PRODUCTION=BLOCKED`.
