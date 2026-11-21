# FR Finance AI Studio — M38701–M38790 | Auditoria local PG18 043/044

## Evidência de entrada

- Checkpoint M38700: commit d51b354, 12.562 testes aprovados, 130 ignorados, 1 aviso e zero falhas.
- Os arquivos SQL 043 e 044 estão versionados, mas não existe atestado de aplicação no banco original.
- Não executar migração, backup, rollback, ativação ou liberação por causa deste relatório.

## Escopo implementado

O comando backend/scripts/aistudio_m38701_local_043_044_catalog_readonly.py tem modo OFFLINE sem acesso ao banco e modo LOCAL opcional, explícito e interativo. A conexão LOCAL usa somente 127.0.0.1:5433, frcaixinha_aistudio_dev, frc_ai_owner, PostgreSQL 18 e data_directory do Termux. Faz BEGIN TRANSACTION ... READ ONLY, timeout, consultas apenas aos metadados do pg_catalog e COMMIT, sem consultar linhas financeiras.

As observações cobrem as duas constraints de piso R$150 e a ausência de defaults da migração 043; a função de preço protegida e a execução restrita do legado; a auditoria de abertura de caixinha da 044, incluindo RLS, triggers imutáveis, idempotência, função de preço explícito e papéis de execução.

Os resultados COMPATIBLE_OBSERVED significam somente que os metadados consultados satisfizeram os controles previstos. Isso não prova que a migração específica foi aplicada, que os dados históricos foram validados ou que há condições para uso real. INCOMPLETE_OR_MISSING significa que a estrutura está ausente, parcial ou distinta; nunca reexecutar SQL automaticamente.

## Comandos Termux

Sem rede ou credenciais, na raiz do repositório:

    python backend/scripts/aistudio_m38701_local_043_044_catalog_readonly.py offline
    python -m pytest -q -p no:cacheprovider backend/tests/test_m38701_local_043_044_catalog_readonly_ci.py

Opcional, após sincronizar e somente com decisão consciente de consultar o PostgreSQL local:

    python backend/scripts/aistudio_m38701_local_043_044_catalog_readonly.py local AUTHORIZE_PG18_043_044_CATALOG_READ_ONLY

O prompt pede a senha do banco de forma oculta no próprio Termux. A senha não é gravada em arquivos ou argumentos de shell e não deve ser enviada ao chat ou GitHub. O programa passa a senha temporariamente ao processo psql por variável de ambiente: executar somente em telefone e sessão confiáveis, pois processos autorizados do mesmo usuário podem conseguir observar o ambiente do processo.

### Correção M38791 — entrada de senha no Termux

O checkpoint M38790 demonstrou que a versão original rejeitava caracteres
não ASCII e espaços na senha antes mesmo de tentar conexão, gerando
M38790_PASSWORD_INVALID. A correção aceita caracteres Unicode imprimíveis,
acentuação, símbolos e espaços sem alterar seu conteúdo. A senha continua
oculta, não é registrada no log e é rejeitada se estiver vazia, exceder 512
caracteres ou contiver controles invisíveis como NUL e quebra de linha.
Não há alteração na autenticação do PostgreSQL e não foi realizada
conexão real pelo CI. A senha correta continua exigida.

Caso o aviso PASSWORD_INVALID permaneça, conferir somente no próprio
Termux se foi digitada uma senha não vazia e sem quebras de linha. Caso
surja LOCAL_PG_QUERY_FAILED, a validação preliminar da senha já passou,
mas a causa poderá ser credencial incorreta, conexão ou consulta SQL.
Não enviar a senha nem outros segredos ao chat.

A auditoria não registra stdout ou stderr brutos do psql; falhas retornam somente causas codificadas. Não é destinada a cron nem CI com credenciais reais.

## Separação de evidências

- M38790_LOCAL_043_SCHEMA=COMPATIBLE_OBSERVED: estruturas mínimas esperadas para 043 presentes.
- M38790_LOCAL_044_SCHEMA=COMPATIBLE_OBSERVED: estruturas mínimas esperadas para 044 presentes.
- M38790_MIGRATION_PROVENANCE=NOT_ATTESTED: constante, mesmo se as estruturas forem compatíveis.
- M38790_PRODUCTION=BLOCKED: constante, mesmo com ambos os esquemas compatíveis.

O teste do GitHub usa psql falso (mock) e nenhuma conexão PostgreSQL real. Não há migração SQL nova, mutação do banco original, uso de OCI, SMTP, Brevo, Mercado Pago, Pix, pagamentos ou ativação.

Antes de qualquer aplicação futura de migrações 043/044, exigir separadamente inventário do estado, backup restaurável, verificação de dependências, aprovação de operação, transação e prova pós-aplicação. Esta etapa não concede essa autorização.

## M38792 — Falha de consulta PostgreSQL classificada com segurança

O checkpoint M38791 teve 12.602 testes PASS, 130 SKIP, 1 aviso e 0 falhas,
mas a consulta local retornou `M38790_LOCAL_PG_QUERY_FAILED`. Esse código
abrangia erro de senha no servidor, conexão, papéis, objetos ausentes ou
SQL de auditoria; não informa qual caso aconteceu.

Após a correção M38792, a própria consulta local informa exclusivamente uma
classe predeterminada `M38792_FAILURE_CLASS`, sem revelar a mensagem bruta
do PostgreSQL, dados de conexão sensíveis, senha ou texto SQL dinâmico.
A leitura continua estritamente sob modo somente leitura, com autorização
interativa; a execução automática de CI usa apenas retornos falsos do psql.

Categorias comuns: `AUTH_REJECTED` (autenticação do PostgreSQL rejeitada),
`CONNECTION_REFUSED` (porta/serviço indisponível),
`DATABASE_UNAVAILABLE`, `ROLE_UNAVAILABLE`,
`PERMISSION_DENIED`, `SQL_SYNTAX_ERROR`,
`SQL_FUNCTION_UNAVAILABLE`, `SQL_RELATION_UNAVAILABLE`,
`QUERY_EXECUTION_ERROR` ou `UNCLASSIFIED`.
Os códigos são uma pista preliminar; não representam autorização para alterar
credenciais, configurar servidores, editar funções ou migrar bancos.

Executar após sincronização, em sessão local confiável, sem enviar senha ao chat:

    python backend/scripts/aistudio_m38701_local_043_044_catalog_readonly.py local AUTHORIZE_PG18_043_044_CATALOG_READ_ONLY

Caso `M38792_FAILURE_CLASS` apareça, compartilhar apenas o código e os estados
de segurança. Nenhuma aplicação SQL, correção de senha nem mutação de dados
é realizada por esse comando.
