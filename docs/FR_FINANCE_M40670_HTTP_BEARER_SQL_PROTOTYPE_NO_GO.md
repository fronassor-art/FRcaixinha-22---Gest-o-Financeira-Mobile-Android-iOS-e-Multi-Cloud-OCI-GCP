# FR Finance M40670 — Bearer HTTP e gateway SQL (protótipo sintético, NO-GO)

**Data:** 18/11/2026. **PR #2:** draft, sem merge. **Não há integração real.**

## Objetivo

Demonstrar uma ligação estritamente experimental, com ASGI/FastAPI independente, entre um cabeçalho HTTP Authorization: Bearer e uma função SQL parametrizada de privilégio mínimo em **PostgreSQL 18 descartável no GitHub Actions**.

O teste executa uma pequena aplicação FastAPI criada **dentro do arquivo de testes**. Não registra roteadores reais, não usa app.main, não cria contas reais, não carrega configurações do Termux, não modifica migrações, não abre a API financeira instalada e não aciona pagamentos. Todos os usuários, tokens, roles, dados, valores e credenciais são sintéticos.

## Evidências esperadas

- O papel SQL da aplicação não tem SELECT direto nas tabelas de contas, sessões, vínculos e lançamentos.
- A função SECURITY DEFINER possui search_path fixo, sem SQL dinâmico, com EXECUTE restrito e autenticação por hash do token.
- A identidade autorizada deriva do registro da sessão e do vínculo ATIVO no banco descartável, não de X-Role, X-Tenant, app.current_role, app.current_user_id ou outro GUC.
- Uma sessão de membro só obtém os lançamentos do próprio usuário na caixinha autenticada; um administrador vê apenas os lançamentos do seu tenant.
- Tokens inexistentes, expirados e revogados, conta suspensa, vínculo desligado, papel Master e tentativa de atravessar tenant falham fechados; a identidade com mais de um vínculo não muda de contexto apenas por passar outro tenant na URL.
- Respostas API não incluem nem token bruto nem hash e usam Cache-Control: no-store. A CI não imprime tokens, senhas de usuários ou dados de sessões.

## Impedimentos para integração real

O protótipo transmite o bearer bruto como parâmetro SQL, estritamente dentro de um runner descartável. **Isso NÃO é um desenho aceitável para implantação direta em produção**: é preciso resolver a exposição potencial em logs de SQL, telemetria, diagnóstico de erros, extensão do PostgreSQL, processos e pools. Um invasor que obtenha tokens ainda poderá se apresentar como o titular. Também faltam revisão da concessão de EXECUTE, modelo de autenticação e autorização entre papéis, rotação, revogação sob concorrência, rate limiting, prevenção de replay, isolamento de funções com SECURITY DEFINER, auditoria de todos os caminhos SQL, revisão de segurança independente e testes E2E com sessão real.

A arquitetura atual **continua vulnerável a GUC spoofing se um executor arbitrário obtiver acesso ao papel SQL da aplicação**. M40670 não corrige isso nas tabelas reais: a API atual ainda usa contexto RLS baseado em GUC e as rotas financeiras não passaram a chamar a função sintética.

## Gate de produção

- M40670_REAL_FASTAPI_ROUTES=NOT_MODIFIED
- M40670_BEARER_SQL_LOG_RISK=UNRESOLVED
- M40670_EXISTING_GUC_RISK=NOT_REMEDIATED
- M40670_ORIGINAL_PG_5433=NOT_ACCESSED
- M40670_MIGRATIONS=NONE
- M40670_SERVICE_RESTARTS=NONE
- PIX_REAL=OFF, PAGAMENTOS_REAIS=OFF, ATIVACAO_REAL=OFF, PRODUCTION=BLOCKED

A CI verde significa apenas que os controles sintéticos passaram. Antes de migração no PostgreSQL original ou integração das rotas financeiras será necessária **autorização explícita**, além da revisão de arquitetura e dos testes de segurança, autenticação e isolamento.
