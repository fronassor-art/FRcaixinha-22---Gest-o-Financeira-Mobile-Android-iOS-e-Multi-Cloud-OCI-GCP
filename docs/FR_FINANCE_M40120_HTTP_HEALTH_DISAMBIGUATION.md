# FR Finance M40120 — Desambiguação somente HTTP do FastAPI no Termux

Data: 15/11/2026. Continuação do M40110. PR #2 continua em rascunho; sem autorização de merge, reinício ou produção.

## Evidência de origem

- M40110 sincronizado no Termux: commit 719ef12.
- O script M40110 respondeu `M40110_STATUS=BLOCKED_UNKNOWN_API` antes de qualquer ps/lsof.
- Essa saída significa que `/api/health` não confirmou `FR Finance / ONLINE` na verificação de entrada. Ela não revela se ocorreu timeout, HTTP 404, resposta não JSON, outro app ou erro.
- M40100 havia identificado previamente o FastAPI como FR Finance. As duas observações são feitas em instantes diferentes; nenhuma autoriza inferência causal sobre PostgreSQL ou sobre o processo.

## Novo diagnóstico

O script `backend/scripts/frfinance_m40120_http_health_disambiguation_readonly.py` roda somente no **Termux nativo**, depois de `git pull --ff-only`.

Usa exclusivamente o cliente HTTP preexistente do M40090: GET para `127.0.0.1:8000` com allowlist fixa e proteção contra redirecionamento/proxy; nenhuma chamada fora do loopback.

Faz duas leituras de `/api/health`. Se não forem HTTP 200 com identidade exata `FR Finance / ONLINE`, informa classes de status HTTP e identidade sem mostrar o JSON. Não tenta ler sockets nem processos. Se houver identidade estável, consulta apenas os códigos HTTP dos checkpoints M39700 e M40080 e verifica a saúde novamente. Nunca usa status HTTP 200 como prova de código carregado nem concede permissão de reinício.

**Interpretação:** `BLOCKED_HEALTH_NO_RESPONSE` sugere ausência de resposta local naquele instante, não prova interrupção do FastAPI. `BLOCKED_HEALTH_ROUTE_NOT_FOUND` registra apenas o código 404. `BLOCKED_HEALTH_APP_IDENTITY_UNVERIFIED` não identifica qual aplicativo respondeu. `BLOCKED_BOTH_RUNTIME_MARKERS_404_OWNER_UNVERIFIED` significa que as duas rotas faltam, mas a titularidade da porta continua não comprovada.

Não são executados: ps, lsof, /proc, instalação de pacotes, conexões PostgreSQL, operações de pagamento, migrações, sinalização/reinício do FastAPI ou alteração no Android.

## Gate imutável

`FASTAPI_RESTART=NONE`; `RESTART_AUTHORIZED=FALSE`; `DATABASE_CONNECTIONS=NONE`; `LOCAL_DB_WRITES=NONE`; `MIGRATIONS=NONE`; `PIX_REAL=OFF`; `PAGAMENTOS_REAIS=OFF`; `ATIVACAO_REAL=OFF`; `PRODUCTION=BLOCKED`.

Se Android ou o serviço impedir a inspeção, manter bloqueio; continuar outras frentes independentes em CI. Nenhuma conclusão sobre banco FR Finance porta 5433 ou FR Caixinha 2.2 é produzida pelo M40120.
