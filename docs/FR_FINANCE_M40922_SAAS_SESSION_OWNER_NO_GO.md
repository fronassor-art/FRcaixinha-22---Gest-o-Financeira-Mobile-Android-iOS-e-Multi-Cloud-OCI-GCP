# FR Finance M40922 — custódia de sessão segregada no laboratório (NO-GO)

## Motivo

Após o M40921, leitura e escrita SaaS são funções proprietárias de roles NOLOGIN separadas. Porém a role de leitura M40910 ainda controla a tabela sintética m40910.sessions: uma role de leitura comprometida poderia criar ou revogar tokens, inclusive MASTER, e por esse caminho alcançar a role de escrita sem ser membro dela.

O M40922 demonstra um terceiro papel, sem LOGIN, INHERIT ou BYPASSRLS, para propriedade da tabela e do schema de sessão. Esta separação é feita **somente no PostgreSQL 18 descartável GitHub Actions**, não no Termux.

## Escopo da prova

- Reutiliza o SQL113 sintético, fence M40900, broker M40920 e role split M40921 após todas as verificações de identidade de CI.
- Transfere \`m40910.sessions\` e o schema \`m40910\` para o custódio \`m40922_session_owner\`, preservando USAGE/SELECT explícitos para reader e writer, nunca INSERT/UPDATE/DELETE/TRUNCATE.
- Confere proprietário real pelo catálogo; testa \`has_table_privilege\`, \`pg_has_role\` e tentativas reais sob cada role com SQLSTATE 42501.
- Com emissor sintético privilegiado somente na CI, revalida leitura tenant-administrador, criação de draft, publicação, cancelamento, trilha de auditoria e revogação de sessão em operações seguintes.
- Não concede a role custodiadora a app, reader ou writer. App não consulta nem emite sessões por SQL.

## Riscos e pendências

**NO-GO:** Este ambiente não inclui um emissor real de sessões separado e atestado; um administrador/superuser SQL comprometido ainda pode forjar tokens. O M40730 permanece NO-GO. O M40570 continua NO-GO nos demais fluxos que confiam em GUC. Um token válido roubado continua permitindo leitura ou escrita conforme sua identidade, e a custódia sintética não cria segundo fator, autenticação de comando, criptografia de ação ou anti-replay. A separação de roles não mitiga esses riscos sozinha.

Não integra FastAPI, rotas de promoções, PostgreSQL original, configuração de produção, OCI/Vault/KMS ou pagamentos. Nenhum SQL/migration de aplicação é modificado. Antes de liberar são necessárias identidade fora da autoridade SQL comprometida, ACL auditada, plano reversível, homologação física Android e revisão jurídica/técnica.

**M40570=NO-GO; M40730=NO-GO; HTTP=NOT_INTEGRATED; ANDROID_PHYSICAL=RETEST_REQUIRED.**

MIGRATIONS=NONE; ORIGINAL_DB_CONNECTIONS=NONE; ORIGINAL_ACL_CHANGES=NONE; LOCAL_DB_WRITES=NONE; SERVICE_RESTARTS=NONE; PIX_REAL=OFF; PAGAMENTOS_REAIS=OFF; ATIVACAO_REAL=OFF; PRODUCTION=BLOCKED.
