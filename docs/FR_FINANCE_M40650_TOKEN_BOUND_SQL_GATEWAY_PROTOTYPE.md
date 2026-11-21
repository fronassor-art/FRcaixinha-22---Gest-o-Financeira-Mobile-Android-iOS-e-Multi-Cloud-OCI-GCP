# FR Finance M40650 — proposta de gateway SQL vinculado a token (somente CI)

**Estado:** protótipo experimental e isolado. **Não implementado na API real. Não é migração. Produção NO-GO.**

## Evidências anteriores

- M40570/M40630: um papel SQL de aplicação pode modificar os GUCs `app.current_role`, `app.current_user_id` e `app.current_tenant_id`. Isso torna inseguro tratar esses valores, isoladamente, como prova de identidade dentro de SQL arbitrário.
- M40590/M40610/M40620: consultas literais, verificação de sessão HTTP e filtros explícitos reduzem superfícies de risco; não provam que todas as chamadas SQL possíveis são seguras.
- M40640: correção na validação de conta Master com papel financeiro ativo; sem reload do FastAPI local.

## Experimento M40650

Apenas o PostgreSQL 18 descartável do GitHub Actions recebe roles e tabelas **sintéticas** em um schema próprio. O preparo do fixture ocorre sob o proprietário descartável, mas os testes de ataque utilizam **outra conexão autenticada como `m40650_ci_login` sem superusuário**, que somente pode assumir `m40650_app`; isso evita uma falsa demonstração de elevação de privilégio ao executar `SET ROLE` de uma sessão superusuária. O papel `m40650_app` é `NOLOGIN`, sem privilégio direto de leitura das tabelas de sessão, vínculo e lançamentos, e sem associação ao papel proprietário. Pode apenas chamar `m40650.read_entries(token, tenant)`.

A função `SECURITY DEFINER`, com `search_path` restrito e consultas fixas/qualificadas, calcula o SHA-256 de um token de teste, confere sessão não revogada/não expirada, role ativo, tenant escolhido e vínculo `ATIVA`, e então retorna somente lançamentos correspondentes ao tenant e papel autenticado. Não utiliza custom GUCs como autoridade. O teste tenta SELECT/UPDATE direto, SET ROLE, falsificação dos GUCs, troca de tenant, token desconhecido, sessão revogada/expirada, papel Master e objeto temporário em `search_path`.

**Limites importantes:** essa prova não demonstra proteção dos atuais objetos e funções da API; o canal antigo continua exposto enquanto os privilégios de acesso direto/GUC forem válidos. Uma função `SECURITY DEFINER` pode introduzir novos riscos se aceitar SQL dinâmico, permitir efeitos colaterais, usar search path inseguro, conceder EXECUTE excessivo ou executar com credencial privilegiada. A presença do token dentro da conexão SQL exige modelo contra vazamento de token, logs, SQL injection e concorrência na pool. O token usado na prova é gerado e descartado no runner e nunca é registrado em logs.

## Critérios antes de qualquer integração real

1. Mapear todas as tabelas financeiras, papéis, grants, funções invocáveis e rotas; bloquear todos os caminhos SQL alternativos, não apenas a nova função.
2. Desenhar contrato explícito das leituras/escritas com menor privilégio, parâmetros tipados e políticas de autorização verificadas no servidor, com revisão adversarial de `SECURITY DEFINER` e concessões `EXECUTE`.
3. Integrar com o verificador de sessão real sem expor tokens em consultas/logs, rever tratamento de revogação, expiração, multitenancy e conexões da pool; testar autenticação real via bearer em PostgreSQL descartável.
4. Executar regressões completas, revisar SQL, aprovar formalmente eventual migração e somente então considerar implantação no banco original em janela autorizada. Não usar resultado verde deste protótipo como autorização.

**Guardas preservadas:** nenhuma conexão com FR Finance PostgreSQL local :5433, FR Caixinha 2.2, Termux, OCI, provedores ou FastAPI. Nenhum restart, nenhuma migração local, nenhum PIX/pagamento/ativação real. `PIX_REAL=OFF`, `PAGAMENTOS_REAIS=OFF`, `ATIVACAO_REAL=OFF`, `PRODUCTION=BLOCKED`.

## M40660 — extensão adversarial sem acesso ao banco original

O protótipo sintético agora inclui uma tabela de contas com status `ACTIVE`/`SUSPENDED`. A função de leitura exige **conta ativa**, além de token válido, vínculo ativo, papel da sessão e tenant. A prova negativa verifica: conta suspensa, mesma identidade com vínculos ativos em **duas caixinhas**, conta Master autenticada explicitamente com papel `TENANT_MEMBER`, tentativa de promover o papel da sessão sem vínculo e revogação de sessão após autenticação. O papel de aplicação continua sem SELECT nas tabelas de contas e sessões.

Esse teste apenas amplia a cobertura do protótipo e não altera `backend/app/routers`, migrações nem configurações do PostgreSQL local. PASS na CI não equivale à implementação de uma fronteira de confiança no código real, nem valida tratamento de concorrência, rotação de tokens ou o fluxo HTTP bearer completo.

