# FR Finance — M37974–M37978 | Proteção da API móvel e notificações

**Ponto de partida:** Termux M37973 no commit 9540315, 615 testes aprovados, 109 SQL catalogados. Esta rodada altera código do FR Finance AI Studio apenas.

## Implementado
- M37974: política única de endereço de API. HTTPS com domínio de rede ou HTTP loopback de desenvolvimento; credenciais, paths, query strings, fragments, barras invertidas e domínios reservados são recusados sem ecoar segredos.
- M37975: autenticação no cliente e diagnóstico visual usam o mesmo validador. API inválida resulta em origem vazia; nenhum token é enviado para aquela URL.
- M37976: caixa de entrada rejeita resultados de JSON inválido e resposta de erro de rede depois da troca de sessão; não gera mensagens fictícias.

## Limites
- Não cria conta nem prova login E2E; a tela de notificações segue limitada a ambiente local.
- Não altera banco PostgreSQL ou OCI, SMTP, OAuth, Pix, licenças ou contratos.
- M37977: a tela de notificações agora descarta respostas assíncronas vencidas por refresh, troca de usuário, troca de papel e logout; usa sessão, papel, tenant, identidade e sequência. Uma resposta do contexto anterior fica invisível antes mesmo da limpeza por efeito.
- M37978: regressão específica da sequência e teste estático de integração da tela, sem prometer teste E2E em aparelho.
- Produção real e 20/7 gates permanecem BLOQUEADOS.

## Verificação
- npm run lint
- npx tsx src/tests/m37974_api_origin_notification_guard_ci.test.ts
- npx tsx src/tests/m37447_mobile_backend_diagnostic_ci.test.ts
- npx tsx src/tests/m19000_notifications_functional_ui.test.ts
- npx tsx src/tests/m37977_notification_race_ci.test.ts
- npx tsx src/tests/auth_context_security.test.ts

SQL_APPLY=NONE; PIX_REAL=OFF; REAL_ACTIVATION=OFF; PRODUCTION_NOT_AUTHORIZED.
