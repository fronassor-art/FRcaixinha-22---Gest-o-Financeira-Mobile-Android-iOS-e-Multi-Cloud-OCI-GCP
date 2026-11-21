# FR Finance M40230 — matriz negativa de autorização entre perfis e caixinhas

Data: 15/11/2026. Continuação do M40220 PASS (12/12 HTTP 401 sem credenciais) e M40210 PASS (33 rotas documentadas, 2 declaradas ocultas).

## Escopo

- Executar na CI isolada um TestClient sintético com os routers originais de caixinha, crédito especial e caixa exclusivo, sem importar o app principal nem provocar startup operacional.
- Identidades fictícias MASTER, TENANT_ADMIN, TENANT_MEMBER e duas caixinhas UUID fixas; dependency_overrides de sessão e DB para impedir consultas ao PostgreSQL.
- Negar acesso do Master às áreas de caixinha, de administrador/membro à área Master, de perfis vinculados ao tenant B aos dados do tenant A, de membros aos painéis exclusivos de admin e de admins à caixa de oportunidades privadas do membro.
- Negar acesso de admin que não seja titular ativo, mesmo quando a sessão pertence à própria caixinha. O banco sintético devolve outro titular e apenas a consulta permitida ao campo `admin_user_id`.
- Testar rejeição de POST sintéticos de publicação, cancelamento e revogação de campanhas/grants quando solicitados por perfil ou caixinha não autorizados. Não gera campanhas ou destinatários reais.
- Preservar rejeição com `FR_FINANCE_SPECIAL_CREDIT_SANDBOX=OFF`, mesmo para um administrador titular simulado.

A CI também incorpora regressões anteriores sobre M40220 (401 anônimo), M40060 (rotas ocultas e revisão não ratificada), M39090 (caixas exclusivos), M39020 (RBAC de crédito) e M39033 (fluxo inteiramente simulado).

## Limitações

**Não comprova RLS do PostgreSQL original nem a autenticação real dos usuários.** As identidades e conexões são substituídas por objetos sintéticos, e a CI não tem acesso ao aparelho. O teste M39033 cria registros *apenas* em objetos Python simulados, não em qualquer banco. A sessão sintética `POSTGRES_TOKEN_HASH_REFRESH` é somente um atributo testado, não uma sessão PostgreSQL emitida.

O script `backend/scripts/frfinance_m40230_role_rls_source_readonly.py` executa exclusivamente leitura AST do código no Termux: confirma guardas de sessão e tenant no backend e `set_config(...,true)` transacional, rollback, commit e reset da pool. Isso é uma verificação de fonte; não substitui teste RLS com linhas reais.

Não acessar PGDATA legacy FR Caixinha 2.2, não abrir conexão SQL do Termux, não criar contas, tokens, credenciais, notificações, PIX, empréstimos, migrações ou serviços. Segurança financeira e produção seguem bloqueadas.

## Operação

Sem reiniciar o Uvicorn: sincronizar M40230 na branch AI Studio e executar apenas no Termux **nativo**:

`python -B backend/scripts/frfinance_m40230_role_rls_source_readonly.py --source-only`

Resultado esperado `M40230_SOURCE_BOUNDARIES=PASS_SOURCE_BOUNDARIES_ONLY_NOT_RUNTIME_RLS`. O status não autoriza escrever em banco nem provar RLS com sessões. A fase posterior exige desenho separado de verificação real sob perfis autenticados existentes, com políticas de privacidade e autorização para qualquer criação de sessão.
