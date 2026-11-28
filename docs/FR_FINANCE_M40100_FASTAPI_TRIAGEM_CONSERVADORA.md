# FR Finance M40100 — triagem conservadora do FastAPI local

Data: 15/11/2026. Aditivo ao M40090. Caderno Mestre e Contrato Técnico preservados.

## Evidência recebida do Termux

- Sincronização M40090 `FAST_FORWARD`, commit `7e06027`, sem migração, escrita ou restart.
- `M40090_API_IDENTITY=FR_FINANCE_ONLINE_DOUBLE_CHECKED`.
- `M40090_M39700_CHECKPOINT=CHECKPOINT_MISSING_OR_UNAVAILABLE`.
- `M40090_M40080_IMPORT_SNAPSHOT=M40080_NOT_LOADED_OR_ROUTE_ABSENT`.
- `M40090_PROCESS_OWNER=NOT_ATTESTED_ANDROID_OR_UNKNOWN`.
- `M40090_PORT_8000_SCOPE=ANDROID_SOCKET_VISIBILITY_PARTIAL_OR_RESTRICTED`.
- `M40090_POSTGRES_STATUS=NOT_CHECKED` e `M40090_RESTART_AUTHORIZED=FALSE`.

Isso sugere código mais antigo que M39700 no processo, mas o M40090 não distinguiu HTTP 404 de 503, timeout ou outra condição para o checkpoint. Não declarar certeza de versão, propriedade do socket ou erro de banco.

## M40100 — avanço funcional

O diagnóstico `backend/scripts/frfinance_m40100_safe_runtime_triage.py`, executado **somente no Termux nativo**, consulta por GET exclusivamente:
`/api/health`, `/api/health/checkpoint`, `/api/health/features/m40080` em `127.0.0.1:8000`, usando o leitor seguro M40090, sem proxy externo e sem seguir redirecionamentos.

Expõe apenas **categorias de códigos HTTP** e de contrato — por exemplo `HTTP_404`, `HTTP_503` e `HTTP_NO_RESPONSE` não são equivalentes. A identidade HTTP FR Finance é conferida antes e depois. O diagnóstico só consulta `ps -u <UID próprio> -o args=` quando a identidade HTTP é confirmada; o conteúdo é processado internamente e nunca exibido. Há limite de saída, timeout e reconhecimento conservador de uma possível linha de comando Uvicorn do próprio usuário. Em Android restrito, informa `PS_SAME_UID_UNAVAILABLE_OR_RESTRICTED`.

**Uma linha compatível com Uvicorn é apenas uma candidata**; `ps` não associa processo ao socket da porta 8000 e não comprova cwd, bytecode carregado ou vínculo ao banco de dados. Um processo ausente na lista também não prova que não exista. `M40100_PORT_OWNER_VERIFIED=FALSE` e `M40100_RESTART_AUTHORIZED=FALSE` são constantes.

O resultado deve voltar ao ChatGPT para uma eventual avaliação específica de manutenção. Este pacote não implementa parada, reinício, troca de serviço, instalação APK, SQL, PG start/stop, conexão com PostgreSQL nem aprovações financeiras.

## Condições antes de qualquer futura reativação

Exigir a identificação **inequívoca** do detentor de `127.0.0.1:8000`, a separação FR Finance e FR Caixinha 2.2, a preservação do banco FR Finance na porta 5433, uma verificação da configuração local sem mostrar segredos e **autorização explícita** do operador. Se o Android não permitir comprovar a propriedade do socket, não sinalizar ou matar processos por nome ou PID presumido. Não tocar nos processos do FR Caixinha 2.2.

Mesmo após uma eventual manutenção supervisionada, futuras checagens de código, autenticação e banco permanecerão independentes; nenhum teste sintético comprova revogação ou consentimento real.

`M40100_DB_CONNECTIONS=NONE`; `M40100_LOCAL_MIGRATIONS=NONE`; `M40100_FASTAPI_RESTART=NONE`; `M40100_REAL_REVIEW_APPROVAL=FALSE`; `PIX_REAL=OFF`; `PAGAMENTOS_REAIS=OFF`; `ATIVACAO_REAL=OFF`; `PRODUCTION=BLOCKED`.
