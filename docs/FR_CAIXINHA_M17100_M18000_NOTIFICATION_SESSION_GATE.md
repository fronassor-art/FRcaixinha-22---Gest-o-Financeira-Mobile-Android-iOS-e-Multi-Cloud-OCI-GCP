# FR Caixinha AI Studio M17100–M18000 — sessão ↔ destinatário ↔ inbox CI

Checkpoint do proprietário: M17000 local d6ca755, FastAPI PID 2387, PostgreSQL exclusivo AI Studio 5433 pronto, 11/11 contratos HTTP PASS, migração 041 não aplicada e envios reais desligados.

## Componentes
1. backend/app/notification_session_gate.py: valida forma e consistência da sessão originada pelo get_current_session; não aceita override por cabeçalho, formulário, body ou query. O objeto AuthenticatedSession isolado não é prova de autenticação. O middleware depende de autenticação já realizada upstream.
2. backend/app/notification_ci_reader.py: adapter de leitura/paginação real por SQL e marcação de leitura, **sem integração HTTP**, recusado fora de GitHub Actions + frcaixinha_ci descartável + credencial SQL de homologação literal. Vincula no início de cada transação os GUCs de user/role/tenant fornecidos pelo teste, sobrepondo GUCs antigos. Consultas usam RLS no banco sintético, cursor MAC por destinatário e limite+1.
3. backend/app/routers/notifications.py: GET /api/v1/notifications/readiness autenticado, retorna somente capacidades indisponíveis, não retorna mensagens falsas nem dados pessoais; POST /api/v1/notifications/{id}/read autenticado e **503** até deployment legítimo; GET /api/v1/notifications continua **503** para sessão válida e **401** sem sessão.
4. Health /api/health/features/m18000: contrato declarativo com status de implantação, eventos, canais e finanças false.
5. Testes de papel Master/Admin/Membro, contexto contraditório, injeção de cabeçalho, janela de autorização e resultado HTTP 401/403/503. Mais ensaios físicos com PostgreSQL 16/18 descartáveis.

## Limitação crítica
A sessão de teste e os GUCs SQL ainda são simulados e alteráveis se a credencial SQL for obtida por terceiros. Mesmo que o adapter de CI passe, isso **não prova** autenticação produtiva anti-spoof, entrega real ou segurança de um banco público. A migração 041 continua exclusiva da CI. O código de leitura do CI jamais é chamado pelas rotas HTTP. Nenhuma tabela local ou produção foi migrada.

## Pendências não liberadas
- P0: identidade de origem service-to-service, evidência transacional persistente e anti-replay vinculados a serviço real, RLS/capacidade de leitura sob sessão autenticada e credenciais em Vault; migração revisada, backups e aprovação.
- P1: conectar API oficial às tabelas autorizadas; marcar lida, contador real, políticas de retenção, preferência/consentimento, calendário de notificações aprovado e workers.
- P1: e-mail/push/WhatsApp somente com opt-in aplicável, provas de entrega, filas/retentativas e auditoria independente.
- P2: homologação APK em Master/Admin/Membro e AT-01–50, acessibilidade e atualização da matriz de 147 cláusulas.
- Financeiro: Connect, webhooks, conciliação bancária tripla, ledger e fechamento seguem bloqueados.


## Prova física adicional
- backend/tests/test_m18000_notification_ci_adapter_postgres.py tem nove ensaios que só executam sob CI GitHub Actions com PostgreSQL frcaixinha_staging descartável; usa duas caixinhas sintéticas, Master e Member.
- Testes da consulta paginada, cursor, isolamento por papel/usuário, substituição de GUC antigo em conexão reutilizada, marcação de leitura idempotente, ausência de acesso direto à tabela outbox e ao cadastro users.
- O adaptador permanece proibido de entrar na rota de produção; usar credencial SQL diretamente permitiria forjar os GUCs e por isso a autenticação efetiva ainda exige desenho adicional.
