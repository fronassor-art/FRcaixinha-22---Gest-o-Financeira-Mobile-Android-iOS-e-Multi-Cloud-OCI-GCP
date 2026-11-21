# FR Finance M40932 — transação SQL Master READ ONLY antes de GUC (NO-GO)

20/11/2026. Sucessor dos pacotes M40930–M40931. **Somente código-fonte GitHub**, sem sincronização Termux ou mudança de ambiente original.

## Alteração real no FastAPI

O `get_rls_db_connection` de `backend/app/database.py` mantém M40840: antes de qualquer pool financeira, nega produção e flags financeiras que não estejam OFF. Depois da verificação de sessão e do início de uma transação (PostgreSQL `BEGIN`), quando `session.role == "MASTER"`, a **primeira instrução SQL** agora é:

```sql
SET TRANSACTION READ ONLY
```

Apenas em seguida o código define as três GUCs de contexto `app.current_user_id`, `app.current_role`, `app.current_tenant_id`, mediante `set_config(...,true)`. Assim, consultas Master no caminho existente ficam dentro de uma transação que o PostgreSQL classifica como *read-only*: tentativas ordinárias de INSERT/UPDATE/DELETE/DDL nesta mesma transação falham. Um erro ao estabelecer READ ONLY causa rollback, sem contexto Master nem entrega de conexão à rota.

Essa medida **não concede confiança a GUCs** nem impede que alguém que roubou o DSN do app abra outra transação read-write. Para isso são necessárias restrições de função/papel no servidor e fronteira de autorização independente. Outro privilégio, owner ou superuser pode contornar a proteção. O modo read-only é limitado **à transação autenticada de request**, não altera configuração global nem schema, não reinicia ou atualiza serviços no telefone.

As três gravações comerciais de Master continuam **HTTP 503** pela dependência incondicional M40930; a proibição de break-glass é mantida. Nenhuma rota foi liberada. O inventário AST M40931 detecta novas rotas Master alteradoras sem revisão. M40840 permanece bloqueado para produção.

## Prova de regressão

- `backend/tests/test_m40932_master_sql_readonly_ci.py` monta um pool e uma transação falsos em Python, sem import de cliente de rede operacional ou conexão com PostgreSQL. Assertivas: SQL `SET TRANSACTION READ ONLY` é emitido **antes** das GUCs Master; erro de ativação causa rollback sem liberar a conexão; fluxo TENANT_ADMIN não muda; M40930/M40840 continuam presentes.
- Workflow `frfinance-m40932-master-readonly-sql-ci.yml` usa apenas CI Linux efêmera e FastAPI/asyncpg instalados para import. Resultado da CI deve ser conferido antes de declarar PASS.
- O teste sintético não prova que o PostgreSQL de staging é seguro contra `SECURITY DEFINER`, `SET ROLE`, GUC spoof, owner/superuser, SQL dinâmico fora da dependência ou acesso direto com credenciais vazadas.

## Próximos gates de arquitetura (P0)

1. Revalidar funções SECURITY DEFINER, RLS/ACL/owners e resolver a identidade GUC falsificável M40570 e emissor SQL M40730 **dentro** da política do servidor SQL.
2. Segregar operacionalmente os logins app, issuer e guardian; ligar autorização Master a prova externa e log/nonce durável; não depender de SO_PEERCRED apenas por UID (M40929).
3. Testar o próprio código FastAPI e funções SQL autorizativas em PostgreSQL18 **descartável**, depois em staging separado, com credenciais comprometidas e ensaios de replay, concorrência e rollback.
4. Só após revisão independente e autorização separada elaborar migrations de produção. Não modificar o PostgreSQL original `:5433`, nem retirar M40840/M40930 com base em testes positivos isolados.

**Invariantes:** `M40840=BLOCKED`, `M40930_MASTER_WRITES=HTTP_503`, `PIX_REAL=OFF`, `PAGAMENTOS_REAIS=OFF`, `ATIVACAO_REAL=OFF`, `PRODUCTION=NO-GO`, `ORIGINAL_PG18_WRITES=NONE`, `MIGRATIONS=NONE`, `SERVICE_RESTARTS=NONE`, `TERMUX_SYNC=NONE`.
