# FR Finance M40620 — rastreamento estático do SQL em todas as rotas

**Data:** 18/11/2026. **Base:** M40610 b11b9493b2cffbfc89255948a300f9b23fcf0e83. **PR #2 Draft; produção NO-GO.**

## Por que ampliar o scanner

O M40580 protegia cinco módulos críticos (database.py, dependencies.py, saas_promotions.py, loans.py e contributions.py). A revisão da árvore do backend encontrou 25 módulos Python no diretório routers. O M40620 passa a revisar todos automaticamente, incluindo novos arquivos, inspecionando chamadas diretas .execute/.executemany/.fetch/.fetchrow/.fetchval. Consultas devem vir de literais estáticos, e os argumentos de dados devem continuar parametrizados.

Exceção explícita e limitada: member_lifecycle_sandbox.py possui um encaminhador \`_fetch_request_rows(conn, sql, *args)\` com um \`conn.fetch(sql, *args)\`. O guard verifica que ele continua sendo o único encaminhador nesse módulo, com **exatamente dois** chamadores que fornecem texto SQL literal sem interpolação. Qualquer encaminhamento externo, contagem adicional ou argumento não literal falha na CI. Esse controle cobre os 25 módulos de roteadores para chamadas SQL diretas, mas não examina todo o grafo de dados de todas as funções auxiliares em \`backend/app/\`, o conteúdo de PL/pgSQL ou a possibilidade de SQL arbitrário por credenciais vazadas.

## Limites de segurança

O M40620 é guard de regressão estática, não faz tracing dinâmico, não prova ausência de SQL injection e não corrige a capacidade de alterar custom GUCs \`app.current_*\` sob comandos SQL arbitrários do papel app. O achado M40570 continua \`GUC_SPOOF_EXPOSURE=NOT_REMEDIATED\`. O M40610 continua exigindo sessão verificada no código; a mudança só estará efetiva no FastAPI quando autorizado um reload/restart.

Testes somente em GitHub Actions, leitura AST, sem banco de dados, sem credenciais, sem migração, sem reinícios; Termux e os dois PostgreSQL originais preservados. PIX_REAL=OFF; PAGAMENTOS_REAIS=OFF; ATIVACAO_REAL=OFF; PRODUCTION=BLOCKED.

## M40620 — correção após primeiro bloqueio da CI

A primeira execução encontrou **5 chamadas de SQL dinâmico estático por concatenação** em `routers/master.py` (registro de administradores, registro de caixinhas e contagem de portfólio SaaS). Esses cinco trechos foram substituídos por consultas SQL literais, mantendo os mesmos filtros e parâmetros `$1` a `$4`. Não houve evidência de SQL injection explorável nos trechos originais; a alteração visa impedir que concatenações futuras de valores de usuário sejam introduzidas sem serem detectadas. A guarda deve agora validar todas as 25 rotas e a exceção restrita do encaminhador de homologação. A aplicação original não foi recarregada, nem o PostgreSQL alterado.
