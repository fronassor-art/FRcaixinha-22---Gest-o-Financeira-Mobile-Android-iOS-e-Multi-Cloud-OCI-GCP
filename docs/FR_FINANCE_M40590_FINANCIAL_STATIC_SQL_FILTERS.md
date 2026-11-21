# FR Finance M40590 — filtros de empréstimos, cotas e contribuições com SQL fixo

**Data:** 18/11/2026. **Base:** M40580 (`10071dfe`). **PR #2:** Draft. **Produção real:** NO-GO.

## Motivação e mudança

A revisão dos módulos de rotas encontrou três trechos onde o SQL era montado por concatenação de fragmentos **estáticos controlados pelo servidor** (um para empréstimos, dois para cotas/contribuições). Não se demonstrou SQL injection nesses trechos; porém, o padrão dificulta uma auditoria automática capaz de barrar futura inserção de um fragmento variável.

O M40590 troca cada construção por **SQL textual fixo**, mantendo os JOINs, campos, ordenações e restrições de `tenant_id`. A distinção administrador/membro foi parametrizada por `$2::boolean = FALSE OR (... m.user_id=$3::uuid AND m.role='TENANT_MEMBER' AND m.status='ATIVA')`, onde os três parâmetros são derivados da URL de tenant previamente autorizada e da sessão **verificada pelo backend**, nunca usados para compor texto SQL. Resultado esperado: administrador visualiza o tenant autorizado; membro visualiza somente registros de seu próprio vínculo ativo.

A guarda AST M40580 foi ampliada para os módulos `routers/loans.py` e `routers/contributions.py`, total de cinco módulos críticos. O M40590 acrescenta sete testes de fonte/segurança e um teste real de **24 combinações fictícias** no PostgreSQL 18 **descartável** da CI. O banco de CI usa porta 55434, usuários aleatórios e cinco memberships sintéticos; não consulta registros reais nem executa serviços do FR Finance.

## Limites

A alteração de código operacional só valerá após **deploy/restart autorizado**, que **não ocorrerá nesta etapa**. Os testes exercitam os filtros SQL e não equivalem a autenticação real, enforcement RLS com produção ou liberação de operação financeira. A exposição de GUCs do M40570 permanece **não mitigada**. O PostgreSQL original em `:5433`, o outro PostgreSQL do FR Caixinha 2.2, os processos FastAPI/Android e as migrações não são modificados.

**M40590_MIGRATIONS=NONE; M40590_LOCAL_DB_WRITES=NONE; M40590_SERVICE_RESTARTS=NONE; PIX_REAL=OFF; PAGAMENTOS_REAIS=OFF; ATIVACAO_REAL=OFF; PRODUCTION=BLOCKED.**
