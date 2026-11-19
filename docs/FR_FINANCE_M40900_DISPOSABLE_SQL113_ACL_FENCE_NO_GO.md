# FR Finance M40900 — ensaio de revogação SQL113 em PostgreSQL 18 descartável

**Base:** M40881 `81a632b` confirmado sincronizado pelo operador no Termux, sem escritas nem migrations. **PR #2 Draft; main preservada.**

## Insegurança real reproduzida

O pacote M40570 demonstrou que `app.current_*` é controlável por qualquer SQL sob `frcaixinha_app_role`; M40870 mapeou cinco superfícies relacionadas na SQL113, inclusive uma função `SECURITY DEFINER` e permissões de `INSERT` concedidas por coluna. Um `REVOKE INSERT ON table` genérico **não equivale** à revogação dos `GRANT INSERT(column,...)` históricos e poderia deixar escrita indevida disponível.

## M40900 — ensaio (SOMENTE na CI)

O runner verifica `GITHUB_ACTIONS=true`, `CI_M40900_DISPOSABLE=1`, `CI_M40560_DISPOSABLE=1`, `FRCAIXINHA_CI_ISOLATED=1`, flags reais todas OFF, DSN exato `postgres@127.0.0.1:55433/fr_m39067_disposable_ci`. Só então importa o driver e cria o esquema SQL112–113 sintético previamente coberto por M40560.

Ele **primeiro** demonstra leitura indevida por GUC de Master falsificado no app role. Depois, em banco efêmero, revoga `SELECT` na tabela `platform_saas_promotion_revisions`, `INSERT` **para as 14 colunas explicitamente concedidas**, e `EXECUTE` da função `frfinance_saas_new_admin_published_promotions()`. Verifica com `has_table_privilege`, `has_column_privilege` e `has_function_privilege`; mesmo após nova falsificação de GUC o SELECT, INSERT e a função precisam retornar SQLSTATE 42501. A role dona permanece capaz de consultar os dados sintéticos não alterados.

## Limites: ainda NÃO é migração de produção

A revogação isolada **desativa o recurso SaaS de promoções**, incluindo endpoints legítimos do app. Ainda não existe gateway SQL de identidade comprovável capaz de substituí-lo; o ensaio NÃO resolve sozinho os demais caminhos GUC/RLS, o emissor SQL M40730, nem a custódia de chaves. **É proibido aplicar as instruções de revogação ao PostgreSQL original.** Antes de um rollout real: inventário completo de ACLs e dependências, nova autoridade de sessão independente de GUC, plano de coexistência/rollback, backup e restauração verificados, SQL revisado e autorização explícita com janela operacional. Não há migrations de schema publicadas por este pacote.

**M40570 = NO-GO. M40730 = NO-GO. M40870 = NO-GO.** O M40840 mantém bloqueio de toda a pool financeira em produção; OTP/cifragem M40830 é laboratório. FR Caixinha 2.2 não é afetado. FastAPI permanece sem owner atestado, e APK M40860 requer teste físico.

`MIGRATIONS=NONE`; `ORIGINAL_DB_CONNECTIONS=NONE`; `ORIGINAL_DB_WRITES=NONE`; `SERVICE_RESTARTS=NONE`; `PIX_REAL=OFF`; `PAGAMENTOS_REAIS=OFF`; `ATIVACAO_REAL=OFF`; `PRODUCTION=BLOCKED`.
