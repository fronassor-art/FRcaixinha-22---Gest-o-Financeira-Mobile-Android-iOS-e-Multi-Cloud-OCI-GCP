# FR Finance — M39061: identificar o processo FastAPI original antes da correção

## Resultado M39060 (Termux original)
- PostgreSQL FR Finance original PG18.6/5433 e credenciais de frc_ai_app,
  frc_ai_auth e frc_ai_verifier: PASS (M39058).
- Configuração privada api.env: três DSNs válidas, modo homologation,
  FRCAIXINHA_TEST_AUTH=1, chave HMAC presente, Pix/worker não ativados.
- FastAPI em 127.0.0.1:8000: FR Finance ONLINE e CORS Android PASS,
  mas DATABASE_URL ativo vazio, /auth/status=BLOCKED_PENDING_CONFIG
  e /health/ready=HTTP 503 (M39059–M39060).

## Explicação provável, ainda não comprovada
M39051 no modo --serve existe para visualização do APK sem banco,
e limpa deliberadamente DATABASE_URL, AUTH_DATABASE_URL e
AUTH_VERIFIER_DATABASE_URL no próprio processo, não no api.env.
Outros lançamentos sem sourcing do api.env poderiam produzir o
mesmo estado. Por isso a origem do listener deve ser inspecionada
ANTES de qualquer reinício.

## M39061
Script backend/scripts/frfinance_m39061_existing_fastapi_process_origin.py:
- exibe apenas classes controladas, não argumentos completos;
- verifica por GET que /api/health identifica FR Finance na porta 8000;
- consulta apenas /proc/net/tcp e os descritores do UID do Termux
  para vincular o inode de LISTEN 127.0.0.1:8000 ao processo;
- examina somente /proc/PID/cmdline do processo do próprio UID;
- NÃO lê /proc/PID/environ ou tokens, não exibe PID,
  credenciais, cmdline, usuário, host externo ou caminhos privados;
- se Android restringir /proc, responde ANDROID_PROC_TCP_RESTRICTED
  sem inventar identidade;
- nunca executa kill, stop, start, SQL, migração, login, sessão
  ou envio externo.

## Como interpretar
M39061_PROCESS_ORIGIN=M39051_VISUAL_APK
: indica forte prova de que a API existente foi iniciada pelo
  comando de visualização --serve; a troca futura deve ser
  deliberada e supervisionada, sem processo duplicado.

M39061_PROCESS_ORIGIN=UVICORN_DIRECT_OR_LAUNCHER
: listener lançado diretamente por Uvicorn, sem prova do mecanismo
  original que injetou ou omitiu o api.env.

M39061_PROCESS_ORIGIN=NOT_UNIQUELY_IDENTIFIED
: impedir stop/restart automático; confirmar supervisão no Termux.
  Pode ocorrer quando Android restringe inspeção de processos.

## Handoff planejado (NÃO EXECUTADO)
Se for confirmado modo visual, o procedimento de migração para
homologação consiste em parar APENAS aquela instância de API no
seu terminal/supervisor de origem, verificar a liberação de 8000,
e iniciar somente a FastAPI original usando o script
backend/scripts/run_termux_fastapi.sh, que importa api.env
protegido, valida PGDATA, banco, porta e evita processo duplicado.

Toda transição exige autorização expressa após a M39061.
**Não usar** kill -9/pkill genérico, não tocar em PostgreSQL,
não criar/redefinir roles, não fazer UPDATE em api.env, não
habilitar Pix ou usuário real. Após a transição, executar M39059
para confirmar READY_FOR_TEST_AUTH e rotas privadas com 401.

## Termux (somente leitura)
    cd "$HOME/fr-finance"
    test -z "$(git status --porcelain --untracked-files=all)"
    git fetch --no-tags origin atualizacao-ai-studio-9b46a63187
    # verificar SHA aprovado antes do fast-forward:
    git merge --ff-only FETCH_HEAD
    AI_STUDIO_APPROVED_SHA="$(git rev-parse HEAD)" PYTHONDONTWRITEBYTECODE=1 \
        python3 -B -m backend.scripts.frfinance_m39061_existing_fastapi_process_origin
