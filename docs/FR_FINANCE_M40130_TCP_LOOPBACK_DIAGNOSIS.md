# FR Finance M40130 — diagnóstico de conexão TCP local após M40120

Data: 15/11/2026. Continuidade M40120, sem autorização de reinício.

## Evidência local observada

Termux nativo sincronizou M40120 no commit `7b8353e` e reportou:
- `M40120_HEALTH_FIRST_HTTP=HTTP_NO_RESPONSE`
- `M40120_HEALTH_SECOND_HTTP=HTTP_NO_RESPONSE`
- `M40120_STATUS=BLOCKED_HEALTH_NO_RESPONSE`

O diagnóstico **não confirma** que o FastAPI foi encerrado. O código HTTP antigo reduz conexão recusada, timeout, indisponibilidade ou falha de transporte ao mesmo status 0. Como as duas tentativas não receberam resposta, os checkpoints M39700/M40080 não foram consultados.

## Implementação

O M40130 faz exatamente duas tentativas curtas de conexão TCP IPv4 com `127.0.0.1:8000` (sem enviar dados), intercaladas por um GET de saúde do cliente HTTP allowlisted do M40090. A conexão é sempre fechada. Não são usados pacotes externos, /proc, ps, lsof, stdout de processos, variáveis de segredo, DSN, sockets no Debian, nem endpoints de prontidão que consultem banco.

Classifica as amostras TCP como `TCP_HANDSHAKE_ACCEPTED`, `TCP_CONNECTION_REFUSED`, `TCP_CONNECT_TIMEOUT`, `TCP_UNREACHABLE_OR_RESTRICTED` ou `TCP_CONNECT_UNVERIFIED`.

Se ambas recusarem, `BLOCKED_LOOPBACK_PORT_REFUSED_AT_TWO_SAMPLES` significa apenas que as duas tentativas pontuais não encontraram listener acessível naquela porta. Se o TCP aceitar conexões e HTTP não responder, `BLOCKED_TCP_ACCEPTS_BUT_HTTP_NO_RESPONSE` indica que algum listener aceitou a conexão, mas não foi comprovada a identidade do serviço. Se o estado mudar durante as amostras, não há conclusão estável.

A resposta `FR_FINANCE_ONLINE` tampouco comprova worktree, bytecode, sessão ou legitimidade para interromper ou reiniciar processo.

## Próxima ação

Rodar somente no Termux nativo, após sincronização de commit verificado:

```bash
python -B backend/scripts/frfinance_m40130_loopback_tcp_health_readonly.py
```

Mesmo `M40130_DIAGNOSTIC_EXIT=2` é resultado previsto e conservador. Não executar comandos `kill`, `pkill`, `uvicorn`, `service restart`, `pg_ctl`, migrações ou alterações de credenciais com base neste diagnóstico.

**Controles:** `FASTAPI_RESTART=NONE`, `DATABASE_CONNECTIONS=NONE`, `LOCAL_DB_WRITES=NONE`, `MIGRATIONS=NONE`, `PIX_REAL=OFF`, `PAGAMENTOS_REAIS=OFF`, `ATIVACAO_REAL=OFF`, `PRODUCTION=BLOCKED`. Bancos FR Finance PG18 porta 5433 e FR Caixinha 2.2 permanecem fora do escopo.
