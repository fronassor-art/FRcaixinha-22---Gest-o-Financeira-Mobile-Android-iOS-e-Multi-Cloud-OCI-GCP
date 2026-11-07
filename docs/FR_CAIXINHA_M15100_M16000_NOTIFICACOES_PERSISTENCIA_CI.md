# AI Studio — M15100–M16000 | Persistência de Notificações em PostgreSQL Descartável

**Baseline informado pelo operador:** M15000 local \`acdee64\`, FastAPI PID 20220, PostgreSQL AI Studio 5433 pronto, nove contratos M7900–M15000 PASS, sem migrações/OCI/dinheiro real. PR #2 Draft.

## Entrega do pacote
A migração \`backend/staging_migrations/041_notifications_inbox_outbox_staging_ci_only.sql\` fica **FORA** da cadeia local \`backend/migrations\` e só pode ser executada na base \`frcaixinha_staging\` clonada de \`frcaixinha_ci\` na CI GitHub Actions.

1. Duas tabelas físicas: \`notification_outbox_staging\` e \`notification_inbox_staging\`, vinculadas por FK com unicidade e integridade transacional.
2. Índice de paginação keyset por destinatário, papel, tenant, data e UUID.
3. Deduplicação \`UNIQUE NULLS NOT DISTINCT\` para incluir avisos globais de plataforma.
4. Gravação de outbox/inbox em uma só transação, sem mensagem órfã.
5. Produtor CI sem privilégios de SELECT/INSERT direto, apenas RPC delimitada.
6. Guardas para evento/usuário/tenant/ciclo/papel e catálogo fechado de 10 tipos.
7. Templates fixos sem CPF, dados bancários, senha ou conteúdo livre.
8. Worker CI não pode marcar pagamento, conciliar banco ou modificar ledger.
9. Outbox mantém \`HELD_CI_NO_DELIVERY\`, origem não autenticada e efeitos financeiros falsos por CHECK.
10. RLS ENABLE/FORCE nas duas tabelas; sem acesso direto da aplicação à outbox.
11. SELECT da inbox filtrado pelo usuário/papel/tenant da transação do app.
12. Aplicação sem INSERT/UPDATE/DELETE/TRUNCATE direto na inbox.
13. Marcação de leitura somente por função CI que valida escopo, destinatário, papel, usuário ativo e membership ativo.
14. Idempotência de leitura, bloqueio de leitura por outro usuário/tenant.
15. Dez testes PostgreSQL com concorrência, replay, separação, Master, leitura, cursor e rollback.
16. Execução da mesma suíte em PostgreSQL 16 e PostgreSQL 18 descartáveis.
17. Rotas reais \`GET /api/v1/notifications\` continuam bloqueadas sem autenticação/dados persistidos.
18. Health \`GET /api/health/features/m16000\` declara capacidades de CI, sem declarar implantação ou entrega real.
19. CI de frontend, FastAPI, ZIP e APK preservada.
20. Nenhuma alteração ou migração no banco local Termux nem na OCI.

**Limitação de segurança crucial:** os GUCs \`app.current_user_id\`, \`app.current_role\` e \`app.current_tenant_id\` no teste simulado podem ser alterados por um cliente com credencial SQL. Portanto, os testes de RLS de staging **NÃO provam autenticação produtiva nem asseguram que um cliente malicioso com acesso ao banco não possa forjar identidade**. Antes de implantar, exigir papéis/segredos isolados, sessão autenticada pela API, proteção anti-injeção e prova completa de origem do evento. Superuser ainda pode modificar as tabelas.

## Pendências P0 e P1
- **P0:** autenticar eventos, produtor e destinatário de verdade, anti-spoof de contexto, migrar a proposta 041 para esquema de produção sob revisão/aprovação e backup verificável.
- **P0:** implantar caixa de entrada RLS persistente com servidor, identidade, API e ausência de falsa confirmação.
- **P1:** endpoints \`GET /notifications\`, cursor, \`mark-read\` e contadores autoritativos; integrar UI às respostas do servidor com revalidação após reativar app.
- **P1:** decidir calendário/quiet hours, canais, fornecedores, consentimentos LGPD, retenção e mecanismos de cancelamento.
- **P1:** e-mail, push (FCM/APNs) e WhatsApp Business somente com autorização e provas de contato; retries/DLQ, antispam.
- **P2:** homologação Android de Master/Admin/Membro, indicadores de mensagens não lidas reais, acessibilidade.
- **P0 financeiros preexistentes:** prova de conciliação bancária externa, OAuth Mercado Pago por empresa, idempotência econômica e ledger/fechamento, todos bloqueados.

**As 147 cláusulas e AT-01–AT-50 não são declarados cumpridos por estes ensaios.**
