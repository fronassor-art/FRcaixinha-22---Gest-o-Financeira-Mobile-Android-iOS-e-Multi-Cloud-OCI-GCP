# FR Finance M40921 — separação de autoridade do broker SaaS (NO-GO)

## Checkpoint e objetivo

M40920 \`c53e943\` passou 2/2 jobs específicos e CI geral 7/7, mantendo a PR #2 Draft. O M40920 criou operações experimentais Master por token opaco, mas compartilhou a role NOLOGIN proprietária do broker de leitura M40910. Isso deu à mesma role o direito de ler ofertas e inserir revisões de campanhas. M40921 elimina a sobreposição **somente na CI PostgreSQL 18 descartável**.

## Ensaio no PostgreSQL 18 efêmero

Após os guards ambientais de M40900/M40910/M40920 e a aplicação do fence de ACL em \`fr_m39067_disposable_ci\` (\`127.0.0.1:55433\`), o novo runner:

1. Monta o protótipo de escrita M40920 já aprovado; não modifica o banco original.
2. Cria uma role \`m40921_writer_owner NOLOGIN NOINHERIT NOBYPASSRLS\` e transfere a propriedade das duas funções Master e da auditoria a ela.
3. Revoga todos os 14 privilégios INSERT por coluna previamente concedidos ao broker de leitura, remove sua policy de escrita e não concede participação do papel writer ao app.
4. Dá ao novo writer apenas as permissões necessárias para verificar digest de sessão existente e gravar revisões append-only; conserva a role reader para as ofertas de administradores.
5. Exige via catálogo que o reader não tenha INSERT nas 14 colunas, nem INSERT na auditoria, nem EXECUTE nas funções de escrita; o app não pode assumir o papel writer.
6. Exercita leitura válida do novo administrador, Master com token válido (DRAFT, PUBLISH e CANCEL), SQL GUC falsificado, membro/outsider/token expirado/revogado, revisão divergente, replay e revogação em tempo real, conferindo a auditoria.

O runtime real **não recebe** as funções, roles, grants ou revogações. Banco PostgreSQL 18 original, FR Caixinha 2.2 e processos de FastAPI são preservados.

## Riscos conhecidos e próximos gates

- A credencial Master válida ainda pode ser roubada e reutilizada. M40921 não implementa vinculação criptográfica de ação/dispositivo, segundo fator para publicar, assinatura externa ou aprovação antifraude.
- O emissor SQL M40730 continua vulnerável em seu próprio modelo; a separação entre roles \`NOLOGIN\` não recupera essa confiança.
- M40570 permanece NO-GO enquanto os demais caminhos de autorização GUC e a API real não forem removidos. O ensaio não substitui listagem Master nem roteadores HTTP nem plano de migração.
- A configuração de privilégios e custódia em PostgreSQL original não está comprovada. Antes de qualquer rollout exigir revisão independente, backups/restore ensaiados, inventário de ACL e reversão controlada, revisão jurídica, segurança do processo FastAPI e teste Android físico.

**M40570=NO-GO; M40730=NO-GO; HTTP=NOT_INTEGRATED; ANDROID_PHYSICAL=RETEST_REQUIRED.**

MIGRATIONS=NONE; ORIGINAL_DB_CONNECTIONS=NONE; ORIGINAL_ACL_CHANGES=NONE; LOCAL_DB_WRITES=NONE; SERVICE_RESTARTS=NONE; PIX_REAL=OFF; PAGAMENTOS_REAIS=OFF; ATIVACAO_REAL=OFF; PRODUCTION=BLOCKED.
