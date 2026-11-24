# FR Finance — M40850 | Bloqueio de downgrade do DSN financeiro e pool em cache

**Base:** M40840 `e611abe`; origem FastAPI do Termux **NOT_ATTESTED**.

## Ameaça identificada

M40800 validava o usuário `frc_ai_app`, a porta 5433 e o banco `frcaixinha_aistudio_dev` **somente** quando `FRCAIXINHA_TERMUX_LOCAL_API=1`. Sem essa variável, qualquer DSN de homologação devidamente formatado retornava `NONPRODUCTION_UNATTESTED`, inclusive um destino com nome `*_prod` ou um papel privilegiado. Além disso, o construtor de pool validava DSN apenas na criação: um objeto `_db_pool` já em cache era retornado sem reavaliar a identidade declarada.

## Ajustes de defesa em profundidade

- Ambiente NÃO produtivo recusa sempre as roles `postgres`, `root`, `frc_ai_owner`, `frc_ai_auth`, `frc_ai_verifier` no DSN financeiro. Não aceita bancos com sufixo `_prod`/`_production`, bancos administrativos `postgres`/`template0`/`template1` ou nomes do projeto FR Caixinha 2.2.
- No endereço loopback porta 5433, apenas `frc_ai_app@frcaixinha_aistudio_dev` é elegível, mesmo quando a variável do Termux não estiver presente. Com a variável presente, a checagem rigorosa M40800 continua.
- `get_db_pool` reaplica a validação sintática quando há pool em cache e DSN configurado, **depois** da trava absoluta M40840 contra produção e flags financeiras reais.
- As mensagens de erro não expõem DSN, senha ou hostname; testes offline usam credenciais exclusivamente fictícias.

## Limites de segurança NÃO resolvidos

A verificação de DSN **não autentica o servidor PostgreSQL**, nem impede um servidor malicioso de imitar um nome/porta. Também não atesta a identidade de um pool que tenha sido criado por outro código e injetado no processo. Sem configuração explícita de Termux, um DSN de desenvolvimento não listado pode continuar `NONPRODUCTION_UNATTESTED`. O resultado positivo do teste é um guard sintático, não uma prova de isolamento de produção.

- **M40570:** GUC `app.current_*` permanece falsificável sob execução SQL arbitrária na role app (**NO-GO**).
- **M40730:** papel SQL de emissor comprometido continua capaz de gerar tickets sem PoP (**NO-GO**).
- FastAPI carregado, PostgreSQL original, segurança do host OCI, Vault, MFA Master, regularização jurídica, pagamentos reais e homologação Android ainda exigem provas independentes.

Não há mudanças em SQL, migrações, schema, roles ou permissões no PostgreSQL original, Termux, Debian, serviços, credenciais reais, CI secrets ou provedores. `MIGRATIONS=NONE`; `DB_WRITES=NONE`; `SERVICE_RESTARTS=NONE`; `PIX_REAL=OFF`; `PAGAMENTOS_REAIS=OFF`; `ATIVACAO_REAL=OFF`; `PRODUCTION=BLOCKED`. PR #2 Draft, sem merge.


## M40943 — fechamento da janela de DSN vazio com pool em cache (23/11/2026)

**Falha localizada no código-fonte:** a condição `if _db_pool is not None and settings.DATABASE_URL` ignorava o preflight M40800/M40850 quando um pool já existia e `DATABASE_URL` era apagado ou substituído por string vazia. Assim, um objeto de pool previamente inicializado poderia ser devolvido sem a revalidação sintática do destino na condição de DSN ausente.

**Correção segura no código-fonte:** para qualquer pool em cache, revalidar `settings.DATABASE_URL` incondicionalmente. DSN vazio ou malformado passa a ser recusado antes de devolver o objeto, sem fechá-lo, reiniciá-lo ou fazer SQL. Regressão sintética `test_cached_pool_cannot_bypass_guard_when_dsn_cleared_or_invalid` verifica ambos os casos mantendo o objeto de pool intacto. A trava M40840 de produção/flags continua sendo executada antes dessa verificação.

**Escopo/limites:** não há prova de integridade do objeto `_db_pool`, nem da identidade do servidor SQL, nem de remediação da GUC M40570 ou do emissor M40730. A correção é defesa em profundidade, não autorização de produção ou segurança do runtime em memória. Nenhuma migration, nova role, conexão ao banco original, sincronização Termux, reinício ou operação real foi iniciada por esta alteração.

`M40943_SOURCE_PATCH=APPLIED` · `M40943_TESTS=CI_REQUIRED_ON_EXACT_SHA` · `PIX_REAL=OFF` · `PAGAMENTOS_REAIS=OFF` · `ATIVACAO_REAL=OFF` · `PRODUCTION=BLOCKED`.
